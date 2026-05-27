// static/js/booking.js

// Note: This script assumes the following global variables are defined in the HTML:
// - isAdminView (Boolean)
// - selectedMeetingId (Number)
// - currentBookingHash (String)

let accordionState = {};
try {
  accordionState = JSON.parse(sessionStorage.getItem('bookingAccordionState')) || {};
} catch (e) {
  console.warn("Session storage not available:", e);
}

document.addEventListener("DOMContentLoaded", function () {
  if (isAdminView) {
    initializeAdminAutocomplete();

    // Handle clicks on recommendation badges
    document.addEventListener("click", function (e) {
      const badge = e.target.closest(".recommendation-badge");
      if (badge) {
        const container = badge.closest(".recommended-members-container");
        const sessionId = container.dataset.sessionId;
        const contactId = badge.dataset.contactId;
        const contactName = badge.dataset.contactName;

        // Find the input for this session
        const inputRow = document.querySelector(`tr[data-session-id="${sessionId}"]:not(.recommendation-row)`);
        if (inputRow) {
          const input = inputRow.querySelector(".admin-assign-input");
          const results = inputRow.querySelector(".autocomplete-results");

          if (input && results) {
            selectContact(sessionId, contactId, contactName, input, results);
          }
        }
      }
    });

    // Close results when clicking outside
    document.addEventListener("mousedown", function (e) {
      if (!e.target.closest(".autocomplete-container")) {
        document.querySelectorAll(".autocomplete-results.active").forEach((res) => {
          res.classList.remove("active");
        });
      }
    });
  }

  initializeAccordions();

  // Meeting Filter Logic
  const meetingFilter = document.getElementById("meeting-filter");
  if (meetingFilter) {
    meetingFilter.addEventListener("change", function () {
      if (this.value) {
        window.location.href = '/booking/' + this.value;
      }
    });
  }

  document.querySelectorAll(".timeline-event").forEach((item) => {
    item.addEventListener("click", function () {
      const meetingId = this.dataset.meetingId;
      if (meetingId) {
        window.location.href = "/booking/" + meetingId;
      }
    });
  });

  // Setup state polling if a valid meeting is selected and hash is present
  if (typeof selectedMeetingId !== "undefined" && selectedMeetingId && typeof currentBookingHash !== "undefined") {
    setInterval(pollBookingState, 10000);
  }
});

function initializeAdminAutocomplete() {
  document.querySelectorAll(".autocomplete-container").forEach((container) => {
    if (container.dataset.autocompleteInitialized) return;
    container.dataset.autocompleteInitialized = "true";

    const input = container.querySelector(".admin-assign-input");
    const results = container.querySelector(".autocomplete-results");
    const sessionId = container.dataset.sessionId;
    const isMemberOnly = container.dataset.isMemberOnly === "true";

    input.addEventListener("focus", function () {
      if (results.classList.contains("active")) return;
      this.dataset.previousValue = this.value;
      this.dataset.previousId = this.dataset.currentId;

      // Hide placeholder on focus
      this.dataset.savedPlaceholder = this.placeholder;
      this.placeholder = "";

      showResults("", results, sessionId, input, isMemberOnly);
    });

    input.addEventListener("blur", function () {
      // Restore placeholder on blur
      if (this.dataset.savedPlaceholder) {
        this.placeholder = this.dataset.savedPlaceholder;
      }
    });

    input.addEventListener("input", function () {
      showResults(this.value, results, sessionId, input, isMemberOnly);
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        results.classList.remove("active");
      }
    });
  });
}

