// static/js/speech_modal.js

// --- Globals (from HTML) ---
// These are assumed to be defined in the HTML <script> tags:
// - allProjects, pathwayMap, allPresentations, presentationSeries

// --- DOM Elements Cache ---
// Cache all modal DOM elements at once for performance and readability.
const modalElements = {
  modal: document.getElementById("speechEditModal"),
  form: document.getElementById("speechEditForm"),
  title: document.querySelector("#speechEditModal h1"),
  logId: document.getElementById("edit-log-id"),
  sessionType: document.getElementById("edit-session-type-title"),
  speechTitle: document.getElementById("edit-speech-title"),
  mediaUrl: document.getElementById("edit-speech-media-url"),
  pathwayGenericRow: document.getElementById("pathway-generic-row"),
  pathwaySelect: document.getElementById("edit-pathway"),
  levelSelectGroup: document.getElementById("level-select-group"),
  levelSelect: document.getElementById("edit-level"),
  projectSelectGroup: document.getElementById("project-select-group"),
  projectSelect: document.getElementById("edit-project"),
  genericCheckbox: document.getElementById("edit-is-generic"),
  labelPathway: document.getElementById("label-pathway-series"),
  labelLevel: document.getElementById("label-level"),
  labelProject: document.getElementById("label-project-presentation"),
  evalProjectGroup: document.getElementById("eval-project-group"),
  evalIsProjectChk: document.getElementById("eval-is-project-chk"),
  evalProjectSelect: document.getElementById("eval-project-select"),
  ttProjectGroup: document.getElementById("tt-project-group"),
  ttIsProjectChk: document.getElementById("tt-is-project-chk"),
  ttPathwayGroup: document.getElementById("tt-pathway-group"),
  ttPathwaySelect: document.getElementById("tt-pathway-select"),
};

// --- Main Public Functions ---

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

  if (isGeneric) {
    levelSelectGroup.style.display = "none";
    projectSelectGroup.style.display = "none";
    pathwaySelect.disabled = true;
    levelSelect.disabled = true;
    projectSelect.disabled = true;
    pathwaySelect.value = "";
    levelSelect.value = "";
    projectSelect.value = "";
    projectSelect.innerHTML = '<option value="">-- Select --</option>';
  } else {
    levelSelectGroup.style.display = "block";
    projectSelectGroup.style.display = "block";
    pathwaySelect.disabled = false;
    levelSelect.disabled = false;
    projectSelect.disabled = false;
  }
}

/**
 * Main entry point to open the speech edit modal.
 * Fetches log details and delegates to a setup function based on session type.
 */
