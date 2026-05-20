// static/js/speech_modal.js

// --- Globals (from HTML) ---
// These are assumed to be defined in the HTML <script> tags:
// - allProjects, pathwayMap

// --- DOM Elements Cache ---
const modalElements = {
  modal: document.getElementById("speechEditModal"),
  form: document.getElementById("speechEditForm"),
  title: document.querySelector("#speechEditModal h2"),
  logId: document.getElementById("edit-log-id"),
  sessionType: document.getElementById("edit-session-type-title"),
  speechTitle: document.getElementById("edit-speech-title"),
  speechTitleLabel: document.querySelector('#edit-speech-title-label'),
  sessionOwner: document.getElementById("edit-session-owner"),
  credential: document.getElementById("edit-credential"),
  mediaUrl: document.getElementById("edit-speech-media-url"),

  standardSelection: document.getElementById("standard-selection"),

  projectModeFields: document.getElementById("project-mode-fields"),

  pathwayGenericRow: document.getElementById("pathway-generic-row"),
  pathwaySelect: document.getElementById("edit-pathway"),
  isProjectCheckbox: document.getElementById("edit-is-project"),
  levelSelectGroup: document.getElementById("level-select-group"),
  levelSelect: document.getElementById("edit-level"),
  projectSelectGroup: document.getElementById("project-select-group"),
  projectSelect: document.getElementById("edit-project"),
  labelPathway: document.getElementById("label-pathway-series"),
  labelLevel: document.getElementById("label-level"),
  labelProject: document.getElementById("label-project-presentation"),
  projectGroup: document.getElementById("project-group"),
  isProjectChk: document.getElementById("is-project-chk"),
  projectSelectDropdown: document.getElementById("project-select-dropdown"),
  pathwayGroup: document.getElementById("pathway-group"),
  pathwaySelectDropdown: document.getElementById("pathway-select-dropdown"),
  levelGroup: document.getElementById("level-group"),
  levelSelectDropdown: document.getElementById("level-select-dropdown"),
  speechModeFields: document.getElementById("speech-mode-fields"),
  roleModeFields: document.getElementById("role-mode-fields"),
  roleNameDisplay: document.getElementById("role-name-display"),
  roleOwnersScroll: document.getElementById("role-owners-scroll"),
};

// --- Utility Functions ---

/**
 * Generic utility to populate a <select> dropdown.
 */
function populateDropdown(
  dropdown,
  items,
  { defaultOption, valueField, textField }
) {
  dropdown.innerHTML = `<option value="">${defaultOption}</option>`;
  items.forEach((item) => {
    dropdown.add(new Option(item[textField], item[valueField]));
  });
}

/**
 * Populates a <select> with <optgroup>s.
 * @param {HTMLSelectElement} dropdown
 * @param {Object} groupedData - { "Type": ["Item1", "Item2"] }
 */
function populateGroupedDropdown(dropdown, groupedData, { defaultOption }) {
  dropdown.innerHTML = `<option value="">${defaultOption}</option>`;
  for (const [groupLabel, items] of Object.entries(groupedData)) {
    const optgroup = document.createElement("optgroup");
    optgroup.label = groupLabel;
    items.forEach((item) => {
      // Handle both simple string lists and object lists (if needed in future)
      const value = typeof item === 'object' ? item.name : item;
      const text = typeof item === 'object' ? item.name : item;
      optgroup.appendChild(new Option(text, value));
    });
    dropdown.appendChild(optgroup);
  }
}

/**
 * Toggles the "Generic Speech" mode, hiding/showing pathway fields.
 */
function toggleGeneric(isGeneric) {
  const {
    pathwayGenericRow,
    levelSelectGroup,
    projectSelectGroup,
    pathwaySelect,
    levelSelect,
    projectSelect,
  } = modalElements;
  const display = isGeneric ? "none" : "block";
  if (pathwayGenericRow) pathwayGenericRow.style.display = "block";
  if (levelSelectGroup) levelSelectGroup.style.display = display;
  if (projectSelectGroup) projectSelectGroup.style.display = display;
  if (pathwaySelect) pathwaySelect.disabled = false;
  if (levelSelect) levelSelect.disabled = isGeneric;
  if (projectSelect) projectSelect.disabled = isGeneric;

  if (isGeneric) {
    if (levelSelect) levelSelect.value = "";
    if (projectSelect) {
      projectSelect.value = "";
      projectSelect.innerHTML = '<option value="">-- Select --</option>';
    }
  }
}
// --- Main Public Functions ---

/**
 * Main entry point to open the speech or role edit details modal.
 */
