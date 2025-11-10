// static/js/speech_modal.js

function toggleGeneric(isGeneric) {
  const levelGroup = document.getElementById("level-select-group");
  const projectGroup = document.getElementById("project-select-group");
  const pathwaySelect = document.getElementById("edit-pathway");
  const levelSelect = document.getElementById("edit-level");
  const projectSelect = document.getElementById("edit-project");

  if (isGeneric) {
    // HIDE pathway fields and clear them
    levelGroup.style.display = "none";
    projectGroup.style.display = "none";
    pathwaySelect.disabled = true;
    levelSelect.disabled = true;
    projectSelect.disabled = true;

    // Clear selections
    pathwaySelect.value = "";
    levelSelect.value = "";
    projectSelect.value = "";
    projectSelect.innerHTML = '<option value="">-- Select --</option>';
  } else {
    // SHOW pathway fields
    levelGroup.style.display = "block";
    projectGroup.style.display = "block";
    pathwaySelect.disabled = false;
    levelSelect.disabled = false;
    projectSelect.disabled = false;
  }
}

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
        // --- 1. Set simple values ---
        document.getElementById("edit-log-id").value = data.log.id;
        document.getElementById("edit-speech-title").value =
          data.log.Session_Title || "";
        document.getElementById("edit-media-url").value =
          data.log.Media_URL || "";

        const currentSessionType = passedSessionType || "Pathway Speech"; // Default if not passed
        document.getElementById("edit-session-type-title").value =
          currentSessionType;

        // --- 2. Get all elements ---
        const pathwaySeriesSelect = document.getElementById("edit-pathway");
        const levelSelectGroup = document.getElementById("level-select-group");
        const levelSelect = document.getElementById("edit-level");
        const projectPresentationSelect =
          document.getElementById("edit-project");
        const labelPathwaySeries = document.getElementById(
          "label-pathway-series"
        );
        const labelLevel = document.getElementById("label-level");
        const labelProjectPresentation = document.getElementById(
          "label-project-presentation"
        );
        const genericCheckbox = document.getElementById("edit-is-generic"); // Get checkbox

        // --- 3. Clear dynamic dropdowns ---
        pathwaySeriesSelect.innerHTML = "";
        projectPresentationSelect.innerHTML =
          '<option value="">-- Select --</option>';

        // Store the presentation level if applicable
        let presentationLevel = null;

        if (currentSessionType === "Presentation") {
          // --- 4. Presentation Mode ---
          labelPathwaySeries.textContent = "Education Series:";
          labelProjectPresentation.textContent = "Presentation Title:";
          levelSelectGroup.style.display = "none"; // Hide Level dropdown
          genericCheckbox.checked = false; // Uncheck Generic
          genericCheckbox.disabled = true; // Disable Generic
          toggleGeneric(false); // Ensure pathway fields are visible (for pathway select)

          // Find the current presentation to determine its series and level
          const currentPresentation = Array.isArray(allPresentations)
            ? allPresentations.find((p) => p.id == data.log.Project_ID)
            : null;
          const currentSeries = currentPresentation
            ? currentPresentation.series
            : "";
          presentationLevel = currentPresentation
            ? currentPresentation.level
            : null; // Store the level

          // Populate Series dropdown
          pathwaySeriesSelect.add(new Option("-- Select Series --", ""));
          if (Array.isArray(presentationSeries)) {
            presentationSeries.forEach((series) => {
              pathwaySeriesSelect.add(new Option(series, series));
            });
          } else {
            console.error(
              "presentationSeries is not an array or is undefined."
            );
          }
          pathwaySeriesSelect.value = currentSeries; // Select the correct series

          // Populate Presentation options
          updatePresentationOptions(data.log.Project_ID, presentationLevel);
        } else {
          // --- 5. Pathway Speech Mode (Default) ---
          labelPathwaySeries.textContent = "Pathway:";
          labelLevel.textContent = "Level:";
          labelProjectPresentation.textContent = "Project:";
          // Note: toggleGeneric() will manage levelSelectGroup display
          genericCheckbox.disabled = false; // Enable Generic checkbox

          // Populate Pathway dropdown
          pathwaySeriesSelect.add(new Option("-- Select Pathway --", ""));
          if (pathwayMap && typeof pathwayMap === "object") {
            Object.keys(pathwayMap).forEach((p_name) => {
              pathwaySeriesSelect.add(new Option(p_name, p_name));
            });
          } else {
            console.error("pathwayMap is not defined or invalid.");
          }

          // --- 6. NEW "Generic" LOGIC ---
          let pathwayToSelect = data.log.pathway;
          let levelToSelect = data.log.level || "";
          let projectToSelect = data.log.Project_ID;
          let projectCodeToFind = null;

          if (projectToSelect == "60") {
            // It's a Generic speech
            genericCheckbox.checked = true;
            toggleGeneric(true);
            // Pre-fill pathway for display even if disabled
            pathwaySeriesSelect.value = pathwayToSelect || "";
          } else {
            // It's a Pathway speech
            genericCheckbox.checked = false;
            toggleGeneric(false);

            // --- 7. Existing logic for finding Pathway/Level/Project ---
            if (
              window.location.pathname.includes("/agenda") &&
              !data.log.Project_ID
            ) {
              if (nextProject) {
                try {
                  const nextPathAbbr = nextProject.substring(0, 2); // "EH"
                  const nextLevel = nextProject.substring(2, 3); // "3"
                  projectCodeToFind = nextProject.substring(2); // "3.1"

                  const pathwayName = Object.keys(pathwayMap).find(
                    (name) => pathwayMap[name] === nextPathAbbr
                  );

                  if (pathwayName) {
                    pathwayToSelect = pathwayName;
                    levelToSelect = nextLevel;
                  }
                } catch (e) {
                  console.error(
                    "Could not parse nextProject string:",
                    nextProject
                  );
                  projectCodeToFind = null; // Clear on error
                }
              } else if (workingPath) {
                pathwayToSelect = workingPath;
              }
            } else if (
              window.location.pathname.includes("/agenda") &&
              workingPath
            ) {
              pathwayToSelect = workingPath;
            }

            pathwaySeriesSelect.value = pathwayToSelect || "";
            levelSelect.value = levelToSelect;

            if (projectCodeToFind) {
              const codeSuffix = pathwayMap[pathwayToSelect];
              const codeAttr = `Code_${codeSuffix}`; // e.g., "Code_EH"

              if (codeSuffix && Array.isArray(allProjects)) {
                const foundProject = allProjects.find(
                  (p) => p[codeAttr] === projectCodeToFind
                );
                if (foundProject) {
                  projectToSelect = foundProject.ID; // Found it!
                }
              }
            }
            updateProjectOptions(projectToSelect);
          }
        }

        // --- 8. Show modal ---
        document.getElementById("speechEditModal").style.display = "flex";
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