function initializeAccordions() {
  const accordionHeaders = document.querySelectorAll(".accordion-header");

  accordionHeaders.forEach(header => {
    if (header.dataset.accordionInitialized) return;
    header.dataset.accordionInitialized = "true";

    const accordionItem = header.parentElement;
    const category = accordionItem.dataset.category;
    const accordionContent = header.nextElementSibling;

    // Restore state on page load
    if (category && accordionState[category]) {
      header.classList.add("active");
      accordionContent.style.maxHeight = accordionContent.scrollHeight + "px";
    }

    header.addEventListener("click", () => {
      const isActive = header.classList.toggle("active");

      if (accordionContent.style.maxHeight) {
        accordionContent.style.maxHeight = null;
        if (category) {
          delete accordionState[category];
        }
      } else {
        accordionContent.style.maxHeight = accordionContent.scrollHeight + "px";
        if (category) {
          accordionState[category] = true;
        }
      }
      try {
        sessionStorage.setItem('bookingAccordionState', JSON.stringify(accordionState));
      } catch (e) {
        // Ignore session storage errors
      }
    });
  });
}

function showResults(query, resultsContainer, sessionId, input, isMemberOnly) {
  const filteredContacts = allContacts.filter((c) => {
    const matchesQuery = c.name.toLowerCase().includes(query.toLowerCase());
    const matchesType = !isMemberOnly || c.type === "Member";
    return matchesQuery && matchesType;
  }).slice(0, 5);

  resultsContainer.innerHTML = "";

  filteredContacts.forEach((contact) => {
    const item = document.createElement("div");
    item.className = "autocomplete-item";
    item.innerHTML = `
      <div class="item-avatar">
          <img src="${contact.avatar_url || '/static/default_avatar.jpg'}" alt="">
      </div>
      <div class="item-name">${contact.name}</div>
      <div class="item-type ${contact.type.toLowerCase()}">${contact.type}</div>
    `;
    item.addEventListener("mousedown", (e) => {
      e.preventDefault();
      selectContact(sessionId, contact.id, contact.name, input, resultsContainer);
    });
    resultsContainer.appendChild(item);
  });

  if (resultsContainer.children.length > 0) {
    resultsContainer.classList.add("active");
  } else {
    resultsContainer.classList.remove("active");
  }
}

function selectContact(sessionId, contactId, contactName, input, resultsContainer) {
  input.value = contactName;
  input.dataset.currentId = contactId;
  resultsContainer.classList.remove("active");
  if (contactId === "0" || contactId === 0) {
    input.classList.add("unassigned-role");
  } else {
    input.classList.remove("unassigned-role");
  }
  assignRole(sessionId, contactId, input);
}

function shouldSkipRefresh() {
  // 1. Any autocomplete input is focused or autocomplete dropdown is active
  const focusedInput = document.querySelector(".admin-assign-input:focus");
  const activeDropdown = document.querySelector(".autocomplete-results.active");
  if (focusedInput || activeDropdown) {
    return true;
  }

  // 2. Modals are open
  const speechDetailModal = document.getElementById("speechDetailModal");
  const waitlistDetailModal = document.getElementById("waitlistDetailModal");
  if (
    (speechDetailModal && speechDetailModal.style.display === "flex") ||
    (waitlistDetailModal && waitlistDetailModal.style.display === "flex")
  ) {
    return true;
  }

  return false;
}

