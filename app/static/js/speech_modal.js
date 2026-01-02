// static/js/speech_modal.js

// --- Globals (from HTML) ---
// These are assumed to be defined in the HTML <script> tags:
// - allProjects, pathwayMap, allPresentations, presentationSeries

// --- DOM Elements Cache ---
const modalElements = {
  modal: document.getElementById("speechEditModal"),
  form: document.getElementById("speechEditForm"),
  title: document.querySelector("#speechEditModal h1"),
  logId: document.getElementById("edit-log-id"),
  sessionType: document.getElementById("edit-session-type-title"),
  speechTitle: document.getElementById("edit-speech-title"),
  speechTitleLabel: document.querySelector('label[for="edit-speech-title"]'),
  mediaUrl: document.getElementById("edit-speech-media-url"),

  standardSelection: document.getElementById("standard-selection"),

  projectModeFields: document.getElementById("project-mode-fields"),

  pathwayGenericRow: document.getElementById("pathway-generic-row"),
  pathwaySelect: document.getElementById("edit-pathway"),
  genericCheckbox: document.getElementById("edit-is-generic"),
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
    levelSelectGroup,
    projectSelectGroup,
    pathwaySelect,
    levelSelect,
    projectSelect,
  } = modalElements;
  const display = isGeneric ? "none" : "block";
  levelSelectGroup.style.display = display;
  projectSelectGroup.style.display = display;
  pathwaySelect.disabled = isGeneric;
  levelSelect.disabled = isGeneric;
  projectSelect.disabled = isGeneric;

  if (isGeneric) {
    pathwaySelect.value = "";
    levelSelect.value = "";
    projectSelect.value = "";
    projectSelect.innerHTML = '<option value="">-- Select --</option>';
  }
}

// --- Main Public Functions ---

/**
 * Main entry point to open the speech edit modal.
 */
async function openSpeechEditModal(
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
      sessionTypeTitle ||
      document.querySelector(`tr[data-id="${logId}"]`)?.dataset
        .sessionTypeTitle;
    const currentSessionType = passedSessionType || "Pathway Speech";

    resetModal(data.log, currentSessionType);

    const setupFunctions = {
      Evaluation: setupEvaluatorModal,
      "Panel Discussion": setupSpecialProjectModal,
      "Table Topics": setupSpecialProjectModal,
      default: setupSpeechModal,
    };
    const setupFunction =
      setupFunctions[currentSessionType] || setupFunctions.default;
    setupFunction(data.log, {
      workingPath,
      nextProject,
      sessionType: currentSessionType,
    });

    modalElements.modal.style.display = "flex";
  } catch (error) {
    console.error("Fetch error:", error);
    alert(`An error occurred while fetching speech details: ${error.message}`);
  }
}

/**
 * Closes the speech edit modal.
 */
function closeSpeechEditModal() {
  modalElements.modal.style.display = "none";
}

/**
 * Main save function. Builds a payload and sends it.
 */