function closeSpeechEditModal() {
  document.getElementById("speechEditModal").style.display = "none";
}

// Combined update function called on change
function updateDynamicOptions() {
  const sessionType = document.getElementById("edit-session-type-title").value;
  if (sessionType === "Presentation") {
    // When changing series for Presentation, level is determined by the *new* selection
    // We might not know the level until a presentation is chosen,
    // OR we filter based *only* on series first. Let's filter only on series first.
    updatePresentationOptions(null, null); // Pass null for level initially
  } else {
    updateProjectOptions();
  }
}

function updateProjectOptions(selectedProjectId = null) {
  const pathwaySelect = document.getElementById("edit-pathway");
  const levelSelect = document.getElementById("edit-level");
  const projectSelect = document.getElementById("edit-project");

  const selectedPathway = pathwaySelect.value;
  const selectedLevel = levelSelect.value;

  projectSelect.innerHTML = '<option value="">-- Select a Project --</option>';

  if (!pathwayMap || typeof pathwayMap !== "object") {
    console.error("pathwayMap is not defined or invalid.");
    return;
  }

  const codeSuffix = pathwayMap[selectedPathway];

  if (!codeSuffix) {
    return;
  }

  const codeAttr = `Code_${codeSuffix}`;

  if (!Array.isArray(allProjects)) {
    console.error("allProjects is not defined or not an array.");
    return;
  }

  if (selectedPathway && selectedLevel) {
    const filteredProjects = allProjects.filter(
      (p) => p[codeAttr] && p[codeAttr].startsWith(selectedLevel + ".")
    );

    filteredProjects.sort((a, b) => {
      const codeA = a[codeAttr];
      const codeB = b[codeAttr];
      if (!codeA) return 1;
      if (!codeB) return -1;
      if (codeA < codeB) return -1;
      if (codeA > codeB) return 1;
      return 0;
    });

    filteredProjects.forEach((p) => {
      // Display format: "Code - Project Name"
      const optionText = p[codeAttr]
        ? `${p[codeAttr]} - ${p.Project_Name}`
        : p.Project_Name;
      const option = new Option(optionText, p.ID);
      projectSelect.add(option);
    });

    if (selectedProjectId) {
      projectSelect.value = selectedProjectId;
    }
  }
}