async function openEditDetailsModal(
  logId,
  workingPath = null,
  sessionTypeTitle = null,
  nextProject = null
) {
  try {
    const response = await fetch(`/speech_log/details/${logId}`);
    const data = await response.json();
    if (!data.success) throw new Error(data.message || "Unknown error");

    const passedSessionType =
      data.log.session_type_title ||
      sessionTypeTitle ||
      document.querySelector(`tr[data-id="${logId}"]`)?.dataset.sessionTypeTitle;
    const currentSessionType = passedSessionType || "Pathway Speech";

    // Setup basic details
    resetModal(data.log, currentSessionType);

    const sessionType = currentSessionType;
    const isPreparedSpeech = sessionType === "Prepared Speech" || sessionType === "Pathway Speech" || sessionType === "Presentation";
    const isProjectRole = ["Evaluation", "Panel Discussion", "Table Topics", "Keynote Speech"].includes(sessionType);

    const row = document.querySelector(`tr[data-id="${logId}"]`);

    if (!isPreparedSpeech && !isProjectRole && row) {
      // Toggle wrappers: show role mode, hide speech mode
      modalElements.speechModeFields.style.display = "none";
      modalElements.roleModeFields.style.display = "block";

      const roleName = row.dataset.role || "N/A";
      modalElements.roleNameDisplay.textContent = roleName;

      // Get all owner IDs for this row
      let ownerIds = [];
      try {
        ownerIds = JSON.parse(row.dataset.ownerIds || "[]");
      } catch (e) {
        const singleId = row.dataset.ownerId;
        if (singleId) ownerIds = [singleId];
      }
      if (ownerIds.length === 0) {
        const singleId = row.dataset.ownerId;
        if (singleId) ownerIds = [singleId];
      }

      // Parse existing per-owner targets if available
      let existingOwnerTargets = {};
      try {
        existingOwnerTargets = JSON.parse(row.dataset.ownerTargets || "{}");
      } catch (e) { /* ignore */ }

      // Build the scrollable owner cards
      const scrollContainer = modalElements.roleOwnersScroll;
      scrollContainer.innerHTML = "";

      // Helper: build a pathway <select> with grouped options
      function buildPathwaySelect() {
        const sel = document.createElement("select");
        sel.className = "role-card-pathway";
        sel.innerHTML = '<option value="">-- Select Pathway --</option>';
        if (typeof groupedPathways !== "undefined") {
          for (const [groupLabel, items] of Object.entries(groupedPathways)) {
            const optgroup = document.createElement("optgroup");
            optgroup.label = groupLabel;
            items.forEach((item) => {
              const value = typeof item === "object" ? item.name : item;
              const text = typeof item === "object" ? item.name : item;
              optgroup.appendChild(new Option(text, value));
            });
            sel.appendChild(optgroup);
          }
        } else if (typeof pathwayMap !== "undefined") {
          Object.keys(pathwayMap).forEach((name) => {
            sel.appendChild(new Option(name, name));
          });
        }
        return sel;
      }

      // Helper: build a level <select>
      function buildLevelSelect() {
        const sel = document.createElement("select");
        sel.className = "role-card-level";
        sel.innerHTML = '<option value="">-- Select Level --</option>';
        for (let i = 1; i <= 5; i++) {
          sel.appendChild(new Option(`Level ${i}`, i));
        }
        return sel;
      }

      // Helper: determine default pathway + level for an owner
      function getOwnerDefaults(ownerId) {
        let pathway = "";
        let level = "";

        // 1. Check per-owner saved target first
        const savedTarget = existingOwnerTargets[ownerId];
        if (savedTarget && savedTarget.pathway) {
          pathway = savedTarget.pathway;
          level = savedTarget.level || "1";
        }

        // 2. Fallback to row pathway
        if (!pathway) {
          pathway = (row.dataset.pathway || "").trim();
        }

        // 3. Fallback to contact data
        const contactsList = window.allContacts || [];
        const contact = contactsList.find((c) => c.id == ownerId);
        if (contact) {
          if (!pathway) {
            if (contact.Type === "Guest" || !contact.Current_Path) {
              pathway = "Non Pathway";
            } else {
              pathway = contact.Current_Path;
            }
          }
          if (!level) {
            const levelMatch = (contact.Credentials || "").match(/\d+/);
            if (levelMatch) {
              level = Math.min(parseInt(levelMatch[0], 10) + 1, 5).toString();
            } else {
              level = "1";
            }
          }
        }

        if (!pathway) pathway = "Non Pathway";
        if (pathway === "Non Pathway") {
          level = "";
        } else if (!level) {
          level = "1";
        }

        return { pathway, level };
      }

      // Create one card per owner
      const contactsList = window.allContacts || [];
      ownerIds.forEach((ownerId) => {
        const contact = contactsList.find((c) => c.id == ownerId);
        const ownerName = contact ? contact.Name : `Owner #${ownerId}`;
        const defaults = getOwnerDefaults(ownerId);

        const card = document.createElement("div");
        card.className = "role-owner-card";
        card.dataset.ownerId = ownerId;

        // Owner name header
        const nameDiv = document.createElement("div");
        nameDiv.className = "card-owner-name";
        nameDiv.textContent = ownerName;
        card.appendChild(nameDiv);

        // Pathway
        const pathGroup = document.createElement("div");
        pathGroup.className = "form-group";
        const pathLabel = document.createElement("label");
        pathLabel.textContent = "Pathway";
        const pathSelect = buildPathwaySelect();
        pathSelect.value = defaults.pathway;
        pathGroup.appendChild(pathLabel);
        pathGroup.appendChild(pathSelect);
        card.appendChild(pathGroup);

        // Level
        const levelGroup = document.createElement("div");
        levelGroup.className = "form-group";
        const levelLabel = document.createElement("label");
        levelLabel.textContent = "Level";
        const levelSelect = buildLevelSelect();
        levelSelect.value = defaults.level;
        levelGroup.appendChild(levelLabel);
        levelGroup.appendChild(levelSelect);
        card.appendChild(levelGroup);

        scrollContainer.appendChild(card);
      });

      // If no owners, show a placeholder card
      if (ownerIds.length === 0) {
        const defaults = getOwnerDefaults(null);
        const card = document.createElement("div");
        card.className = "role-owner-card";
        card.dataset.ownerId = "";

        const nameDiv = document.createElement("div");
        nameDiv.className = "card-owner-name";
        nameDiv.textContent = "No Owner Assigned";
        card.appendChild(nameDiv);

        const pathGroup = document.createElement("div");
        pathGroup.className = "form-group";
        const pathLabel = document.createElement("label");
        pathLabel.textContent = "Pathway";
        const pathSelect = buildPathwaySelect();
        pathSelect.value = defaults.pathway;
        pathGroup.appendChild(pathLabel);
        pathGroup.appendChild(pathSelect);
        card.appendChild(pathGroup);

        const levelGroup = document.createElement("div");
        levelGroup.className = "form-group";
        const levelLabel = document.createElement("label");
        levelLabel.textContent = "Level";
        const levelSelect = buildLevelSelect();
        levelSelect.value = defaults.level;
        levelGroup.appendChild(levelLabel);
        levelGroup.appendChild(levelSelect);
        card.appendChild(levelGroup);

        scrollContainer.appendChild(card);
      }
    } else {
      // Toggle wrappers: show speech mode, hide role mode
      modalElements.speechModeFields.style.display = "block";
      modalElements.roleModeFields.style.display = "none";

      const setupFunctions = {
        "Evaluation": (log, opts) => SpeechModalSetupManager.setupProjectRole(log, {
          ...opts,
          projectIds: ProjectID.EVALUATION_PROJECTS,
          defaultOption: "-- Select Evaluation Project --",
          speechTitleLabelText: "Evaluator for:"
        }),
        "Panel Discussion": (log, opts) => SpeechModalSetupManager.setupProjectRole(log, {
          ...opts,
          projectIds: [ProjectID.MODERATOR_PROJECT],
          defaultOption: "-- Select Panel Discussion Project --"
        }),
        "Table Topics": (log, opts) => SpeechModalSetupManager.setupProjectRole(log, {
          ...opts,
          projectIds: [ProjectID.TOPICSMASTER_PROJECT],
          defaultOption: "-- Select Table Topics Project --"
        }),
        "Keynote Speech": (log, opts) => SpeechModalSetupManager.setupProjectRole(log, {
          ...opts,
          projectIds: [ProjectID.KEYNOTE_SPEAKER_PROJECT],
          defaultOption: "-- Select Keynote Speech Project --"
        }),
        "Pathway Speech": (log, opts) => SpeechModalSetupManager.setupSpeech(log, opts),
        "Prepared Speech": (log, opts) => SpeechModalSetupManager.setupSpeech(log, opts),
        "Presentation": (log, opts) => SpeechModalSetupManager.setupSpeech(log, opts),
        default: (log, opts) => SpeechModalSetupManager.setupRole(log, opts),
      };
      const setupFunction =
        setupFunctions[currentSessionType] || setupFunctions.default;
      setupFunction(data.log, {
        workingPath,
        nextProject,
        sessionType: currentSessionType,
      });
    }

    modalElements.modal.style.display = "flex";
  } catch (error) {
    console.error("Fetch error:", error);
    alert(`An error occurred while fetching details: ${error.message}`);
  }
}

