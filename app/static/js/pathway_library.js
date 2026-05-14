let isEditing = false;

function updatePathCodes(project) {
  document.querySelectorAll(".path-code-box").forEach((box) => {
    const pathAbbr = box.dataset.path;
    const code =
      project && project.path_codes ? project.path_codes[pathAbbr] : null;
    
    // Configure marked options
    marked.use({
      breaks: true,
      gfm: true
    });

    // Use .badge-text span if available (new structure), fallback to span (old structure/desktop)
    const valueSpan = box.querySelector(".badge-text span") || box.querySelector("span");

    if (code) {
      box.style.display = ""; // Remove inline style to let CSS (display: flex) take over
      if (valueSpan) valueSpan.textContent = code;
    } else {
      box.style.display = "none";
      if (valueSpan) valueSpan.textContent = "";
    }
  });
}

function clearPathCodes() {
  document.querySelectorAll(".path-code-box").forEach((box) => {
    // Use .badge-text span if available (new structure), fallback to span (old structure/desktop)
    const valueSpan = box.querySelector(".badge-text span") || box.querySelector("span");
    if (valueSpan) valueSpan.textContent = "";
    box.style.display = "none";
  });
}

function toggleEditView() {
  const editButton = document.getElementById("edit-project-btn");
  const cancelButton = document.getElementById("cancel-project-btn");
  const contentDivs = document.querySelectorAll(
    "#project-details .project-section .markdown-content"
  );
  const textareas = document.querySelectorAll(
    "#project-details .project-section textarea"
  );

  const pathSelect = document.getElementById("path");
  const projectSelect = document.getElementById("project");
  const selectedPathway = pathways.find((p) => p.abbr === pathSelect.value);
  const projectId = parseInt(projectSelect.value, 10);
  const currentProject = selectedPathway
    ? selectedPathway.projects.find((p) => p.id === projectId)
    : null;

  isEditing = !isEditing;

  if (isEditing) {
    editButton.innerHTML = '<i class="fas fa-check"></i>';
    // Remove the inline style to let CSS (display: inline-flex) take over, allowing proper alignment
    cancelButton.style.display = ""; 
    // Fallback: if CSS isn't applied for some reason, force inline-flex
    if (getComputedStyle(cancelButton).display === 'none') {
        cancelButton.style.display = "inline-flex";
    }

    contentDivs.forEach((div) => (div.style.display = "none"));
    textareas.forEach((textarea) => {
      const fieldName = textarea.id.replace("edit-", "");
      if (currentProject) {
        textarea.value =
          currentProject[
          fieldName.charAt(0).toUpperCase() + fieldName.slice(1)
          ] || "";
      }
      textarea.style.display = "block";
      adjustTextareaHeight(textarea);
    });
  } else {
    editButton.innerHTML = '<i class="fas fa-edit"></i>';
    // Restore the strict hiding with !important
    cancelButton.style.setProperty('display', 'none', 'important');
    contentDivs.forEach((div) => (div.style.display = "block"));
    textareas.forEach((textarea) => (textarea.style.display = "none"));
    displayProjectDetails();
  }
}

function adjustTextareaHeight(textarea) {
  let n = 3;
  textarea.rows = n;
  
  // Logic: while content overflows visible area, increase rows by 3
  // clientHeight includes padding but not border. scrollHeight includes padding.
  // We want scrollHeight <= clientHeight
  while (textarea.scrollHeight > textarea.clientHeight && n < 100) {
    n += 3;
    textarea.rows = n;
  }
}