// --- MODIFIED Function for Presentations ---
function updatePresentationOptions(
  selectedPresentationId = null,
  level = null
) {
  const seriesSelect = document.getElementById("edit-pathway"); // Used for series
  const presentationSelect = document.getElementById("edit-project"); // Used for presentation titles

  const selectedSeries = seriesSelect.value;

  presentationSelect.innerHTML =
    '<option value="">-- Select Presentation --</option>';

  // Use global allPresentations
  if (!Array.isArray(allPresentations)) {
    console.error("allPresentations is not defined or not an array.");
    return;
  }

  if (selectedSeries) {
    // Filter by series AND level if level is provided
    const filteredPresentations = allPresentations.filter(
      (p) => p.series === selectedSeries && (level === null || p.level == level)
    );

    // Sort presentations by level first, then title
    filteredPresentations.sort((a, b) => {
      if (a.level !== b.level) {
        return a.level - b.level;
      }
      return a.title.localeCompare(b.title);
    });

    filteredPresentations.forEach((p) => {
      // Display format: "L# - Title"
      const option = new Option(`L${p.level} - ${p.title}`, p.id);
      presentationSelect.add(option);
    });

    if (selectedPresentationId) {
      presentationSelect.value = selectedPresentationId;
    }
  }
}

function saveSpeechChanges(event) {
  event.preventDefault();
  const logId = document.getElementById("edit-log-id").value;
  const form = document.getElementById("speechEditForm");
  const sessionType = document.getElementById("edit-session-type-title").value;

  // Get the state of the new checkbox
  const isGeneric = document.getElementById("edit-is-generic").checked;
  let data; // Declare data object

  // Build the 'data' object based on the context
  if (sessionType === "Presentation") {
    // --- 1. Presentation Mode ---
    data = {
      session_title: form.querySelector("#edit-speech-title").value,
      project_id: form.querySelector("#edit-project").value || null,
      session_type_title: sessionType,
      media_url: form.querySelector("#edit-media-url").value || null,
    };
  } else if (isGeneric) {
    // --- 2. Generic Speech Mode ---
    data = {
      session_title: form.querySelector("#edit-speech-title").value,
      project_id: "60", // Hard-code the Generic Speech ID
      session_type_title: sessionType,
      media_url: form.querySelector("#edit-media-url").value || null,
      // Still save the pathway, even if it was disabled, for reference
      pathway: form.querySelector("#edit-pathway").value,
    };
  } else {
    // --- 3. Pathway Speech Mode ---
    data = {
      session_title: form.querySelector("#edit-speech-title").value,
      project_id: form.querySelector("#edit-project").value || null,
      session_type_title: sessionType,
      media_url: form.querySelector("#edit-media-url").value || null,
      pathway: form.querySelector("#edit-pathway").value,
    };

    // If no project is selected in Pathway mode, default to Generic (60)
    if (!data.project_id) {
      data.project_id = "60";
    }
  }

  fetch(`/speech_log/update/${logId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
    .then((response) => response.json())
    .then((updateResult) => {
      if (updateResult.success) {
        // --- Update UI (Agenda or Speech Logs page) ---
        if (window.location.pathname.includes("/agenda")) {
          // --- Agenda Page Update ---
          const agendaRow = document.querySelector(`tr[data-id="${logId}"]`);
          if (agendaRow) {
            agendaRow.dataset.projectId = updateResult.project_id || "";
            agendaRow.dataset.sessionTitle = updateResult.session_title;

            const editTitleCell = agendaRow.querySelector(
              'td[data-field="Session_Title"]'
            );
            if (editTitleCell) {
              const titleControl = editTitleCell.querySelector(
                "input, select, span"
              );
              if (titleControl) {
                if (titleControl.tagName === "SPAN") {
                  titleControl.textContent = updateResult.session_title;
                } else {
                  titleControl.value = updateResult.session_title;
                }
              }
            }

            const sessionTitleCell = agendaRow.querySelector(
              ".non-edit-mode-cell:nth-child(2)"
            );

            if (sessionTitleCell) {
              let titleDisplay = updateResult.session_title;
              if (
                sessionType === "Pathway Speech" &&
                updateResult.project_id != "60"
              ) {
                titleDisplay = `"${updateResult.session_title.replace(
                  /"/g,
                  ""
                )}"`;
              }

              let projectCodeDisplay = updateResult.project_code
                ? `(${updateResult.project_code})`
                : "";
              if (updateResult.project_id == "60") {
                projectCodeDisplay = "(TM1.0)"; // Set generic display
              }

              let projectName = updateResult.project_name;
              let projectPurpose = "";

              if (sessionType === "Presentation") {
                const presentation = Array.isArray(allPresentations)
                  ? allPresentations.find(
                      (p) => p.id == updateResult.project_id
                    )
                  : null;
                projectName = presentation
                  ? presentation.title
                  : updateResult.session_title;
              } else {
                const project = Array.isArray(allProjects)
                  ? allProjects.find((p) => p.ID == updateResult.project_id)
                  : null;
                projectPurpose = project ? project.Purpose : "";
              }

              sessionTitleCell.innerHTML = "";
              const wrapper = document.createElement("div");
              wrapper.className = "speech-tooltip-wrapper";

              if (updateResult.project_id == "60") {
                wrapper.textContent =
                  `${titleDisplay} ${projectCodeDisplay}`.trim();
              } else {
                wrapper.textContent =
                  `${titleDisplay} ${projectCodeDisplay}`.trim();
              }

              if (updateResult.project_id && updateResult.project_id != "60") {
                const tooltip = document.createElement("div");
                tooltip.className = "speech-tooltip";
                tooltip.innerHTML = `<span class="tooltip-title">${
                  projectName || ""
                }</span><span class="tooltip-purpose">${
                  projectPurpose || ""
                }</span>`;
                wrapper.appendChild(tooltip);
              }
              sessionTitleCell.appendChild(wrapper);
            }

            agendaRow.dataset.durationMin = updateResult.duration_min || "";
            agendaRow.dataset.durationMax = updateResult.duration_max || "";
            const durationCell = agendaRow.querySelector(
              ".non-edit-mode-cell:nth-child(4)"
            );
            if (durationCell) {
              const min = updateResult.duration_min;
              const max = updateResult.duration_max;
              if (min && max && min != max) {
                durationCell.textContent = `${min}'-${max}'`;
              } else if (max) {
                durationCell.textContent = `${max}'`;
              } else {
                durationCell.textContent = "";
              }
            }
          }
        } else {
          // --- Speech Logs Page Update ---
          const card = document.getElementById(`log-card-${logId}`);
          if (card) {
            card.querySelector(
              ".speech-title"
            ).innerText = `"${updateResult.session_title.replace(/"/g, "")}"`;

            card.querySelector(".project-name").innerText =
              updateResult.project_name || "N/A";

            let projectCodeText = updateResult.project_code
              ? `(${updateResult.project_code})`
              : "";
            if (updateResult.project_id == "60") {
              projectCodeText = "(TM1.0)"; // Set generic display
            }
            card.querySelector(".project-code").innerText = projectCodeText;

            card.querySelector(".pathway-info").innerText =
              updateResult.pathway || "N/A";
          }
        }
        closeSpeechEditModal();
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