function pollBookingState() {
  if (document.hidden || shouldSkipRefresh()) {
    return;
  }

  fetch(`/booking/${selectedMeetingId}/hash`)
    .then((response) => response.json())
    .then((data) => {
      if (data.success && data.hash && data.hash !== currentBookingHash) {
        // State has changed! Fetch updated HTML fragment
        fetch(`/booking/${selectedMeetingId}/tables_html`)
          .then((res) => res.text())
          .then((html) => {
            // Double check protection before swapping
            if (shouldSkipRefresh()) return;

            const container = document.getElementById("booking-tables-container");
            if (container) {
              // Map of new owner/waitlist state per session_id
              const newStates = {};
              const tempDiv = document.createElement("div");
              tempDiv.innerHTML = html;

              tempDiv.querySelectorAll("tr[data-session-id]").forEach((row) => {
                const sid = row.dataset.sessionId;
                if (!sid) return;

                let stateStr = "";
                const adminInput = row.querySelector(".admin-assign-input");
                if (adminInput) {
                  stateStr += adminInput.value + "|" + adminInput.dataset.currentId;
                } else {
                  const ownerDisplay = row.querySelector(".owner-display");
                  if (ownerDisplay) {
                    stateStr += ownerDisplay.textContent.trim();
                  }
                }

                row.querySelectorAll(".waitlist-avatar").forEach((w) => {
                  stateStr += "|" + (w.dataset.name || "") + "|" + (w.dataset.userId || "");
                });

                newStates[sid] = stateStr;
              });

              // Collect session_ids whose state changed
              const changedSessionIds = [];
              container.querySelectorAll("tr[data-session-id]").forEach((row) => {
                const sid = row.dataset.sessionId;
                if (!sid) return;

                let oldStateStr = "";
                const adminInput = row.querySelector(".admin-assign-input");
                if (adminInput) {
                  oldStateStr += adminInput.value + "|" + adminInput.dataset.currentId;
                } else {
                  const ownerDisplay = row.querySelector(".owner-display");
                  if (ownerDisplay) {
                    oldStateStr += ownerDisplay.textContent.trim();
                  }
                }

                row.querySelectorAll(".waitlist-avatar").forEach((w) => {
                  oldStateStr += "|" + (w.dataset.name || "") + "|" + (w.dataset.userId || "");
                });

                if (newStates[sid] && newStates[sid] !== oldStateStr) {
                  changedSessionIds.push(sid);
                }
              });

              // Perform DOM Swap
              container.innerHTML = html;
              currentBookingHash = data.hash;

              // Rebind listeners
              if (isAdminView) {
                initializeAdminAutocomplete();
              }
              initializeAccordions();

              // Trigger pulse glow animation on changed rows
              changedSessionIds.forEach((sid) => {
                const row = container.querySelector(`tr[data-session-id="${sid}"]:not(.recommendation-row)`);
                if (row) {
                  row.classList.add("row-pulse-glow");
                  row.addEventListener("animationend", () => {
                    row.classList.remove("row-pulse-glow");
                  }, { once: true });
                }
              });
            }
          })
          .catch((err) => console.error("Error fetching tables HTML:", err));
      }
    })
    .catch((err) => console.error("Error polling booking hash:", err));
}


function resetRole(btn, sessionId) {
  const row = btn.closest('tr');
  const input = row.querySelector('.admin-assign-input');

  if (!input) {
    console.error("Input not found for reset button", { sessionId });
    return;
  }

  if (!input.dataset.currentId || input.dataset.currentId === "0") {
    // Check for multi-owner inputs
    const multiInputs = row.querySelectorAll('.admin-assign-input');
    if (multiInputs.length > 0) {
      // If any input has a value, proceed with unassign
      const hasAssigned = Array.from(multiInputs).some(inp => inp.dataset.currentId && inp.dataset.currentId !== "0");
      if (!hasAssigned) return;
    } else {
      return; // Already unassigned
    }
  }

  // To unassign ALL owners, we pass contactId=0 and no previousValue/previousId
  // The backend handle 'assign' with contact_id=0 as "clear all" if no previous_contact_id is sent.
  assignRole(sessionId, 0, null);
}

function bookOrCancelRole(sessionId, action, roleLabel) {
  if (action === 'book') {
    const row = document.querySelector(`tr[data-session-id="${sessionId}"]`);
    const isValidForProject = row && row.dataset.validForProject === 'true';

    if (isValidForProject) {
      openSpeechDetailModal(sessionId, action, roleLabel);
      return;
    }
  }

  executeBookingAction(sessionId, action, roleLabel);
}

function executeBookingAction(sessionId, action, roleLabel, projectId = null, title = null, pathway = null) {
  const payload = {
    session_id: sessionId,
    action: action,
    role: roleLabel
  };

  if (projectId) payload.project_id = projectId;
  if (title) payload.title = title;
  if (pathway) payload.pathway = pathway;

  fetch("/booking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        window.location.reload(true);
      } else {
        alert("Error: " + data.message);
      }
    })
    .catch((error) => {
      console.error("executeBookingAction error:", error);
      alert("An error occurred. Please try again.");
      window.location.reload(true);
    });
}


