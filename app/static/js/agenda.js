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
  const exportButton = document.getElementById("export-btn");
  const jpgButton = document.getElementById("jpg-btn");
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

  // --- Main Initialization Function (called after data is fetched) ---
  function initializeAgendaPage() {
    initializeEventListeners(); // Attach listeners to buttons
    toggleEditMode(false); // Set initial UI state
    // Any other initial setup that depends on fetched data
  }

  // --- Fetch all necessary data asynchronously and then initialize the page ---
  // This fetch is now inside the DOMContentLoaded listener.
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
        window.allProjects = allProjects;
        window.pathways = data.pathways;
        window.pathwayMap = data.pathway_mapping;
        window.groupedPathways = data.pathways;
        window.ProjectID = data.project_id_constants;

        initializeAgendaPage(); // Now that data is loaded, initialize the page
      })
      .catch((error) => {
        console.error("Error fetching initial data:", error);
        showCustomAlert("Warning", "Could not load some editing data. You may need to reload the page to edit fully.\n\nError: " + error.message);
        // Even if data load fails, we MUST initialize the page so buttons work!
        initializeAgendaPage();
      });
  } else {
    initializeAgendaPage(); // Initialize for guest view without fetching edit data
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
      editBtn.addEventListener("click", () => toggleEditMode(true));
    }
    if (saveBtn) {
      saveBtn.addEventListener("click", () => saveChanges(false));
    }
    if (cancelButton) {
      cancelButton.addEventListener("click", () => {
        if (isEditing) {
          const meetingId = meetingFilter.value;
          if (!meetingId) {
            window.location.reload();
            return;
          }

          // Fast Cancel: Fetch current data and re-render without reload
          fetch(`/api/agenda/get_logs/${meetingId}`)
            .then(response => response.json())
            .then(data => {
              if (data.success) {
                if (data.project_speakers) {
                  projectSpeakers = data.project_speakers;
                  tableContainer.dataset.projectSpeakers = JSON.stringify(projectSpeakers);
                }
                if (data.logs_data) {
                  renderTableRows(data.logs_data);
                  toggleEditMode(false);
                } else {
                  // Fallback if no logs returned
                  window.location.reload();
                }
              } else {
                console.error("Fast cancel failed:", data.message);
                window.location.reload();
              }
            })
            .catch(err => {
              console.error("Fast cancel error:", err);
              window.location.reload();
            });
        }
      });
    }
    if (addRowButton) {
      addRowButton.addEventListener("click", addNewRow);
    }

    if (exportButton) {
      exportButton.addEventListener("click", exportAgenda);
    }
    if (createButton) {
      createButton.addEventListener("click", () => {
        const createAgendaModal = document.getElementById("createAgendaModal");
        if (createAgendaModal) {
          createAgendaModal.style.display = "flex";
        }
      });
    }
    const pptButton = document.getElementById("ppt-btn");
    if (pptButton) {
      pptButton.addEventListener("click", downloadPPT);
    }
    if (jpgButton) {
      jpgButton.addEventListener("click", exportAgendaJPG);
    }
    if (tableBody) {
      tableBody.addEventListener("click", (event) => {
        if (event.target.closest(".delete-btn")) {
          deleteLogRow(event.target.closest("tr"));
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

  // --- Core Functions ---

  function closeMeetingDetailsModal() {
    document.getElementById("meetingDetailsModal").style.display = "none";
  }
  // Ensure the function is global so the close button onclick works
  window.closeMeetingDetailsModal = closeMeetingDetailsModal;

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
    fetch("/agenda/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        meeting_id: meetingId,
        agenda_data: dataToSave,
        ge_mode: parseInt(geStyleSelect.value),
        meeting_title: document.getElementById("edit-meeting-title").value,
        subtitle: document.getElementById("edit-subtitle").value,
        meeting_type: document.getElementById("edit-meeting-type").value,
        wod: document.getElementById("edit-wod").value,
        media_url: document.getElementById("edit-media-url").value,
        manager_id: document.getElementById("edit-manager").value,
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
      row.dataset.currentPathLevel = log.current_path_level || '';

      // --- Set Classes ---
      if (log.is_section) row.classList.add('section-row');
      if (log.is_hidden) row.classList.add('hidden-row');
      if (log.is_readonly) row.classList.add('readonly-row');

      // --- Create Cells ---
      if (log.is_section) {
        const td = document.createElement('td');
        td.colSpan = 4;
        td.className = 'non-edit-mode-cell';
        td.textContent = log.Session_Title || log.session_type_title;
        row.appendChild(td);
      } else {
        // 1. Start Time
        const tdTime = document.createElement('td');
        tdTime.className = 'non-edit-mode-cell';
        tdTime.textContent = log.Start_Time_str;
        row.appendChild(tdTime);

        // 2. Session Title (Complex Logic)
        const tdSession = document.createElement('td');
        tdSession.className = 'non-edit-mode-cell';
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
        if (log.project_code_display) {
          tooltipWrapper.appendChild(document.createTextNode(' ')); // Space
          if (log.Project_ID && log.pathway_code) {
            const aCode = document.createElement('a');
            aCode.href = `/pathway_library?path=${log.pathway_code}&level=${log.level}&project_id=${log.Project_ID}`;
            aCode.className = 'project-code-link';
            aCode.title = 'View in Pathway Library';
            aCode.textContent = `(${log.project_code_display})`;
            tooltipWrapper.appendChild(aCode);
          } else {
            const spanCode = document.createElement('span');
            spanCode.className = 'project-code-link';
            spanCode.title = 'Project Code';
            spanCode.textContent = `(${log.project_code_display})`;
            tooltipWrapper.appendChild(spanCode);
          }
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

          const nameSpan = document.createElement('span');
          nameSpan.className = 'owner-name';
          nameSpan.textContent = ownerInfo.name;
          ownerRow.appendChild(nameSpan);

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
        row.appendChild(tdOwner);

        // 4. Duration
        const tdDur = document.createElement('td');
        tdDur.className = 'non-edit-mode-cell';
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

  function handleMeetingStatusChange(button) {
    const meetingId = button.dataset.meetingId;
    let currentStatus = button.dataset.currentStatus;

    if (!meetingId) {
      showCustomAlert("No Selection", "No meeting selected.");
      return;
    }

    if (currentStatus === "finished") {
      showCustomConfirm("Delete Meeting", "Are you sure you want to PERMANENTLY DELETE this meeting and all its records (logs, votes, media)? This action cannot be undone.")
        .then((confirmed) => {
          if (!confirmed) return;
          performStatusUpdate(meetingId);
        });
    } else {
      performStatusUpdate(meetingId);
    }

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
              button.textContent = "Start";
              button.classList.remove("btn-success");
              button.classList.add("btn-primary");
              iconClass = "fa-play-circle";
            } else if (newStatus === "running") {
              button.textContent = "Stop";
              iconClass = "fa-broadcast-tower";
            } else if (newStatus === "finished") {
              button.textContent = "Delete";
              iconClass = "fa-check-circle";
            } else if (newStatus === "cancelled") {
              button.textContent = "Cancelled";
              button.disabled = true;
              button.classList.remove("btn-info", "btn-primary", "btn-success");
              button.classList.add("btn-secondary");
              iconClass = "fa-ban";
            } else if (newStatus === "unpublished") {
              button.textContent = "Publish";
              button.classList.add("btn-success");
              iconClass = "fa-eye-slash";
            } else {
              button.textContent = "Start";
              iconClass = "fa-play-circle";
            }

            statusDisplayElement.innerHTML = `<i class="fas fa-fw ${iconClass}"></i>${statusText}`;
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
          if (activeOwnerInput) {
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

      // Dynamically set colspan based on whether the 'No' column is hidden (mobile view)
      const colNoHeader = document.querySelector('#logs-table th.col-no');
      const isMobileView = colNoHeader && window.getComputedStyle(colNoHeader).display === 'none';

      if (isMobileView) {
        titleCell.colSpan = 5; // Spans the visible middle columns on mobile (8 total - gap of 2 hidden columns + 1 action column? no, 7 visible total: header has 8, sequence is 1, actions is 1, title needs to fill 6? wait.)
      } else {
        titleCell.colSpan = 6; // Spans the middle columns on desktop
      }

      titleCell.classList.add("section-row");
      titleCell.classList.add("drag-handle"); // Enable dragging from title
      seqCell.classList.add("drag-handle");   // Enable dragging from sequence no

      row.append(
        seqCell,
        titleCell,
        createActionsCell(originalData.id, typeId, hasRole, isHidden)
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

    return {
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
      duration_min:
        row.querySelector('[data-field="Duration_Min"] input')?.value || null,
      duration_max:
        row.querySelector('[data-field="Duration_Max"] input')?.value || null,
      project_id: row.dataset.projectId,
      status: row.dataset.status,
      project_code: row.dataset.projectCode || "",
      project_code: row.dataset.projectCode || "",
      pathway: row.dataset.pathway || "",
      is_hidden: row.dataset.isHidden === "true", // Include hidden status in save data
    };
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
    let newTitle =
      sessionType && sessionType.Predefined ? sessionType.Title : currentTitle;

    // Special case: If changing *to* Evaluation, keep the speaker name
    if (sessionType && sessionType.Title === "Evaluation") {
      newTitle = currentTitle;
    }

    titleCell.innerHTML = "";
    titleCell.appendChild(
      createSessionTitleControl(
        typeId,
        sessionType ? sessionType.Title : "",
        newTitle
      )
    );

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

  function createTypeSelect(selectedValue) {
    const select = document.createElement("select");
    select.add(new Option("-- Select Session Type --", ""));

    // Allow duplicate session types (User Request: "Ballot Counting" needs to appear twice)
    const availableTypes = [...allSessionTypes];

    const sections = availableTypes.filter(t => t.Is_Section);

    // Group Non-Section types into Standard and Club Specific
    const standard = availableTypes.filter(
      (type) => !type.Is_Section && type.club_id === GLOBAL_CLUB_ID
    );
    const clubSpecific = availableTypes.filter(
      (type) => !type.Is_Section && type.club_id !== GLOBAL_CLUB_ID
    );

    const createOptGroup = (label, types) => {
      const optgroup = document.createElement("optgroup");
      optgroup.label = label;
      // Sort types alphabetically within the group
      types.sort((a, b) => a.Title.localeCompare(b.Title));
      types.forEach((type) => {
        optgroup.appendChild(new Option(type.Title, type.id));
      });
      return optgroup;
    };

    // 1. Club Specific (Local) - Show first for visibility
    if (clubSpecific.length > 0) {
      select.appendChild(createOptGroup("--- Club Specific Sessions ---", clubSpecific));
    }

    // 2. Standard (Global)
    if (standard.length > 0) {
      select.appendChild(
        createOptGroup("--- Standard Sessions ---", standard)
      );
    }

    // 3. Section Headers
    if (sections.length > 0) {
      select.appendChild(createOptGroup("--- Section Headers ---", sections));
    }

    select.value = selectedValue;
    select.addEventListener("change", () => handleSectionChange(select));
    return select;
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
          const currentPath = contact ? contact.Current_Path : null;
          const nextProject = contact ? contact.Next_Project : null;
          const typeId = row.querySelector(
            '[data-field="Type_ID"] select'
          ).value;
          const sessionType = allSessionTypes.find((st) => st.id == typeId); // Use allSessionTypes
          const sessionTypeTitle = sessionType ? sessionType.Title : null; // Use allSessionTypes
          if (logId === "new") {
            saveChanges();
          } else {
            openSpeechEditModal(
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
            openRoleEditModal(logId);
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

  window.openRoleEditModal = function (logId) {
    const row = tableBody.querySelector(`tr[data-id="${logId}"]`);
    if (!row) return;

    const roleName = row.dataset.role || "N/A";
    const currentPathLevel = row.dataset.currentPathLevel || "";

    document.getElementById("edit-role-log-id").value = logId;
    document.getElementById("role-name-display").textContent = roleName;
    document.getElementById("edit-current-path-level").value = currentPathLevel;

    // // If using separate dropdowns:
    // const pathLevelMatch = currentPathLevel.match(/^([A-Z]+)(\d+)$/);
    // document.getElementById('edit-role-pathway').value = pathLevelMatch ? pathLevelMatch[1] : '';
    // document.getElementById('edit-role-level').value = pathLevelMatch ? pathLevelMatch[2] : '';

    document.getElementById("roleEditModal").style.display = "flex";
  };

  window.closeRoleEditModal = function () {
    document.getElementById("roleEditModal").style.display = "none";
  };

  window.saveRoleChanges = function (event) {
    event.preventDefault();
    const logId = document.getElementById("edit-role-log-id").value;
    const row = tableBody.querySelector(`tr[data-id="${logId}"]`);
    if (!row) return;

    const newPathLevel = document
      .getElementById("edit-current-path-level")
      .value.trim()
      .toUpperCase();

    // // If using separate dropdowns:
    // const pathway = document.getElementById('edit-role-pathway').value;
    // const level = document.getElementById('edit-role-level').value;
    // const newPathLevel = (pathway && level) ? `${pathway}${level}` : '';

    // Update the row's dataset immediately
    row.dataset.currentPathLevel = newPathLevel;

    // Optionally update a visible cell if needed (though path/level isn't usually displayed directly in edit mode)
    // Example: const pathLevelCell = row.querySelector('.some-path-level-display-cell');
    // if(pathLevelCell) pathLevelCell.textContent = newPathLevel;

    // NOTE: Actual saving happens when the main "Save" button is clicked,
    // which reads the updated dataset via getRowData.
    closeRoleEditModal();
  };
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
    messageEl.textContent = message;
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
    messageEl.textContent = message;
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

