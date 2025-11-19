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
      Presentation: setupPresentationModal,
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
  modalElements.speechTitleLabel.textContent = "Evaluation for:";

  const evalProjects = allProjects
    .filter((p) => [4, 5, 6].includes(p.ID))
    .sort((a, b) => a.ID - b.ID);
  populateDropdown(modalElements.projectSelectDropdown, evalProjects, {
    defaultOption: "-- Select Evaluation Project --",
    valueField: "ID",
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

  const pathways = Object.keys(pathwayMap).map((name) => ({ name }));
  populateDropdown(modalElements.pathwaySelectDropdown, pathways, {
    defaultOption: "-- Select Pathway --",
    valueField: "name",
    textField: "name",
  });
  modalElements.pathwaySelectDropdown.value =
    logData.pathway || workingPath || "";

  modalElements.pathwayGroup.style.display = "none";
  modalElements.projectSelectDropdown.style.display = "none";

  modalElements.isProjectChk.onchange = (e) => {
    modalElements.pathwayGroup.style.display = "none";
    if (!e.target.checked) {
      modalElements.pathwaySelectDropdown.value = "";
    }
  };
}

function setupPresentationModal(logData) {
  modalElements.title.textContent = "Edit Presentation Details";
  modalElements.labelPathway.textContent = "Education Series:";
  modalElements.labelProject.textContent = "Presentation Title:";
  modalElements.pathwaySelect.required = true;
  modalElements.standardSelection.style.display = "block";
  modalElements.pathwayGenericRow.style.display = "block";
  modalElements.projectSelectGroup.style.display = "block";

  const currentPres = allPresentations.find((p) => p.id == logData.Project_ID);
  const currentSeries = currentPres ? currentPres.series : "";

  populateDropdown(
    modalElements.pathwaySelect,
    presentationSeries.map((s) => ({ series: s })),
    {
      defaultOption: "-- Select Series --",
      valueField: "series",
      textField: "series",
    }
  );
  modalElements.pathwaySelect.value = currentSeries;
  updatePresentationOptions(
    logData.Project_ID,
    currentPres ? currentPres.level : null
  );
}

function setupSpeechModal(logData, { workingPath, nextProject }) {
  modalElements.title.textContent = "Edit Speech Details";

  modalElements.standardSelection.style.display = "block";
  modalElements.pathwaySelect.required = true;
  modalElements.pathwayGenericRow.style.display = "block";
  modalElements.levelSelectGroup.style.display = "block";
  modalElements.projectSelectGroup.style.display = "block";
  modalElements.genericCheckbox.style.display = "block";

  const pathways = Object.keys(pathwayMap).map((name) => ({ name }));
  populateDropdown(modalElements.pathwaySelect, pathways, {
    defaultOption: "-- Select Pathway --",
    valueField: "name",
    textField: "name",
  });

  let {
    pathway: pathwayToSelect,
    level: levelToSelect,
    Project_ID: projectToSelect,
  } = logData;
  if (projectToSelect == "60") {
    modalElements.genericCheckbox.checked = true;
    toggleGeneric(true);
    modalElements.pathwaySelect.value = pathwayToSelect || "";
  } else {
    modalElements.genericCheckbox.checked = false;
    toggleGeneric(false);
    if (window.location.pathname.includes("/agenda")) {
      if (!logData.Project_ID && nextProject) {
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
            const codeAttr = `Code_${codeSuffix}`;
            const foundProject = allProjects.find(
              (p) => p[codeAttr] === nextProject.substring(2)
            );
            if (foundProject) projectToSelect = foundProject.ID;
          }
        } catch (e) {
          /* Parsing failed */
        }
      } else if (workingPath) {
        pathwayToSelect = workingPath;
      }
    }
    modalElements.pathwaySelect.value = pathwayToSelect || "";
    modalElements.levelSelect.value = levelToSelect || "";
    updateProjectOptions(projectToSelect);
  }
}

// --- Dynamic Dropdown Helpers ---

function updateDynamicOptions() {
  if (modalElements.sessionType.value === "Presentation") {
    updatePresentationOptions();
  } else {
    updateProjectOptions();
  }
}