function populatePathwayDropdownInSpeechModal() {
  const pathwaySelect = document.getElementById('speech_pathway');
  if (!pathwaySelect) return;
  
  pathwaySelect.innerHTML = '<option value="">Select Pathway</option>';
  
  if (typeof groupedPathways !== 'undefined' && groupedPathways) {
    for (const [groupLabel, items] of Object.entries(groupedPathways)) {
      const optgroup = document.createElement('optgroup');
      optgroup.label = groupLabel;
      items.forEach(item => {
        const value = typeof item === 'object' ? item.name : item;
        const text = typeof item === 'object' ? item.name : item;
        optgroup.appendChild(new Option(text, value));
      });
      pathwaySelect.appendChild(optgroup);
    }
  }
}

function updateSpeechProjectDropdownOptions(selectedProjectId = null) {
  const projectSelect = document.getElementById('speech_project_id');
  const pathwaySelect = document.getElementById('speech_pathway');
  const roleLabelInput = document.getElementById('speech-role-label');
  if (!projectSelect || !pathwaySelect) return;

  projectSelect.innerHTML = '<option value="">Select Project</option>';

  const pathwayName = pathwaySelect.value;
  if (!pathwayName) {
    return;
  }

  const pathwayAbbr = typeof pathwayMap !== 'undefined' ? pathwayMap[pathwayName] : null;
  if (!pathwayAbbr) {
    return;
  }

  // Find selected role's allowed project formats or IDs
  const roleLabel = roleLabelInput ? roleLabelInput.value : '';
  const roleProjectMapping = {
    'Prepared Speaker': { formats: ['Prepared Speech', 'Presentation'] },
    'Keynote Speaker': { ids: [51] },
    'Topicsmaster': { ids: [10] },
    'Individual Evaluator': { ids: [4, 5, 6] },
    'Speech Evaluator': { ids: [4, 5, 6] },
    'Evaluator': { ids: [4, 5, 6] },
    'Meeting Manager': { formats: ['Meeting Manager'] },
    'Moderator': { ids: [57] },
    'Panelist': { ids: [57] }
  };

  let normalizedRole = roleLabel.trim().replace(/\s+\d+$/, '');
  const mapping = roleProjectMapping[normalizedRole];

  // Find all projects that belong to this pathway and match role formats/IDs
  const pathwayProjects = [];
  if (typeof allProjects !== 'undefined') {
    allProjects.forEach(proj => {
      if (proj.path_codes && proj.path_codes[pathwayAbbr]) {
        // Filter strictly if mapping matches
        if (mapping) {
          if (mapping.ids && !mapping.ids.includes(proj.id)) {
            return;
          }
          if (mapping.formats && (!proj.Format || !mapping.formats.includes(proj.Format))) {
            return;
          }
        }
        const meta = proj.path_codes[pathwayAbbr];
        pathwayProjects.push({
          id: proj.id,
          name: proj.Project_Name,
          level: meta.level || 1,
          code: `${pathwayAbbr}${meta.code}`,
          is_completed: proj.is_completed || false,
          format: proj.Duration_Min && proj.Duration_Max ? `${proj.Duration_Min}-${proj.Duration_Max} Min` : ''
        });
      }
    });
  }

  // Group projects by level
  const projectsByLevel = {};
  pathwayProjects.forEach(p => {
    if (!projectsByLevel[p.level]) {
      projectsByLevel[p.level] = [];
    }
    projectsByLevel[p.level].push(p);
  });

  // Sort projects within each level by code
  Object.keys(projectsByLevel).forEach(level => {
    projectsByLevel[level].sort((a, b) => {
      if (a.code && b.code) {
        return a.code.localeCompare(b.code, undefined, { numeric: true, sensitivity: 'base' });
      }
      return 0;
    });
  });

  // Populate projects dropdown
  const sortedLevels = Object.keys(projectsByLevel).sort((a, b) => a - b);
  sortedLevels.forEach(level => {
    const optgroup = document.createElement('optgroup');
    optgroup.label = `Level ${level}`;

    projectsByLevel[level].forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.innerText = p.is_completed ? `✓ ${p.name}` : p.name;
      if (p.is_completed) {
        opt.classList.add('project-completed');
      }
      opt.dataset.format = p.format;
      opt.dataset.code = p.code;
      optgroup.appendChild(opt);
    });

    projectSelect.appendChild(optgroup);
  });

  if (selectedProjectId) {
    projectSelect.value = selectedProjectId;
  }
}

