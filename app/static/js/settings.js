// static/js/settings.js

/**
 * Handles switching tabs on the settings page.
 */
function openTab(evt, tabName) {
  const tabcontent = document.getElementsByClassName("tab-content");
  for (let i = 0; i < tabcontent.length; i++) {
    tabcontent[i].style.display = "none";
  }

  const tablinks = document.getElementsByClassName("tab-btn");
  for (let i = 0; i < tablinks.length; i++) {
    tablinks[i].className = tablinks[i].className.replace(" active", "");
  }

  const tabElement = document.getElementById(tabName);
  if (tabElement) {
    tabElement.style.display = "block";
  }

  // Handle both click event (has evt) and programmatic call (uses tabName)
  let targetElement = null;
  if (evt && evt.currentTarget) {
    targetElement = evt.currentTarget;
  } else {
    // Find the button associated with the tabName
    for (let i = 0; i < tablinks.length; i++) {
      if (tablinks[i].getAttribute("onclick").includes(`'${tabName}'`)) {
        targetElement = tablinks[i];
        break;
      }
    }
  }

  if (targetElement) {
    targetElement.className += " active";
  }
}

/**
 * Generic function to close any modal by its ID.
 */
function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.style.display = "none";
  }
}

/**
 * Saves changes for an inline-editable table.
 */
function saveTableChanges(config) {
  const { tableBody, url, toggleEditFn, getCellValue, updateCell } = config;
  const dataToSave = [];

  tableBody.querySelectorAll("tr").forEach((row) => {
    const rowData = { id: row.dataset.id };
    row.querySelectorAll("td[data-field]").forEach((cell) => {
      const field = cell.dataset.field;
      rowData[field] = getCellValue(cell, field);
    });
    dataToSave.push(rowData);
  });

  fetchWithRetry(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dataToSave),
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return response.json();
    })
    .then((data) => {
      if (data.success) {
        toggleEditFn(false);
        tableBody.querySelectorAll("tr").forEach((row) => {
          const id = row.dataset.id;
          const updatedRow = dataToSave.find((item) => item.id == id);
          if (updatedRow) {
            row.querySelectorAll("td[data-field]").forEach((cell) => {
              const field = cell.dataset.field;
              updateCell(cell, field, updatedRow[field]);
            });
          }
        });
        showNotification("Changes saved successfully!", "success");
      } else {
        throw new Error(data.message || "Request failed");
      }
    })
    .catch((error) => {
      console.error("Save error:", error);
      showNotification(`Error saving changes: ${error.message}`, "error");
    });
}

/**
 * Toggles inline-editing mode for a table.
 */
function toggleEditMode(config) {
  const {
    enable,
    editBtn,
    cancelBtn,
    tableBody,
    originalData,
    createEditor,
    restoreCell,
  } = config;

  // Update state
  editBtn.textContent = enable ? "Save" : "Edit";
  cancelBtn.style.display = enable ? "inline-block" : "none";

  tableBody.querySelectorAll("tr").forEach((row) => {
    const id = row.dataset.id;
    if (enable) {
      originalData[id] = {};
    }
    row.querySelectorAll("td[data-field]").forEach((cell) => {
      const field = cell.dataset.field;
      let currentValue;

      if (enable) {
        if (
          field.startsWith("Is_") ||
          field === "Valid_for_Project" ||
          field == "Predefined" ||
          field == "needs_approval" ||
          field == "is_distinct"
        ) {
          currentValue = cell.querySelector('input[type="checkbox"]').checked;
        } else {
          currentValue = cell.textContent.trim();
        }
        originalData[id][field] = currentValue;
        createEditor(cell, field, currentValue);
      } else {
        restoreCell(cell, field, originalData[id][field]);
      }
    });
  });
}

/**
 * REFACTORED HELPER: Sets up a single, global filter for all tabs.
 */
