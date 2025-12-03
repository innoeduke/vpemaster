let isEditing = false;

function updatePathCodes(project) {
  document.querySelectorAll(".path-code-box").forEach((box) => {
    const pathAbbr = box.dataset.path;
    const code =
      project && project.path_codes ? project.path_codes[pathAbbr] : null;

    if (code) {
      box.style.display = "block";
      box.querySelector("span").textContent = code;
    } else {
      box.style.display = "none";
      box.querySelector("span").textContent = "";
    }
  });
}

function clearPathCodes() {
  document
    .querySelectorAll(".path-code-box span")
    .forEach((span) => (span.textContent = ""));
  document
    .querySelectorAll(".path-code-box")
    .forEach((box) => (box.style.display = "none"));
}

function toggleEditView() {
  const editButton = document.getElementById("edit-project-btn");
  const cancelButton = document.getElementById("cancel-project-btn");
  const pTags = document.querySelectorAll(
    "#project-details .project-section p"
  );
  const textareas = document.querySelectorAll(
    "#project-details .project-section textarea"
  );

  const pathSelect = document.getElementById("path");
  const projectSelect = document.getElementById("project");
  const selectedPathway = pathways.find((p) => p.abbr === pathSelect.value);
  const projectId = parseInt(projectSelect.value, 10);
  const currentProject = selectedPathway
    ? selectedPathway.projects.find((p) => p.ID === projectId)
    : null;

  isEditing = !isEditing;

  if (isEditing) {
    editButton.innerHTML = '<i class="fas fa-check"></i>';
    cancelButton.style.display = "inline-block";

    pTags.forEach((p) => (p.style.display = "none"));
    textareas.forEach((textarea) => {
      const fieldName = textarea.id.replace("edit-", "");
      if (currentProject) {
        textarea.value =
          currentProject[
            fieldName.charAt(0).toUpperCase() + fieldName.slice(1)
          ] || "";
      }
      textarea.style.display = "block";
    });
  } else {
    editButton.innerHTML = '<i class="fas fa-edit"></i>';
    cancelButton.style.display = "none";
    pTags.forEach((p) => (p.style.display = "block"));
    textareas.forEach((textarea) => (textarea.style.display = "none"));
    displayProjectDetails();
  }
}

function displayProjectDetails() {
  const pathSelect = document.getElementById("path");
  const projectSelect = document.getElementById("project");
  const projectDetails = document.getElementById("project-details");

  const selectedPathway = pathways.find((p) => p.abbr === pathSelect.value);
  const projectId = parseInt(projectSelect.value, 10);
  const project = selectedPathway
    ? selectedPathway.projects.find((p) => p.ID === projectId)
    : null;

  if (project) {
    const toHtml = (str) => (str || "").replace(/\n/g, "<br>");

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
    projectDetails.style.display = "block";
  } else {
    projectDetails.style.display = "none";
    clearPathCodes();
  }
}

function filterProjects() {
  const pathSelect = document.getElementById("path");
  const levelSelect = document.getElementById("level");
  const projectSelect = document.getElementById("project");

  const selectedPathway = pathways.find((p) => p.abbr === pathSelect.value);
  const levelValue = levelSelect.value;

  projectSelect.innerHTML = '<option value="">-- Select a Project --</option>';

  if (selectedPathway) {
    let filteredProjects = selectedPathway.projects;
    if (levelValue) {
      filteredProjects = filteredProjects.filter(
        (p) => p.code && p.code.startsWith(levelValue + ".")
      );
    }

    filteredProjects.sort((a, b) =>
      a.code.localeCompare(b.code, undefined, { numeric: true })
    );

    filteredProjects.forEach((p) => {
      const option = document.createElement("option");
      option.value = p.ID;
      option.textContent = `${p.Project_Name}`;
      projectSelect.appendChild(option);
    });
  }
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
            (p) => p.ID === projectId
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

  function handleFilterChange() {
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
        handleFilterChange();
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
      // No-op
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

  if (levelParam) {
    levelSelect.value = levelParam;
  } else {
    levelSelect.value = "1";
  }

  filterProjects();

  if (projectIdParam) {
    projectSelect.value = projectIdParam;
  } else if (projectSelect.options.length > 1) {
    projectSelect.selectedIndex = 1;
  }

  displayProjectDetails();
});