function openSpeechDetailModal(sessionId, action, roleLabel) {
  const modal = document.getElementById('speechDetailModal');
  const form = document.getElementById('speechDetailForm');
  const titleGroup = document.getElementById('speech-title-group');
  const titleInput = document.getElementById('speech_title');
  const projectSelect = document.getElementById('speech_project_id');
  const pathwaySelect = document.getElementById('speech_pathway');
  const pathwayGroup = document.getElementById('speech-pathway-group');

  document.getElementById('speech-session-id').value = sessionId;
  document.getElementById('speech-action').value = action;
  document.getElementById('speech-role-label').value = roleLabel;

  // Reset form
  form.reset();

  // Populate pathways dropdown list
  populatePathwayDropdownInSpeechModal();

  // Project checkbox setup: checked for Prepared Speaker, unchecked for others by default
  const projectChk = document.getElementById('speech_is_project');
  const projectGroup = document.getElementById('speech-project-group');
  if (projectChk) {
    const isPreparedSpeaker = (roleLabel === 'Prepared Speaker');
    projectChk.checked = isPreparedSpeaker;

    if (pathwaySelect && typeof workingPath !== 'undefined' && workingPath) {
      pathwaySelect.value = workingPath;
    }

    if (isPreparedSpeaker) {
      if (pathwayGroup) pathwayGroup.style.display = 'block';
      if (pathwaySelect) pathwaySelect.required = true;
      if (projectGroup) projectGroup.style.display = 'block';
      if (projectSelect) projectSelect.required = true;
      updateSpeechProjectDropdownOptions();
    } else {
      if (pathwayGroup) pathwayGroup.style.display = 'none';
      if (pathwaySelect) {
        pathwaySelect.required = false;
        pathwaySelect.value = '';
      }
      if (projectGroup) projectGroup.style.display = 'none';
      if (projectSelect) {
        projectSelect.required = false;
        projectSelect.value = '';
      }
    }
  }

  // Conditionally show title field
  const rolesWithTitles = ['Prepared Speaker', 'Keynote Speaker'];
  if (rolesWithTitles.includes(roleLabel)) {
    titleGroup.style.display = 'block';
    titleInput.required = true;
  } else {
    titleGroup.style.display = 'none';
    titleInput.required = false;
  }

  modal.style.display = 'flex';
}

/**
 * Shows the waitlist detail modal with planner information.
 * @param {HTMLElement} element - The waitlist avatar element.
 */
function showWaitlistDetails(element) {
  const modal = document.getElementById('waitlistDetailModal');
  const name = element.dataset.name;
  const projectName = element.dataset.projectName;
  const projectCode = element.dataset.projectCode;
  const title = element.dataset.title;
  const notes = element.dataset.notes;
  const userId = element.dataset.userId;

  document.getElementById('waitlist-person-name').textContent = name;

  const projectContainer = document.getElementById('waitlist-project-container');
  if (projectName || projectCode) {
    projectContainer.style.display = 'block';
    document.getElementById('waitlist-project-code').textContent = projectCode;
    document.getElementById('waitlist-project-code').style.display = projectCode ? 'inline-block' : 'none';
    document.getElementById('waitlist-project-name').textContent = projectName;
  } else {
    projectContainer.style.display = 'none';
  }

  const titleContainer = document.getElementById('waitlist-title-container');
  if (title) {
    titleContainer.style.display = 'block';
    document.getElementById('waitlist-speech-title').textContent = title;
  } else {
    titleContainer.style.display = 'none';
  }

  const notesContainer = document.getElementById('waitlist-notes-container');
  if (notes) {
    notesContainer.style.display = 'block';
    document.getElementById('waitlist-notes').textContent = notes;
  } else {
    notesContainer.style.display = 'none';
  }

  // Handle Message button
  const messageBtn = document.getElementById('waitlist-message-btn');
  // Only show if contact has a user account AND is not the current user
  if (userId && String(userId) !== String(currentUserId)) {
    messageBtn.style.display = 'inline-flex';
    messageBtn.dataset.userId = userId;
    messageBtn.dataset.userName = name;
    messageBtn.dataset.projectCode = projectCode || '';
    messageBtn.dataset.projectName = projectName || '';
    messageBtn.title = `Send message to ${name}`;
  } else {
    messageBtn.style.display = 'none';
  }

  modal.style.display = 'flex';
}