/**
 * Closes the edit details modal.
 */
function closeEditDetailsModal() {
  modalElements.modal.style.display = "none";
}

/**
 * Main save function. Handles both role and speech updates.
 */
async function saveEditDetailsChanges(event) {
  event.preventDefault();
  const logId = modalElements.logId.value;

  const isRoleMode = modalElements.roleModeFields.style.display === "block";

  if (isRoleMode) {
    const submitBtn = modalElements.form.querySelector('button[type="submit"]');
    const originalText = submitBtn ? submitBtn.textContent : "Save";
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Saving...";
    }

    const cards = document.querySelectorAll("#role-owners-scroll .role-owner-card");
    const ownerTargets = {};
    let primaryPathway = "";

    cards.forEach((card, idx) => {
      const ownerId = card.dataset.ownerId;
      const pathwayName = card.querySelector(".role-card-pathway")?.value || "";
      const levelVal = card.querySelector(".role-card-level")?.value || "";

      if (ownerId) {
        ownerTargets[ownerId] = { pathway: pathwayName, level: levelVal };
      }

      if (idx === 0) {
        primaryPathway = pathwayName;
      }
    });

    try {
      const response = await fetch(`/speech_log/update/${logId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owner_targets: ownerTargets })
      });
      const data = await response.json();
      if (data.success) {
        const row = document.querySelector(`tr[data-id="${logId}"]`);
        if (row) {
          row.dataset.ownerTargets = JSON.stringify(ownerTargets);
          row.dataset.pathway = primaryPathway;
        }

        const affectedLogIds = [logId];
        if (data.affected_log_ids && data.affected_log_ids.length > 0) {
          affectedLogIds.push(...data.affected_log_ids);
        }

        affectedLogIds.forEach(id => {
          const affectedRow = document.querySelector(`tr[data-id="${id}"]`);
          if (affectedRow) {
            affectedRow.dataset.ownerTargets = JSON.stringify(ownerTargets);
            affectedRow.dataset.pathway = primaryPathway;
          }
        });

        closeEditDetailsModal();
      } else {
        alert("Error saving: " + (data.message || "Unknown error"));
      }
    } catch (error) {
      console.error("Save error:", error);
      alert("An error occurred while saving: " + error.message);
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
      }
    }
  } else {
    // Speech/Project mode save
    const payload = buildSavePayload();

    try {
      const response = await fetch(`/speech_log/update/${logId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const updateResult = await response.json();
      if (updateResult.success) {
        handleSaveSuccess(updateResult, payload);
      } else {
        throw new Error(updateResult.message || "Unknown error");
      }
    } catch (error) {
      console.error("Save error:", error);
      alert(`An error occurred while saving changes: ${error.message}`);
    }
  }
}

// Expose functions globally for backward-compatibility with other HTML/templates
window.openSpeechEditModal = openEditDetailsModal;
window.closeSpeechEditModal = closeEditDetailsModal;
window.saveSpeechChanges = saveEditDetailsChanges;


// --- Setup Helpers ---

function resetModal(logData, sessionType) {
  toggleGeneric(false);
  modalElements.form.reset();
  modalElements.logId.value = logData.id;
  modalElements.title.textContent = "Edit Details";
  modalElements.sessionOwner.value = logData.owner_name || "";
  modalElements.speechTitle.value = logData.Session_Title || "";
  modalElements.credential.value = logData.credential || "";
  modalElements.sessionType.value = sessionType;
  modalElements.mediaUrl.value = logData.Media_URL || "";
  modalElements.speechTitle.disabled = false;
  modalElements.credential.disabled = false;
  
  // Reset visibility of Speech Title form group (might be hidden by role modal)
  modalElements.speechTitle.closest('.form-group').style.display = 'block';

  if (modalElements.standardSelection)
    modalElements.standardSelection.style.display = "none";

  const optionalElements = [
    modalElements.pathwayGenericRow,
    modalElements.levelSelectGroup,
    modalElements.projectSelectGroup,
    modalElements.projectGroup,
    modalElements.pathwayGroup,
    modalElements.projectModeFields,
  ];
  optionalElements.forEach((el) => {
    if (el) el.style.display = "none";
  });

  modalElements.speechTitleLabel.textContent = "Session Title:";
  modalElements.labelPathway.textContent = "Pathway:";
  modalElements.labelLevel.textContent = "Level:";
  modalElements.labelProject.textContent = "Project:";
  modalElements.pathwaySelect.required = false;
}

const SpeechModalSetupManager = {
  populatePathwayDropdown(dropdown) {
    if (typeof groupedPathways !== 'undefined' && groupedPathways) {
      populateGroupedDropdown(dropdown, groupedPathways, {
        defaultOption: "-- Select Pathway --"
      });
    } else {
      const pathways = Object.keys(pathwayMap).map((name) => ({ name }));
      populateDropdown(dropdown, pathways, {
        defaultOption: "-- Select Pathway --",
        valueField: "name",
        textField: "name",
      });
    }
  },

  setupRole(logData, { sessionType, workingPath }) {
    modalElements.title.textContent = "Edit Details";
    modalElements.speechTitle.disabled = true;
    modalElements.standardSelection.style.display = "none";
    modalElements.projectGroup.style.display = "none";
    modalElements.speechTitle.closest('.form-group').style.display = 'none';

    // Show pathway dropdown for all roles (unified pathway handling)
    modalElements.pathwayGroup.style.display = "flex";
    if (modalElements.levelGroup) {
      modalElements.levelGroup.style.display = "block";
    }
    SpeechModalSetupManager.populatePathwayDropdown(modalElements.pathwaySelectDropdown);
    // Priority: saved log target pathway > workingPath > "Non Pathway"
    const defaultPath = logData.pathway || workingPath || "Non Pathway";
    modalElements.pathwaySelectDropdown.value = defaultPath;
    
    // Priority: saved log target level > empty
    const defaultLevel = logData.level || "";
    modalElements.levelSelectDropdown.value = defaultLevel;
  },

  setupProjectRole(logData, { sessionType, workingPath, projectIds, defaultOption, speechTitleLabelText }) {
    modalElements.title.textContent = "Edit Details";
    if (speechTitleLabelText) {
      modalElements.speechTitleLabel.textContent = speechTitleLabelText;
    }
    if (sessionType !== "Evaluation") {
      modalElements.speechTitle.disabled = true;
    }
    modalElements.projectGroup.style.display = "block";
    modalElements.pathwayGroup.style.display = "flex";
    if (modalElements.levelGroup) {
      modalElements.levelGroup.style.display = "block";
    }

    const targetProjectIds = Array.isArray(projectIds)
      ? projectIds.map(Number)
      : [Number(projectIds)];

    const projectsList = allProjects
      .filter((p) => targetProjectIds.includes(Number(p.id)))
      .sort((a, b) => a.id - b.id);

    populateDropdown(modalElements.projectSelectDropdown, projectsList, {
      defaultOption: defaultOption,
      valueField: "id",
      textField: "Project_Name"
    });

    if (projectsList.length === 1) {
      modalElements.projectSelectDropdown.value = projectsList[0].id;
    }

    this.populatePathwayDropdown(modalElements.pathwaySelectDropdown);

    // Priority: saved log target pathway > owner's working path > "Non Pathway"
    const defaultPath = logData.pathway || workingPath || "Non Pathway";
    modalElements.pathwaySelectDropdown.value = defaultPath;
    
    const defaultLevel = logData.level || "";
    if (modalElements.levelSelectDropdown) {
        modalElements.levelSelectDropdown.value = defaultLevel;
    }

    const isProject = logData.Project_ID && targetProjectIds.includes(Number(logData.Project_ID));
    modalElements.isProjectChk.checked = isProject;

    const toggleFields = (isChecked) => {
      modalElements.projectModeFields.style.display = isChecked ? "block" : "none";
      if (modalElements.projectSelectDropdown && sessionType !== "Evaluation") {
        modalElements.projectSelectDropdown.style.display = isChecked ? "block" : "none";
      }
      if (!isChecked) {
        modalElements.projectSelectDropdown.value = "";
        if (sessionType === "Evaluation") {
          modalElements.speechTitle.value = logData.Session_Title || "";
        }
      } else {
        if (projectsList.length === 1) {
          modalElements.projectSelectDropdown.value = projectsList[0].id;
        } else if (isProject) {
          modalElements.projectSelectDropdown.value = logData.Project_ID;
        }
      }
    };

    modalElements.isProjectChk.onchange = (e) => toggleFields(e.target.checked);
    toggleFields(isProject);
  },

  setupSpeech(logData, { workingPath, nextProject, sessionType }) {
    modalElements.title.textContent = "Edit Details";
    modalElements.standardSelection.style.display = "block";
    modalElements.pathwaySelect.required = true;
    modalElements.pathwayGenericRow.style.display = "block";
    modalElements.levelSelectGroup.style.display = "block";
    modalElements.projectSelectGroup.style.display = "block";

    modalElements.labelPathway.textContent = "Pathway:";
    modalElements.labelProject.textContent = "Project:";
    modalElements.labelLevel.textContent = "Level:";

    this.populatePathwayDropdown(modalElements.pathwaySelect);

    let pathwayToSelect = logData.pathway;
    let levelToSelect = logData.level;
    let projectToSelect = logData.Project_ID;
    const projectCode = logData.project_code || nextProject;

    // REQUIREMENT: Populate path/level/project based on project_code if available and non-generic
    if (projectCode && !['TM1.0', '', 'null'].includes(projectCode)) {
      const codeMatch = projectCode.match(/^([A-Z]+)(\d+(?:\.\d+)?)$/);
      if (codeMatch) {
        const abbr = codeMatch[1];
        const codePart = codeMatch[2];

        const pathwayName = Object.keys(pathwayMap).find(name => pathwayMap[name] === abbr);
        if (pathwayName) {
          pathwayToSelect = pathwayName;
          
          if (projectToSelect && projectToSelect != ProjectID.GENERIC) {
            // Already have a specific project ID, look up its level for this pathway
            const foundProject = allProjects.find(p => Number(p.id) === Number(projectToSelect));
            if (foundProject && foundProject.path_codes[abbr]) {
              levelToSelect = foundProject.path_codes[abbr].level;
            }
          } else {
            // Find first matching project by pathway and code part
            const foundProject = allProjects.find(p => p.path_codes[abbr] && String(p.path_codes[abbr].code) === codePart);
            if (foundProject) {
              projectToSelect = foundProject.id;
              levelToSelect = foundProject.path_codes[abbr].level;
            }
          }
        }
      }
    } else if (!pathwayToSelect && workingPath) {
      pathwayToSelect = workingPath;
    }

    // Fallback: derive level if pathway and project are set but level is not
    if (pathwayToSelect && pathwayToSelect !== "Non Pathway" && projectToSelect && projectToSelect != ProjectID.GENERIC && !levelToSelect) {
      const abbr = pathwayMap[pathwayToSelect];
      if (abbr) {
        const foundProject = allProjects.find(p => Number(p.id) === Number(projectToSelect));
        if (foundProject && foundProject.path_codes[abbr]) {
          levelToSelect = foundProject.path_codes[abbr].level;
        }
      }
    }

    if (!pathwayToSelect) {
      pathwayToSelect = "Non Pathway";
    }

    // Ensure level value is string type to match dropdown options
    if (levelToSelect !== undefined && levelToSelect !== null) {
      levelToSelect = String(levelToSelect);
    }

    const isGeneric = projectToSelect == ProjectID.GENERIC;
    modalElements.isProjectCheckbox.checked = !isGeneric;
    toggleGeneric(isGeneric);

    modalElements.pathwaySelect.value = pathwayToSelect || "";

    if (!isGeneric) {
      updateLevelOptions();
      modalElements.levelSelect.value = levelToSelect || "";
      updateProjectOptions(projectToSelect);
    }
  }
};

// --- Dynamic Dropdown Helpers ---

function updateDynamicOptions() {
  updateLevelOptions();
  updateProjectOptions();
}

function updateLevelOptions() {
  const { pathwaySelect, levelSelect } = modalElements;
  const pathwayName = pathwaySelect.value;
  const currentLevel = levelSelect.value;

  if (!pathwayName) return;

  const codeSuffix = (typeof pathwayMap !== 'undefined' ? pathwayMap[pathwayName] : null);

  if (!codeSuffix) return;

  // Find all unique levels for this pathway
  const availableLevels = new Set();

  allProjects.forEach(p => {
    const info = p.path_codes[codeSuffix];
    if (info && (info.level || info.level === 0 || info.level === '0')) {
      availableLevels.add(info.level);
    }
  });

  // Sort levels
  const sortedLevels = Array.from(availableLevels).sort((a, b) => a - b);

  // Rebuild Level Options
  // Keep "All Levels" or empty option if that's desired? 
  // Usually for editing a speech, we want to force valid selection.
  // But let's keep a default prompt.
  levelSelect.innerHTML = '<option value="">-- Select Level --</option>';

  sortedLevels.forEach(lvl => {
    levelSelect.add(new Option(`Level ${lvl}`, lvl));
  });

  // Restore selection if valid, otherwise clear
  if (availableLevels.has(parseInt(currentLevel))) {
    levelSelect.value = currentLevel;
  } else if (availableLevels.has(currentLevel)) { // Check string match
    levelSelect.value = currentLevel;
  } else {
    levelSelect.value = "";
  }
}

function updateProjectOptions(selectedProjectId = null) {
  const { pathwaySelect, levelSelect, projectSelect } = modalElements;
  const pathwayName = pathwaySelect.value;
  const level = levelSelect.value;
  // If we know it's a presentation (e.g. from session type context, or checking value), behavior is same
  // except maybe validation. But `pathwayMap` handles translation of name to 'code'.
  // For presentations, we might need to handle series names if they aren't in pathwayMap or handle them generically.
  // Actually, 'pathwayMap' is critical here. It maps "Presentation Mastery" -> "PM".
  // For series like "Successful Club Series", do we have a mapping?
  // If not, we need a way to look it up or rely on logic that presentation series are treated as pathways.
  // Backend passes "Successful Club Series" as pathway name. 
  // We need to ensure `pathwayMap` or similar logical structure supports it.

  // Assuming the `groupedPathways` or `pathwayMap` on page load contains Series now?
  // The backend `pathway_library` route includes series if they are in `Pathway` table.

  // Let's assume standard logic works if `pathwayMap` or equivalent is updated or valid.
  // If `codeSuffix` is undefined, we might fail to find keys.

  const codeSuffix = (typeof pathwayMap !== 'undefined' ? pathwayMap[pathwayName] : null);

  /* console.log("Debug updateProjectOptions:", { pathwayName, codeSuffix, level }); */

  projectSelect.innerHTML = '<option value="">-- Select a Project --</option>';
  if (!codeSuffix) {
    // console.warn("No code suffix found for pathway:", pathwayName);
    return;
  }

  const filteredProjects = allProjects
    .filter(p => {
      // Backend now sends path_codes as objects: { code: '...', level: 5 }
      const pathInfo = p.path_codes[codeSuffix];
      if (!pathInfo) return false;

      const { code, level: projectLevel } = pathInfo;

      if (level) {
        // Strict, explicit level check from DB (as requested)
        // Ensure string comparison to handle any type mismatches
        return String(projectLevel) === String(level);
      }
      return true;
    })
    .sort((a, b) => {
      const infoA = a.path_codes[codeSuffix];
      const infoB = b.path_codes[codeSuffix];

      // Sort by Level first
      if (infoA.level !== infoB.level) {
        return infoA.level - infoB.level;
      }

      // Then Numeric Code if possible
      const fA = parseFloat(infoA.code);
      const fB = parseFloat(infoB.code);
      if (!isNaN(fA) && !isNaN(fB)) {
        return fA - fB;
      }
      // Fallback to string sort
      return infoA.code.localeCompare(infoB.code);
    });

  filteredProjects.forEach((p) => {
    const info = p.path_codes[codeSuffix];
    // Display: "Code - Name"
    projectSelect.add(new Option(`${info.code} - ${p.Project_Name}`, p.id));
  });

  if (selectedProjectId) projectSelect.value = selectedProjectId;
}

// --- Save Helpers ---

function buildSavePayload() {
  const {
    sessionType,
    mediaUrl,
    credential,
    isProjectChk,
    speechTitle,
    projectSelect,
    pathwaySelect,
    projectSelectDropdown,
    pathwaySelectDropdown,
  } = modalElements;
  const payload = {
    session_type_title: sessionType.value,
    media_url: mediaUrl.value || null,
    credential: credential.value || null,
  };
  const isProject = isProjectChk?.checked || false;

  // Helper to read the level dropdown (shared across all session types that use pathwayGroup)
  const levelDropdownValue = modalElements.levelSelectDropdown
    ? modalElements.levelSelectDropdown.value || null
    : null;

  switch (sessionType.value) {
    case "Panel Discussion":
      payload.project_id = isProject ? ProjectID.MODERATOR_PROJECT : null;
      payload.pathway = pathwaySelectDropdown.value || "";
      payload.level = levelDropdownValue;
      break;
    case "Table Topics":
      payload.project_id = isProject ? ProjectID.TOPICSMASTER_PROJECT : null;
      payload.pathway = pathwaySelectDropdown.value || "";
      payload.level = levelDropdownValue;
      break;
    case "Keynote Speech":
      payload.project_id = isProject ? ProjectID.KEYNOTE_SPEAKER_PROJECT : null;
      payload.pathway = pathwaySelectDropdown.value || "";
      payload.level = levelDropdownValue;
      break;
    case "Evaluation":
      payload.project_id =
        isProject && projectSelectDropdown.value
          ? projectSelectDropdown.value
          : null;
      payload.pathway = pathwaySelectDropdown.value || "";
      payload.level = levelDropdownValue;
      break;
    default:
      // Include speech-specific fields if the standard selection UI is visible
      if (modalElements.standardSelection && modalElements.standardSelection.style.display !== "none") {
        const isGeneric = !modalElements.isProjectCheckbox.checked;
        payload.session_title = speechTitle.value;
        payload.project_id = isGeneric ? ProjectID.GENERIC : projectSelect.value || ProjectID.GENERIC;
        payload.pathway = pathwaySelect.value;
        payload.level = modalElements.levelSelect.value || null;
      } else {
        // For roles (GE, Timer, etc.), send the pathway and level from the pathway-group dropdowns
        payload.pathway = pathwaySelectDropdown.value || "";
        payload.level = levelDropdownValue;
      }
      break;
  }
  return payload;
}

function handleSaveSuccess(updateResult, payload) {
  const logId = modalElements.logId.value;
  
  const logsToUpdate = [logId];
  if (updateResult.affected_log_ids && updateResult.affected_log_ids.length > 0) {
    logsToUpdate.push(...updateResult.affected_log_ids);
  }

  logsToUpdate.forEach(id => {
    if (window.location.pathname.includes("/agenda")) {
      updateAgendaRow(id, updateResult, payload);
    } else {
      const card = document.getElementById(`log-card-${id}`);
      if (card) {
        updateSpeechLogCard(id, updateResult, payload);
      }
    }
  });

  closeSpeechEditModal();
}

// --- UI Update Functions ---

function updateAgendaRow(logId, updateResult, payload) {
  const agendaRow = document.querySelector(`tr[data-id="${logId}"]`);
  if (!agendaRow) return;

  const { session_type_title: sessionType, media_url: newMediaUrl } = payload;

  const updateMediaLink = (cell) => {
    let mediaLink = cell.querySelector(".media-play-btn");
    const wrapper = cell.querySelector(".speech-tooltip-wrapper") || cell;
    if (newMediaUrl) {
      if (!mediaLink) {
        mediaLink = document.createElement("a");
        mediaLink.target = "_blank";
        mediaLink.className = "icon-btn media-play-btn";
        mediaLink.title = "Watch Media";
        mediaLink.innerHTML = ' <i class="fas fa-play-circle"></i>';
        wrapper.appendChild(mediaLink);
      }
      mediaLink.href = newMediaUrl;
    } else if (mediaLink) {
      mediaLink.remove();
    }
  };

  // Always sync pathway on the row dataset (unified for all role types)
  if (updateResult.pathway !== undefined) {
    agendaRow.dataset.pathway = updateResult.pathway || "";
  }

  if (sessionType === "Individual Evaluator") {
    const titleCell = agendaRow.querySelector(
      ".non-edit-mode-cell:nth-child(2)"
    );
    if (titleCell) updateMediaLink(titleCell);
    return;
  }

  if (sessionType === "Table Topics" || sessionType === "Panel Discussion") {
    agendaRow.dataset.projectId = updateResult.project_id || "";
    const viewTitleCell = agendaRow.querySelector(
      ".non-edit-mode-cell:nth-child(2)"
    );
    if (viewTitleCell) {
      let title =
        sessionType === "Table Topics"
          ? "Table Topics Master"
          : sessionType === "Keynote Speech"
            ? "Keynote Speech"
            : "Panel Discussion";
      let code = updateResult.project_code
        ? `(${updateResult.project_code})`
        : "";

      let projName = updateResult.project_name;
      const proj = allProjects.find((p) => p.id == updateResult.project_id);
      let projPurpose = proj ? proj.Purpose : "";

      viewTitleCell.innerHTML = ""; // Clear
      const wrapper = document.createElement("div");
      wrapper.className = "speech-tooltip-wrapper";
      wrapper.textContent = `${title} ${code}`.trim();

      if (updateResult.project_id && updateResult.project_id != ProjectID.GENERIC) {
        const tooltip = document.createElement("div");
        tooltip.className = "speech-tooltip";
        tooltip.innerHTML = `<span class="tooltip-title">${projName || ""
          }</span><span class="tooltip-purpose">${projPurpose || ""}</span>`;
        wrapper.appendChild(tooltip);
      }
      viewTitleCell.appendChild(wrapper);
      updateMediaLink(viewTitleCell);
    }
    return;
  }

  agendaRow.dataset.projectId = updateResult.project_id || "";
  agendaRow.dataset.sessionTitle = updateResult.session_title;
  agendaRow.dataset.durationMin = updateResult.duration_min || "";
  agendaRow.dataset.durationMax = updateResult.duration_max || "";
  agendaRow.dataset.pathway = updateResult.pathway || "";

  // Update Session Title Input/Span
  const editTitleCell = agendaRow.querySelector(
    'td[data-field="Session_Title"]'
  );
  if (editTitleCell) {
    const ctl = editTitleCell.querySelector("input, select, span");
    if (ctl)
      ctl.tagName === "SPAN"
        ? (ctl.textContent = updateResult.session_title)
        : (ctl.value = updateResult.session_title);
  }

  // Update Duration Inputs (Fixes overwrite issue)
  const durationMinInput = agendaRow.querySelector(
    '[data-field="Duration_Min"] input'
  );
  if (durationMinInput) {
    durationMinInput.value = updateResult.duration_min || "";
  }

  const durationMaxInput = agendaRow.querySelector(
    '[data-field="Duration_Max"] input'
  );
  if (durationMaxInput) {
    durationMaxInput.value = updateResult.duration_max || "";
  }

  // Update View Mode Title
  const viewTitleCell = agendaRow.querySelector(
    ".non-edit-mode-cell:nth-child(2)"
  );
  if (viewTitleCell) {
    let title =
      (sessionType === "Pathway Speech" || sessionType === "Prepared Speech") && updateResult.project_id != ProjectID.GENERIC
        ? `"${updateResult.session_title.replace(/"/g, "")}"`
        : updateResult.session_title;
    let code = updateResult.project_code
      ? `(${updateResult.project_code})`
      : "";
    if (updateResult.project_id == ProjectID.GENERIC) code = "(TM1.0)";

    let projName = updateResult.project_name;
    let projPurpose = "";
    const proj = allProjects.find((p) => p.id == updateResult.project_id);
    if (proj) {
      projName = proj.Project_Name;
      projPurpose = proj.Purpose;
    }

    viewTitleCell.innerHTML = "";
    const wrapper = document.createElement("div");
    wrapper.className = "speech-tooltip-wrapper";
    wrapper.textContent = `${title} ${code}`.trim();
    if (updateResult.project_id && updateResult.project_id != ProjectID.GENERIC) {
      const tooltip = document.createElement("div");
      tooltip.className = "speech-tooltip";
      tooltip.innerHTML = `<span class="tooltip-title">${projName || ""
        }</span><span class="tooltip-purpose">${projPurpose || ""}</span>`;
      wrapper.appendChild(tooltip);
    }
    viewTitleCell.appendChild(wrapper);
    updateMediaLink(viewTitleCell);
  }

  // Update View Mode Duration Cell
  const durationCell = agendaRow.querySelector(
    ".non-edit-mode-cell:nth-child(4)"
  );
  if (durationCell) {
    const { duration_min: min, duration_max: max } = updateResult;
    durationCell.textContent =
      min && max && min != max ? `${min}'-${max}'` : max ? `${max}'` : "";
  }
}

function updateSpeechLogCard(logId, updateResult, payload) {
  const card = document.getElementById(`log-card-${logId}`);
  if (!card) return;

  if (payload.session_type_title !== "Individual Evaluator") {
    // Helper to safely set text content if element exists
    const setSafeText = (selector, text) => {
      const el = card.querySelector(selector);
      if (el) el.innerText = text;
    };

    setSafeText(".speech-title", `"${updateResult.session_title.replace(/"/g, "")}"`);
    setSafeText(".role-title", updateResult.session_title.replace(/"/g, "") + (updateResult.project_code ? ` (${updateResult.project_code})` : ""));
    
    setSafeText(".project-name", updateResult.project_name || "N/A");
    
    let code = updateResult.project_code
      ? `(${updateResult.project_code})`
      : "";
    if (updateResult.project_id == ProjectID.GENERIC) code = "(TM1.0)";
    
    setSafeText(".project-code", code);
    setSafeText(".pathway-info", updateResult.pathway || "N/A");
  }

  let mediaLink = card.querySelector(".btn-play");
  const newMediaUrl = payload.media_url;
  if (newMediaUrl) {
    if (!mediaLink) {
      mediaLink = document.createElement("a");
      mediaLink.href = newMediaUrl;
      mediaLink.target = "_blank";
      mediaLink.className = "icon-btn btn-play";
      mediaLink.title = "Watch Media";
      mediaLink.innerHTML = '<i class="fas fa-play-circle"></i>';
      card.querySelector(".card-actions").prepend(mediaLink);
    }
    mediaLink.href = newMediaUrl;
  } else if (mediaLink) {
    mediaLink.remove();
  }
}

// --- Event Listeners ---
document.addEventListener("DOMContentLoaded", () => {
  modalElements.form.addEventListener("submit", saveSpeechChanges);
  modalElements.pathwaySelect.addEventListener("change", updateDynamicOptions);
  modalElements.levelSelect.addEventListener("change", updateDynamicOptions);
  if (modalElements.isProjectCheckbox) {
    modalElements.isProjectCheckbox.addEventListener("change", (e) =>
      toggleGeneric(!e.target.checked)
    );
  }
});