function setupGlobalFilter(searchInputId, searchClearId, tabNavSelector) {
  const searchInput = document.getElementById(searchInputId);
  const searchClear = document.getElementById(searchClearId);
  const tabNav = document.querySelector(tabNavSelector);

  if (!searchInput || !searchClear || !tabNav) {
    console.error("Global filter setup is missing required elements.");
    return;
  }

  const filterActiveTable = () => {
    const filter = searchInput.value.toUpperCase().trim();
    searchClear.style.display = filter.length > 0 ? "block" : "none";

    // Find the active tab and its table
    const activeTab = document.querySelector(
      ".tab-content[style*='display: block']"
    );
    if (!activeTab) return;

    const table = activeTab.querySelector("table");
    if (!table) return; // 'General' tab has no table

    const tbody = table.querySelector("tbody");
    if (!tbody) return;

    const rows = tbody.querySelectorAll("tr");
    rows.forEach((row) => {
      let rowText = "";
      row.querySelectorAll("td").forEach((cell) => {
        if (cell.querySelector('input[type="checkbox"]')) {
          rowText +=
            (cell.querySelector('input[type="checkbox"]').checked
              ? "TRUE"
              : "FALSE") + " ";
        } else {
          rowText += cell.textContent.toUpperCase() + " ";
        }
      });

      row.style.display = rowText.includes(filter) ? "" : "none";
    });
  };

  const clearSearch = () => {
    searchInput.value = "";
    filterActiveTable();
  };

  searchInput.addEventListener("keyup", filterActiveTable);
  searchClear.addEventListener("click", clearSearch);

  // Add listeners to all tab buttons to clear search on tab switch
  tabNav.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      // Use a short delay to allow the tab to switch *before* filtering
      setTimeout(() => {
        clearSearch();
      }, 0);
    });
  });

  // Initial run
  filterActiveTable();
}

/**
 * REFACTORED HELPER: Sets up inline editing for a table.
 */
function setupInlineEdit(config) {
  const {
    editBtnId,
    cancelBtnId,
    tableId,
    saveUrl,
    createEditor,
    restoreCell,
    getCellValue,
    updateCell,
  } = config;

  const editBtn = document.getElementById(editBtnId);
  const cancelBtn = document.getElementById(cancelBtnId);
  const tableBody = document.querySelector(`#${tableId} tbody`);

  if (!editBtn || !cancelBtn || !tableBody) {
    // Silently fail if elements aren't on the page
    return;
  }

  let isEditing = false;
  let originalData = {};

  const toggleEditFn = (enable) => {
    isEditing = enable;
    toggleEditMode({
      enable,
      editBtn,
      cancelBtn,
      tableBody,
      originalData,
      createEditor,
      restoreCell,
    });
  };

  const saveChangesFn = () => {
    saveTableChanges({
      tableBody,
      url: saveUrl,
      toggleEditFn,
      getCellValue,
      updateCell,
    });
  };

  editBtn.addEventListener("click", () => {
    if (isEditing) {
      saveChangesFn();
    } else {
      toggleEditFn(true);
    }
  });

  cancelBtn.addEventListener("click", () => {
    toggleEditFn(false);
  });
}

/**
 * Enhanced fetch with retry logic
 */
function fetchWithRetry(url, options = {}, retries = 3, retryDelay = 1000) {
  return fetch(url, options).catch((error) => {
    if (retries <= 0) throw error;
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(fetchWithRetry(url, options, retries - 1, retryDelay));
      }, retryDelay);
    });
  });
}

/**
 * Show notification to user
 */
