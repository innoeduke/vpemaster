document.addEventListener("DOMContentLoaded", () => {
  "use strict";

  // --- DOM Elements ---
  const agendaContent = document.getElementById("agenda-content");
  const editBtn = document.getElementById("edit-btn");
  const saveBtn = document.getElementById("edit-logs-btn");
  const cancelButton = document.getElementById("cancel-edit-btn");
  const addRowButton = document.getElementById("add-row-btn");
  const createButton = document.getElementById("create-btn");
  const meetingFilter = document.getElementById("meeting-filter");
  const xlsxButton = document.getElementById("xlsx-btn");
  const jpgButton = document.getElementById("jpg-btn");
  const pptButton = document.getElementById("ppt-btn");
  const actionBtn = document.getElementById("action-btn");
  const actionMenu = document.getElementById("action-menu");
  const tableContainer = document.getElementById("table-container");
  const meetingStatusBtn = document.getElementById("meeting-status-btn");
  const tableBody = document.querySelector("#logs-table tbody");
  const contactForm = document.getElementById("contactForm");
  // const geStyleToggle = document.getElementById("ge-style-toggle"); // Removed as it's always visible in modal
  const geStyleSelect = document.getElementById("ge-style-select");
  const viewModeButtons = document.getElementById("view-mode-buttons");
  const wodDisplay = document.querySelector(".wod-display");
  const editModeButtons = document.getElementById("edit-mode-buttons");
  const statusDisplayElement = document.querySelector(
    ".meeting-status-display"
  );
  const clockEl = document.getElementById("meeting-clock");
  const clockDisplayEl = document.getElementById("meeting-clock-display");

  // -----------------------------------------------------------------------
  // Status group placement
  // -----------------------------------------------------------------------
  // Desktop layout: the .status-group lives inside .action-bar-left, paired
  // visually with the meeting picker (both describe the *selected meeting*).
  // Mobile layout: that placement forces the status cluster onto its own row
  // because .action-bar stacks vertically; users see two empty-ish rows.
  // Solution: move the .status-group node into .action-bar-right > #view-mode-buttons
  // when the viewport is mobile-width, so it sits inline with .action-group.
  // Reverse on widening. Uses matchMedia for cheap reactive updates.
  // Status group stays in its natural DOM position inside .action-bar-left.
  // On mobile the CSS grid (display:contents on wrappers + explicit grid-column/row)
  // handles placement — no DOM relocation needed.
  (function relocateStatusGroup() {
    const statusGroup = document.querySelector(".action-bar-left > .status-group");
    if (!statusGroup) return;
    const desktopHome = document.querySelector(".action-bar-left");
    const mobileHome = document.querySelector(".action-bar-right #view-mode-buttons");
    if (!desktopHome || !mobileHome) return;
    const mobileMQ = window.matchMedia("(max-width: 768px)");
    const apply = (e) => {
      if (e.matches) {
        // Mobile: CSS grid handles layout via display:contents — leave statusGroup in place.
        // Ensure it's back in desktopHome if a legacy move happened.
        if (statusGroup.parentElement !== desktopHome) {
          desktopHome.appendChild(statusGroup);
        }
      } else {
        // Desktop: ensure it's in action-bar-left after the picker wrapper.
        if (statusGroup.parentElement !== desktopHome) {
          desktopHome.appendChild(statusGroup);
        }
      }
    };
    apply(mobileMQ);
    mobileMQ.addEventListener
      ? mobileMQ.addEventListener("change", apply)
      : mobileMQ.addListener(apply); // legacy Safari
  })();

  // Global identifier for classification
  let GLOBAL_CLUB_ID = 1; // Default fallback, will be updated from API

  let projectSpeakers = JSON.parse(tableContainer.dataset.projectSpeakers);

  let allSessionTypes = [];
  let allContacts = [];
  let allProjects = [];
  let allMeetingTypes = {};
  let allMeetingRoles = {};

  // --- State ---
  let isEditing = false;
  let sortable = null;
  let activeOwnerInput = null;
  let pendingEditRequest = false;
  let clockInterval = null;
  let serverSyncInterval = null;
  let meetingStartTime = null;
  let clockOffset = 0;

  // --- Clock & Session Highlighting ---

  function getMeetingStartDateTime() {
    const dateStr = agendaContent.dataset.meetingDate;
    const timeStr = meetingStartTime || agendaContent.dataset.meetingStartTime;
    if (!dateStr || !timeStr) return null;
    return new Date(dateStr + 'T' + timeStr + ':00');
  }

  function startClock() {
    if (!clockEl) return;
    stopClock();
    clockEl.classList.remove('hidden');

    function tick() {
      const now = new Date(Date.now() + clockOffset);
      if (clockDisplayEl) {
        clockDisplayEl.textContent = now.toTimeString().slice(0, 8);
      }
      highlightCurrentSession(now);
    }

    tick();
    clockInterval = setInterval(tick, 1000);
    serverSyncInterval = setInterval(syncServerTime, 60000);
  }

  function stopClock() {
    if (clockInterval) {
      clearInterval(clockInterval);
      clockInterval = null;
    }
    if (serverSyncInterval) {
      clearInterval(serverSyncInterval);
      serverSyncInterval = null;
    }
  }

  function syncServerTime() {
    fetch('/agenda/server-time')
      .then(r => r.json())
      .then(data => {
        const serverTime = new Date(data.iso);
        clockOffset = serverTime - Date.now();
        if (clockDisplayEl) {
          const now = new Date(Date.now() + clockOffset);
          clockDisplayEl.textContent = now.toTimeString().slice(0, 8);
        }
      })
      .catch(() => {}); // Silently ignore sync failures
  }

  function highlightCurrentSession(now) {
    if (!meetingStartTime && !agendaContent.dataset.meetingStartTime) return;
    if (!tableBody) return;

    const startDateTime = getMeetingStartDateTime();
    if (!startDateTime) return;

    const elapsedMinutes = (now - startDateTime) / 60000;
    if (elapsedMinutes < 0) return;

    const timeStr = meetingStartTime || agendaContent.dataset.meetingStartTime;
    const [sh, sm] = timeStr.split(':').map(Number);
    const meetingStartMinutes = sh * 60 + sm;
    const virtualClock = (meetingStartMinutes + elapsedMinutes) % 1440;

    let matchingRow = null;
    const rows = tableBody.querySelectorAll('tr');

    rows.forEach(row => {
      if (row.dataset.isSection === 'true') return;
      if (row.dataset.isHidden === 'true') return;
      const rowStart = row.dataset.startTime;
      if (!rowStart) return;
      const durationMax = parseInt(row.dataset.durationMax, 10) || 0;
      if (durationMax === 0) return;

      const [rh, rm] = rowStart.split(':').map(Number);
      const rowStartMinutes = rh * 60 + rm;
      const rowEndMinutes = rowStartMinutes + durationMax;

      if (virtualClock >= rowStartMinutes && virtualClock < rowEndMinutes) {
        matchingRow = row;
      }
    });

    rows.forEach(r => r.classList.remove('current-session'));
    if (matchingRow) {
      matchingRow.classList.add('current-session');
    }
  }

  function clearHighlights() {
    if (!tableBody) return;
    tableBody.querySelectorAll('tr.current-session').forEach(r => {
      r.classList.remove('current-session');
    });
  }

  async function initMeetingClock() {
    if (!clockEl) return;

    // Sync server time first
    try {
      const resp = await fetch('/agenda/server-time');
      const data = await resp.json();
      const serverTime = new Date(data.iso);
      clockOffset = serverTime - Date.now();
      if (clockDisplayEl) {
        clockDisplayEl.textContent = serverTime.toTimeString().slice(0, 8);
      }
    } catch (e) {
      // Fall back to client time
      if (clockDisplayEl) {
        clockDisplayEl.textContent = new Date().toTimeString().slice(0, 8);
      }
    }

    meetingStartTime = agendaContent.dataset.meetingStartTime || null;

    const status = meetingStatusBtn
      ? meetingStatusBtn.dataset.currentStatus
      : '';

    if (status === 'running') {
      startClock();
    } else if (status === 'finished') {
      // Don't show the clock for finished meetings.
      stopClock();
    }
  }

  const sessionPairs = {
    "Ah-Counter Introduction": "Ah-Counter Report",
    "Grammarian Introduction": "Grammarian Report",
    "Timer Introduction": "Timer Report",
    "General Evaluator's Address": "General Evaluation Report",
    "Toastmaster of the Evening's Address": "Voting and Announcements",
    "President's Address": "Awards / Meeting Closing",
  };

  const reverseSessionPairs = {};
  for (const key in sessionPairs) {
    reverseSessionPairs[sessionPairs[key]] = key;
  }

  // --- Constants ---
  const fieldsOrder = [
    "Meeting_Seq",
    "Start_Time",
    "Type_ID",
    "Session_Title",
    "Owner_ID",
    "Duration_Min",
    "Duration_Max",
  ];

  // --- Main Initialization Function (called after data is fetched) ---
  let originalTableHTML = "";
  function initializeAgendaPage() {
    originalTableHTML = tableBody.innerHTML;
    toggleEditMode(false); // Set initial UI state
  }

  // Attach event listeners immediately so the Edit button works even if the
  // user clicks before the /api/data/all fetch resolves.
  initializeEventListeners();

  // --- Fetch all necessary data asynchronously and then initialize the page ---
  // Only fetch edit-related data if the edit button is present (i.e., user is authorized)
  if (editBtn) {
    fetch("/api/data/all")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        allSessionTypes = data.session_types;
        allContacts = data.contacts;
        allProjects = data.projects;
        allMeetingTypes = data.meeting_types;
        allMeetingTypes = data.meeting_types;
        allMeetingRoles = data.meeting_roles;
        GLOBAL_CLUB_ID = data.global_club_id || 1; // Update from server response

        // Make data available globally for speech_modal.js, which expects them as globals
        window.allContacts = allContacts;
        window.allProjects = allProjects;
        window.pathways = data.pathways;
        window.pathwayMap = data.pathway_mapping;
        window.groupedPathways = data.pathways;
        window.ProjectID = data.project_id_constants;

        initializeAgendaPage(); // Now that data is loaded, initialize the page
        if (pendingEditRequest) {
          pendingEditRequest = false;
          toggleEditMode(true);
        }
      })
      .catch((error) => {
        console.error("Error fetching initial data:", error);
        showCustomAlert("Warning", "Could not load some editing data. You may need to reload the page to edit fully.\n\nError: " + error.message);
        initializeAgendaPage();
      });
  } else {
    initializeAgendaPage(); // Initialize for guest view without fetching edit data
  }

  // --- Event Listeners ---
  function initializeEventListeners() {
    if (contactForm) {
      contactForm.addEventListener("submit", handleContactFormSubmit);
    }
    if (meetingFilter) {
      meetingFilter.addEventListener("change", () => {
        window.location.href = `/agenda?meeting_id=${meetingFilter.value}`;
      });
    }
    if (editBtn) {
      editBtn.addEventListener("click", () => {
        if (allSessionTypes.length === 0) {
          pendingEditRequest = true;
        } else {
          toggleEditMode(true);
        }
      });
    }
    const noHeaderInfo = document.getElementById("no-header-info");
    const noHeaderTooltip = document.getElementById("no-header-tooltip");
    if (noHeaderInfo && noHeaderTooltip) {
      noHeaderInfo.addEventListener("click", (e) => {
        e.stopPropagation();
        noHeaderTooltip.classList.toggle("show");
      });
      document.addEventListener("click", (e) => {
        if (!noHeaderTooltip.contains(e.target) && e.target !== noHeaderInfo) {
          noHeaderTooltip.classList.remove("show");
        }
      });
    }
    if (saveBtn) {
      saveBtn.addEventListener("click", () => saveChanges(false));
    }
    if (cancelButton) {
      cancelButton.addEventListener("click", () => {
        if (isEditing) {
          if (originalTableHTML) {
            tableBody.innerHTML = originalTableHTML;
            toggleEditMode(false);
          } else {
            window.location.reload();
          }
        }
      });
    }
    if (addRowButton) {
      addRowButton.addEventListener("click", addNewRow);
    }

    if (xlsxButton) {
      xlsxButton.addEventListener("click", exportAgenda);
    }
    if (createButton) {
      createButton.addEventListener("click", () => {
        const createAgendaModal = document.getElementById("createAgendaModal");
        if (createAgendaModal) {
          createAgendaModal.style.display = "flex";
        }
      });
    }
    if (pptButton) {
      pptButton.addEventListener("click", downloadPPT);
    }
    if (jpgButton) {
      jpgButton.addEventListener("click", exportAgendaJPG);
    }

    const exportTemplateBtn = document.getElementById("export-template-btn");
    if (exportTemplateBtn) {
      exportTemplateBtn.addEventListener("click", () => {
        const meetingId = meetingFilter.value;
        if (!meetingId) {
          showCustomAlert("Select Meeting", "Please select a meeting to export.");
          return;
        }

        const templateName = prompt("Enter a name for the new meeting template:");
        if (templateName && templateName.trim()) {
          fetch("/agenda/export_template", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              meeting_id: meetingId,
              template_name: templateName
            }),
          })
            .then((response) => response.json())
            .then((data) => {
              if (data.success) {
                window.location.reload();
              } else {
                showCustomAlert("Error", "Error exporting template: " + data.message);
              }
            })
            .catch((error) => {
              console.error("Error:", error);
              showCustomAlert("Error", "An error occurred while exporting.");
            });
        }
      });
    }

    // --- Action Button Logic ---
    if (actionBtn && actionMenu) {
      actionBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        actionMenu.classList.toggle("show");
      });

      document.addEventListener("click", (e) => {
        if (!actionBtn.contains(e.target) && !actionMenu.contains(e.target)) {
          actionMenu.classList.remove("show");
        }
      });

      const actionNew = document.getElementById("action-new-opt");
      const actionEdit = document.getElementById("action-edit-opt");
      const actionXlsx = document.getElementById("action-xlsx-opt");
      const actionPpt = document.getElementById("action-ppt-opt");
      const actionJpg = document.getElementById("action-jpg-opt");

      if (actionNew)
        actionNew.addEventListener("click", () => {
          const createAgendaModal = document.getElementById("createAgendaModal");
          if (createAgendaModal) {
            createAgendaModal.style.display = "flex";
          }
          actionMenu.classList.remove("show");
        });
      if (actionEdit)
        actionEdit.addEventListener("click", () => {
          toggleEditMode(true);
          actionMenu.classList.remove("show");
        });
      if (actionXlsx)
        actionXlsx.addEventListener("click", () => {
          exportAgenda();
          actionMenu.classList.remove("show");
        });
      if (actionPpt)
        actionPpt.addEventListener("click", () => {
          downloadPPT();
          actionMenu.classList.remove("show");
        });
      if (actionJpg)
        actionJpg.addEventListener("click", () => {
          exportAgendaJPG();
          actionMenu.classList.remove("show");
        });
    }
    if (tableBody) {
      tableBody.addEventListener("click", (event) => {
        if (event.target.closest(".delete-btn")) {
          deleteLogRow(event.target.closest("tr"));
          return;
        }

        const colSession = event.target.closest(".col-session");
        if (colSession && !isEditing && editBtn) {
          // If the user clicked a link (a element) inside the session column, don't trigger the modal
          if (event.target.closest("a")) {
            return;
          }
          const row = colSession.closest("tr");
          if (row) {
            handleSessionTitleClick(row);
          }
        }
      });
    }
    if (wodDisplay) {
      wodDisplay.addEventListener("click", () => {
        wodDisplay.classList.toggle("open");
      });
    }
    if (meetingStatusBtn) {
      meetingStatusBtn.addEventListener("click", () => {
        handleMeetingStatusChange(meetingStatusBtn);
      });
    }

    const viewDetailsBtn = document.getElementById("view-details-btn");
    if (viewDetailsBtn) {
      viewDetailsBtn.addEventListener("click", () => {
        const currentStatus = meetingStatusBtn ? meetingStatusBtn.dataset.currentStatus : '';
        const isFinished = (currentStatus === 'finished');
        const currentType = viewDetailsBtn.dataset.meetingType || '';
        // The four classic best_* awards and Lucky Draw Winner only need
        // the meeting to be finished. Best Debater is meaningful only on
        // Debate-type meetings, so it needs both gates.
        const finishedOnlySelects = [
          "edit-best-speaker",
          "edit-best-evaluator",
          "edit-best-table-topic",
          "edit-best-role-taker",
          "edit-lucky-draw-winner"
        ];
        finishedOnlySelects.forEach(id => {
          const select = document.getElementById(id);
          if (select) {
            select.disabled = !isFinished;
          }
        });
        const debaterSelect = document.getElementById("edit-best-debater");
        if (debaterSelect) {
          debaterSelect.disabled = !(isFinished && currentType === 'Debate');
        }
        document.getElementById("meetingDetailsModal").style.display = "flex";
      });
    }

    const saveDetailsBtn = document.getElementById("save-meeting-details-btn");
    if (saveDetailsBtn) {
      saveDetailsBtn.addEventListener("click", () => saveChanges(true));
    }

    const createMeetingForm = document.getElementById("create-meeting-form");
    if (createMeetingForm) {
      createMeetingForm.addEventListener("submit", function (e) {
        e.preventDefault();

        const submitForm = (ignoreSuspicious) => {
          const formData = new FormData(createMeetingForm);
          if (ignoreSuspicious) {
            formData.append("ignore_suspicious_date", "true");
          }

          fetch("/agenda/create", {
            method: "POST",
            body: formData,
            headers: {
              "X-Requested-With": "XMLHttpRequest",
            },
          })
            .then((response) => response.json())
            .then(async (data) => {
              if (data.success) {
                window.location.href = data.redirect_url;
              } else if (data.suspicious_date) {
                const confirmed = await showCustomConfirm("Confirm Date", data.message + "\n\nDo you want to create the meeting anyway?");
                if (confirmed) {
                  submitForm(true);
                }
              } else {
                showCustomAlert("Error", "Error creating meeting: " + data.message);
              }
            })
            .catch((error) => {
              console.error("Error:", error);
              showCustomAlert("Error", "An error occurred while creating the meeting.");
            });
        };

        submitForm(false);
      });
    }
  }

  function handleSessionTitleClick(row) {
    if (isEditing) return;
    if (!editBtn) return;
    if (allSessionTypes.length === 0) return;

    const logId = row.dataset.id;
    if (!logId || logId === "new") return;

    const typeId = row.dataset.typeId;
    const sessionType = allSessionTypes.find((st) => st.id == typeId);
    if (!sessionType) return;

    // Project-button branch: pre-populate the pathway/project for prepared
    // speeches and other project-valid types so the modal opens with the
    // right defaults.
    if (sessionType.Valid_for_Project) {
      const ownerId = row.dataset.ownerId;
      const contact = allContacts.find((c) => c.id == ownerId);
      let currentPath = null;
      if (contact) {
        const isGuestWithoutUser = (contact.Type === "Guest");
        if (!isGuestWithoutUser && contact.Current_Path) {
          currentPath = contact.Current_Path;
        } else {
          currentPath = "Non Pathway";
        }
      } else {
        currentPath = "Non Pathway";
      }
      const nextProject = contact ? contact.Next_Project : null;
      const sessionTypeTitle = sessionType.Title || null;
      openEditDetailsModal(logId, currentPath, sessionTypeTitle, nextProject);
    } else {
      // Every other editable session type — functional roles (Timer,
      // Grammarian, Welcome Officer, …), club-specific types, and types
      // with no role FK (Networking). The modal's role-mode fallback
      // handles them all.
      openEditDetailsModal(logId);
    }
  }

  // --- Core Functions ---

  function closeMeetingDetailsModal() {
    document.getElementById("meetingDetailsModal").style.display = "none";
  }
  // Ensure the function is global so the close button onclick works
  window.closeMeetingDetailsModal = closeMeetingDetailsModal;

  window.refreshAgendaTable = function() {
    const meetingId = meetingFilter ? meetingFilter.value : null;
    if (!meetingId) return;

    fetch(`/api/agenda/get_logs/${meetingId}`)
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          // 1. Update project speakers dataset
          if (data.project_speakers) {
            projectSpeakers = data.project_speakers;
            if (tableContainer) {
              tableContainer.dataset.projectSpeakers = JSON.stringify(projectSpeakers);
            }
          }

          // 2. Re-render table rows
          if (data.logs_data) {
            renderTableRows(data.logs_data);
          }

          // 3. Update meeting metadata dynamically
          if (data.meeting_info) {
            // Update Title
            const titleEl = document.querySelector(".meeting-title.view-mode");
            if (titleEl) {
              const linkEl = titleEl.querySelector("a");
              if (linkEl) {
                linkEl.textContent = data.meeting_info.title;
              } else {
                titleEl.textContent = data.meeting_info.title;
              }
            }

            // Update Subtitle
            const subtitleEl = document.querySelector(".subtitle.view-mode");
            if (subtitleEl) {
              if (data.meeting_info.subtitle) {
                subtitleEl.textContent = data.meeting_info.subtitle;
                subtitleEl.style.display = "";
              } else {
                subtitleEl.style.display = "none";
              }
            }

            // Update WOD (Word of the Day)
            const wodDisplay = document.querySelector(".wod-display");
            if (data.meeting_info.wod) {
              if (wodDisplay) {
                const letterSpan = wodDisplay.querySelector(".letter span:last-child");
                if (letterSpan) {
                  letterSpan.textContent = `"${data.meeting_info.wod}"`;
                }
                wodDisplay.style.display = "";
              }
            } else if (wodDisplay) {
              wodDisplay.style.display = "none";
            }

            // Update Meeting Status Display & Button
            const newStatus = data.meeting_info.status;
            const statusDisplayElement = document.querySelector(".meeting-status-display");
            const button = document.getElementById("meeting-status-btn");
            if (statusDisplayElement && newStatus) {
              statusDisplayElement.className = `meeting-status-display status-${newStatus.replace(/ /g, "-")}`;
              let iconClass = "";
              if (newStatus === "unpublished") iconClass = "fa-eye-slash";
              else if (newStatus === "not started") iconClass = "fa-play-circle";
              else if (newStatus === "running") iconClass = "fa-broadcast-tower";
              else if (newStatus === "finished") iconClass = "fa-check-circle";
              else if (newStatus === "cancelled") iconClass = "fa-ban";

              const statusText = newStatus.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
              statusDisplayElement.innerHTML = `<i class="fas fa-fw ${iconClass}"></i>${statusText}`;

              if (button) {
                button.dataset.currentStatus = newStatus;
                button.className = "btn"; // Reset class list base
                button.disabled = false;
                button.style.display = "";

                if (newStatus === "not started") {
                  button.innerHTML = '<i class="fas fa-fw fa-play"></i> Start';
                  button.classList.remove("btn-danger", "btn-secondary", "btn-light");
                  button.classList.add("btn-success");
                  button.title = "Start to let audience vote.";
                } else if (newStatus === "running") {
                  button.innerHTML = '<i class="fas fa-fw fa-stop"></i> Stop';
                  button.classList.remove("btn-primary", "btn-success", "btn-secondary", "btn-light");
                  button.classList.add("btn-danger");
                  button.title = "Stop to end voting and show results.";
                } else if (newStatus === "finished") {
                  const canDelete = agendaContent && agendaContent.dataset.canDelete === "true";
                  if (canDelete) {
                    button.innerHTML = '<i class="fas fa-fw fa-check-circle"></i> Delete';
                    button.classList.remove("btn-success", "btn-danger", "btn-light");
                    button.classList.add("btn-secondary");
                    button.title = "";
                  } else {
                    button.style.display = "none";
                  }
                } else if (newStatus === "cancelled") {
                  button.innerHTML = '<i class="fas fa-fw fa-ban"></i> Cancelled';
                  button.disabled = true;
                  button.classList.remove("btn-success", "btn-danger", "btn-light");
                  button.classList.add("btn-secondary");
                  button.title = "";
                } else if (newStatus === "unpublished") {
                  button.innerHTML = 'Publish';
                  button.classList.remove("btn-danger", "btn-secondary", "btn-success");
                  button.classList.add("btn-light");
                  button.title = "Publish to allow members to book roles.";
                }
              }
            }

            // --- Clock State Sync ---
            if (clockEl && data.meeting_info) {
              if (data.meeting_info.start_time) {
                meetingStartTime = data.meeting_info.start_time;
                agendaContent.dataset.meetingStartTime = data.meeting_info.start_time;
              }
              if (data.meeting_info.status === 'running') {
                if (clockInterval === null) startClock();
              } else if (data.meeting_info.status === 'finished') {
                stopClock();
                clearHighlights();
              } else {
                stopClock();
                clockEl.classList.add('hidden');
                clearHighlights();
              }
            }
          }
        }
      })
      .catch(err => console.error("Error refreshing agenda table:", err));
  };

  function toggleEditMode(enable) {
    isEditing = enable;
    agendaContent.classList.toggle("edit-mode-active", enable);
    updateHeaderVisibility(enable);
    updateRowsForEditMode(enable);
    updateActionButtonsVisibility(enable);
    if (meetingFilter) {
      meetingFilter.disabled = enable;
    }
    initializeSortable(enable);
    if (enable && geStyleSelect) {
      geStyleSelect.value = geStyleSelect.dataset.currentStyle;
    }
    const editMeetingDate = document.getElementById("edit-meeting-date");
    if (enable && editMeetingDate) {
      // Date value is already set by Jinja in the template attribute value
    }
  }

  function saveChanges(shouldReload = false) {
    let invalidRowFound = false;
    const allRows = tableBody.querySelectorAll("tr");

    allRows.forEach((row, index) => {
      // Find the select element for this row
      const selectEl = row.querySelector('[data-field="Type_ID"] select');
      if (!selectEl) return; // Not an editable row, skip

      // Check for empty value (our default option)
      if (!selectEl.value || selectEl.value === "") {
        invalidRowFound = true;
        // Highlight the invalid dropdown
        selectEl.style.border = "2px solid red";
        selectEl.style.backgroundColor = "#fff0f0";
      } else {
        // Reset style if it was previously invalid
        selectEl.style.border = "";
        selectEl.style.backgroundColor = "";
      }
    });

    if (invalidRowFound) {
      showCustomAlert(
        "Save Failed",
        "One or more sessions has a missing 'Session Type'.\n\nPlease select a valid type for the highlighted row(s) before saving."
      );
      return; // Stop the save operation
    }
    const dataToSave = Array.from(tableBody.querySelectorAll("tr")).map(
      getRowData
    );
    const meetingId = meetingFilter.value;

    if (!meetingId) {
      showCustomAlert("Error", "No meeting is selected. Cannot save.");
      return;
    }

    if (dataToSave.length === 0) {
      toggleEditMode(false);
      window.location.reload();
      return;
    }

    const awardConfigs = {};
    const categories = ['speaker', 'evaluator', 'table-topic', 'role-taker', 'debater', 'lucky_draw'];
    categories.forEach(cat => {
      const votesEl = document.getElementById(`edit-votes-${cat}`);
      const winnersEl = document.getElementById(`edit-winners-${cat}`);
      if (votesEl && winnersEl) {
        awardConfigs[cat] = {
          max_votes_per_user: parseInt(votesEl.value) || 1,
          max_winners: parseInt(winnersEl.value) || 1
        };
      }
    });

    fetch("/agenda/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        meeting_id: meetingId,
        agenda_data: dataToSave,
        ge_mode: geStyleSelect ? parseInt(geStyleSelect.value) : null,
        meeting_date: document.getElementById("edit-meeting-date").value,
        meeting_title: document.getElementById("edit-meeting-title").value,
        subtitle: document.getElementById("edit-subtitle").value,
        meeting_type: document.getElementById("edit-meeting-type").value,
        wod: document.getElementById("edit-wod").value,
        media_url: document.getElementById("edit-media-url").value,
        meeting_number: (() => {
          const el = document.getElementById("edit-meeting-number");
          if (!el || el.value === "") return null;
          const n = parseInt(el.value, 10);
          return Number.isFinite(n) ? n : null;
        })(),
        best_speaker_id: document.getElementById("edit-best-speaker") ? Array.from(document.getElementById("edit-best-speaker").selectedOptions).map(opt => opt.value) : [],
        best_evaluator_id: document.getElementById("edit-best-evaluator") ? Array.from(document.getElementById("edit-best-evaluator").selectedOptions).map(opt => opt.value) : [],
        best_table_topic_id: document.getElementById("edit-best-table-topic") ? Array.from(document.getElementById("edit-best-table-topic").selectedOptions).map(opt => opt.value) : [],
        best_role_taker_id: document.getElementById("edit-best-role-taker") ? Array.from(document.getElementById("edit-best-role-taker").selectedOptions).map(opt => opt.value) : [],
        best_debater_id: document.getElementById("edit-best-debater") ? Array.from(document.getElementById("edit-best-debater").selectedOptions).map(opt => opt.value) : [],
        lucky_draw_winner_id: document.getElementById("edit-lucky-draw-winner") ? Array.from(document.getElementById("edit-lucky-draw-winner").selectedOptions).map(opt => opt.value) : [],
        award_configs: awardConfigs,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          // If forced reload is requested (e.g., from Meeting Details modal), do it now
          if (shouldReload) {
            window.location.reload();
            return;
          }

          // Update global data
          if (data.project_speakers) {
            projectSpeakers = data.project_speakers;
            // Update the dataset as well for consistency
            tableContainer.dataset.projectSpeakers = JSON.stringify(projectSpeakers);
          }

          if (geStyleSelect) {
            geStyleSelect.dataset.currentStyle = geStyleSelect.value;
          }

          // Re-render the table with the new data
          if (data.logs_data) {
            renderTableRows(data.logs_data);
            // Refresh the cancel cache so a future cancel restores the saved state
            originalTableHTML = tableBody.innerHTML;
            // Exit edit mode and update UI only after successful render
            toggleEditMode(false);
            closeMeetingDetailsModal(); // Close the modal if open
          } else {
            // Fallback: If no data returned, force reload to ensure clean state
            window.location.reload();
          }
        } else {
          showCustomAlert("Error", "Error saving changes: " + data.message);
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        showCustomAlert("Error", "An error occurred while saving.");
      });
  }

  function renderTableRows(logsData) {
    tableBody.innerHTML = '';
    const displayedAwards = new Set();

    logsData.forEach(log => {
      const row = document.createElement('tr');

      // --- Set Data Attributes ---
      row.dataset.id = log.id;
      row.dataset.sectionId = log.section_id != null ? log.section_id : '';
      row.dataset.projectId = log.Project_ID !== null ? log.Project_ID : '';
      row.dataset.meetingId = log.meeting_id;
      row.dataset.meetingNumber = log.Meeting_Number;
      row.dataset.meetingDate = log.meeting_date_str;
      row.dataset.isSection = String(log.is_section).toLowerCase();
      row.dataset.isHidden = String(log.is_hidden).toLowerCase();
      row.dataset.isReadonly = String(log.is_readonly || false).toLowerCase();
      row.dataset.meetingSeq = log.Meeting_Seq;
      row.dataset.startTime = log.Start_Time_str;
      row.dataset.sessionTitle = log.Session_Title !== null ? log.Session_Title : '';
      row.dataset.typeId = log.Type_ID;
      row.dataset.ownerId = log.Owner_ID;
      row.dataset.ownerIds = JSON.stringify(log.owner_ids || []);
      row.dataset.credentials = log.Credentials !== null ? log.Credentials : '';
      row.dataset.durationMin = log.Duration_Min !== null ? log.Duration_Min : '';
      row.dataset.durationMax = log.Duration_Max !== null ? log.Duration_Max : '';
      row.dataset.status = log.status || '';
      row.dataset.role = log.role || '';
      row.dataset.currentPathLevel = log.project_code || log.Credentials || '';
      row.dataset.projectCode = log.project_code || log.Credentials || '';
      row.dataset.pathway = log.pathway || '';
      row.dataset.ownerTargets = JSON.stringify(log.owner_targets || {});

      // --- Set Classes ---
      if (log.is_section) row.classList.add('section-row');
      if (log.is_hidden) row.classList.add('hidden-row');
      if (log.is_readonly) row.classList.add('readonly-row');

      // --- Create Cells ---
      if (log.is_section) {
        const td = document.createElement('td');
        td.colSpan = 4;
        td.className = 'non-edit-mode-cell section-header-cell';

        const wrapper = document.createElement('div');
        wrapper.className = 'section-header-content';

        const micIcon = document.createElement('i');
        micIcon.className = 'fas fa-microphone section-icon';
        wrapper.appendChild(micIcon);

        const titleSpan = document.createElement('span');
        titleSpan.className = 'section-title';
        titleSpan.textContent = log.Session_Title || log.session_type_title;
        wrapper.appendChild(titleSpan);

        const toggle = document.createElement('i');
        toggle.className = 'fas fa-caret-down section-toggle';
        toggle.dataset.toggleSection = log.id;
        toggle.setAttribute('role', 'button');
        toggle.setAttribute('aria-label', 'Toggle section');
        wrapper.appendChild(toggle);

        td.appendChild(wrapper);
        row.appendChild(td);
      } else {
        // 1. Start Time
        const tdTime = document.createElement('td');
        tdTime.className = 'non-edit-mode-cell';
        tdTime.textContent = log.Start_Time_str;
        row.appendChild(tdTime);

        // 2. Session Title (Complex Logic)
        const tdSession = document.createElement('td');
        tdSession.className = 'non-edit-mode-cell col-session';
        const tooltipWrapper = document.createElement('div');
        tooltipWrapper.className = 'speech-tooltip-wrapper';

        let cleanedTitle = log.Session_Title ? log.Session_Title.replace(/"/g, '') : '';
        let displayTitle = '';

        if (log.session_type_title === 'Evaluation') {
          displayTitle = 'Evaluator for ' + cleanedTitle;
        } else if (['Pathway Speech', 'Prepared Speech', 'Presentation'].includes(log.session_type_title) || log.Project_ID) {
          displayTitle = '"' + cleanedTitle + '"';
        } else {
          displayTitle = cleanedTitle;
        }

        // Media URL Link
        let titleContent;
        if (log.media_url) {
          const a = document.createElement('a');
          a.href = log.media_url;
          a.target = '_blank';
          a.title = 'Watch Media';
          a.textContent = displayTitle;
          titleContent = a;
        } else {
          titleContent = document.createTextNode(displayTitle);
        }
        tooltipWrapper.appendChild(titleContent);

        // DTM Superscript (for Evaluators)
        if (log.session_type_title === 'Evaluation' && log.speaker_is_dtm) {
          const sup = document.createElement('sup');
          sup.className = 'dtm-superscript';
          sup.textContent = 'DTM';
          tooltipWrapper.appendChild(sup);
        }

        // Project Code
        // Always render a clickable <a> when the code is available, even if
        // Project_ID / pathway_code are missing on this row. The server
        // template also links whenever a code exists; falling back to a
        // <span> here would produce a non-clickable badge that looks
        // identical to a clickable one — a silent regression after a
        // post-update re-render.
        if (log.project_code_display) {
          tooltipWrapper.appendChild(document.createTextNode(' ')); // Space
          const aCode = document.createElement('a');
          if (log.Project_ID && log.pathway_code) {
            aCode.href = `/pathway_library?path=${log.pathway_code}&level=${log.level}&project_id=${log.Project_ID}`;
            aCode.title = 'View in Pathways Library';
          } else {
            // Fallback: link to the library index. Better a generic landing
            // page than a dead element.
            aCode.href = '/pathway_library';
            aCode.title = 'Open Pathways Library';
          }
          aCode.className = 'project-code-link';
          aCode.textContent = `(${log.project_code_display})`;
          tooltipWrapper.appendChild(aCode);
        }

        // Tooltip
        if (log.Project_ID) {
          const tooltip = document.createElement('div');
          tooltip.className = 'speech-tooltip';

          const tTitle = document.createElement('span');
          tTitle.className = 'tooltip-title';
          tTitle.textContent = log.project_name;

          const tPurpose = document.createElement('span');
          tPurpose.className = 'tooltip-purpose';
          tPurpose.textContent = log.project_purpose;

          tooltip.appendChild(tTitle);
          tooltip.appendChild(tPurpose);
          tooltipWrapper.appendChild(tooltip);
        }

        tdSession.appendChild(tooltipWrapper);
        row.appendChild(tdSession);

        // 3. Owner
        const tdOwner = document.createElement('td');
        tdOwner.className = 'non-edit-mode-cell col-owner';

        const ownersData = log.owners_data || [];
        ownersData.forEach((ownerInfo, index) => {
          const ownerRow = document.createElement('div');
          ownerRow.className = 'owner-row';

          const canViewContacts = document.getElementById('agenda-content')?.dataset.canViewContacts === 'true';
          if (canViewContacts && ownerInfo.id) {
            const nameLink = document.createElement('a');
            nameLink.className = 'owner-name owner-link';
            nameLink.href = `/profile/${ownerInfo.id}`;
            nameLink.textContent = ownerInfo.name;
            ownerRow.appendChild(nameLink);
          } else {
            const nameSpan = document.createElement('span');
            nameSpan.className = 'owner-name';
            nameSpan.textContent = ownerInfo.name;
            ownerRow.appendChild(nameSpan);
          }

          if (ownerInfo.credentials && ownerInfo.credentials !== "DTM") {
            const credSpan = document.createElement('span');
            credSpan.className = 'owner-meta';
            credSpan.textContent = ` - ${ownerInfo.credentials}`;
            ownerRow.appendChild(credSpan);
          }

          // Award Trophy (usually for the first owner in a shared role)
          if (index === 0 && log.award_type && !displayedAwards.has(log.role)) {
            const spanAward = document.createElement('span');
            spanAward.className = 'icon-btn icon-btn-voted';
            spanAward.title = log.award_type + ' Winner';
            spanAward.style.marginLeft = '4px';
            spanAward.innerHTML = '<i class="fas fa-award"></i>';
            ownerRow.appendChild(spanAward);
            displayedAwards.add(log.role);
          }

          tdOwner.appendChild(ownerRow);
        });
        if (ownersData.length === 0) {
          tdOwner.textContent = '-';
        }
        row.appendChild(tdOwner);

        // 4. Duration
        const tdDur = document.createElement('td');
        tdDur.className = 'non-edit-mode-cell col-view-duration';
        if (log.Duration_Min && log.Duration_Max) {
          tdDur.textContent = `${log.Duration_Min}'-${log.Duration_Max}'`;
        } else if (log.Duration_Max) {
          tdDur.textContent = `${log.Duration_Max}'`;
        }
        row.appendChild(tdDur);
      }

      tableBody.appendChild(row);
    });
  }

  function addNewRow() {
    if (!meetingFilter.value) {
      showCustomAlert("Select Meeting", "Please select a meeting to add a section to.");
      return;
    }

    const newRow = tableBody.insertRow();
    Object.assign(newRow.dataset, {
      id: "new",
      isSection: "true",
      meetingNumber: meetingFilter.value,
      projectId: "",
      status: "Booked",
      typeId: allSessionTypes.find(st => st.Is_Section)?.id || "",
      sessionTitle: "",
      ownerId: "",
      durationMin: "",
      durationMax: "",
    });

    buildEditableRow(newRow, tableBody.children.length);
    renumberRows();
  }

  function addSessionToSection(sectionRow) {
    if (!meetingFilter.value) {
      showCustomAlert("Select Meeting", "Please select a meeting.");
      return;
    }

    // Find the insertion point: the end of the current section
    let nextRow = sectionRow.nextElementSibling;
    while (nextRow && nextRow.dataset.isSection !== "true") {
      nextRow = nextRow.nextElementSibling;
    }

    const newRow = document.createElement("tr");
    Object.assign(newRow.dataset, {
      id: "new",
      isSection: "false",
      meetingNumber: meetingFilter.value,
      projectId: "",
      status: "Booked",
      typeId: "",
      sessionTitle: "",
      ownerId: "",
      durationMin: "",
      durationMax: "",
      isNewManually: "true", // Flag for auto-title logic
    });

    if (nextRow) {
      tableBody.insertBefore(newRow, nextRow);
    } else {
      tableBody.appendChild(newRow);
    }

    buildEditableRow(newRow, Array.from(tableBody.children).indexOf(newRow) + 1);
    renumberRows();
  }

  function deleteLogRow(row) {
    if (row.dataset.id === "new") {
      row.remove();
      renumberRows();
      return;
    }

    showCustomConfirm("Delete Log", "Are you sure you want to delete this log?")
      .then((confirmed) => {
        if (!confirmed) return;
        fetch(`/agenda/delete/${row.dataset.id}`, { method: "POST" })
          .then((response) => response.json())
          .then((data) => {
            if (data.success) {
              row.remove();
              renumberRows();
            } else {
              showCustomAlert("Error", "Error deleting log: " + data.message);
            }
          })
          .catch((error) => console.error("Error:", error));
      });
  }

  // --- Helper Functions ---

  function syncMeetingFilterStatus(meetingId, newStatus) {
    const STATUS_MAP = {
      'unpublished':  { icon: '🔒',  label: 'Unpublished',  cls: 'status-unpublished' },
      'not started':  { icon: '▶️',  label: 'Not Started',  cls: 'status-not-started' },
      'running':      { icon: '🔴',  label: 'Running',      cls: 'status-running' },
      'finished':     { icon: '✅',  label: 'Finished',     cls: 'status-finished' },
      'cancelled':    { icon: '🚫',  label: 'Cancelled',    cls: 'status-cancelled' },
    };
    const info = STATUS_MAP[newStatus];
    if (!info) return;

    // Update all autocomplete result items that reference this meeting
    document.querySelectorAll(`.autocomplete-result-item[data-value="${meetingId}"]`).forEach(item => {
      const iconEl = item.querySelector('.status-icon');
      if (iconEl) { iconEl.textContent = info.icon; iconEl.title = info.label; }

      const tagEl = item.querySelector('.status-tag');
      if (tagEl) {
        tagEl.textContent = info.label;
        tagEl.className = 'status-tag ' + info.cls;
      }
    });
  }

  function handleMeetingStatusChange(button) {
    const meetingId = button.dataset.meetingId;
    let currentStatus = button.dataset.currentStatus;

    if (!meetingId) {
      showCustomAlert("No Selection", "No meeting selected.");
      return;
    }

    let confirmTitle = "";
    let confirmMessage = "";

    if (currentStatus === "unpublished") {
      confirmTitle = "Publish Meeting";
      confirmMessage = "<strong>Publishing opens booking roles and speeches to all members.</strong> Please make sure the meeting theme and structure are finalized before publishing. Do you want to proceed?";
    } else if (currentStatus === "not started") {
      confirmTitle = "Start Meeting";
      confirmMessage = "<strong>Starting will open voting to the audience.</strong> Please only click this when the meeting has already started. Do you want to proceed?";
    } else if (currentStatus === "running") {
      confirmTitle = "Stop Meeting";
      confirmMessage = "<strong>Stopping the meeting ends voting and shows the final vote results.</strong> Do you want to proceed?";
    } else if (currentStatus === "finished") {
      confirmTitle = "Delete Meeting";
      confirmMessage = "Are you sure you want to <strong>PERMANENTLY DELETE</strong> this meeting and all its records (logs, votes, media)? This action <strong>cannot be undone</strong>.";
    } else {
      performStatusUpdate(meetingId);
      return;
    }

    showCustomConfirm(confirmTitle, confirmMessage)
      .then((confirmed) => {
        if (!confirmed) return;
        performStatusUpdate(meetingId);
      });

    function performStatusUpdate(meetingId) {
      fetch(`/agenda/status/${meetingId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.success) {
            if (data.deleted) {
              window.location.href = "/agenda";
              return;
            }
            const newStatus = data.new_status;
            button.dataset.currentStatus = newStatus;

            statusDisplayElement.classList.remove(
              "status-unpublished",
              "status-not-started",
              "status-running",
              "status-finished",
              "status-cancelled"
            );
            statusDisplayElement.classList.add(
              `status-${newStatus.replace(/ /g, "-")}`
            );

            let iconClass = "";
            let statusText = newStatus
              .replace(/_/g, " ")
              .replace(/\b\w/g, (l) => l.toUpperCase());

            if (newStatus === "not started") {
              button.innerHTML = '<i class="fas fa-fw fa-play"></i> Start';
              button.classList.remove("btn-danger", "btn-secondary", "btn-light");
              button.classList.add("btn-success");
              iconClass = "fa-play-circle";
              button.title = "Start to let audience vote.";
            } else if (newStatus === "running") {
              button.innerHTML = '<i class="fas fa-fw fa-stop"></i> Stop';
              button.classList.remove("btn-primary", "btn-success", "btn-secondary", "btn-light");
              button.classList.add("btn-danger");
              iconClass = "fa-broadcast-tower";
              button.title = "Stop to end voting and show results.";
            } else if (newStatus === "finished") {
              const canDelete = agendaContent.dataset.canDelete === "true";
              if (canDelete) {
                button.innerHTML = '<i class="fas fa-fw fa-check-circle"></i> Delete';
                button.classList.remove("btn-success", "btn-danger", "btn-light");
                button.title = "";
              } else {
                button.style.display = "none";
              }
              iconClass = "fa-check-circle";
            } else if (newStatus === "cancelled") {
              button.innerHTML = '<i class="fas fa-fw fa-ban"></i> Cancelled';
              button.disabled = true;
              button.classList.remove("btn-info", "btn-primary", "btn-success", "btn-danger", "btn-light");
              button.classList.add("btn-secondary");
              iconClass = "fa-ban";
              button.title = "";
            } else if (newStatus === "unpublished") {
              button.innerHTML = 'Publish';
              button.classList.remove("btn-danger", "btn-secondary", "btn-success");
              button.classList.add("btn-light");
              iconClass = "fa-eye-slash";
              button.title = "Publish to allow members to book roles.";
            } else {
              button.innerHTML = '<i class="fas fa-fw fa-play"></i> Start';
              iconClass = "fa-play-circle";
              button.title = "";
            }

            statusDisplayElement.innerHTML = `<i class="fas fa-fw ${iconClass}"></i>${statusText}`;

            // Sync the meeting-filter dropdown so its status tag stays in sync
            syncMeetingFilterStatus(meetingId, newStatus);

            // --- Clock Management ---
            if (clockEl) {
              if (newStatus === 'running') {
                if (data.start_time) {
                  meetingStartTime = data.start_time;
                  agendaContent.dataset.meetingStartTime = data.start_time;
                }
                startClock();
              } else if (newStatus === 'finished') {
                stopClock();
                clearHighlights();
              } else {
                stopClock();
                clockEl.classList.add('hidden');
                clearHighlights();
              }
            }
          } else {
            showCustomAlert("Error", "Error updating status: " + data.message);
          }
        })
        .catch((error) => {
          console.error("Error:", error);
          showCustomAlert("Error", "An error occurred while updating the meeting status.");
        });
    }
  }
  function handleContactFormSubmit(event) {
    event.preventDefault(); // Stop the default redirect
    const form = event.target;
    const formData = new FormData(form);

    fetch(form.action, {
      method: "POST",
      body: formData,
      headers: {
        // This header tells your Flask backend it's an AJAX request
        "X-Requested-With": "XMLHttpRequest",
      },
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          // Add the new contact to our local JavaScript array
          allContacts.push(data.contact);
          window.closeContactModal(); // Close the modal

          if (typeof window.onContactSelect === 'function') {
            window.onContactSelect(data.contact);
          } else if (activeOwnerInput) {
            activeOwnerInput.value = data.contact.Name;
            const hiddenInput = activeOwnerInput.nextElementSibling;
            if (
              hiddenInput &&
              hiddenInput.type === "hidden" &&
              (hiddenInput.name === "owner_id" || hiddenInput.name === "owner_ids")
            ) {
              hiddenInput.value = data.contact.id;
            }
          }
        } else {
          if (data.duplicate_contact) {
            showDuplicateModal(data.message, data.duplicate_contact);
          } else {
            showCustomAlert("Error", data.message || "An error occurred while saving the contact.");
          }
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        showCustomAlert("Error", "An error occurred while saving the contact.");
      });
  }

  function updateHeaderVisibility(isEditMode) {
    const header = document.querySelector("#logs-table thead");
    header.querySelector(".edit-mode-header").style.display = isEditMode
      ? "table-row"
      : "none";
    header.querySelector(".non-edit-mode-header").style.display = isEditMode
      ? "none"
      : "table-row";
  }

  function updateRowsForEditMode(isEditMode) {
    const rows = tableBody.querySelectorAll("tr");
    rows.forEach((row, index) => {
      row.classList.toggle("draggable-row", isEditMode);
      if (isEditMode) {
        // This is where the row's editable cells are first built.
        buildEditableRow(row, index + 1);

        const ownerId = row.dataset.ownerId;
        let credentials = row.dataset.credentials; // This might be pre-filled from DB

        if (ownerId && !credentials) {
          const contact = allContacts.find((c) => c.id == ownerId);
          if (contact) credentials = contact.Credentials;
        }
        // Fallback for null/undefined to empty string
        row.dataset.credentials = credentials || "";

        // After building, apply the duration rule.
        updateDurationForSessionType(row, row.dataset.typeId, false);
      }
    });
  }

  function buildEditableRow(row, seq) {
    const originalData = { ...row.dataset };
    row.innerHTML = "";

    const typeId = originalData.typeId; // Get typeId
    const sessionType = allSessionTypes.find((st) => st.id == typeId); // Find session type object
    const hasRole =
      sessionType && sessionType.Role && sessionType.Role.trim() !== ""; // Check if it has a role
    const isHidden = originalData.isHidden === "true"; // Parse hidden state

    if (originalData.isSection === "true") {
      const seqCell = createEditableCell("Meeting_Seq", seq, true, null);
      const titleCell = createEditableCell(
        "Session_Title",
        originalData.sessionTitle,
        true,
        null
      );

      // Determine if Duration_Min is hidden (only on iPad: 769px - 1024px)
      const isiPad = window.matchMedia('(min-width: 769px) and (max-width: 1024px)').matches;

      // Base colspan is 6 (covers Start Time, Session Type, Session Title, Owner, Min, Max)
      // On iPad, Duration_Min is hidden so we reduce colspan to 5.
      // On Mobile (< 768px), "No" is hidden but it's a neighbor, it doesn't affect Title's colspan.
      titleCell.colSpan = isiPad ? 5 : 6;

      titleCell.classList.add("section-row");
      titleCell.classList.add("drag-handle"); // Enable dragging from title
      seqCell.classList.add("drag-handle");   // Enable dragging from sequence no

      // Create a flex wrapper for title input within the section row
      const titleWrapper = document.createElement("div");
      titleWrapper.style.display = "flex";
      titleWrapper.style.alignItems = "center";
      titleWrapper.style.justifyContent = "center";
      titleWrapper.style.width = "100%";

      // Get the input from titleCell (it was appended by createEditableCell but we'll move it)
      const titleInput = titleCell.querySelector("input");
      if (titleInput) {
        titleWrapper.appendChild(titleInput);
      }

      titleCell.appendChild(titleWrapper);

      // Create actions cell separately
      const actionsCell = createActionsCell(originalData.id, typeId, hasRole, isHidden);

      row.append(
        seqCell,
        titleCell,
        actionsCell
      );
    } else {
      fieldsOrder.forEach((field, index) => {
        const value =
          field === "Meeting_Seq"
            ? seq
            : originalData[
            field
              .toLowerCase()
              .replace(/_([a-z])/g, (g) => g[1].toUpperCase())
            ];
        const cell = createEditableCell(field, value, false, typeId, originalData.ownerIds);
        if (index < 3) {
          // Check if it's one of the first three columns
          cell.classList.add("drag-handle");
        }
        row.appendChild(cell);
      });
      row.appendChild(createActionsCell(originalData.id, typeId, hasRole, isHidden));
    }
  }

  function updateActionButtonsVisibility(isEditMode) {
    if (viewModeButtons)
      viewModeButtons.style.display = isEditMode ? "none" : "flex";
    if (editModeButtons)
      editModeButtons.style.display = isEditMode ? "flex" : "none";
    // geStyleToggle logic removed - always visible in modal
  }

  function initializeSortable(enable) {
    if (enable) {
      if (sortable) sortable.destroy();
      sortable = new Sortable(tableBody, {
        animation: 150,
        handle: ".drag-handle",
        onEnd: renumberRows,
      });
    } else {
      if (sortable) {
        sortable.destroy();
        sortable = null;
      }
    }
  }

  function getRowData(row) {
    const isSection = row.dataset.isSection === "true";
    const titleCell = row.querySelector('[data-field="Session_Title"]');

    // Fallback for Read-Only mode (when elements haven't been built by buildEditableRow)
    if (!titleCell) {
      if (isSection) {
        return {
          id: row.dataset.id,
          meeting_number: row.dataset.meetingNumber,
          meeting_seq: row.dataset.meetingSeq,
          type_id: row.dataset.typeId,
          session_title: row.dataset.sessionTitle,
          is_hidden: row.dataset.isHidden === "true",
        };
      }
      return {
        id: row.dataset.id,
        meeting_number: row.dataset.meetingNumber,
        meeting_seq: row.dataset.meetingSeq,
        start_time: row.dataset.startTime,
        type_id: row.dataset.typeId,
        session_title: row.dataset.sessionTitle,
        owner_ids: JSON.parse(row.dataset.ownerIds || '[]'),
        credentials: row.dataset.credentials,
        owner_targets: JSON.parse(row.dataset.ownerTargets || '{}'),
        duration_min: row.dataset.durationMin,
        duration_max: row.dataset.durationMax,
        project_id: row.dataset.projectId,
        status: row.dataset.status,
        project_code: row.dataset.projectCode || "",
        is_hidden: row.dataset.isHidden === "true",
      };
    }

    const titleControl = titleCell.querySelector("input, select");
    const sessionTitleValue = titleControl
      ? titleControl.value
      : titleCell.textContent.trim();
    const seqInput = row.querySelector('[data-field="Meeting_Seq"] input');

    if (isSection) {
      return {
        id: row.dataset.id,
        meeting_number: row.dataset.meetingNumber,
        meeting_seq: seqInput ? seqInput.value : "",
        type_id: row.dataset.typeId,
        session_title: sessionTitleValue,
        is_hidden: row.dataset.isHidden === "true",
      };
    }

    // Collect all owner IDs
    const ownerIdInputs = row.querySelectorAll('input[name="owner_ids"]');
    const ownerIds = Array.from(ownerIdInputs).map(input => input.value).filter(val => val !== "");

    const data = {
      id: row.dataset.id,
      meeting_number: row.dataset.meetingNumber,
      meeting_seq: seqInput ? seqInput.value : "",
      start_time: row.querySelector('[data-field="Start_Time"] input').value,
      type_id: row.querySelector('[data-field="Type_ID"] select').value,
      session_title: sessionTitleValue,
      owner_ids: ownerIds,
      // Backward compat (primary owner)
      owner_id: ownerIds.length > 0 ? ownerIds[0] : "",
      credentials:
        row.querySelector('[data-field="Credentials"] input')?.value || null,
      owner_targets: JSON.parse(row.dataset.ownerTargets || '{}'),
      duration_min:
        row.querySelector('[data-field="Duration_Min"] input')?.value || null,
      duration_max:
        row.querySelector('[data-field="Duration_Max"] input')?.value || null,
      project_id: row.dataset.projectId,
      status: row.dataset.status,
      project_code: row.dataset.projectCode || "",
      pathway: row.dataset.pathway || "",
      is_hidden: row.dataset.isHidden === "true", // Include hidden status in save data
    };

    return data;
  }

  function renumberRows() {
    const rows = tableBody.querySelectorAll("tr");
    rows.forEach((row, index) => {
      const seqCell = row.querySelector('[data-field="Meeting_Seq"]');
      if (seqCell) {
        const input = seqCell.querySelector("input");
        if (input) input.value = index + 1;
      }
    });
  }

  function exportAgenda() {
    const meetingNumber = meetingFilter.value;
    if (meetingNumber) {
      window.location.href = `/agenda/export/${meetingNumber}`;
    } else {
      showCustomAlert("Select Meeting", "Please select a meeting to export.");
    }
  }

  function downloadPPT() {
    const meetingNumber = meetingFilter.value;
    if (meetingNumber) {
      window.location.href = `/agenda/ppt/${meetingNumber}`;
    } else {
      showCustomAlert("Select Meeting", "Please select a meeting to download PPT.");
    }
  }

  function exportAgendaJPG() {
    if (!meetingFilter || !meetingFilter.value) {
      showCustomAlert("Select Meeting", "Please select a meeting to export.");
      return;
    }

    // Show a loading state on the button
    const originalHTML = jpgButton.innerHTML;
    jpgButton.disabled = true;
    jpgButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    // Add the export mode class for A4-friendly styling
    agendaContent.classList.add("jpg-export-mode");

    // Small delay to let the browser repaint with the new class
    requestAnimationFrame(() => {
      setTimeout(() => {
        html2canvas(agendaContent, {
          scale: 2,
          useCORS: true,
          backgroundColor: "#ffffff",
          logging: false,
          windowWidth: 900,
        }).then((canvas) => {
          // Remove export mode class
          agendaContent.classList.remove("jpg-export-mode");

          // Convert to JPG and download
          canvas.toBlob((blob) => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            const clubShortName = agendaContent.dataset.clubShortName || "club";
            const meetingNum = agendaContent.dataset.meetingNumber || "0";
            const meetingDate = agendaContent.dataset.meetingDate || "unknown";
            a.href = url;
            a.download = `${clubShortName}-${meetingNum}-Agenda-${meetingDate}.jpg`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            // Restore button
            jpgButton.disabled = false;
            jpgButton.innerHTML = originalHTML;
          }, "image/jpeg", 0.95);
        }).catch((err) => {
          console.error("JPG export error:", err);
          agendaContent.classList.remove("jpg-export-mode");
          jpgButton.disabled = false;
          jpgButton.innerHTML = originalHTML;
          showCustomAlert("Export Error", "Failed to export agenda as image. Please try again.");
        });
      }, 100);
    });
  }

  function updateProjectSpeakers() {
    const currentSpeakers = new Set();

    // Ensure allSessionTypes is loaded before running
    if (!allSessionTypes || allSessionTypes.length === 0) {
      console.error("Session types not loaded, cannot update speaker list.");
      return;
    }

    tableBody.querySelectorAll("tr").forEach((row) => {
      // Use dataset attributes which are persistent and available even before inputs are built
      const typeId = row.dataset.typeId;
      const ownerId = row.dataset.ownerId;
      const projectId = row.dataset.projectId;

      // Check if we have valid data
      if (typeId && ownerId) {
        const sessionType = allSessionTypes.find((st) => st.id == typeId);

        // Skip if session type isn't found
        if (!sessionType) return;

        // Lookup speaker name from allContacts using ownerId
        const contact = allContacts.find(c => c.id == ownerId);
        const speakerName = contact ? contact.Name : null;

        if (!speakerName) return;

        // 1. EXCLUSION: Skip Individual Evaluators completely
        if (sessionType.Title === "Evaluation") {
          return;
        }

        // 2. INCLUSION: Add if it's a speech ("Prepared Speech") OR has a project ID
        // Note: We use the SessionType titles to identify speech types generally
        if (
          sessionType.Title === "Prepared Speech" ||
          (projectId && projectId !== "")
        ) {
          currentSpeakers.add(speakerName);
        }
      }
    });
    projectSpeakers = [...currentSpeakers];
    return projectSpeakers;
  }

  function handleSectionChange(selectElement) {
    const row = selectElement.closest("tr");
    const typeId = selectElement.value;
    row.dataset.typeId = typeId;
    const sessionType = allSessionTypes.find((st) => st.id == typeId);
    const titleCell = row.querySelector('[data-field="Session_Title"]');

    // Get current title from the control *before* clearing the cell
    const oldTitleControl = titleCell.querySelector("input, select, span");
    let currentTitle = oldTitleControl
      ? oldTitleControl.value || oldTitleControl.textContent
      : "";

    // If new type is predefined, use its title. Otherwise, keep the custom title.
    // PRESERVE: If we have a current title and it's not a new manual row, keep it.
    let newTitle = currentTitle;
    if (sessionType && sessionType.Predefined) {
      newTitle = sessionType.Title === "Evaluation" ? "" : sessionType.Title;
    }

    // --- Auto-Title Logic for Manually Added Rows ---
    if (row.dataset.isNewManually === "true" && !row.dataset.hasUserEditedTitle) {
      if (sessionType && sessionType.Title !== "Evaluation") {
        newTitle = sessionType.Title;
      } else if (sessionType && sessionType.Title === "Evaluation") {
        newTitle = "";
      }
    }

    // Special case: If changing *to* Evaluation, keep the speaker name (if it's not "Evaluation" or empty)
    if (sessionType && sessionType.Title === "Evaluation") {
      newTitle = currentTitle === "Evaluation" ? "" : currentTitle;
    }

    titleCell.innerHTML = "";
    titleCell.appendChild(
      createSessionTitleControl(
        typeId,
        sessionType ? sessionType.Title : "",
        newTitle
      )
    );

    // Sync to dataset for safety
    row.dataset.sessionTitle = newTitle;

    const projectBtn = row.querySelector(".project-btn");
    if (projectBtn) {
      projectBtn.style.display =
        sessionType && sessionType.Valid_for_Project ? "inline-block" : "none";
    }

    // Use the helper to apply duration rules when the type changes.
    updateDurationForSessionType(row, typeId);
  }

  // --- DOM Creation ---

  /**
   * Helper to update Duration inputs (Min/Max) based on the selected session type.
   * Also handles disabling Max duration for Topics Speaker.
   */
  function updateDurationForSessionType(row, typeId, updateValues = true) {
    const sessionType = allSessionTypes.find((st) => st.id == typeId);

    const durationMinInput = row.querySelector('[data-field="Duration_Min"] input');
    const durationMaxInput = row.querySelector('[data-field="Duration_Max"] input');

    // 1. Update Values
    if (updateValues && sessionType) {
      let min = sessionType.Duration_Min;
      let max = sessionType.Duration_Max;

      if (sessionType.Title === 'Presentation') {
        min = 10;
        max = 15;
      }

      if (durationMinInput) durationMinInput.value = (min !== null) ? min : '';
      if (durationMaxInput) durationMaxInput.value = (max !== null) ? max : '';
    }

    // 2. Handle Topics Speaker special case (disable max)
    if (durationMaxInput) {
      durationMaxInput.disabled = String(typeId) === "36";
      // Clear max if disabled (optional, but cleaner)
      if (durationMaxInput.disabled) durationMaxInput.value = '';
    }
  }
  function createEditableCell(field, value, isSection, typeId, ownerIdsJson) {
    const cell = document.createElement("td");
    cell.dataset.field = field;

    // Add classes for CSS targeting
    const fieldToClass = {
      Meeting_Seq: "col-no",
      Start_Time: "col-start-time",
      Type_ID: "col-session-type",
      Session_Title: "col-session-title",
      Owner_ID: "col-owner",
      Duration_Min: "col-duration-min",
      Duration_Max: "col-duration-max",
    };
    if (fieldToClass[field]) {
      cell.classList.add(fieldToClass[field]);
    }

    if (isSection) {
      const input = document.createElement("input");
      input.type = "text";
      input.value = value || "";
      if (field === "Meeting_Seq") {
        input.readOnly = true;
      }
      cell.appendChild(input);
      return cell;
    }

    switch (field) {
      case "Meeting_Seq":
      case "Start_Time":
        const input = document.createElement("input");
        input.type = "text";
        input.value = value || "";
        input.readOnly = true;
        cell.appendChild(input);
        break;
      case "Type_ID":
        cell.appendChild(createTypeSelect(value));
        break;
      case "Session_Title":
        const sessionType = allSessionTypes.find((st) => st.id == typeId);
        cell.appendChild(
          createSessionTitleControl(
            typeId,
            sessionType ? sessionType.Title : "",
            value
          )
        );
        break;
      case "Owner_ID":
        // Parse owner_ids from dataset if available
        let ownerIds = [];
        try {
          if (ownerIdsJson) {
            ownerIds = JSON.parse(ownerIdsJson);
          }
        } catch (e) {
          console.error("Error parsing ownerIds", e);
        }

        // Fallback to single value if list is empty but single ID exists
        if (ownerIds.length === 0 && value) {
          ownerIds = [value];
        }

        cell.appendChild(createOwnerInput(ownerIds));
        break;
      default:
        const defaultInput = document.createElement("input");
        defaultInput.type = "text";
        defaultInput.value = value || "";

        // For Topics Speaker (ID 36), always clear the Max Duration field on creation.
        if (field === "Duration_Max" && String(typeId) === "36") {
          defaultInput.value = "";
        }
        cell.appendChild(defaultInput);
    }
    return cell;
  }

  // --- Session Type Picker Modal ---
  // The native <select> is replaced by a button that opens a grouped modal
  // picker. A hidden <select> is kept in the DOM so existing query sites
  // (row.querySelector('[data-field="Type_ID"] select')) keep working.
  let stModal = null;
  let stModalCtx = null; // { row, hiddenSelect, triggerBtn }

  // Group metadata: label, icon, icon-color class, subtitle. Order = display order.
  const ST_GROUP_META = [
    { key: "Officers",                    icon: "fa-user-tie", iconClass: "st-icon--awards", subtitle: "Club officer-led sessions." },
    { key: "Featured",                    icon: "fa-star",     iconClass: "st-icon--featured", subtitle: "Highlighted featured sessions." },
    { key: "Standard",                    icon: "fa-cogs",     iconClass: "st-icon--info",   subtitle: "Sessions defined by the super club and shared with all clubs." },
    { key: "Custom",                      icon: "fa-building", iconClass: "st-icon--media",  subtitle: "Custom sessions specific to this club." },
  ];

  function ensureSessionTypeModal() {
    if (stModal) return stModal;

    const backdrop = document.createElement("div");
    backdrop.id = "session-type-modal";
    backdrop.className = "st-modal-backdrop";
    backdrop.style.display = "none";
    backdrop.innerHTML = `
      <div class="st-modal-panel" role="dialog" aria-modal="true" aria-label="Select Session Type">
        <div class="st-modal-header">
          <div>
            <h2 class="st-modal-title">Select Session Type</h2>
            <p class="st-modal-subtitle">Choose a session type for this row. Sections are added via the <strong>+Section</strong> button.</p>
          </div>
          <button type="button" class="st-modal-close" aria-label="Close"><i class="fas fa-times"></i></button>
        </div>
        <div class="st-modal-body" id="st-modal-body"></div>
        <div class="st-modal-footer">
          <button type="button" class="st-modal-cancel">Cancel</button>
          <button type="button" class="st-modal-ok">OK</button>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);

    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) closeSessionTypeModal();
    });
    backdrop.querySelector(".st-modal-close").addEventListener("click", closeSessionTypeModal);
    backdrop.querySelector(".st-modal-cancel").addEventListener("click", closeSessionTypeModal);
    backdrop.querySelector(".st-modal-ok").addEventListener("click", () => {
      if (stModalCtx && stModalCtx.pendingTypeId) {
        stModalCtx.hiddenSelect.value = stModalCtx.pendingTypeId;
        stModalCtx.hiddenSelect.dispatchEvent(new Event("change"));
        const labelEl = stModalCtx.triggerBtn.querySelector(".st-trigger-label");
        const t = allSessionTypes.find((st) => st.id == stModalCtx.pendingTypeId);
        if (labelEl && t) labelEl.textContent = t.Title;
      }
      closeSessionTypeModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && backdrop.style.display === "flex") closeSessionTypeModal();
    });

    stModal = backdrop;
    return stModal;
  }

  function classifySessionType(t) {
    const rg = (t.Role_Group || "").toLowerCase();
    if (rg === "officer") return "Officers";
    if (t.featured)       return "Featured";
    // "Standard" only means truly standard when it comes from the super club
    // (GLOBAL_CLUB_ID). Club-specific types tagged 'standard' belong in Custom.
    if (rg === "standard" && t.club_id === GLOBAL_CLUB_ID) return "Standard";
    return "Custom";
  }

  function openSessionTypeModal(row, hiddenSelect, triggerBtn) {
    ensureSessionTypeModal();
    stModalCtx = { row, hiddenSelect, triggerBtn, pendingTypeId: String(hiddenSelect.value || "") };

    const body = stModal.querySelector("#st-modal-body");
    const currentTypeId = String(hiddenSelect.value || "");
    const genericType = allSessionTypes.find((t) => t.Title === "Generic");

    // Exclude Generic from the listed candidates — it is selected via the
    // "Not listed below" checkbox instead.
    const candidates = allSessionTypes.filter((t) => !t.Is_Section && t.Title !== "Generic");
    const groups = {};
    for (const meta of ST_GROUP_META) groups[meta.key] = [];
    for (const t of candidates) groups[classifySessionType(t)].push(t);

    body.innerHTML = "";

    // "Not listed below" checkbox — selects Generic and disables the picker
    let isGenericSelected = false;
    let toggleItems = () => {};
    if (genericType) {
      const row = document.createElement("div");
      row.className = "st-generic-row";

      const label = document.createElement("label");
      label.className = "st-generic-label";

      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.id = "st-generic-check";

      const span = document.createElement("span");
      span.textContent = "Not listed below";

      label.appendChild(cb);
      label.appendChild(span);
      row.appendChild(label);

      isGenericSelected = currentTypeId === String(genericType.id);
      cb.checked = isGenericSelected;

      toggleItems = (disabled) => {
        body.querySelectorAll(".st-item, .st-section-header, .st-section-icon").forEach((el) => {
          el.style.opacity = disabled ? "0.35" : "";
          el.style.pointerEvents = disabled ? "none" : "";
        });
        body.querySelectorAll(".st-item").forEach((b) => {
          b.disabled = disabled;
        });
      };

      cb.addEventListener("change", () => {
        if (cb.checked) {
          toggleItems(true);
          body.querySelectorAll(".st-item.selected").forEach((b) => b.classList.remove("selected"));
          stModalCtx.pendingTypeId = String(genericType.id);
        } else {
          toggleItems(false);
          stModalCtx.pendingTypeId = ""; // force user to pick
        }
      });

      body.appendChild(row);
    }

    for (const meta of ST_GROUP_META) {
      const items = groups[meta.key];
      if (items.length === 0) continue;
      items.sort((a, b) => a.Title.localeCompare(b.Title));

      const section = document.createElement("div");
      section.className = `st-section st-section--${meta.key.replace(/\s+/g, "-").toLowerCase()}`;

      const header = document.createElement("div");
      header.className = "st-section-header";
      const icon = document.createElement("div");
      icon.className = `st-section-icon ${meta.iconClass}`;
      icon.innerHTML = `<i class="fas ${meta.icon}"></i>`;
      header.appendChild(icon);
      const titles = document.createElement("div");
      const title = document.createElement("div");
      title.className = "st-section-title";
      title.textContent = meta.key;
      titles.appendChild(title);
      const desc = document.createElement("div");
      desc.className = "st-section-desc";
      desc.textContent = meta.subtitle;
      titles.appendChild(desc);
      header.appendChild(titles);
      section.appendChild(header);

      const grid = document.createElement("div");
      grid.className = "st-item-grid";
      for (const t of items) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "st-item";
        if (String(t.id) === currentTypeId) btn.classList.add("selected");

        const check = document.createElement("i");
        check.className = "fas fa-check st-item-check";
        btn.appendChild(check);

        const text = document.createElement("span");
        text.className = "st-item-text";
        text.textContent = t.Title;
        btn.appendChild(text);

        btn.addEventListener("click", () => {
          // Highlight the selection; OK confirms, Cancel discards.
          stModalCtx.pendingTypeId = String(t.id);
          body.querySelectorAll(".st-item.selected").forEach((b) => b.classList.remove("selected"));
          btn.classList.add("selected");
        });
        grid.appendChild(btn);
      }
      section.appendChild(grid);
      body.appendChild(section);
    }

    // Now that sections are built, dim them if Generic is preselected
    if (genericType && isGenericSelected) toggleItems(true);

    stModal.style.display = "flex";
  }

  function closeSessionTypeModal() {
    if (stModal) stModal.style.display = "none";
    stModalCtx = null;
  }

  function createTypeSelect(selectedValue) {
    // Hidden <select> — kept for compatibility with existing query sites
    // (row.querySelector('[data-field="Type_ID"] select')) and so that
    // dispatching 'change' triggers the existing handleSectionChange flow.
    const select = document.createElement("select");
    select.style.display = "none";
    select.add(new Option("-- Select Session Type --", ""));
    const candidates = allSessionTypes.filter((t) => !t.Is_Section);
    candidates.sort((a, b) => a.Title.localeCompare(b.Title));
    for (const t of candidates) select.add(new Option(t.Title, t.id));
    select.value = selectedValue || "";
    select.addEventListener("change", () => handleSectionChange(select));

    // Visible trigger button — opens the grouped modal picker.
    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "st-trigger";

    const label = document.createElement("span");
    label.className = "st-trigger-label";
    const initialType = allSessionTypes.find((st) => st.id == selectedValue);
    label.textContent = initialType ? initialType.Title : "-- Select Session Type --";
    trigger.appendChild(label);

    const arrow = document.createElement("i");
    arrow.className = "fas fa-caret-down st-trigger-arrow";
    trigger.appendChild(arrow);

    trigger.addEventListener("click", (e) => {
      e.stopPropagation();
      const row = select.closest("tr");
      openSessionTypeModal(row, select, trigger);
    });

    const wrapper = document.createElement("div");
    wrapper.className = "st-type-wrapper";
    wrapper.appendChild(select);
    wrapper.appendChild(trigger);
    return wrapper;
  }

  function createSessionTitleControl(
    typeId,
    sessionTypeTitle,
    originalValue = ""
  ) {
    // Check if session type is Evaluation (ID 31)
    if (sessionTypeTitle === "Evaluation") {
      // Use the returned list directly
      const speakers = updateProjectSpeakers();
      const select = document.createElement("select");
      select.add(new Option("-- Select Speaker --", ""));

      // Populate with returned speakers
      if (speakers) {
        speakers.forEach((name) => select.add(new Option(name, name)));
      }
      select.value = originalValue || "";

      // Update speaker list on mouse down
      select.addEventListener("mousedown", function () {
        const currentValue = this.value;
        const currentSpeakers = updateProjectSpeakers();

        // Clear all options except the first one
        while (this.options.length > 1) {
          this.remove(1);
        }

        // Repopulate with updated speakers
        if (currentSpeakers) {
          currentSpeakers.forEach((name) => this.add(new Option(name, name)));
        }

        // Keep current selection if it still exists
        const stillExists = currentSpeakers && currentSpeakers.some(
          (name) => name === currentValue
        );
        if (stillExists) {
          this.value = currentValue;
        }
      });

      return select;
    } else if (sessionTypeTitle === "Pathway Speech") {
      const span = document.createElement("span");
      span.textContent = originalValue;
      span.title = "Edit speech title in the project modal";
      return span;
    }

    const input = document.createElement("input");
    input.type = "text";
    input.value = originalValue;

    // Track manual edits for auto-title logic
    input.addEventListener("input", function () {
      const row = this.closest("tr");
      if (row && row.dataset.isNewManually === "true") {
        row.dataset.hasUserEditedTitle = "true";
      }
    });

    return input;
  }

  function createOwnerInput(ownerIds) {
    if (!Array.isArray(ownerIds)) ownerIds = ownerIds ? [ownerIds] : [];

    const wrapper = document.createElement("div");
    wrapper.className = "owner-cell-wrapper";
    wrapper.style.display = "flex";
    wrapper.style.flexDirection = "column";
    wrapper.style.gap = "4px";

    const tagsContainer = document.createElement("div");
    tagsContainer.className = "owners-tags-container";

    const hiddenInputsContainer = document.createElement("div");
    hiddenInputsContainer.className = "hidden-owners-container";

    // Internal state of selected owner IDs
    let selectedIds = [...ownerIds];

    const renderTags = () => {
      tagsContainer.innerHTML = "";
      hiddenInputsContainer.innerHTML = "";

      selectedIds.forEach(id => {
        const contact = allContacts.find(c => c.id == id);
        if (!contact) return;

        const tag = document.createElement("div");
        tag.className = "owner-tag";
        tag.innerHTML = `<span>${contact.Name}</span>`;

        const removeBtn = document.createElement("span");
        removeBtn.className = "remove-tag";
        removeBtn.innerHTML = '<i class="fas fa-times"></i>';
        removeBtn.onclick = (e) => {
          e.stopPropagation();
          selectedIds = selectedIds.filter(sid => sid != id);
          renderTags();
        };

        tag.appendChild(removeBtn);
        tagsContainer.appendChild(tag);

        // Add hidden input for form submission
        const hidden = document.createElement("input");
        hidden.type = "hidden";
        hidden.name = "owner_ids";
        hidden.value = id;
        hiddenInputsContainer.appendChild(hidden);
      });

      // Hide container if empty to avoid gap/space
      tagsContainer.style.display = selectedIds.length > 0 ? "flex" : "none";

      // Sync primary owner data to row (for credentials/project)
      const currentRow = wrapper.closest("tr");
      if (currentRow) {
        const primaryId = selectedIds[0];
        const primaryContact = allContacts.find(c => c.id == primaryId);

        // Critical updates for save logic to pick up
        currentRow.dataset.ownerId = primaryId || "";
        currentRow.dataset.ownerIds = JSON.stringify(selectedIds);

        const credentialsInput = currentRow.querySelector('[data-field="Credentials"] input');
        if (credentialsInput) {
          credentialsInput.value = primaryContact ? (primaryContact.Credentials || "") : "";
          currentRow.dataset.credentials = credentialsInput.value;
        }

        if (primaryContact) {
          updatePairedSession(currentRow, selectedIds);

          // Auto-update Project for Prepared Speeches (ID 30)
          const typeSelect = currentRow.querySelector('[data-field="Type_ID"] select');
          // ... rest of the logic
          if (typeSelect && typeSelect.value == 30 && primaryContact.Next_Project && window.allProjects) {
            const nextProjCode = primaryContact.Next_Project;
            let foundProjId = null;
            for (const proj of window.allProjects) {
              if (proj.path_codes) {
                for (const [abbr, details] of Object.entries(proj.path_codes)) {
                  if (abbr + details.code === nextProjCode) {
                    foundProjId = proj.id;
                    break;
                  }
                }
              }
              if (foundProjId) break;
            }
            if (foundProjId) {
              currentRow.dataset.projectId = foundProjId;
            }
          }
        } else {
          updatePairedSession(currentRow, null);
          if (currentRow.dataset.typeId == 30) {
            currentRow.dataset.projectId = "";
          }
        }
      }
    };

    const searchContainer = document.createElement("div");
    searchContainer.className = "autocomplete-container";

    const searchInput = document.createElement("input");
    searchInput.type = "text";
    searchInput.placeholder = ""; // Don't show a placeholder for a blank owner
    searchInput.className = "owner-search-input";

    const tempHidden = document.createElement("input");
    tempHidden.type = "hidden";

    // Custom autocomplete logic to add to tags and clear input
    const setupOwnerAutocomplete = (input) => {
      let currentFocus;
      input.addEventListener("input", function () {
        let container, item, val = this.value;
        closeAllLists();
        if (!val) return;
        currentFocus = -1;
        container = document.createElement("div");
        container.setAttribute("class", "autocomplete-items");
        this.parentNode.appendChild(container);

        allContacts
          .filter(c => c.Name.toUpperCase().includes(val.toUpperCase()))
          .slice(0, 10) // Limit results
          .forEach(contact => {
            item = document.createElement("div");
            item.innerHTML = `<strong>${contact.Name.substr(0, val.length)}</strong>${contact.Name.substr(val.length)}`;
            item.addEventListener("click", () => {
              if (!selectedIds.includes(contact.id.toString())) {
                selectedIds.push(contact.id.toString());
                renderTags();
              }
              input.value = "";
              input.focus();
              closeAllLists();
            });
            container.appendChild(item);
          });
      });

      function closeAllLists(elmnt) {
        const items = document.getElementsByClassName("autocomplete-items");
        for (let i = 0; i < items.length; i++) {
          if (elmnt != items[i] && elmnt != input) {
            items[i].parentNode.removeChild(items[i]);
          }
        }
      }
      document.addEventListener("click", (e) => closeAllLists(e.target));
    };

    setupOwnerAutocomplete(searchInput);
    searchContainer.appendChild(searchInput);

    // Picker button
    const pickerBtn = document.createElement("button");
    pickerBtn.type = "button";
    pickerBtn.innerHTML = '<i class="fas fa-user-plus"></i>';
    pickerBtn.className = "btn btn-primary btn-sm icon-btn";
    pickerBtn.title = "Pick from Contact List";
    pickerBtn.style.padding = "2px 8px";
    pickerBtn.onclick = () => {
      activeOwnerInput = searchInput; // So the modal knows where to "return" the value
      // We need to override the default modal behavior to ADD instead of REPLACE
      const oldOnContactSelect = window.onContactSelect;
      window.onContactSelect = (contact) => {
        if (!selectedIds.includes(contact.id.toString())) {
          selectedIds.push(contact.id.toString());
          renderTags();
        }
        searchInput.value = "";
        searchInput.focus();
        // Restore? Usually modal selection closes it.
      };
      window.openContactModal();
    };

    const inputRow = document.createElement("div");
    inputRow.style.display = "flex";
    inputRow.style.gap = "4px";
    inputRow.append(searchContainer, pickerBtn);

    wrapper.append(tagsContainer, inputRow, hiddenInputsContainer);

    // Initial render
    renderTags();

    return wrapper;
  }

  function updatePairedSession(currentRow, ownerData) {
    let ownerIds = [];
    if (Array.isArray(ownerData)) {
      ownerIds = ownerData.filter(id => id !== null && id !== undefined && id !== "");
    } else if (ownerData && typeof ownerData === 'object' && ownerData.id) {
      ownerIds = [ownerData.id];
    } else if (ownerData) {
      ownerIds = [ownerData];
    }

    const primaryId = ownerIds[0];
    const newContact = allContacts.find(c => c.id == primaryId);

    const typeSelect = currentRow.querySelector(
      '[data-field="Type_ID"] select'
    );
    if (!typeSelect) return;

    const currentSessionType = allSessionTypes.find(
      (st) => st.id == typeSelect.value
    );
    if (!currentSessionType || !currentSessionType.Role) return;

    // 1. Determine the "Scope" of synchronization
    // A. Predefined pairs (legacy logic)
    const pairedSessionTitle =
      sessionPairs[currentSessionType.Title] ||
      reverseSessionPairs[currentSessionType.Title];

    // B. Shared roles (General logic based on has_single_owner property)
    const roleKey = currentSessionType.Role.toUpperCase().replace(/ /g, "_").replace(/-/g, "_");
    const roleInfo = allMeetingRoles[roleKey];
    const isSharedRole = roleInfo && !roleInfo.unique;

    if (!pairedSessionTitle && !isSharedRole) return;

    const allRows = document.querySelectorAll("#logs-table tbody tr");
    allRows.forEach((row) => {
      if (row === currentRow) return;

      const rowTypeSelect = row.querySelector('[data-field="Type_ID"] select');
      let shouldSync = false;

      if (rowTypeSelect) {
        const rowSessionType = allSessionTypes.find(
          (st) => st.id == rowTypeSelect.value
        );
        if (rowSessionType) {
          // Match by paired title OR by exact same role (if shared)
          if (pairedSessionTitle && rowSessionType.Title === pairedSessionTitle) {
            shouldSync = true;
          } else if (isSharedRole && rowSessionType.Role === currentSessionType.Role) {
            shouldSync = true;
          }
        }
      } else {
        // If not in edit mode, check dataset.role
        if (isSharedRole && row.dataset.role === currentSessionType.Role) {
          shouldSync = true;
        }
      }

      if (shouldSync) {
        // Sync Dataset (Critical for non-edit mode rows during save)
        row.dataset.ownerId = primaryId || "";
        row.dataset.ownerIds = JSON.stringify(ownerIds);
        if (newContact) {
          row.dataset.credentials = (newContact.Credentials || "");
        }

        // If in edit mode, sync UI components
        if (rowTypeSelect) {
          // Legacy inputs
          const pairedHiddenInput = row.querySelector('input[name="owner_id"]');
          if (pairedHiddenInput) pairedHiddenInput.value = primaryId || "";

          const pairedCredentialsInput = row.querySelector('[data-field="Credentials"] input');
          if (pairedCredentialsInput && newContact) {
            pairedCredentialsInput.value = (newContact.Credentials || "");
          }

          // [NEW] Multi-owner hidden inputs
          // We use a simplified sync: if the other row is being edited, 
          // the user might find it weird that tags don't update.
          // But implementing a full renderTags cross-call is complex.
          // Minimum: ensure hidden inputs match so save works.
          const hiddenContainer = row.querySelector(".hidden-owners-container");
          if (hiddenContainer) {
            hiddenContainer.innerHTML = "";
            ownerIds.forEach(id => {
              const hidden = document.createElement("input");
              hidden.type = "hidden";
              hidden.name = "owner_ids";
              hidden.value = id;
              hiddenContainer.appendChild(hidden);
            });
          }

          // Sync tags visually if possible
          const tagsContainer = row.querySelector(".owners-tags-container");
          if (tagsContainer) {
            tagsContainer.innerHTML = "";
            ownerIds.forEach(id => {
              const contact = allContacts.find(c => c.id == id);
              if (contact) {
                const tag = document.createElement("div");
                tag.className = "owner-tag";
                tag.innerHTML = `<span>${contact.Name}</span>`;
                tagsContainer.appendChild(tag);
              }
            });
            // Toggle visibility based on content
            tagsContainer.style.display = ownerIds.length > 0 ? "flex" : "none";
          }
        }
      }
    });

    // Generic sync loop completed
  }

  function setupAutocomplete(searchInput, hiddenInput) {
    let currentFocus;
    searchInput.addEventListener("input", function () {
      if (this.readOnly) return;

      if (this.value === "") {
        hiddenInput.value = "";
        const currentRow = searchInput.closest("tr");
        const credentialsInput = currentRow.querySelector(
          '[data-field="Credentials"] input'
        );
        currentRow.dataset.ownerId = "";
        credentialsInput.value = "";
        currentRow.dataset.credentials = "";
        updatePairedSession(currentRow, null);
      }

      let container,
        item,
        val = this.value;
      closeAllLists();
      if (!val) return;
      currentFocus = -1;
      container = document.createElement("div");
      container.setAttribute("class", "autocomplete-items");
      this.parentNode.appendChild(container);

      allContacts
        .filter((c) => c.Name.toUpperCase().includes(val.toUpperCase())) // Use allContacts
        .forEach((contact) => {
          item = document.createElement("div");
          item.innerHTML = `<strong>${contact.Name.substr(
            0,
            val.length
          )}</strong>${contact.Name.substr(val.length)}`;
          item.innerHTML += `<input type='hidden' value='${contact.Name}' data-id='${contact.id}'>`;
          item.addEventListener("click", function () {
            searchInput.value = this.querySelector("input").value;
            hiddenInput.value = this.querySelector("input").dataset.id;
            closeAllLists();

            const selectedContactId =
              this.getElementsByTagName("input")[0].dataset.id;
            const currentRow = searchInput.closest("tr");
            const credentialsInput = currentRow.querySelector(
              '[data-field="Credentials"] input'
            );
            const selectedContact = allContacts.find(
              (c) => c.id == selectedContactId
            );

            if (credentialsInput && selectedContact) {
              credentialsInput.value = selectedContact.Credentials || "";
            }
            currentRow.dataset.ownerId = selectedContactId;
            if (credentialsInput) {
              currentRow.dataset.credentials = credentialsInput.value;
            }

            const currentSessionType = allSessionTypes.find(
              (st) =>
                st.id ==
                currentRow.querySelector('[data-field="Type_ID"] select').value
            );

            updatePairedSession(currentRow, selectedContact);

            // --- Auto-update Project for Prepared Speeches (ID 30) ---
            if (
              currentSessionType &&
              currentSessionType.id == 30 &&
              selectedContact.Next_Project &&
              window.allProjects
            ) {
              const nextProjCode = selectedContact.Next_Project;
              let foundProjId = null;

              for (const proj of window.allProjects) {
                if (proj.path_codes) {
                  for (const [abbr, details] of Object.entries(
                    proj.path_codes
                  )) {
                    if (abbr + details.code === nextProjCode) {
                      foundProjId = proj.id;
                      break;
                    }
                  }
                }
                if (foundProjId) break;
              }

              if (foundProjId) {
                currentRow.dataset.projectId = foundProjId;
                // Optional: visual cue?
                // console.log("Auto-updated project to", foundProjId);
              }
            }
          });
          container.appendChild(item);
        });
    });

    function closeAllLists(elmnt) {
      const items = document.getElementsByClassName("autocomplete-items");
      for (let i = 0; i < items.length; i++) {
        if (elmnt != items[i] && elmnt != searchInput) {
          items[i].parentNode.removeChild(items[i]);
        }
      }
    }
    document.addEventListener("click", (e) => closeAllLists(e.target));
  }

  function createActionsCell(logId, typeId, hasRole, isHidden) {
    const cell = document.createElement("td");
    cell.className = "actions-column";

    // Create a wrapper for flex layout to avoid breaking table cell borders
    const wrapper = document.createElement("div");
    wrapper.className = "actions-wrapper";

    // --- Visibility Toggle Button (Created but not appended yet) ---
    const toggleBtn = document.createElement("button");
    toggleBtn.innerHTML = isHidden ? '<i class="fas fa-eye-slash"></i>' : '<i class="fas fa-eye"></i>';
    // Use 'is-hidden-state' class for visual cue (opacity) instead of btn-secondary (border/bg)
    toggleBtn.className = isHidden ? "icon-btn toggle-visibility-btn is-hidden-state" : "icon-btn toggle-visibility-btn";
    toggleBtn.type = "button";
    toggleBtn.title = isHidden ? "Show in Agenda" : "Hide in Agenda";

    toggleBtn.onclick = function () {
      const row = this.closest("tr");
      const currentHidden = row.dataset.isHidden === "true";
      const newHidden = !currentHidden;

      // Update dataset
      row.dataset.isHidden = String(newHidden);

      // Update styling immediately
      row.classList.toggle("hidden-row", newHidden);

      // Update Icon
      this.innerHTML = newHidden ? '<i class="fas fa-eye-slash"></i>' : '<i class="fas fa-eye"></i>';
      // Toggle opacity class
      this.className = newHidden ? "icon-btn toggle-visibility-btn is-hidden-state" : "icon-btn toggle-visibility-btn";
      this.title = newHidden ? "Show in Agenda" : "Hide in Agenda";
    };
    // ----------------------------

    const sessionType = allSessionTypes.find((st) => st.id == typeId);
    const rolesToHideFor = [
      allMeetingRoles.PREPARED_SPEAKER
        ? allMeetingRoles.PREPARED_SPEAKER.name
        : "Prepared Speaker",
      "Table Topics",
    ];

    const shouldShowProjectButton =
      sessionType &&
      (sessionType.Valid_for_Project || sessionType.Title === "Table Topics");
    const shouldShowRoleButton =
      hasRole && sessionType && !rolesToHideFor.includes(sessionType.Role);

    const isSection = sessionType && sessionType.Is_Section;

    // 1. Add/Edit Button (First Position)
    if (isSection) {
      const addSessionBtn = document.createElement("button");
      addSessionBtn.innerHTML = '<i class="fas fa-plus-circle"></i>';
      addSessionBtn.className = "icon-btn add-session-btn";
      addSessionBtn.type = "button";
      addSessionBtn.title = "Add Session to Section";
      addSessionBtn.onclick = function () {
        addSessionToSection(this.closest("tr"));
      };
      wrapper.append(addSessionBtn);
    } else {
      // The consolidated edit button for non-section rows
      const editDetailsBtn = document.createElement("button");
      editDetailsBtn.innerHTML = '<i class="fas fa-edit"></i>'; // Generic edit icon
      editDetailsBtn.className = "icon-btn edit-details-btn"; // New class
      editDetailsBtn.type = "button";

      if (shouldShowProjectButton) {
        editDetailsBtn.title = "Edit Speech/Project Details";
        editDetailsBtn.onclick = function () {
          const row = this.closest("tr");
          const logId = row.dataset.id;
          const ownerId = row.dataset.ownerId; // Use allContacts
          const contact = allContacts.find((c) => c.id == ownerId);
          let currentPath = null;
          if (contact) {
            const isGuestWithoutUser = (contact.Type === "Guest");
            if (!isGuestWithoutUser && contact.Current_Path) {
              currentPath = contact.Current_Path;
            } else {
              currentPath = "Non Pathway";
            }
          } else {
            currentPath = "Non Pathway";
          }
          const nextProject = contact ? contact.Next_Project : null;
          const typeId = row.querySelector(
            '[data-field="Type_ID"] select'
          ).value;
          const sessionType = allSessionTypes.find((st) => st.id == typeId); // Use allSessionTypes
          const sessionTypeTitle = sessionType ? sessionType.Title : null; // Use allSessionTypes
          if (logId === "new") {
            saveChanges();
          } else {
            openEditDetailsModal(
              logId,
              currentPath,
              sessionTypeTitle,
              nextProject
            );
          }
        };
      } else if (shouldShowRoleButton) {
        editDetailsBtn.title = "Edit Role Path/Level";
        editDetailsBtn.onclick = function () {
          const row = this.closest("tr");
          const logId = row.dataset.id;
          if (logId === "new") {
            saveChanges();
          } else {
            openEditDetailsModal(logId);
          }
        };
      }

      // Only append the edit button if it's needed, otherwise append a placeholder
      if (shouldShowProjectButton || shouldShowRoleButton) {
        wrapper.append(editDetailsBtn);
      } else {
        // Create placeholder to maintain alignment
        const placeholder = document.createElement("button");
        placeholder.className = "icon-btn"; // Use same class for consistent box-model
        placeholder.style.visibility = "hidden";
        placeholder.style.pointerEvents = "none";
        // Add the icon so it takes up the exact same width
        placeholder.innerHTML = '<i class="fas fa-edit"></i>';
        wrapper.append(placeholder);
      }
    }

    // 2. Toggle Visibility Button (Second Position)
    wrapper.appendChild(toggleBtn);

    // 3. Delete Button (Third Position)
    const deleteBtn = document.createElement("button");
    deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i>';
    deleteBtn.className = "delete-btn icon-btn";
    deleteBtn.type = "button";

    wrapper.append(deleteBtn);

    cell.appendChild(wrapper);
    return cell;
  }


  // --- Section collapse/expand ---
  // Walk every subsequent row until the next section header; rows whose
  // data-section-id matches the toggled section are hidden (or restored).
  // Rows belonging to other sections are left untouched.
  function toggleSection(sectionRow) {
    const sectionId = String(sectionRow.dataset.id);
    if (!sectionId) return;
    const collapsed = sectionRow.classList.toggle('collapsed');
    const toggleIcon = sectionRow.querySelector('.section-toggle');
    if (toggleIcon) {
      toggleIcon.classList.toggle('fa-caret-down', !collapsed);
      toggleIcon.classList.toggle('fa-caret-up', collapsed);
    }
    let cursor = sectionRow.nextElementSibling;
    while (cursor) {
      if (cursor.classList.contains('section-row')) break;
      if (String(cursor.dataset.sectionId) === sectionId) {
        cursor.classList.toggle('section-collapsed-child', collapsed);
      }
      cursor = cursor.nextElementSibling;
    }
  }

  document.addEventListener('click', (e) => {
    const toggleEl = e.target.closest('.section-toggle');
    if (!toggleEl) return;
    const sectionRow = toggleEl.closest('tr.section-row');
    if (!sectionRow) return;
    e.preventDefault();
    e.stopPropagation();
    toggleSection(sectionRow);
  });

  // --- Test Hooks ---
  if (typeof window !== 'undefined') {
    window._agendaTestHooks = {
      updateProjectSpeakers: updateProjectSpeakers,
      getProjectSpeakers: () => projectSpeakers,
      setSessionTypes: (types) => { allSessionTypes = types; },
      setContacts: (contacts) => { allContacts = contacts; }
    };
  }

  // --- Init ---
  initMeetingClock();
  window.addEventListener('beforeunload', stopClock);
}); // End of DOMContentLoaded listener