function displayProjectDetails() {
  const pathSelect = document.getElementById("path");
  const projectSelect = document.getElementById("project");
  const projectDetails = document.getElementById("project-details");

  const selectedPathway = pathways.find((p) => p.abbr === pathSelect.value);
  const projectVal = projectSelect ? projectSelect.value : "";
  const projectId = projectVal ? parseInt(projectVal, 10) : null;
  const project = (selectedPathway && projectId !== null)
    ? selectedPathway.projects.find((p) => p.id === projectId)
    : null;


  if (project) {
    const toHtml = (str) => DOMPurify.sanitize(marked.parse(str || ""));

    document.getElementById("project-name").textContent =
      project.Project_Name || "";
    document.getElementById("project-purpose").innerHTML = toHtml(
      project.Purpose
    );
    document.getElementById("project-introduction").innerHTML = toHtml(
      project.Introduction
    );
    document.getElementById("project-overview").innerHTML = toHtml(
      project.Overview
    );
    document.getElementById("project-requirements").innerHTML = toHtml(
      project.Requirements
    );
    document.getElementById("project-resources").innerHTML = toHtml(
      project.Resources
    );

    updatePathCodes(project);

    const downloadBtn = document.getElementById("download-project-btn");
    if (downloadBtn) {
      const filename = ((project.Project_Name || "").replace(/ /g, "_") + ".pdf").toLowerCase();
      downloadBtn.href = `/static/eval_forms/${filename}`;
      downloadBtn.style.display = "inline-block";
    }

    projectDetails.style.display = "block";
  } else {
    projectDetails.style.display = "none";
    clearPathCodes();
  }
}

function updateLevelOptions(selectedPathway) {
  const levelSelect = document.getElementById("level");
  const currentSelection = levelSelect.value;

  // Clear existing options
  levelSelect.innerHTML = '<option value="">All Levels</option>';

  if (selectedPathway && selectedPathway.projects) {
    // Get unique levels
    const levels = new Set();
    selectedPathway.projects.forEach(p => {
      if (p.level) {
        levels.add(p.level);
      }
    });

    // Sort and add options
    const sortedLevels = Array.from(levels).sort((a, b) => a - b);
    sortedLevels.forEach(level => {
      const option = document.createElement("option");
      option.value = level;
      option.textContent = `Level ${level}`;
      levelSelect.appendChild(option);
    });
  }

  // Restore selection if valid, otherwise default to All Levels or Level 1 if implied
  const options = Array.from(levelSelect.options).map(o => o.value);
  if (options.includes(currentSelection)) {
    levelSelect.value = currentSelection;
  } else {
    levelSelect.value = "";
  }
  // Dispatch change event to notify CustomSelectAdapter (MutationObserver might be too slow for immediate UI sync)
  levelSelect.dispatchEvent(new Event('change', { bubbles: true }));
}

function filterProjects() {
  const pathSelect = document.getElementById("path");
  const levelSelect = document.getElementById("level");
  const projectSelect = document.getElementById("project");

  const selectedPathway = pathways.find((p) => p.abbr === pathSelect.value);
  const levelValue = levelSelect.value; // string

  projectSelect.innerHTML = '<option value="">-- Select a Project --</option>';

  if (selectedPathway) {
    let filteredProjects = selectedPathway.projects;

    if (levelValue) {
      // Filter by strict level equality (converting string to int for safety)
      const lvl = parseInt(levelValue, 10);
      filteredProjects = filteredProjects.filter(p => p.level === lvl);
    }

    // Sort by level then code (or project name if code is same/missing)
    // Actually existing sort was by code.
    filteredProjects.sort((a, b) =>
      (a.code || "").localeCompare(b.code || "", undefined, { numeric: true })
    );

    filteredProjects.forEach((p) => {
      const option = document.createElement("option");
      option.value = p.id;
      option.textContent = `${p.Project_Name}`;
      projectSelect.appendChild(option);
    });
  }
  // Dispatch change event to notify CustomSelectAdapter
  projectSelect.dispatchEvent(new Event('change', { bubbles: true }));
}