function sendWaitlistMessage() {
  const btn = document.getElementById('waitlist-message-btn');
  const userId = btn.dataset.userId;
  const userName = btn.dataset.userName;
  const projectCode = btn.dataset.projectCode;
  const projectName = btn.dataset.projectName;

  if (userId) {
    let subject = '[Booking]';
    if (projectCode || projectName) {
      subject += ' ' + `${projectCode} ${projectName}`.trim();
    }
    window.location.href = `/messages?recipient_id=${userId}&recipient_name=${encodeURIComponent(userName)}&subject=${encodeURIComponent(subject)}`;
  }
}

function closeWaitlistDetailModal() {
  document.getElementById('waitlistDetailModal').style.display = 'none';
}

function closeSpeechDetailModal() {
  document.getElementById('speechDetailModal').style.display = 'none';
}

// Handle speech detail form submission
document.addEventListener('DOMContentLoaded', () => {
  const speechForm = document.getElementById('speechDetailForm');
  if (speechForm) {
    speechForm.addEventListener('submit', function (e) {
      e.preventDefault();
      const sessionId = document.getElementById('speech-session-id').value;
      const action = document.getElementById('speech-action').value;
      const roleLabel = document.getElementById('speech-role-label').value;
      const isProjectChk = document.getElementById('speech_is_project');
      const isProject = isProjectChk ? isProjectChk.checked : true;
      const pathway = isProject ? document.getElementById('speech_pathway').value : null;
      const projectId = isProject ? document.getElementById('speech_project_id').value : null;
      const title = document.getElementById('speech_title').value;

      closeSpeechDetailModal();
      executeBookingAction(sessionId, action, roleLabel, projectId, title, pathway);
    });
  }

  const speechIsProject = document.getElementById('speech_is_project');
  if (speechIsProject) {
    speechIsProject.addEventListener('change', function () {
      const projectGroup = document.getElementById('speech-project-group');
      const projectSelect = document.getElementById('speech_project_id');
      const pathwayGroup = document.getElementById('speech-pathway-group');
      const pathwaySelect = document.getElementById('speech_pathway');
      if (projectGroup && projectSelect && pathwayGroup && pathwaySelect) {
        if (this.checked) {
          pathwayGroup.style.display = 'block';
          pathwaySelect.required = true;
          if (typeof workingPath !== 'undefined' && workingPath) {
            pathwaySelect.value = workingPath;
          }
          projectGroup.style.display = 'block';
          projectSelect.required = true;
          updateSpeechProjectDropdownOptions();
        } else {
          pathwayGroup.style.display = 'none';
          pathwaySelect.required = false;
          pathwaySelect.value = '';
          projectGroup.style.display = 'none';
          projectSelect.required = false;
          projectSelect.value = '';
        }
      }
    });
  }

  const speechPathway = document.getElementById('speech_pathway');
  if (speechPathway) {
    speechPathway.addEventListener('change', function () {
      updateSpeechProjectDropdownOptions();
    });
  }
});


function removeOwner(sessionId, ownerId) {
  fetch("/booking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      action: "remove_owner",
      contact_id: ownerId,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        window.location.reload(true);
      } else {
        alert("Error: " + data.message);
      }
    })
    .catch((error) => {
      console.error("removeOwner error:", error);
      alert("An error occurred. Please try again.");
      window.location.reload(true);
    });
}