window.closeModal = function (modalId) {
  document.getElementById(modalId).style.display = "none";
};
// Ensure createAgendaModal closing function is global if needed
window.closeCreateAgendaModal = function () {
  const createAgendaModal = document.getElementById("createAgendaModal");
  if (createAgendaModal) {
    createAgendaModal.style.display = "none";
  }
};

// --- Custom Modal Helper Functions ---
window.showCustomConfirm = function (title, message, iconClass = "confirm") {
  return new Promise((resolve) => {
    const modal = document.getElementById("custom-modal");
    const titleEl = document.getElementById("custom-modal-title");
    const messageEl = document.getElementById("custom-modal-message");
    const iconEl = document.getElementById("custom-modal-icon");
    const okBtn = document.getElementById("custom-modal-ok");
    const cancelBtn = document.getElementById("custom-modal-cancel");

    titleEl.textContent = title;
    messageEl.innerHTML = message;
    iconEl.className = "custom-modal-icon " + iconClass;
    iconEl.innerHTML = iconClass === "confirm" ? '<i class="fas fa-question-circle"></i>' : '<i class="fas fa-exclamation-circle"></i>';

    cancelBtn.style.display = "inline-block";
    modal.style.display = "flex";

    const handleOk = () => {
      modal.style.display = "none";
      cleanup();
      resolve(true);
    };

    const handleCancel = () => {
      modal.style.display = "none";
      cleanup();
      resolve(false);
    };

    const cleanup = () => {
      okBtn.removeEventListener("click", handleOk);
      cancelBtn.removeEventListener("click", handleCancel);
    };

    okBtn.addEventListener("click", handleOk);
    cancelBtn.addEventListener("click", handleCancel);
  });
};