async function saveSpeechChanges(event) {
  event.preventDefault();
  const logId = modalElements.logId.value;
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

// --- Setup Helpers ---

function resetModal(logData, sessionType) {
  toggleGeneric(false);
  modalElements.form.reset();
  modalElements.logId.value = logData.id;
  modalElements.title.textContent = `Edit ${sessionType} Details`;
  modalElements.speechTitle.value = logData.Session_Title || "";
  modalElements.sessionType.value = sessionType;
  modalElements.mediaUrl.value = logData.Media_URL || "";
  modalElements.speechTitle.disabled = false;

  if (modalElements.standardSelection)
    modalElements.standardSelection.style.display = "none";

  const optionalElements = [
    modalElements.pathwayGenericRow,
    modalElements.levelSelectGroup,
    modalElements.projectSelectGroup,
    modalElements.genericCheckbox,
    modalElements.projectGroup,
    modalElements.pathwayGroup,
  ];
  optionalElements.forEach((el) => {
    if (el) el.style.display = "none";
  });

  modalElements.speechTitleLabel.textContent = "Speech Title:";
  modalElements.labelPathway.textContent = "Pathway:";
  modalElements.labelLevel.textContent = "Level:";
  modalElements.labelProject.textContent = "Project:";
  modalElements.pathwaySelect.required = false;
}

function setupEvaluatorModal(logData) {
  modalElements.projectGroup.style.display = "block";
  modalElements.speechTitleLabel.textContent = "Evaluator for:";

  const evalProjects = allProjects
    .filter((p) => [4, 5, 6].includes(p.id))
    .sort((a, b) => a.id - b.id);
  populateDropdown(modalElements.projectSelectDropdown, evalProjects, {
    defaultOption: "-- Select Evaluation Project --",
    valueField: "id",
    textField: "Project_Name",
  });

  modalElements.isProjectChk.onchange = (e) => {
    modalElements.projectModeFields.style.display = e.target.checked
      ? "block"
      : "none";
    if (!e.target.checked) {
      modalElements.projectSelectDropdown.value = "";
      modalElements.speechTitle.value = logData.agenda_title || "";
    } else {
      // When switching to project mode, keep the existing speech title
      // Do not override with the project name
    }
  };

  const isEvalProject =
    logData.Project_ID && ["4", "5", "6"].includes(String(logData.Project_ID));
  modalElements.isProjectChk.checked = isEvalProject;

  // Show/hide the project mode fields container
  modalElements.projectModeFields.style.display = isEvalProject
    ? "block"
    : "none";

  // Set the project dropdown value if it's an evaluation project
  if (isEvalProject) {
    modalElements.projectSelectDropdown.value = logData.Project_ID;
  }
}

function setupSpecialProjectModal(logData, { sessionType, workingPath }) {
  modalElements.title.textContent = `Edit ${sessionType} Details`;
  modalElements.speechTitle.disabled = true;
  modalElements.projectGroup.style.display = "block";

  const PROJECT_IDS = { "Table Topics": 10, "Panel Discussion": 57 };
  const isProject = logData.Project_ID == PROJECT_IDS[sessionType];
  modalElements.isProjectChk.checked = isProject;

  if (typeof groupedPathways !== 'undefined' && groupedPathways) {
    populateGroupedDropdown(modalElements.pathwaySelectDropdown, groupedPathways, {
      defaultOption: "-- Select Pathway --"
    });
  } else {
    const pathways = Object.keys(pathwayMap).map((name) => ({ name }));
    populateDropdown(modalElements.pathwaySelectDropdown, pathways, {
      defaultOption: "-- Select Pathway --",
      valueField: "name",
      textField: "name",
    });
  }
  modalElements.pathwaySelectDropdown.value =
    logData.pathway || workingPath || "";

  modalElements.pathwayGroup.style.display = isProject ? "block" : "none";
  modalElements.projectSelectDropdown.style.display = "none";

  modalElements.isProjectChk.onchange = (e) => {
    modalElements.pathwayGroup.style.display = e.target.checked ? "block" : "none";
    if (!e.target.checked) {
      modalElements.pathwaySelectDropdown.value = "";
    }
  };
}


function setupSpeechModal(logData, { workingPath, nextProject, sessionType }) {
  modalElements.title.textContent = "Edit Speech Details";

  modalElements.standardSelection.style.display = "block";
  modalElements.pathwaySelect.required = true;
  modalElements.pathwayGenericRow.style.display = "block";
  modalElements.levelSelectGroup.style.display = "block";
  modalElements.projectSelectGroup.style.display = "block";
  modalElements.genericCheckbox.style.display = "block";

  modalElements.labelPathway.textContent = "Pathway:";
  modalElements.labelProject.textContent = "Project:";
  modalElements.labelLevel.textContent = "Level:";


  if (typeof groupedPathways !== 'undefined' && groupedPathways) {
    populateGroupedDropdown(modalElements.pathwaySelect, groupedPathways, {
      defaultOption: "-- Select Pathway --"
    });
  } else {
    const pathways = Object.keys(pathwayMap).map((name) => ({ name }));
    populateDropdown(modalElements.pathwaySelect, pathways, {
      defaultOption: "-- Select Pathway --",
      valueField: "name",
      textField: "name",
    });
  }

  let {
    pathway: pathwayToSelect,
    level: levelToSelect,
    Project_ID: projectToSelect,
  } = logData;

  // Ensure level value is string type to match dropdown options
  if (levelToSelect !== undefined && levelToSelect !== null) {
    levelToSelect = String(levelToSelect);
  }

  if (projectToSelect == GENERIC_PROJECT_ID) {
    modalElements.genericCheckbox.checked = true;
    toggleGeneric(true);
    modalElements.pathwaySelect.value = pathwayToSelect || "";
  } else {
    modalElements.genericCheckbox.checked = false;

    toggleGeneric(false);
    if (!projectToSelect) {
      // Logic for auto-selecting next project for standard speeches
      if (window.location.pathname.includes("/agenda")) {
        if (nextProject) {
          try {
            const [, nextPathAbbr, nextLevel] =
              nextProject.match(/([A-Z]{2})(\d)/);
            const pathwayName = Object.keys(pathwayMap).find(
              (name) => pathwayMap[name] === nextPathAbbr
            );
            if (pathwayName) {
              pathwayToSelect = pathwayName;
              levelToSelect = nextLevel;
              const codeSuffix = pathwayMap[pathwayToSelect];
              const projectCode = nextProject.substring(2);
              const foundProject = allProjects.find(p => p.path_codes[codeSuffix] && p.path_codes[codeSuffix].code === projectCode);
              if (foundProject) projectToSelect = foundProject.id;
            }
          } catch (e) {
            /* Parsing failed */
          }
        } else if (workingPath) {
          pathwayToSelect = workingPath;
        }
      }
    }
    modalElements.pathwaySelect.value = pathwayToSelect || "";
    // Update levels based on selected pathway BEFORE trying to set the level value
    updateLevelOptions();

    // Now set the level if valid
    modalElements.levelSelect.value = levelToSelect || "";

    updateProjectOptions(projectToSelect);
  }
}

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

  const codeSuffix = (typeof pathwayMap !== 'undefined' ? pathwayMap[pathwayName] : null) ||
    (typeof allSeriesInitials !== 'undefined' ? allSeriesInitials[pathwayName] : null);

  if (!codeSuffix) return;

  // Find all unique levels for this pathway
  const availableLevels = new Set();

  allProjects.forEach(p => {
    const info = p.path_codes[codeSuffix];
    if (info && info.level) {
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

  // FIX: Access `allSeriesInitials` if `allSeriesInitials` is available globally, or rely on `pathwayMap`.
  // In `speech_logs_routes`, we pass `series_initials`.
  // We should try `pathwayMap[pathwayName]` OR `allSeriesInitials[pathwayName]`.

  const codeSuffix = (typeof pathwayMap !== 'undefined' ? pathwayMap[pathwayName] : null) ||
    (typeof allSeriesInitials !== 'undefined' ? allSeriesInitials[pathwayName] : null);

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
    isProjectChk,
    speechTitle,
    projectSelect,
    pathwaySelect,
    genericCheckbox,
    projectSelectDropdown,
    pathwaySelectDropdown,
  } = modalElements;
  const payload = {
    session_type_title: sessionType.value,
    media_url: mediaUrl.value || null,
  };
  const isProject = isProjectChk?.checked || false;

  switch (sessionType.value) {
    case "Panel Discussion":
      payload.project_id = isProject ? 57 : null;
      payload.pathway = isProject ? pathwaySelectDropdown.value || "" : null;
      break;
    case "Table Topics":
      payload.project_id = isProject ? 10 : null;
      payload.pathway = isProject ? pathwaySelectDropdown.value || "" : null;
      break;
    case "Evaluation":
      payload.project_id =
        isProject && projectSelectDropdown.value
          ? projectSelectDropdown.value
          : null;
      break;
    case "Presentation":
      // Updated to use standardized fields but explicit session type title handling
      payload.session_title = speechTitle.value;
      payload.project_id = projectSelect.value || null;
      // Also include pathway if set
      payload.pathway = pathwaySelect.value;
      break;
    default: // Pathway Speech
      const isGeneric = genericCheckbox.checked;
      payload.session_title = speechTitle.value;
      payload.project_id = isGeneric ? GENERIC_PROJECT_ID : projectSelect.value || GENERIC_PROJECT_ID;
      payload.pathway = pathwaySelect.value;
      break;
  }
  return payload;
}

function handleSaveSuccess(updateResult, payload) {
  const logId = modalElements.logId.value;
  if (window.location.pathname.includes("/agenda")) {
    updateAgendaRow(logId, updateResult, payload);
  } else {
    updateSpeechLogCard(logId, updateResult, payload);
  }
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

      if (updateResult.project_id && updateResult.project_id != GENERIC_PROJECT_ID) {
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
      sessionType === "Pathway Speech" && updateResult.project_id != GENERIC_PROJECT_ID
        ? `"${updateResult.session_title.replace(/"/g, "")}"`
        : updateResult.session_title;
    let code = updateResult.project_code
      ? `(${updateResult.project_code})`
      : "";
    if (updateResult.project_id == GENERIC_PROJECT_ID) code = "(TM1.0)";

    let projName = updateResult.project_name;
    let projPurpose = "";
    if (sessionType === "Presentation" && updateResult.project_id) {
      // Try finding in allProjects (unified now)
      const proj = allProjects.find((p) => p.id == updateResult.project_id);
      projName = proj ? proj.Project_Name : updateResult.session_title;
      projPurpose = proj ? proj.Purpose : "";
    } else {
      const proj = allProjects.find((p) => p.id == updateResult.project_id);
      projPurpose = proj ? proj.Purpose : "";
    }

    viewTitleCell.innerHTML = "";
    const wrapper = document.createElement("div");
    wrapper.className = "speech-tooltip-wrapper";
    wrapper.textContent = `${title} ${code}`.trim();
    if (updateResult.project_id && updateResult.project_id != GENERIC_PROJECT_ID) {
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
    card.querySelector(
      ".speech-title"
    ).innerText = `"${updateResult.session_title.replace(/"/g, "")}"`;
    card.querySelector(".project-name").innerText =
      updateResult.project_name || "N/A";
    let code = updateResult.project_code
      ? `(${updateResult.project_code})`
      : "";
    if (updateResult.project_id == GENERIC_PROJECT_ID) code = "(TM1.0)";
    card.querySelector(".project-code").innerText = code;
    card.querySelector(".pathway-info").innerText =
      updateResult.pathway || "N/A";
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
  if (modalElements.genericCheckbox) {
    modalElements.genericCheckbox.addEventListener("change", (e) =>
      toggleGeneric(e.target.checked)
    );
  }
});