function removeWaitlist(sessionId, contactId) {
  fetch("/booking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      action: "remove_waitlist",
      contact_id: contactId,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        window.location.reload(true);
      } else {
        alert("Error: " + data.message);
      }
    })
    .catch((error) => {
      console.error("removeWaitlist error:", error);
      alert("An error occurred. Please try again.");
      window.location.reload(true);
    });
}

function assignRole(sessionId, contactId, selectElement) {
  // For shared roles, we need to know which owner to replace
  const previousContactId = selectElement ? selectElement.dataset.previousId : null;

  fetch("/booking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      action: "assign",
      contact_id: contactId,
      previous_contact_id: previousContactId,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        if (contactId === 0 || contactId === "0") {
          window.location.reload(true);
        } else if (data.updated_sessions) {
          data.updated_sessions.forEach(session => {
            updateSessionRow(session);
          });
        } else {
          window.location.reload(true);
        }
      } else {
        showFlashMessage(data.message, "error", selectElement); // Display message inline if possible

        // Revert the input if provided
        if (selectElement && selectElement.dataset.previousValue !== undefined) {
          selectElement.value = selectElement.dataset.previousValue;
          selectElement.dataset.currentId = selectElement.dataset.previousId;
          if (selectElement.dataset.currentId === "0") {
            selectElement.classList.add("unassigned-role");
          } else {
            selectElement.classList.remove("unassigned-role");
          }
        }
      }
    });
}


function updateSessionRow(sessionData) {
  const row = document.querySelector(`tr[data-session-id="${sessionData.session_id}"]`);
  if (!row) return;

  // Update Input (if present - Admin Book / Assign View)
  const inputElement = row.querySelector(".admin-assign-input");
  if (inputElement) {
    inputElement.value = sessionData.owner_name || '';
    inputElement.dataset.currentId = sessionData.owner_id !== null ? sessionData.owner_id : "0";
    if (sessionData.owner_id && sessionData.owner_id != 0) {
      inputElement.classList.remove('unassigned-role');
    } else {
      inputElement.classList.add('unassigned-role');
    }
  }

  // Update Text Display (if present)
  const ownerDisplay = row.querySelector('.owner-display');
  if (ownerDisplay) {
    ownerDisplay.textContent = sessionData.owner_name || 'Unassigned';
  }

  // Update Avatar
  const avatarContainer = row.querySelector('.role-avatar:not(.waitlist-avatar)');
  if (avatarContainer) {
    if (sessionData.owner_name) {
      avatarContainer.title = sessionData.owner_name;
    } else {
      avatarContainer.removeAttribute('title');
    }

    if (sessionData.owner_avatar_url) {
      let avatarPath = sessionData.owner_avatar_url;
      if (avatarPath.indexOf('/') === -1) {
        const root = (typeof avatarRootDir !== 'undefined') ? avatarRootDir : 'avatars';
        avatarPath = `${root}/${avatarPath}`;
      }
      avatarContainer.innerHTML = `<img src="/static/${avatarPath}" alt="User Avatar">`;
    } else {
      avatarContainer.innerHTML = '<img src="/static/default_avatar.jpg" alt="Default Avatar">';
    }
  }

  // Clear icons if unassigned
  if (!sessionData.owner_id || sessionData.owner_id == 0) {
    const roleActions = row.querySelector(".role-cell-actions");
    if (roleActions) {
      roleActions.innerHTML = "";
    }
  }

  // Update Admin Recommendation Badges Visibility
  const recommendationRow = document.querySelector(`.recommendation-row[data-session-id="${sessionData.session_id}"]`);
  if (recommendationRow) {
    if (sessionData.owner_id && sessionData.owner_id != 0) {
      recommendationRow.style.display = "none";
    } else {
      recommendationRow.style.display = "";
    }
  }
}