window.showCustomAlert = function (title, message, iconClass = "alert") {
  return new Promise((resolve) => {
    const modal = document.getElementById("custom-modal");
    const titleEl = document.getElementById("custom-modal-title");
    const messageEl = document.getElementById("custom-modal-message");
    const iconEl = document.getElementById("custom-modal-icon");
    const okBtn = document.getElementById("custom-modal-ok");
    const cancelBtn = document.getElementById("custom-modal-cancel");

    titleEl.textContent = title;
    messageEl.innerHTML = message;
    iconEl.className = "custom-modal-icon " + iconClass;
    iconEl.innerHTML = '<i class="fas fa-info-circle"></i>';

    cancelBtn.style.display = "none";
    modal.style.display = "flex";

    const handleOk = () => {
      modal.style.display = "none";
      okBtn.removeEventListener("click", handleOk);
      resolve();
    };

    okBtn.addEventListener("click", handleOk);
  });
};

window.deleteMeetingTemplate = async function (value, text, customSelectInstance) {
  if (typeof window.closeCreateAgendaModal === "function") {
    window.closeCreateAgendaModal();
  }
  const confirmed = await window.showCustomConfirm(
    "Delete Template",
    `Are you sure you want to delete the template '${text}'?`
  );
  if (confirmed) {
    try {
      const response = await fetch("/agenda/delete_template", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ template_name: text }),
      });
      const data = await response.json();
      if (data.success) {
        const select = customSelectInstance.select;
        for (let i = 0; i < select.options.length; i++) {
          if (select.options[i].text === text) {
            select.remove(i);
            break;
          }
        }
        customSelectInstance.refresh();
      } else {
        showCustomAlert("Error", "Error deleting template: " + data.message);
      }
    } catch (error) {
      console.error("Error:", error);
      showCustomAlert("Error", "An error occurred while deleting.");
    }
  }
};