function openSpeechEditModal(
  logId,
  workingPath = null,
  sessionTypeTitle = null,
  nextProject = null
) {
  // Try to get session type directly if passed from agenda.js
  const passedSessionType =
    sessionTypeTitle ||
    document.querySelector(`tr[data-id="${logId}"]`)?.dataset.sessionTypeTitle;

  fetch(`/speech_log/details/${logId}`)
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        const currentSessionType = passedSessionType || "Pathway Speech";

        // 1. Set common values and reset all fields to a default state
        setCommonModalValues(data.log, currentSessionType);

        // 2. Specialize the modal based on its type
        switch (currentSessionType) {
          case "Evaluation":
            setupEvaluatorModal(data.log);
            break;
          case "Table Topics":
            setupTableTopicsModal(data.log);
            break;
          case "Presentation":
            setupPresentationModal(data.log);
            break;
          default: // "Pathway Speech" or other custom types
            setupPathwayModal(data.log, workingPath, nextProject);
            break;
        }

        // 3. Show the modal
        modalElements.modal.style.display = "flex";
      } else {
        alert(
          "Error fetching speech log details: " +
            (data.message || "Unknown error")
        );
      }
    })
    .catch((error) => {
      console.error("Fetch error:", error);
      alert("An error occurred while fetching speech details.");
    });
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
function saveSpeechChanges(event) {
  event.preventDefault();
  const logId = modalElements.logId.value;
  const payload = buildSavePayload();

  fetch(`/speech_log/update/${logId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
    .then((response) => response.json())
    .then((updateResult) => {
      if (updateResult.success) {
        handleSaveSuccess(updateResult, payload);
      } else {
        alert(
          "Error updating speech log: " +
            (updateResult.message || "Unknown error")
        );
      }
    })
    .catch((error) => {
      console.error("Save error:", error);
      alert("An error occurred while saving changes.");
    });
}

// --- Setup Helpers (for opening) ---

/**
 * Resets all modal fields to a default state before specialization.
 */
function setCommonModalValues(logData, sessionType) {
  modalElements.logId.value = logData.id;
  modalElements.mediaUrl.value = logData.Media_URL || "";
  modalElements.speechTitle.value = logData.Session_Title || "";
  modalElements.sessionType.value = sessionType;

  // Reset fields to default "Pathway Speech" state
  modalElements.speechTitle.disabled = false;
  modalElements.pathwayGenericRow.style.display = "flex";
  modalElements.levelSelectGroup.style.display = "block";
  modalElements.projectSelectGroup.style.display = "block";
  modalElements.genericCheckbox.disabled = false;
  modalElements.genericCheckbox.checked = false;

  // Explicitly set required to false here. It will be re-enabled by pathway/presentation setups.
  modalElements.pathwaySelect.required = false;

  toggleGeneric(false); // Ensure fields are visible

  // Reset evaluator-specific fields
  modalElements.evalProjectGroup.style.display = "none";
  modalElements.evalProjectSelect.style.display = "none";
  modalElements.evalIsProjectChk.checked = false;
  modalElements.evalProjectSelect.value = "";

  // Reset Table Topics specific fields
  modalElements.ttProjectGroup.style.display = "none";
  modalElements.ttPathwayGroup.style.display = "none";
  modalElements.ttIsProjectChk.checked = false;
  modalElements.ttPathwaySelect.value = "";
}

/**
 * Configures the modal for an "Individual Evaluator".
 */
function setupEvaluatorModal(logData) {
  modalElements.title.textContent = "Edit Evaluator Details";
  modalElements.speechTitle.disabled = true;
  modalElements.pathwayGenericRow.style.display = "none";
  modalElements.levelSelectGroup.style.display = "none";
  modalElements.projectSelectGroup.style.display = "none";
  modalElements.pathwaySelect.required = false;

  // New logic starts here
  modalElements.evalProjectGroup.style.display = "block";

  // Populate the dropdown with evaluation projects (IDs 4, 5, 6)
  const evalProjects = allProjects
    .filter((p) => [4, 5, 6].includes(p.ID))
    .sort((a, b) => a.ID - b.ID);
  modalElements.evalProjectSelect.innerHTML =
    '<option value="">-- Select Evaluation Project --</option>';
  evalProjects.forEach((p) => {
    modalElements.evalProjectSelect.add(new Option(p.Project_Name, p.ID));
  });

  // Add event listener for the checkbox
  modalElements.evalIsProjectChk.onchange = (e) => {
    modalElements.evalProjectSelect.style.display = e.target.checked
      ? "block"
      : "none";
    if (!e.target.checked) {
      modalElements.evalProjectSelect.value = "";
    }
  };

  // Set initial state based on logData
  if (logData.Project_ID && ["4", "5", "6"].includes(String(logData.Project_ID))) {
    modalElements.evalIsProjectChk.checked = true;
    modalElements.evalProjectSelect.value = logData.Project_ID;
    modalElements.evalProjectSelect.style.display = "block";
  } else {
    modalElements.evalIsProjectChk.checked = false;
    modalElements.evalProjectSelect.style.display = "none";
    modalElements.evalProjectSelect.value = "";
  }
}

/**
 * Configures the modal for a "Table Topics Master".
 */
function setupTableTopicsModal(logData) {
  modalElements.title.textContent = "Edit Table Topics Details";
  modalElements.speechTitle.disabled = true;
  modalElements.pathwayGenericRow.style.display = "none";
  modalElements.levelSelectGroup.style.display = "none";
  modalElements.projectSelectGroup.style.display = "none";
  modalElements.pathwaySelect.required = false;

  modalElements.ttProjectGroup.style.display = "block";

  // Populate Pathway dropdown
  modalElements.ttPathwaySelect.innerHTML = ""; // Clear
  modalElements.ttPathwaySelect.add(new Option("-- Select Pathway --", ""));
  Object.keys(pathwayMap).forEach((p_name) => {
    modalElements.ttPathwaySelect.add(new Option(p_name, p_name));
  });

  // Add event listener for the checkbox
  modalElements.ttIsProjectChk.onchange = (e) => {
    modalElements.ttPathwayGroup.style.display = e.target.checked
      ? "block"
      : "none";
    if (!e.target.checked) {
      modalElements.ttPathwaySelect.value = "";
    }
  };

  // Set initial state based on logData
  if (logData.Project_ID === 10) {
    modalElements.ttIsProjectChk.checked = true;
    modalElements.ttPathwaySelect.value = logData.pathway || "";
    modalElements.ttPathwayGroup.style.display = "block";
  } else {
    modalElements.ttIsProjectChk.checked = false;
    modalElements.ttPathwayGroup.style.display = "none";
    modalElements.ttPathwaySelect.value = "";
  }
}

/**
 * Configures the modal for a "Presentation".
 */
function setupPresentationModal(logData) {
  modalElements.title.textContent = "Edit Speech Details";
  modalElements.labelPathway.textContent = "Education Series:";
  modalElements.labelProject.textContent = "Presentation Title:";
  modalElements.levelSelectGroup.style.display = "none";
  modalElements.genericCheckbox.disabled = true;
  modalElements.pathwaySelect.required = true;

  // Find current presentation
  const currentPres = allPresentations.find((p) => p.id == logData.Project_ID);
  const currentSeries = currentPres ? currentPres.series : "";

  // Populate Series dropdown
  modalElements.pathwaySelect.innerHTML = ""; // Clear
  modalElements.pathwaySelect.add(new Option("-- Select Series --", ""));
  presentationSeries.forEach((series) => {
    modalElements.pathwaySelect.add(new Option(series, series));
  });
  modalElements.pathwaySelect.value = currentSeries;

  // Populate Presentation options
  updatePresentationOptions(
    logData.Project_ID,
    currentPres ? currentPres.level : null
  );
}

/**
 * Configures the modal for a "Pathway Speech".
 */
function setupPathwayModal(logData, workingPath, nextProject) {
  modalElements.title.textContent = "Edit Speech Details";
  modalElements.labelPathway.textContent = "Pathway:";
  modalElements.labelLevel.textContent = "Level:";
  modalElements.labelProject.textContent = "Project:";
  modalElements.pathwaySelect.required = true;

  // Populate Pathway dropdown
  modalElements.pathwaySelect.innerHTML = ""; // Clear
  modalElements.pathwaySelect.add(new Option("-- Select Pathway --", ""));
  Object.keys(pathwayMap).forEach((p_name) => {
    modalElements.pathwaySelect.add(new Option(p_name, p_name));
  });

  // --- Logic to pre-select dropdowns ---
  let pathwayToSelect = logData.pathway;
  let levelToSelect = logData.level || "";
  let projectToSelect = logData.Project_ID;
  let projectCodeToFind = null;

  if (projectToSelect == "60") {
    // "TM1.0" Generic Speech
    modalElements.genericCheckbox.checked = true;
    toggleGeneric(true);
    modalElements.pathwaySelect.value = pathwayToSelect || "";
  } else {
    // Standard Pathway Speech
    modalElements.genericCheckbox.checked = false;
    toggleGeneric(false);

    // Pre-fill logic if opening from agenda for a new/unassigned speech
    if (window.location.pathname.includes("/agenda") && !logData.Project_ID) {
      if (nextProject) {
        try {
          // Try to parse "EH3.1"
          const nextPathAbbr = nextProject.substring(0, 2);
          const nextLevel = nextProject.substring(2, 3);
          projectCodeToFind = nextProject.substring(2);
          const pathwayName = Object.keys(pathwayMap).find(
            (name) => pathwayMap[name] === nextPathAbbr
          );
          if (pathwayName) {
            pathwayToSelect = pathwayName;
            levelToSelect = nextLevel;
          }
        } catch (e) {
          projectCodeToFind = null; // Failed to parse
        }
      } else if (workingPath) {
        pathwayToSelect = workingPath;
      }
    } else if (window.location.pathname.includes("/agenda") && workingPath) {
      // Pre-fill user's current pathway
      pathwayToSelect = workingPath;
    }

    modalElements.pathwaySelect.value = pathwayToSelect || "";
    modalElements.levelSelect.value = levelToSelect;

    // If we found a code (e.g., "3.1"), find the matching Project ID
    if (projectCodeToFind) {
      const codeSuffix = pathwayMap[pathwayToSelect];
      const codeAttr = `Code_${codeSuffix}`;
      if (codeSuffix && Array.isArray(allProjects)) {
        const foundProject = allProjects.find(
          (p) => p[codeAttr] === projectCodeToFind
        );
        if (foundProject) projectToSelect = foundProject.ID;
      }
    }
    // Populate the project dropdown based on selections
    updateProjectOptions(projectToSelect);
  }
}

// --- Dynamic Dropdown Helpers ---

/**
 * Called on change. Routes to the correct dropdown populator.
 */
function updateDynamicOptions() {
  const sessionType = modalElements.sessionType.value;
  if (sessionType === "Presentation") {
    updatePresentationOptions(null, null);
  } else {
    updateProjectOptions();
  }
}

/**
 * Populates the Project dropdown based on selected Pathway and Level.
 */
function updateProjectOptions(selectedProjectId = null) {
  const { pathwaySelect, levelSelect, projectSelect } = modalElements;
  const selectedPathway = pathwaySelect.value;
  const selectedLevel = levelSelect.value;

  projectSelect.innerHTML = '<option value="">-- Select a Project --</option>';

  const codeSuffix = pathwayMap[selectedPathway];
  if (!codeSuffix || !selectedLevel) return; // Need both to filter

  const codeAttr = `Code_${codeSuffix}`;

  const filteredProjects = allProjects
    .filter((p) => p[codeAttr] && p[codeAttr].startsWith(selectedLevel + "."))
    .sort((a, b) => (a[codeAttr] < b[codeAttr] ? -1 : 1));

  filteredProjects.forEach((p) => {
    const optionText = `${p[codeAttr]} - ${p.Project_Name}`;
    projectSelect.add(new Option(optionText, p.ID));
  });

  if (selectedProjectId) {
    projectSelect.value = selectedProjectId;
  }
}

/**
 * Populates the Presentation dropdown based on selected Series.
 */
function updatePresentationOptions(
  selectedPresentationId = null,
  level = null
) {
  const { pathwaySelect: seriesSelect, projectSelect: presentationSelect } =
    modalElements;
  const selectedSeries = seriesSelect.value;

  presentationSelect.innerHTML =
    '<option value="">-- Select Presentation --</option>';

  if (!selectedSeries) return;

  const filtered = allPresentations
    .filter(
      (p) => p.series === selectedSeries && (level === null || p.level == level)
    )
    .sort((a, b) => {
      if (a.level !== b.level) return a.level - b.level;
      return a.title.localeCompare(b.title);
    });

  filtered.forEach((p) => {
    presentationSelect.add(new Option(`L${p.level} - ${p.title}`, p.id));
  });

  if (selectedPresentationId) {
    presentationSelect.value = selectedPresentationId;
  }
}

// --- Save Helpers ---

/**
 * Builds the JSON payload for the save request based on modal state.
 */
function buildSavePayload() {
  const sessionType = modalElements.sessionType.value;
  const isGeneric = modalElements.genericCheckbox.checked;

  if (sessionType === "Evaluation") {
    const isProject = modalElements.evalIsProjectChk.checked;
    const projectId = modalElements.evalProjectSelect.value;
    return {
      session_type_title: sessionType,
      media_url: modalElements.mediaUrl.value || null,
      project_id: isProject && projectId ? projectId : null,
    };
  }

  if (sessionType === "Table Topics") {
    const isProject = modalElements.ttIsProjectChk.checked;
    const pathway = modalElements.ttPathwaySelect.value;
    return {
      session_type_title: sessionType,
      media_url: modalElements.mediaUrl.value || null,
      project_id: isProject && pathway ? 10 : null, // Project ID is 10 for TT project
      pathway: isProject && pathway ? pathway : null,
    };
  }

  if (sessionType === "Presentation") {
    return {
      session_title: modalElements.speechTitle.value,
      project_id: modalElements.projectSelect.value || null,
      session_type_title: sessionType,
      media_url: modalElements.mediaUrl.value || null,
    };
  }

  if (isGeneric) {
    return {
      session_title: modalElements.speechTitle.value,
      project_id: "60", // Generic Speech ID
      session_type_title: sessionType,
      media_url: modalElements.mediaUrl.value || null,
      pathway: modalElements.pathwaySelect.value,
    };
  }

  // Default: Pathway Speech
  return {
    session_title: modalElements.speechTitle.value,
    project_id: modalElements.projectSelect.value || "60", // Default to Generic if empty
    session_type_title: sessionType,
    media_url: modalElements.mediaUrl.value || null,
    pathway: modalElements.pathwaySelect.value,
  };
}

/**
 * Handles the successful save response, delegating UI updates.
 */
function handleSaveSuccess(updateResult, payload) {
  const logId = modalElements.logId.value;
  if (window.location.pathname.includes("/agenda")) {
    updateAgendaRow(logId, updateResult, payload);
  } else {
    updateSpeechLogCard(logId, updateResult, payload);
  }
  closeSpeechEditModal();
}

/**
 * Updates the agenda row in `agenda.html` after a successful save.
 */
function updateAgendaRow(logId, updateResult, payload) {
  const agendaRow = document.querySelector(`tr[data-id="${logId}"]`);
  if (!agendaRow) return;

  const sessionType = payload.session_type_title;

  // Helper to update media link in a given cell
  const updateMediaLink = (cell) => {
    let mediaLink = cell.querySelector(".media-play-btn");
    const newMediaUrl = payload.media_url;
    const wrapper = cell.querySelector(".speech-tooltip-wrapper") || cell;

    if (newMediaUrl && !mediaLink) {
      // Add new link
      mediaLink = document.createElement("a");
      mediaLink.target = "_blank";
      mediaLink.className = "icon-btn media-play-btn";
      mediaLink.title = "Watch Media";
      mediaLink.innerHTML = ' <i class="fas fa-play-circle"></i>';
      wrapper.appendChild(mediaLink);
    } else if (!newMediaUrl && mediaLink) {
      // Remove old link
      mediaLink.remove();
    }
    if (newMediaUrl && mediaLink) {
      // Update existing link
      mediaLink.href = newMediaUrl;
    }
  };

  if (sessionType === "Individual Evaluator") {
    // Evaluators only need their media link updated
    const titleCell = agendaRow.querySelector(
      ".non-edit-mode-cell:nth-child(2)"
    );
    if (titleCell) updateMediaLink(titleCell);
  } else if (sessionType === "Table Topics") {
    agendaRow.dataset.projectId = updateResult.project_id || "";
    const viewTitleCell = agendaRow.querySelector(
      ".non-edit-mode-cell:nth-child(2)"
    );
    if (viewTitleCell) {
        let title = "Table Topics Master";
        let code = updateResult.project_code ? `(${updateResult.project_code})` : "";
        viewTitleCell.querySelector(".speech-tooltip-wrapper").textContent = `${title} ${code}`.trim();
        updateMediaLink(viewTitleCell);
    }
  }
  else {
    // Full update for Speeches/Presentations
    agendaRow.dataset.projectId = updateResult.project_id || "";
    agendaRow.dataset.sessionTitle = updateResult.session_title;

    // Update edit mode title
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

    // Update view mode title
    const viewTitleCell = agendaRow.querySelector(
      ".non-edit-mode-cell:nth-child(2)"
    );
    if (viewTitleCell) {
      let title = updateResult.session_title;
      if (sessionType === "Pathway Speech" && updateResult.project_id != "60") {
        title = `"${title.replace(/"/g, "")}"`;
      }

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
      updateMediaLink(viewTitleCell); // Add media link *after* rebuild
    }

    // Update duration in dataset and view mode
    agendaRow.dataset.durationMin = updateResult.duration_min || "";
    agendaRow.dataset.durationMax = updateResult.duration_max || "";
    const durationCell = agendaRow.querySelector(
      ".non-edit-mode-cell:nth-child(4)"
    );
    if (durationCell) {
      const { duration_min: min, duration_max: max } = updateResult;
      durationCell.textContent =
        min && max && min != max ? `${min}'-${max}'` : max ? `${max}'` : "";
    }
  }
}

/**
 * Updates the log card in `speech_logs.html` after a successful save.
 */
function updateSpeechLogCard(logId, updateResult, payload) {
  const card = document.getElementById(`log-card-${logId}`);
  if (!card) return;

  // Don't update title/project for evaluators
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

  // Update media link for all types
  let mediaLink = card.querySelector(".btn-play");
  const newMediaUrl = payload.media_url;
  if (newMediaUrl && !mediaLink) {
    mediaLink = document.createElement("a");
    mediaLink.href = newMediaUrl;
    mediaLink.target = "_blank";
    mediaLink.className = "icon-btn btn-play";
    mediaLink.title = "Watch Media";
    mediaLink.innerHTML = '<i class="fas fa-play-circle"></i>';
    card.querySelector(".card-actions").prepend(mediaLink);
  } else if (newMediaUrl && mediaLink) {
    mediaLink.href = newMediaUrl;
  } else if (!newMediaUrl && mediaLink) {
    mediaLink.remove();
  }
}