function saveProjectChanges() {
  const pathSelect = document.getElementById("path");
  const projectSelect = document.getElementById("project");
  const projectId = parseInt(projectSelect.value, 10);
  if (!projectId) return;

  const data = {
    Introduction: document.getElementById("edit-introduction").value,
    Overview: document.getElementById("edit-overview").value,
    Purpose: document.getElementById("edit-purpose").value,
    Requirements: document.getElementById("edit-requirements").value,
    Resources: document.getElementById("edit-resources").value,
  };

  fetch(`/pathway_library/update_project/${projectId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        const selectedPathway = pathways.find(
          (p) => p.abbr === pathSelect.value
        );
        if (selectedPathway) {
          const projectIndex = selectedPathway.projects.findIndex(
            (p) => p.id === projectId
          );
          if (projectIndex > -1) {
            const project = selectedPathway.projects[projectIndex];
            project.Introduction = data.Introduction;
            project.Overview = data.Overview;
            project.Purpose = data.Purpose;
            project.Requirements = data.Requirements;
            project.Resources = data.Resources;
          }
        }
        toggleEditView(); // This will exit edit mode
      } else {
        alert("Failed to save changes.");
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      alert("An error occurred while saving.");
    });
}

document.addEventListener("DOMContentLoaded", function () {
  const pathSelect = document.getElementById("path");
  const levelSelect = document.getElementById("level");
  const projectSelect = document.getElementById("project");
  const pathBoxes = document.querySelectorAll(".path-code-box");
  const editButton = document.getElementById("edit-project-btn");
  const cancelButton = document.getElementById("cancel-project-btn");
  const textareas = document.querySelectorAll(
    "#project-details .project-section textarea"
  );

  function handleFilterChange(event) {
    // If exact event target is path select, update levels
    if (event && (event.target === pathSelect || event.target.classList.contains('path-code-box'))) {
      const selectedPathway = pathways.find((p) => p.abbr === pathSelect.value);
      updateLevelOptions(selectedPathway);
    }

    filterProjects();
    if (projectSelect.options.length > 1) {
      projectSelect.selectedIndex = 1;
    }
    displayProjectDetails();
  }

  if (pathSelect) pathSelect.addEventListener("change", handleFilterChange);
  if (levelSelect) levelSelect.addEventListener("change", handleFilterChange);
  if (projectSelect)
    projectSelect.addEventListener("change", displayProjectDetails);

  pathBoxes.forEach((box) => {
    box.addEventListener("click", function () {
      if (pathSelect) {
        pathSelect.value = this.dataset.path;
        // Manually dispatch change event to trigger handleFilterChange and update CustomSelectAdapter
        pathSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
  });

  if (editButton) {
    editButton.addEventListener("click", () => {
      if (isEditing) {
        saveProjectChanges();
      } else {
        toggleEditView();
      }
    });
  }

  if (cancelButton) {
    cancelButton.addEventListener("click", () => {
      toggleEditView();
    });
  }

  textareas.forEach((textarea) => {
    textarea.addEventListener("input", function (event) {
      adjustTextareaHeight(this);
    });
  });

  // --- Initial Load Logic ---
  const urlParams = new URLSearchParams(window.location.search);
  const pathParam = urlParams.get("path");
  const levelParam = urlParams.get("level");
  const projectIdParam = urlParams.get("project_id");

  if (pathParam) {
    pathSelect.value = pathParam;
  } else {
    const pmPathway = pathways.find((p) => p.abbr === "PM");
    if (pmPathway) {
      pathSelect.value = "PM";
    } else if (pathways.length > 0) {
      pathSelect.value = pathways[0].abbr;
    }
  }

  // Initial Level Options population
  const initialPathway = pathways.find((p) => p.abbr === pathSelect.value);
  updateLevelOptions(initialPathway);

  if (levelParam) {
    levelSelect.value = levelParam;
  } else {
    // Default to '1' if available, else ''
    // Check if level 1 exists for this pathway
    if (initialPathway && initialPathway.projects.some(p => p.level === 1)) {
      levelSelect.value = "1";
    } else if (levelSelect.options.length > 1) {
      // Just pick the first available level if 1 isn't there?
      // Or keep it at "" (All Levels)
      // levelSelect.selectedIndex = 1; 
    }
  }

  filterProjects();

  if (projectIdParam) {
    projectSelect.value = projectIdParam;
  } else if (projectSelect.options.length > 1) {
    projectSelect.selectedIndex = 1;
  }

  displayProjectDetails();

  // Initialize Custom Select Adapters
  // These will automatically sync with the native selects and handle updates via MutationObserver
  if (pathSelect) new CustomSelectAdapter(pathSelect);
  if (levelSelect) new CustomSelectAdapter(levelSelect);
  if (projectSelect) new CustomSelectAdapter(projectSelect);
});