function leaveWaitlist(sessionId, roleLabel) {
  fetch("/booking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      action: "leave_waitlist",
      role: roleLabel
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        window.location.reload(true);
      } else {
        alert("Error: " + data.message);
      }
    })
    .catch((error) => {
      console.error("leaveWaitlist error:", error);
      alert("An error occurred. Please try again.");
      window.location.reload(true);
    });
}


function approveWaitlist(sessionId, roleLabel) {
  fetch("/booking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      action: "approve_waitlist",
      role: roleLabel
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        window.location.reload(true);
      } else {
        alert("Error: " + data.message);
      }
    })
    .catch((error) => {
      console.error("approveWaitlist error:", error);
      alert("An error occurred. Please try again.");
      window.location.reload(true);
    });
}


function joinWaitlist(sessionId, roleLabel) {
  const row = document.querySelector(`tr[data-session-id="${sessionId}"]`);
  const isValidForProject = row && row.dataset.validForProject === 'true';

  if (isValidForProject) {
    openSpeechDetailModal(sessionId, "join_waitlist", roleLabel);
    return;
  }

  executeBookingAction(sessionId, "join_waitlist", roleLabel);
}


function syncTally() {
  if (!confirm("Are you sure you want to sync the roles for this meeting to Tally?")) {
    return;
  }

  if (!selectedMeetingId) {
    alert("No meeting selected.");
    return;
  }

  fetch(`/agenda/sync_tally/${selectedMeetingId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        showFlashMessage("Synced successfully!", "success");
      } else {
        showFlashMessage("Error: " + data.message, "error");
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      showFlashMessage("An error occurred.", "error");
    });
}

function showFlashMessage(message, category, targetElement) {
  let container;
  let isRowInjection = false;

  if (targetElement) {
    const row = targetElement.closest('tr');
    if (row && row.parentNode) {
      // We will create a new row to show the message below the current row
      isRowInjection = true;

      // Check if a flash row already exists below this row
      const nextRow = row.nextElementSibling;
      if (nextRow && nextRow.classList.contains('flash-message-row')) {
        nextRow.remove(); // Remove existing to replace/refresh
      }

      // Create the new row structure
      const flashRow = document.createElement('tr');
      flashRow.className = 'flash-message-row';
      const colCount = row.children.length;

      const cell = document.createElement('td');
      cell.colSpan = colCount;
      cell.style.padding = '0'; // Let the div handle padding
      cell.style.border = 'none';

      container = cell; // We will append the div to this cell
      flashRow.appendChild(cell);

      // Insert after current row
      row.parentNode.insertBefore(flashRow, row.nextSibling);

      // Auto-remove row after 5 seconds
      setTimeout(() => {
        if (flashRow && flashRow.parentElement) {
          flashRow.remove();
        }
      }, 5000);
    }
  }

  // Fallback to global container
  if (!container) {
    container = document.querySelector(".flash-messages");
    if (!container) {
      container = document.createElement("div");
      container.className = "flash-messages";
      document.body.appendChild(container);
    }
  }

  // Create the message element
  const flashDiv = document.createElement("div");
  flashDiv.className = `flash ${category}`;

  if (isRowInjection) {
    flashDiv.style.margin = "5px 10px"; // Add some spacing within the row
    flashDiv.style.borderRadius = "4px";
  }

  flashDiv.innerHTML = `${message}<span class="close-flash" onclick="this.closest('${isRowInjection ? 'tr' : '.flash'}').remove();">&times;</span>`;

  // Append to container
  container.appendChild(flashDiv);

  // Auto-remove (global only, row handled above)
  if (!isRowInjection) {
    setTimeout(() => {
      if (flashDiv.parentElement) {
        flashDiv.remove();
      }
    }, 5000);
  }
}

function addTableTopicsSpeech(meetingId) {
  fetch(`/booking/${meetingId}/add_table_topics_speech`, {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      window.location.reload(true);
    } else {
      alert("Error: " + data.message);
    }
  })
  .catch(error => {
    console.error("addTableTopicsSpeech error:", error);
    alert("An error occurred while adding the Table Topics speech session.");
  });
}