function updateProjectOptions(selectedProjectId = null) {
  const { pathwaySelect, levelSelect, projectSelect } = modalElements;
  const codeSuffix = pathwayMap[pathwaySelect.value];
  projectSelect.innerHTML = '<option value="">-- Select a Project --</option>';
  if (!codeSuffix || !levelSelect.value) return;

  const codeAttr = `Code_${codeSuffix}`;
  const filteredProjects = allProjects
    .filter(
      (p) => p[codeAttr] && p[codeAttr].startsWith(levelSelect.value + ".")
    )
    .sort((a, b) => (a[codeAttr] < b[codeAttr] ? -1 : 1));

  filteredProjects.forEach((p) => {
    projectSelect.add(new Option(`${p[codeAttr]} - ${p.Project_Name}`, p.ID));
  });
  if (selectedProjectId) projectSelect.value = selectedProjectId;
}

function updatePresentationOptions(
  selectedPresentationId = null,
  level = null
) {
  const { pathwaySelect: seriesSelect, projectSelect: presentationSelect } =
    modalElements;
  presentationSelect.innerHTML =
    '<option value="">-- Select Presentation --</option>';
  if (!seriesSelect.value) return;

  const filtered = allPresentations
    .filter(
      (p) =>
        p.series === seriesSelect.value && (level === null || p.level == level)
    )
    .sort((a, b) =>
      a.level !== b.level ? a.level - b.level : a.title.localeCompare(b.title)
    );

  filtered.forEach((p) => {
    presentationSelect.add(new Option(`L${p.level} - ${p.title}`, p.id));
  });
  if (selectedPresentationId) presentationSelect.value = selectedPresentationId;
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
      payload.session_title = speechTitle.value;
      payload.project_id = projectSelect.value || null;
      break;
    default: // Pathway Speech
      const isGeneric = genericCheckbox.checked;
      payload.session_title = speechTitle.value;
      payload.project_id = isGeneric ? "60" : projectSelect.value || "60";
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
      const proj = allProjects.find((p) => p.ID == updateResult.project_id);
      let projPurpose = proj ? proj.Purpose : "";

      viewTitleCell.innerHTML = ""; // Clear
      const wrapper = document.createElement("div");
      wrapper.className = "speech-tooltip-wrapper";
      wrapper.textContent = `${title} ${code}`.trim();

      if (updateResult.project_id && updateResult.project_id != "60") {
        const tooltip = document.createElement("div");
        tooltip.className = "speech-tooltip";
        tooltip.innerHTML = `<span class="tooltip-title">${
          projName || ""
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

  const viewTitleCell = agendaRow.querySelector(
    ".non-edit-mode-cell:nth-child(2)"
  );
  if (viewTitleCell) {
    let title =
      sessionType === "Pathway Speech" && updateResult.project_id != "60"
        ? `"${updateResult.session_title.replace(/"/g, "")}"`
        : updateResult.session_title;
    let code = updateResult.project_code
      ? `(${updateResult.project_code})`
      : "";
    if (updateResult.project_id == "60") code = "(TM1.0)";

    let projName = updateResult.project_name;
    let projPurpose = "";
    if (sessionType === "Presentation") {
      const pres = allPresentations.find(
        (p) => p.id == updateResult.project_id
      );
      projName = pres ? pres.title : updateResult.session_title;
    } else {
      const proj = allProjects.find((p) => p.ID == updateResult.project_id);
      projPurpose = proj ? proj.Purpose : "";
    }

    viewTitleCell.innerHTML = "";
    const wrapper = document.createElement("div");
    wrapper.className = "speech-tooltip-wrapper";
    wrapper.textContent = `${title} ${code}`.trim();
    if (updateResult.project_id && updateResult.project_id != "60") {
      const tooltip = document.createElement("div");
      tooltip.className = "speech-tooltip";
      tooltip.innerHTML = `<span class="tooltip-title">${
        projName || ""
      }</span><span class="tooltip-purpose">${projPurpose || ""}</span>`;
      wrapper.appendChild(tooltip);
    }
    viewTitleCell.appendChild(wrapper);
    updateMediaLink(viewTitleCell);
  }

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
    if (updateResult.project_id == "60") code = "(TM1.0)";
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