function showNotification(message, type = "info") {
  // Remove existing notification
  const existingNotification = document.getElementById("settings-notification");
  if (existingNotification) {
    existingNotification.remove();
  }

  const notification = document.createElement("div");
  notification.id = "settings-notification";
  notification.className = `alert alert-${type} alert-dismissible fade show`;
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9999;
    min-width: 300px;
    max-width: 500px;
  `;

  notification.innerHTML = `
    ${message}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
  `;

  document.body.appendChild(notification);

  // Auto-remove after 5 seconds for success messages
  if (type === "success") {
    setTimeout(() => {
      if (notification.parentNode) {
        notification.remove();
      }
    }, 5000);
  }
}

function sortTableByColumn(table, column, asc = true) {
  const dirModifier = asc ? 1 : -1;
  const tBody = table.tBodies[0];
  const rows = Array.from(tBody.querySelectorAll("tr"));

  // Sort each row
  const sortedRows = rows.sort((a, b) => {
    const aCell = a.querySelector(`td:nth-child(${column + 1})`);
    const bCell = b.querySelector(`td:nth-child(${column + 1})`);

    const aCheckbox = aCell.querySelector('input[type="checkbox"]');
    const bCheckbox = bCell.querySelector('input[type="checkbox"]');

    if (aCheckbox && bCheckbox) {
      const aVal = aCheckbox.checked;
      const bVal = bCheckbox.checked;
      return aVal === bVal ? 0 : (aVal < bVal ? -1 : 1) * dirModifier;
    }

    const aColText = aCell.textContent.trim();
    const bColText = bCell.textContent.trim();

    // Check if the values are numbers and compare them as such
    if (
      !isNaN(aColText) &&
      !isNaN(bColText) &&
      aColText !== "" &&
      bColText !== ""
    ) {
      return (parseFloat(aColText) - parseFloat(bColText)) * dirModifier;
    } else {
      return (
        aColText.localeCompare(bColText, undefined, {
          numeric: true,
        }) * dirModifier
      );
    }
  });

  // Remove all existing TRs from the table
  while (tBody.firstChild) {
    tBody.removeChild(tBody.firstChild);
  }

  // Re-add the newly sorted rows
  tBody.append(...sortedRows);

  // Update the sort direction attribute on the header
  table
    .querySelectorAll("th")
    .forEach((th) => th.removeAttribute("data-sort-dir"));
  table
    .querySelector(`th:nth-child(${column + 1})`)
    .setAttribute("data-sort-dir", asc ? "asc" : "desc");
}

/**
 * All setup logic for the settings page.
 */
document.addEventListener("DOMContentLoaded", () => {
  // --- 1. Tab Logic ---
  const generalTab = document.getElementById("general");
  if (generalTab) {
    generalTab.style.display = "block";
  }

  const urlParams = new URLSearchParams(window.location.search);
  const defaultTab = urlParams.get("default_tab");
  if (defaultTab) {
    openTab(null, defaultTab);
  }
  // Attach openTab to window for inline onclick attributes
  window.openTab = openTab;

  // --- 2. Modal Logic ---
  // Attach closeModal to window for inline onclick attributes
  window.closeModal = closeModal;

  // "Add Session" modal
  const addSessionBtn = document.getElementById("add-session-btn");
  const sessionModal = document.getElementById("addSessionModal");
  if (addSessionBtn && sessionModal) {
    addSessionBtn.addEventListener("click", () => {
      sessionModal.style.display = "flex";
    });
  }

  // "Add Role" modal
  const addRoleBtn = document.getElementById("add-role-btn");
  const roleModal = document.getElementById("addRoleModal");
  if (addRoleBtn && roleModal) {
    addRoleBtn.addEventListener("click", () => {
      roleModal.style.display = "flex";
    });
  }

  // "Add Level Role" modal
  const addLevelRoleBtn = document.getElementById("add-level-role-btn");
  const levelRoleModal = document.getElementById("addLevelRoleModal");
  if (addLevelRoleBtn && levelRoleModal) {
    addLevelRoleBtn.addEventListener("click", () => {
      levelRoleModal.style.display = "flex";
    });
  }

  // "Add Presentation" modal
  const addPresentationBtn = document.getElementById("add-presentation-btn");
  const presentationModal = document.getElementById("addPresentationModal");
  if (addPresentationBtn && presentationModal) {
    addPresentationBtn.addEventListener("click", () => {
      presentationModal.style.display = "flex";
    });
  }

  // Generic modal close-on-click-outside logic
  window.addEventListener("click", (event) => {
    if (event.target.classList.contains("modal")) {
      event.target.style.display = "none";
    }
  });

  // --- 3. Sortable & Filterable Table Setup ---
  // A. Setup Sorting for each table by calling the new main.js function
  function setupTableSorting(tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;

    table.querySelectorAll("th.sortable").forEach((headerCell) => {
      headerCell.addEventListener("click", () => {
        const columnIndex = parseInt(headerCell.dataset.columnIndex, 10);
        const currentDir = headerCell.dataset.sortDir;
        const newDir = currentDir === "asc" ? "desc" : "asc";

        sortTableByColumn(table, columnIndex, newDir === "asc");

        table
          .querySelectorAll("th.sortable")
          .forEach((th) => delete th.dataset.sortDir);

        headerCell.dataset.sortDir = newDir;
      });
    });
  }
  setupTableSorting("sessions-table");
  setupTableSorting("user-settings-table");
  setupTableSorting("level-roles-table");
  setupTableSorting("presentations-table");
  setupTableSorting("roles-table");

  // B. Setup the ONE Global Filter
  setupGlobalFilter(
    "global-settings-search",
    "clear-global-settings-search",
    ".tab-nav"
  );

  // --- 4. Inline-Editable Table Setup ---

  // 4a. Session Types
  setupInlineEdit({
    editBtnId: "edit-sessions-btn",
    cancelBtnId: "cancel-sessions-btn",
    tableId: "sessions-table",
    saveUrl: "/settings/sessions/update",
    createEditor: (cell, field, currentValue) => {
      if (
        field.startsWith("Is_") ||
        field === "Valid_for_Project" ||
        field == "Predefined"
      ) {
        cell.querySelector('input[type="checkbox"]').disabled = false;
      } else if (field === "role_id") {
        const select = document.createElement("select");
        select.className = "form-control-sm";

        // Add a "None" option
        const noneOption = new Option("None", "");
        select.appendChild(noneOption);

        // Populate with roles from global data
        ROLES_DATA.forEach((role) => {
          const option = new Option(role.name, role.id);
          if (role.name === currentValue) {
            option.selected = true;
          }
          select.appendChild(option);
        });

        cell.textContent = "";
        cell.appendChild(select);
      } else {
        const input = document.createElement("input");
        input.type = field.includes("Duration") ? "number" : "text";
        input.value = currentValue;
        input.className = "form-control-sm";
        cell.textContent = "";
        cell.appendChild(input);
      }
    },
    restoreCell: (cell, field, originalValue) => {
      if (
        field.startsWith("Is_") ||
        field === "Valid_for_Project" ||
        field == "Predefined"
      ) {
        cell.innerHTML = `<input type="checkbox" ${originalValue ? "checked" : ""
          } disabled>`;
      } else {
        cell.textContent = originalValue;
      }
    },
    getCellValue: (cell, field) => {
      if (
        field.startsWith("Is_") ||
        field === "Valid_for_Project" ||
        field == "Predefined"
      ) {
        return cell.querySelector('input[type="checkbox"]').checked;
      } else if (field === "role_id") {
        const select = cell.querySelector("select");
        return select.value;
      } else {
        return cell.querySelector("input").value;
      }
    },
    updateCell: (cell, field, value) => {
      if (
        field.startsWith("Is_") ||
        field === "Valid_for_Project" ||
        field == "Predefined"
      ) {
        cell.innerHTML = `<input type="checkbox" ${value ? "checked" : ""
          } disabled>`;
      } else if (field === "role_id") {
        const selectedRole = ROLES_DATA.find((role) => role.id == value);
        cell.textContent = selectedRole ? selectedRole.name : "";
      } else {
        cell.textContent = value;
      }
    },
  });

  // 4b. Level Roles
  setupInlineEdit({
    editBtnId: "edit-level-roles-btn",
    cancelBtnId: "cancel-level-roles-btn",
    tableId: "level-roles-table",
    saveUrl: "/settings/level-roles/update",
    createEditor: (cell, field, currentValue) => {
      if (field === "type") {
        const select = document.createElement("select");
        select.className = "form-control-sm";
        ["required", "elective"].forEach((opt) => {
          const option = new Option(opt, opt);
          if (opt === currentValue.toLowerCase()) option.selected = true;
          select.appendChild(option);
        });
        cell.textContent = "";
        cell.appendChild(select);
      } else {
        const input = document.createElement("input");
        input.type =
          field.includes("level") || field.includes("count")
            ? "number"
            : "text";
        input.value = currentValue;
        input.className = "form-control-sm";
        cell.textContent = "";
        cell.appendChild(input);
      }
    },
    restoreCell: (cell, field, originalValue) => {
      cell.textContent = originalValue;
    },
    getCellValue: (cell, field) => {
      const input = cell.querySelector("input, select");
      return input ? input.value : cell.textContent;
    },
    updateCell: (cell, field, value) => {
      cell.textContent = value;
    },
  });

  // 4c. Presentations
  setupInlineEdit({
    editBtnId: "edit-presentations-btn",
    cancelBtnId: "cancel-presentations-btn",
    tableId: "presentations-table",
    saveUrl: "/settings/presentations/update",
    createEditor: (cell, field, currentValue) => {
      const input = document.createElement("input");
      input.type = field === "level" ? "number" : "text";
      input.value = currentValue;
      input.className = "form-control-sm";
      cell.textContent = "";
      cell.appendChild(input);
    },
    restoreCell: (cell, field, originalValue) => {
      cell.textContent = originalValue;
    },
    getCellValue: (cell, field) => {
      const input = cell.querySelector("input");
      return input ? input.value : cell.textContent;
    },
    updateCell: (cell, field, value) => {
      cell.textContent = value;
    },
  });

  // 4d. Roles
  setupInlineEdit({
    editBtnId: "edit-roles-btn",
    cancelBtnId: "cancel-roles-btn",
    tableId: "roles-table",
    saveUrl: "/settings/roles/update",
    createEditor: (cell, field, currentValue) => {
      if (field === "needs_approval" || field === "is_distinct") {
        cell.querySelector('input[type="checkbox"]').disabled = false;
      } else if (field === "type") {
        const select = document.createElement("select");
        select.className = "form-control-sm";
        ["standard", "club-specific", "officer"].forEach((opt) => {
          const option = new Option(opt, opt);
          if (opt === currentValue) option.selected = true;
          select.appendChild(option);
        });
        cell.textContent = "";
        cell.appendChild(select);
      } else if (field === "award_category") {
        const select = document.createElement("select");
        select.className = "form-control-sm";
        // Empty option for 'none'
        select.appendChild(new Option("none", ""));
        ["speaker", "evaluator", "role-taker", "table-topic"].forEach((opt) => {
          const option = new Option(opt, opt);
          if (opt === currentValue) option.selected = true;
          select.appendChild(option);
        });
        cell.textContent = "";
        cell.appendChild(select);
      } else {
        const input = document.createElement("input");
        input.type = "text";
        input.value = currentValue;
        input.className = "form-control-sm";
        cell.textContent = "";
        cell.appendChild(input);
      }
    },
    restoreCell: (cell, field, originalValue) => {
      if (field === "needs_approval" || field === "is_distinct") {
        cell.innerHTML = `<input type="checkbox" ${originalValue ? "checked" : ""
          } disabled>`;
      } else if (field === "icon") {
        cell.innerHTML = `<i class="${originalValue}"></i> ${originalValue}`;
      } else {
        cell.textContent = originalValue;
      }
    },
    getCellValue: (cell, field) => {
      if (field === "needs_approval" || field === "is_distinct") {
        return cell.querySelector('input[type="checkbox"]').checked;
      } else {
        const input = cell.querySelector("input, select");
        return input ? input.value : "";
      }
    },
    updateCell: (cell, field, value) => {
      if (field === "needs_approval" || field === "is_distinct") {
        cell.innerHTML = `<input type="checkbox" ${value ? "checked" : ""
          } disabled>`;
      } else if (field === "icon") {
        cell.innerHTML = `<i class="${value}"></i> ${value}`;
      } else {
        cell.textContent = value;
      }
    },
  });

  // --- 5. Bulk Import Logic ---
  const bulkImportForm = document.getElementById("bulk-import-form");
  const bulkImportFile = document.getElementById("bulk-import-file");
  const bulkImportBtn = document.getElementById("bulk-import-btn");

  if (bulkImportForm && bulkImportFile && bulkImportBtn) {
    bulkImportBtn.addEventListener("click", () => {
      bulkImportFile.click(); // Trigger file input click
    });

    bulkImportFile.addEventListener("change", () => {
      bulkImportForm.submit(); // Submit form when file is selected
    });
  }

  const importRolesForm = document.getElementById("import-roles-form");
  const importRolesFile = document.getElementById("import-roles-file");
  const importRolesBtn = document.getElementById("import-roles-btn");

  if (importRolesForm && importRolesFile && importRolesBtn) {
    importRolesBtn.addEventListener("click", () => {
      importRolesFile.click();
    });

    importRolesFile.addEventListener("change", () => {
      importRolesForm.submit();
    });
  }

  // --- 6. AJAX Form Submission for "Add Session Type" ---
  const addSessionForm = document.getElementById("addSessionForm");
  if (addSessionForm) {
    addSessionForm.addEventListener("submit", function (event) {
      event.preventDefault(); // Prevent the default form submission

      const formData = new FormData(this);
      const url = this.action;

      fetch(url, {
        method: "POST",
        body: formData,
      })
        .then((response) => {
          if (!response.ok) {
            // Try to get error message from JSON response
            return response.json().then((err) => {
              throw new Error(
                err.message || `HTTP error! status: ${response.status}`
              );
            });
          }
          return response.json();
        })
        .then((data) => {
          if (data.success) {
            // Add the new row to the table
            addSessionRowToTable(data.new_session);

            // Close modal and reset form
            closeModal("addSessionModal");
            this.reset();

            // Show success notification
            showNotification("Session type added successfully!", "success");
          } else {
            // Show error from server
            showNotification(data.message, "error");
          }
        })
        .catch((error) => {
          console.error("Error:", error);
          showNotification(`An error occurred: ${error.message}`, "error");
        });
    });
  }

  /**
   * Dynamically adds a new session type row to the sessions table.
   * @param {object} sessionData - The data for the new session from the server.
   */
  function addSessionRowToTable(sessionData) {
    const tableBody = document.querySelector("#sessions-table tbody");
    if (!tableBody) return;

    const newRow = tableBody.insertRow();
    newRow.dataset.id = sessionData.id;

    const roleName = sessionData.role_id
      ? ROLES_DATA.find((r) => r.id == sessionData.role_id)?.name || ""
      : "";

    newRow.innerHTML = `
      <td data-field="Title">${sessionData.Title || ""}</td>
      <td data-field="Default_Owner">${sessionData.Default_Owner || ""}</td>
      <td data-field="role_id">${roleName}</td>
      <td data-field="Duration_Min">${sessionData.Duration_Min || ""}</td>
      <td data-field="Duration_Max">${sessionData.Duration_Max || ""}</td>
      <td data-field="Is_Section">
        <input type="checkbox" ${sessionData.Is_Section ? "checked" : ""
      } disabled>
      </td>
      <td data-field="Predefined">
        <input type="checkbox" ${sessionData.Predefined ? "checked" : ""
      } disabled>
      </td>
      <td data-field="Valid_for_Project">
        <input type="checkbox" ${sessionData.Valid_for_Project ? "checked" : ""
      } disabled>
      </td>
      <td data-field="Is_Hidden">
        <input type="checkbox" ${sessionData.Is_Hidden ? "checked" : ""
      } disabled>
      </td>
    `;

    // Re-apply sorting if a sort order is active
    const activeSortHeader = document.querySelector(
      "#sessions-table th[data-sort-dir]"
    );
    if (activeSortHeader) {
      const table = document.getElementById("sessions-table");
      const columnIndex = parseInt(activeSortHeader.dataset.columnIndex, 10);
      const sortDir = activeSortHeader.dataset.sortDir;
      sortTableByColumn(table, columnIndex, sortDir === "asc");
    }

    // Re-apply filter if a filter is active
    const searchInput = document.getElementById("global-settings-search");
    if (searchInput && searchInput.value) {
      const filter = searchInput.value.toUpperCase().trim();
      const rowText = newRow.textContent.toUpperCase();
      newRow.style.display = rowText.includes(filter) ? "" : "none";
    }
  }
});
