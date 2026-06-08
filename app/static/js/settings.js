// static/js/settings.js
const ICON_LIST = [
  {
    group: "Core Roles", icons: [
      { value: "fa-microphone", label: "Microphone (Speaker/TM)" },
      { value: "fa-stopwatch", label: "Stopwatch (Timer)" },
      { value: "fa-edit", label: "Edit (Evaluator)" },
      { value: "fa-book", label: "Book (Grammarian)" },
      { value: "fa-calculator", label: "Calculator (Ah-Counter/Vote)" },
      { value: "fa-comments", label: "Comments (Topicsmaster)" },
      { value: "fa-comment", label: "Comment (Topics Speaker)" },
      { value: "fa-search", label: "Search (Gen. Eval)" },
      { value: "fa-user-tie", label: "User Tie (Prepared Speaker)" },
      { value: "fa-lightbulb", label: "Lightbulb (Table Topics)" }
    ]
  },
  {
    group: "Officers & Leadership", icons: [
      { value: "fa-gavel", label: "Gavel (President/Judge)" },
      { value: "fa-crown", label: "Crown (President)" },
      { value: "fa-graduation-cap", label: "Graduation Cap (VPE)" },
      { value: "fa-users-cog", label: "Users Cog (VPE/VPM)" },
      { value: "fa-users", label: "Users (VPM)" },
      { value: "fa-bullhorn", label: "Bullhorn (VPPR)" },
      { value: "fa-newspaper", label: "Newspaper (VPPR)" },
      { value: "fa-coins", label: "Coins (Treasurer)" },
      { value: "fa-pen-nib", label: "Pen Nib (Secretary)" },
      { value: "fa-briefcase", label: "Briefcase (SAA)" },
      { value: "fa-landmark", label: "Landmark" },
      { value: "fa-university", label: "University/Building" }
    ]
  },
  {
    group: "Communication & Tools", icons: [
      { value: "fa-handshake", label: "Handshake (Greeter)" },
      { value: "fa-hand-holding-heart", label: "Hand Holding Heart (Greeter)" },
      { value: "fa-chalkboard", label: "Chalkboard (Mentor/Trainer)" },
      { value: "fa-desktop", label: "Desktop (Zoom Master)" },
      { value: "fa-laptop", label: "Laptop" },
      { value: "fa-video", label: "Video" },
      { value: "fa-headphones", label: "Headphones" },
      { value: "fa-podcast", label: "Podcast" },
      { value: "fa-microphone-alt", label: "Microphone Alt" },
      { value: "fa-volume-up", label: "Volume" },
      { value: "fa-bullseye", label: "Bullseye (Goals)" },
      { value: "fa-puzzle-piece", label: "Puzzle Piece" },
      { value: "fa-link", label: "Link" },
      { value: "fa-cog", label: "Gear" },
      { value: "fa-wrench", label: "Wrench" },
      { value: "fa-hammer", label: "Hammer" }
    ]
  },
  {
    group: "Achievements & Symbols", icons: [
      { value: "fa-trophy", label: "Trophy" },
      { value: "fa-medal", label: "Medal" },
      { value: "fa-award", label: "Award" },
      { value: "fa-certificate", label: "Certificate" },
      { value: "fa-star", label: "Star" },
      { value: "fa-heart", label: "Heart" },
      { value: "fa-flag", label: "Flag" },
      { value: "fa-check-double", label: "Check Double" },
      { value: "fa-info-circle", label: "Info" },
      { value: "fa-question-circle", label: "Question" },
      { value: "fa-bolt", label: "Bolt" },
      { value: "fa-rocket", label: "Rocket" },
      { value: "fa-key", label: "Key" },
      { value: "fa-chart-line", label: "Chart Line" },
      { value: "fa-chart-pie", label: "Chart Pie" }
    ]
  },
  {
    group: "Social & Fun", icons: [
      { value: "fa-smile", label: "Smile Face" },
      { value: "fa-laugh-squint", label: "Laugh Face" },
      { value: "fa-grin-stars", label: "Grin Stars" },
      { value: "fa-birthday-cake", label: "Celebration" },
      { value: "fa-mug-hot", label: "Coffee/Break" },
      { value: "fa-music", label: "Music" },
      { value: "fa-camera", label: "Camera" },
      { value: "fa-palette", label: "Palette" },
      { value: "fa-globe-americas", label: "Earth" },
      { value: "fa-globe", label: "Globe" },
      { value: "fa-sun", label: "Sun" },
      { value: "fa-moon", label: "Moon" },
      { value: "fa-leaf", label: "Leaf" }
    ]
  }
];

/**
 * Handles switching tabs on the settings page.
 */
function openTab(evt, tabName) {
  const tabcontent = document.getElementsByClassName("tab-content");
  for (let i = 0; i < tabcontent.length; i++) {
    tabcontent[i].style.display = "none";
  }

  const tablinks = document.getElementsByClassName("nav-item");
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

  // Save active tab
  localStorage.setItem("settings_active_tab", tabName);

  // Trigger pagination update for the active tab's table if it has a paginator
  if (window.activePaginators) {
    const paginator = window.activePaginators[tabName];
    if (paginator) {
      paginator.currentPage = 1;
      paginator.update();
    }
  }
}

/**
 * Initializes the icon matrix in the role modal.
 */
function initIconMatrix() {
  const container = document.getElementById("icon-matrix-container");
  const hiddenInput = document.getElementById("icon");

  if (!container) {
    console.error("icon-matrix-container not found");
    return;
  }
  if (!hiddenInput) {
    console.error("hidden icon input not found");
    return;
  }

  // Clear existing content except the hidden input
  Array.from(container.children).forEach(child => {
    if (child.id !== "icon") child.remove();
  });

  // Add Grouped Icons
  ICON_LIST.forEach((group) => {
    const title = document.createElement("div");
    title.className = "icon-group-title";
    title.textContent = group.group;
    container.appendChild(title);

    const grid = document.createElement("div");
    grid.className = "icon-matrix";

    // If this is the "Core Roles" group, prepend "None" option
    if (group.group === "Core Roles") {
      const noneItem = document.createElement("div");
      noneItem.className = "icon-item active";
      noneItem.dataset.value = "";
      noneItem.title = "None";
      noneItem.innerHTML = `<i class="fas fa-ban"></i>`;
      noneItem.addEventListener("click", () => {
        container.querySelectorAll(".icon-item").forEach(i => i.classList.remove("active"));
        noneItem.classList.add("active");
        hiddenInput.value = "";
      });
      grid.appendChild(noneItem);
    }

    group.icons.forEach((icon) => {
      const item = document.createElement("div");
      item.className = "icon-item";
      item.dataset.value = icon.value;
      item.title = icon.label;
      item.innerHTML = `<i class="fas ${icon.value}"></i>`;

      item.addEventListener("click", () => {
        container.querySelectorAll(".icon-item").forEach(i => i.classList.remove("active"));
        item.classList.add("active");
        hiddenInput.value = icon.value;
      });
      grid.appendChild(item);
    });
    container.appendChild(grid);
  });
}

/**
 * Class to handle client-side table pagination
 */
class TablePaginator {
  constructor(config) {
    this.tableId = config.tableId;
    this.containerId = config.containerId;
    this.pageSize = config.pageSize || 10;
    this.currentPage = 1;
    this.storageKey = config.storageKey;

    this.table = document.getElementById(this.tableId);
    this.container = document.getElementById(this.containerId);

    if (!this.table || !this.container) return;

    this.tbody = this.table.querySelector('tbody');
    this.infoDisplay = this.container.querySelector('.pagination-info');
    this.currentPageDisplay = this.container.querySelector('.current-page-display');
    this.totalPagesDisplay = this.container.querySelector('.total-pages-display');
    this.pageSizeSelect = this.container.querySelector('.page-size-select');

    this.firstBtn = this.container.querySelector('.first-page-btn');
    this.prevBtn = this.container.querySelector('.prev-page-btn');
    this.nextBtn = this.container.querySelector('.next-page-btn');
    this.lastBtn = this.container.querySelector('.last-page-btn');

    this.init();
  }

  init() {
    // Load saved page size
    if (this.storageKey) {
      const savedSize = localStorage.getItem(`${this.storageKey}_page_size`);
      if (savedSize) {
        this.pageSize = parseInt(savedSize);
        if (this.pageSizeSelect) this.pageSizeSelect.value = this.pageSize;
      }
    }

    // Event listeners
    if (this.pageSizeSelect) {
      this.pageSizeSelect.addEventListener('change', (e) => {
        this.pageSize = parseInt(e.target.value);
        this.currentPage = 1;
        if (this.storageKey) {
          localStorage.setItem(`${this.storageKey}_page_size`, this.pageSize);
        }
        this.update();
      });
    }

    if (this.firstBtn) this.firstBtn.addEventListener('click', () => { this.currentPage = 1; this.update(); });
    if (this.prevBtn) this.prevBtn.addEventListener('click', () => { this.currentPage = Math.max(1, this.currentPage - 1); this.update(); });
    if (this.nextBtn) this.nextBtn.addEventListener('click', () => { this.currentPage++; this.update(); });
    if (this.lastBtn) this.lastBtn.addEventListener('click', () => { this.currentPage = this.getTotalPages(); this.update(); });

    this.update();
  }

  getFilteredRows() {
    // Return rows that are not hidden by the search filter and are not sub-rows
    return Array.from(this.tbody.rows).filter(row => {
      const isHiddenBySearch = row.getAttribute('data-search-hidden') === 'true';
      const isSubRow = row.hasAttribute('data-parent-id');
      return !isHiddenBySearch && !isSubRow;
    });
  }

  getTotalPages() {
    const rows = this.getFilteredRows();
    return Math.ceil(rows.length / this.pageSize) || 1;
  }

  update() {
    const rows = Array.from(this.tbody.rows);
    const filteredRows = this.getFilteredRows();
    const totalPages = this.getTotalPages();

    if (this.currentPage > totalPages) this.currentPage = totalPages;
    if (this.currentPage < 1) this.currentPage = 1;

    const startIndex = (this.currentPage - 1) * this.pageSize;
    const endIndex = startIndex + this.pageSize;

    // Create a Set of rows that should be visible (on current page)
    const visibleRows = new Set(filteredRows.slice(startIndex, endIndex));

    // Show/hide rows
    rows.forEach((row) => {
      const parentId = row.getAttribute('data-parent-id');
      if (parentId) {
        // It's a sub-row. Visibility depends on parent row being visible AND expanded.
        const parentRow = this.tbody.querySelector(`tr[data-id="${parentId}"]`);
        if (visibleRows.has(parentRow) && parentRow.classList.contains('expanded')) {
          row.style.display = "";
        } else {
          row.style.display = "none";
        }
      } else {
        // It's a top-level row
        if (visibleRows.has(row)) {
          row.style.display = "";
        } else {
          row.style.display = "none";
        }
      }
    });

    // Update displays
    const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
    if (this.infoDisplay) {
      if (rows.length === 0) {
        this.infoDisplay.textContent = isChinese ? '没有找到记录' : 'No records found';
      } else {
        this.infoDisplay.textContent = isChinese
          ? `显示第 ${startIndex + 1} - ${Math.min(endIndex, rows.length)} 条记录，共 ${rows.length} 条`
          : `Showing ${startIndex + 1} - ${Math.min(endIndex, rows.length)} of ${rows.length}`;
      }
    }

    if (this.currentPageDisplay) this.currentPageDisplay.textContent = this.currentPage;
    if (this.totalPagesDisplay) this.totalPagesDisplay.textContent = totalPages;

    // Update buttons
    if (this.firstBtn) this.firstBtn.disabled = this.currentPage === 1;
    if (this.prevBtn) this.prevBtn.disabled = this.currentPage === 1;
    if (this.nextBtn) this.nextBtn.disabled = this.currentPage >= totalPages;
    if (this.lastBtn) this.lastBtn.disabled = this.currentPage >= totalPages;
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
        const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
        showNotification(isChinese ? "修改保存成功！" : "Changes saved successfully!", "success");
      } else {
        throw new Error(data.message || "Request failed");
      }
    })
    .catch((error) => {
      console.error("Save error:", error);
      const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
      showNotification(isChinese ? `保存修改时出错: ${error.message}` : `Error saving changes: ${error.message}`, "error");
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
  const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
  editBtn.textContent = enable 
    ? (isChinese ? "保存" : "Save") 
    : (isChinese ? "编辑" : "Edit");
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
          field == "needs_approval" ||
          field == "has_single_owner" ||
          field == "is_member_only"
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
    const activeTab = Array.from(document.querySelectorAll(".tab-content")).find(
      (el) =>
        el.style.display === "block" ||
        window.getComputedStyle(el).display === "block"
    );
    if (!activeTab) return;

    const tables = activeTab.querySelectorAll("table");
    if (!tables || tables.length === 0) return;

    tables.forEach(table => {
      const tbody = table.querySelector("tbody");
      if (!tbody) return;

      const categoryMatches = {};
      const rows = tbody.querySelectorAll("tr");
      
      rows.forEach((row) => {
        if (row.classList.contains('category-row')) {
          return;
        }
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

        const isMatch = rowText.includes(filter);
        row.setAttribute('data-search-hidden', isMatch ? 'false' : 'true');
        
        if (isMatch) {
          const categoryClass = Array.from(row.classList).find(c => c.startsWith('category-group-'));
          if (categoryClass) {
            categoryMatches[categoryClass] = true;
          }
        }
      });

      // Simple immediate visibility update for safety (overridden by paginator if active)
      rows.forEach(row => {
        if (row.classList.contains('category-row')) {
          if (filter.length === 0) {
            row.style.display = "";
          } else {
            const onclickAttr = row.getAttribute('onclick') || '';
            const match = onclickAttr.match(/toggleCategory\('([^']+)'/);
            const slug = match ? match[1] : '';
            const hasMatch = categoryMatches[`category-group-${slug}`];
            if (hasMatch) {
              row.style.display = "";
              row.classList.remove('collapsed');
              const icon = row.querySelector('.toggle-icon');
              if (icon) {
                icon.className = 'fas fa-chevron-down toggle-icon';
              }
            } else {
              row.style.display = "none";
            }
          }
        } else {
          const isSearchHidden = row.getAttribute('data-search-hidden') === 'true';
          if (isSearchHidden) {
            row.style.display = "none";
          } else {
            if (filter.length === 0) {
              const categoryClass = Array.from(row.classList).find(c => c.startsWith('category-group-'));
              const slug = categoryClass ? categoryClass.replace('category-group-', '') : '';
              const catRow = tbody.querySelector(`.category-row[onclick*="'${slug}'"]`);
              const isCollapsed = catRow ? catRow.classList.contains('collapsed') : false;
              row.style.display = isCollapsed ? "none" : "";
            } else {
              row.style.display = "";
            }
          }
        }
      });
    });

    // Notify paginator if active (assuming it manages the 'main' table)
    if (window.activePaginators) {
      const activeTabId = activeTab.id;
      const paginator = window.activePaginators[activeTabId];
      if (paginator) {
        paginator.currentPage = 1;
        paginator.update();
      }
    }
  };

  const clearSearch = () => {
    searchInput.value = "";
    filterActiveTable();
  };

  searchInput.addEventListener("keyup", filterActiveTable);
  searchClear.addEventListener("click", clearSearch);

  // Add listeners to all tab buttons to clear search on tab switch
  tabNav.querySelectorAll(".nav-item").forEach((btn) => {
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
 * HELPER: Check if a field is a boolean/checkbox field
 */
function isBooleanField(field) {
  return (
    field.startsWith("Is_") ||
    field === "Valid_for_Project" ||
    field === "needs_approval" ||
    field === "has_single_owner" ||
    field === "is_member_only"
  );
}

/**
 * HELPER: Render checkbox HTML
 */
function renderCheckbox(checked, disabled = true) {
  return `<input type="checkbox" ${checked ? "checked" : ""} ${disabled ? "disabled" : ""}>`;
}

/**
 * HELPER: Get value from a cell (handles checkboxes, selects, and inputs)
 */
function getCellValueGeneric(cell, field) {
  if (isBooleanField(field)) {
    return cell.querySelector('input[type="checkbox"]').checked;
  }
  const input = cell.querySelector("input, select");
  return input ? input.value : cell.textContent.trim();
}

/**
 * HELPER: Setup modal open/close behavior
 */
function setupModal(buttonId, modalId) {
  const button = document.getElementById(buttonId);
  const modal = document.getElementById(modalId);
  if (button && modal) {
    button.addEventListener("click", () => {
      modal.style.display = "flex";
    });
  }
}

/**
 * HELPER: Setup table sorting for a given table ID
 */
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

  // --- NEW: Notify paginator if one is attached to this table ---
  if (window.activePaginators) {
    Object.values(window.activePaginators).forEach(paginator => {
      if (paginator.tableId === table.id) {
        paginator.currentPage = 1;
        paginator.update();
      }
    });
  }
}

// Attach functions to window immediately so inline onclick handlers work
window.openTab = openTab;
window.closeModal = closeModal;

/**
 * All setup logic for the settings page.
 */
document.addEventListener("DOMContentLoaded", () => {
  const urlParams = new URLSearchParams(window.location.search);


  const defaultTab = urlParams.get("default_tab");
  const savedTab = localStorage.getItem("settings_active_tab");

  if (defaultTab) {
    openTab(null, defaultTab);
  } else if (savedTab) {
    openTab(null, savedTab);
  } else {
    // Default to general if nothing is set
    openTab(null, "excomm-settings");
  }

  // --- 2. Modal Logic ---
  // Initialize icon matrix for role modal
  initIconMatrix();

  const addSessionBtn = document.getElementById("add-session-btn");
  if (addSessionBtn) {
    addSessionBtn.addEventListener("click", () => {
      const modal = document.getElementById("addSessionModal");
      const title = document.getElementById("session-modal-title");
      const submitBtn = document.getElementById("session-modal-submit");
      const form = document.getElementById("addSessionForm");

      if (modal && title && submitBtn && form) {
        const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
        title.textContent = isChinese ? "添加新环节类型" : "Add New Session Type";
        submitBtn.textContent = isChinese ? "保存" : "Save";
        form.reset();
        document.getElementById("session_id_input").value = "";
        modal.style.display = "flex";
      }
    });
  }

  const addRoleBtn = document.getElementById("add-role-btn");
  if (addRoleBtn) {
    addRoleBtn.addEventListener("click", () => {

      const modal = document.getElementById("addRoleModal");
      const title = document.getElementById("role-modal-title");
      const submitBtn = document.getElementById("role-modal-submit");
      const form = document.getElementById("addRoleForm");

      if (modal && title && submitBtn && form) {
        const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
        title.textContent = isChinese ? "添加新角色" : "Add New Role";
        submitBtn.textContent = isChinese ? "保存" : "Save";
        form.reset();
        document.getElementById("role_id_input").value = "";

        // Reset matrix selection to "None"
        const container = document.getElementById("icon-matrix-container");
        if (container) {
          container.querySelectorAll(".icon-item").forEach(i => i.classList.remove("active"));
          const noneItem = container.querySelector('.icon-item[data-value=""]');
          if (noneItem) noneItem.classList.add("active");
          const hiddenInput = document.getElementById("icon");
          if (hiddenInput) hiddenInput.value = "";
        }

        // Logic for Type selector based on Club ID
        const typeRadios = document.querySelectorAll('input[name="type"]');
        if (typeof CURRENT_CLUB_ID !== 'undefined') {
          typeRadios.forEach(radio => {
            const label = radio.parentElement;
            if (!label) return;

            if (CURRENT_CLUB_ID === 1) {
              // Club 1: Hide "club-specific", show others
              if (radio.value === 'club-specific') {
                label.style.display = 'none';
              } else {
                label.style.display = 'flex';
              }
            } else {
              // Other clubs: Hide "Standard" option (value="standard")
              // Show all others.
              if (radio.value === 'standard') {
                label.style.display = 'none';
              } else {
                label.style.display = 'flex';
              }
            }
          });

          // Set default selection based on visibility
          // For non-club 1, fail safe to 'club-specific' if not editing
          if (CURRENT_CLUB_ID !== 1) {
            const clubSpecific = document.querySelector('input[name="type"][value="club-specific"]');
            if (clubSpecific) clubSpecific.checked = true;
          } else {
            const standard = document.querySelector('input[name="type"][value="standard"]');
            if (standard) standard.checked = true;
          }
        }

        modal.style.display = "flex";
      }
    });
  }




  // Generic modal close-on-click-outside logic
  window.addEventListener("click", (event) => {
    if (event.target.classList.contains("modal")) {
      event.target.style.display = "none";
    }
  });

  // --- 3. Sortable & Filterable Table Setup ---
  setupTableSorting("global-sessions-table");
  if (document.getElementById("global-sessions-table")) {
    sortTableByColumn(document.getElementById("global-sessions-table"), 1, true);
  }
  setupTableSorting("sessions-table");
  sortTableByColumn(document.getElementById("sessions-table"), 1, true);

  setupTableSorting("user-settings-table");

  setupTableSorting("global-roles-table");
  if (document.getElementById("global-roles-table")) {
    sortTableByColumn(document.getElementById("global-roles-table"), 1, true);
  }
  setupTableSorting("roles-table");
  sortTableByColumn(document.getElementById("roles-table"), 1, true);

  // B. Setup the ONE Global Filter
  setupGlobalFilter(
    "global-settings-search",
    "clear-global-settings-search",
    ".nav-tabs"
  );

  // --- 4. Inline-Editable Table Setup ---

  // 4a. Session Types
  // Legacy Inline Editing removed in favor of modal editing.


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



  // --- 6. AJAX Form Submission for Modals ---
  const addSessionForm = document.getElementById("addSessionForm");
  if (addSessionForm) {
    addSessionForm.addEventListener("submit", function (event) {
      event.preventDefault();

      const formData = new FormData(this);
      const url = this.action;
      const isUpdate = document.getElementById("session_id_input").value !== "";

      fetch(url, {
        method: "POST",
        body: formData,
      })
        .then((response) => {
          if (!response.ok) {
            return response.json().then((err) => {
              throw new Error(err.message || `HTTP error! status: ${response.status}`);
            });
          }
          return response.json();
        })
        .then((data) => {
          if (data.success) {
            addSessionRowToTable(data.new_session);
            closeModal("addSessionModal");
            this.reset();
            // showNotification(data.message, "success");
          } else {
            showNotification(data.message, "error");
          }
        })
        .catch((error) => {
          console.error("Error:", error);
          showNotification(`An error occurred: ${error.message}`, "error");
        });
    });
  }

  const addRoleForm = document.getElementById("addRoleForm");
  if (addRoleForm) {
    addRoleForm.addEventListener("submit", function (event) {
      event.preventDefault();

      const formData = new FormData(this);
      const url = this.action;

      fetch(url, {
        method: "POST",
        body: formData,
      })
        .then((response) => {
          if (!response.ok) {
            return response.json().then((err) => {
              throw new Error(err.message || `HTTP error! status: ${response.status}`);
            });
          }
          return response.json();
        })
        .then((data) => {
          if (data.success) {
            addRoleRowToTable(data.new_role);
            closeModal("addRoleModal");
            this.reset();
            // showNotification(data.message, "success");

            // Update ROLES_DATA for session role dropdown
            const existingIndex = ROLES_DATA.findIndex(r => r.id == data.new_role.id);
            if (existingIndex !== -1) {
              ROLES_DATA[existingIndex] = { id: data.new_role.id, name: data.new_role.name };
            } else {
              ROLES_DATA.push({ id: data.new_role.id, name: data.new_role.name });
            }
          } else {
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
   * Dynamically adds or updates a session type row.
   */
  function addSessionRowToTable(sessionData) {
    const tableBody = document.querySelector("#sessions-table tbody");
    if (!tableBody) return;

    let row = tableBody.querySelector(`tr[data-id="${sessionData.id}"]`);
    const isNew = !row;
    if (isNew) {
      row = tableBody.insertRow();
      row.dataset.id = sessionData.id;
    }

    const roleObj = sessionData.role_id
      ? ROLES_DATA.find((r) => r.id == sessionData.role_id)
      : null;
    const roleName = roleObj ? roleObj.name : "";

    let roleClass = roleObj ? (roleObj.award_category ? `role-${roleObj.award_category}` : 'role-other') : 'role-other';
    if (roleObj && roleObj.type === 'officer') {
      roleClass = 'role-officer';
    }

    const roleBadgeHtml = roleName ? `<span class="roster-role-tag ${roleClass}">${roleName}</span>` : "";

    let durationText = "—";
    if (sessionData.Duration_Min !== null && sessionData.Duration_Max !== null) {
      if (sessionData.Duration_Min === sessionData.Duration_Max) {
        durationText = `${sessionData.Duration_Min}'`;
      } else {
        durationText = `${sessionData.Duration_Min} - ${sessionData.Duration_Max}'`;
      }
    } else if (sessionData.Duration_Min !== null) {
      durationText = `${sessionData.Duration_Min}'`;
    } else if (sessionData.Duration_Max !== null) {
      durationText = `${sessionData.Duration_Max}'`;
    }

    row.innerHTML = `
      <td>${sessionData.id}</td>
      <td data-field="Title" class="session-title-cell">
        <span class="session-title-text">${sessionData.Title || ""}</span>
      </td>
      <td data-field="role_id" data-role-id="${sessionData.role_id || ''}">${roleBadgeHtml}</td>
      <td data-field="Duration" data-min="${sessionData.Duration_Min !== null ? sessionData.Duration_Min : ''}" data-max="${sessionData.Duration_Max !== null ? sessionData.Duration_Max : ''}">${durationText}</td>
      <td data-field="Is_Section">
        <input type="checkbox" ${sessionData.Is_Section ? "checked" : ""} disabled>
      </td>
      <td data-field="Valid_for_Project">
        <input type="checkbox" ${sessionData.Valid_for_Project ? "checked" : ""} disabled>
      </td>
      <td data-field="Is_Hidden">
        <input type="checkbox" ${sessionData.Is_Hidden ? "checked" : ""} disabled>
      </td>
      <td data-field="Featured">
        <input type="checkbox" ${sessionData.Featured ? "checked" : ""} disabled>
      </td>
      <td>
        <div class="action-links">
          <button class="edit-btn icon-btn" onclick="openEditSessionModal('${sessionData.id}')" title="Edit">
            <i class="fas fa-edit"></i>
          </button>
          <button class="delete-btn icon-btn" onclick="openDeleteModal('/settings/sessions/delete/${sessionData.id}', 'session type')" title="Delete">
            <i class="fas fa-trash-alt"></i>
          </button>
        </div>
      </td>
    `;

    if (isNew) {
      // Re-apply sorting if a sort order is active
      const activeSortHeader = document.querySelector("#sessions-table th[data-sort-dir]");
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
        const rowText = row.textContent.toUpperCase();
        row.style.display = rowText.includes(filter) ? "" : "none";
      }
    }
  }

  /**
   * Dynamically adds or updates a role row.
   */
  function addRoleRowToTable(roleData) {
    const tableBody = document.querySelector("#roles-table tbody");
    if (!tableBody) return;

    let row = tableBody.querySelector(`tr[data-id="${roleData.id}"]`);
    const isNew = !row;
    if (isNew) {
      row = tableBody.insertRow();
      row.dataset.id = roleData.id;
    }

    // Resolve translated names using existing DOM translations
    const typeRadio = document.querySelector(`#addRoleForm input[name="type"][value="${roleData.type}"]`);
    const translatedType = typeRadio ? typeRadio.nextElementSibling.textContent.trim() : roleData.type;

    const categoryRadio = document.querySelector(`#addRoleForm input[name="award_category"][value="${roleData.award_category || ''}"]`);
    const translatedCategory = (roleData.award_category && categoryRadio) ? categoryRadio.nextElementSibling.textContent.trim() : "";

    const ticketOption = document.querySelector(`#ticket_type option[value="${roleData.ticket_type || ''}"]`);
    const translatedTicketType = (roleData.ticket_type && ticketOption) ? ticketOption.textContent.trim() : (roleData.ticket_type || "");

    row.innerHTML = `
      <td>${roleData.id}</td>
      <td data-field="name" class="role-type-${roleData.type}">
        <div class="role-name-cell">
          <i class="fas ${typeof resolveRoleIcon === 'function' ? resolveRoleIcon(roleData.icon) : (roleData.icon || 'fa-question-circle')}"></i>
          <span class="role-name-text">${roleData.name}</span>
        </div>
      </td>
      <td data-field="type" data-type="${roleData.type}">${translatedType}</td>
      <td data-field="award_category" data-category="${roleData.award_category || ''}">${translatedCategory}</td>
      <td data-field="needs_approval">
        <input type="checkbox" name="needs_approval" ${roleData.needs_approval ? "checked" : ""} disabled />
      </td>
      <td data-field="has_single_owner">
        <input type="checkbox" name="has_single_owner" ${roleData.has_single_owner ? "checked" : ""} disabled />
      </td>
      <td data-field="is_member_only">
        <input type="checkbox" name="is_member_only" ${roleData.is_member_only ? "checked" : ""} disabled />
      </td>
      <td data-field="ticket_type" data-ticket-type="${roleData.ticket_type || ''}">
        ${roleData.ticket_type ? `<span class="ticket-tag">${translatedTicketType}</span>` : ""}
      </td>
      <td>
        <div class="action-links">
          <button class="edit-btn icon-btn" onclick="openEditRoleModal('${roleData.id}')" title="Edit">
            <i class="fas fa-edit"></i>
          </button>
          <button class="delete-btn icon-btn" onclick="openDeleteModal('/settings/roles/delete/${roleData.id}', 'role')" title="Delete">
            <i class="fas fa-trash-alt"></i>
          </button>
        </div>
      </td>
    `;

    if (isNew) {
      const activeSortHeader = document.querySelector("#roles-table th[data-sort-dir]");
      if (activeSortHeader) {
        const table = document.getElementById("roles-table");
        const columnIndex = parseInt(activeSortHeader.dataset.columnIndex, 10);
        const sortDir = activeSortHeader.dataset.sortDir;
        sortTableByColumn(table, columnIndex, sortDir === "asc");
      }
      const searchInput = document.getElementById("global-settings-search");
      if (searchInput && searchInput.value) {
        const filter = searchInput.value.toUpperCase().trim();
        const rowText = row.textContent.toUpperCase();
        row.style.display = rowText.includes(filter) ? "" : "none";
      }
    }
  }

});

// --- 7. Permission Management & Audit Log ---
let originalPermissions = {}; // role_id -> [perm_id, ...]
let isSavingPermissions = false;
let hasPendingPermissionsSave = false;
let matrixRoles = [];
let rolesByLevel = {};
let mainRoleForLevel = {};
let collapsedLevels = {};

/**
 * Fetches and renders the permission matrix.
 */
function loadPermissionsMatrix() {
  const container = document.getElementById("permissions-matrix");
  const loading = document.getElementById("permissions-matrix-loading");

  if (!container || !loading) return;

  container.style.display = "none";
  loading.style.display = "block";

  // Load functional modules table side-by-side
  loadModules();

  fetch("/api/permissions/matrix")
    .then((r) => r.json())
    .then((data) => {
      renderPermissionsMatrix(data);
      renderAuthRolesTable(data.roles);
      loading.style.display = "none";
      container.style.display = "block";
      loadDefaultInfo();
    })
    .catch((e) => {
      console.error("Matrix load error:", e);
      loading.innerHTML = `<span class="text-danger">Error loading permissions: ${e.message}</span>`;
    });
}

/**
 * POSTs the current per-club matrix to the export endpoint, which writes it
 * to app/static/club_resources/<club_id>/permissions.json. This is the new
 * role of the "Save as Default" button.
 */
async function exportPermissionsDefault() {
  const btn = document.getElementById("save-permissions-btn");
  if (btn) btn.disabled = true;
  try {
    const resp = await fetch("/api/permissions/export-default", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    const data = await resp.json();
    if (data.success) {
      showNotification("Saved as default.", "success");
      loadDefaultInfo();
    } else {
      showNotification(data.message || "Export failed", "error");
    }
  } catch (e) {
    showNotification(e.message, "error");
  } finally {
    if (btn) btn.disabled = false;
  }
}

/**
 * POSTs to the reset endpoint. The server reads the club JSON (or falls back
 * to the global JSON), wipes the per-club role_permissions, and re-inserts
 * from the JSON. On success, the matrix is re-rendered.
 */
async function resetPermissionsToDefault() {
  const ok = confirm(
    "Reset the permission matrix to the default?\n\n" +
    "This will REPLACE all current role permissions for this club with the saved default " +
    "(club JSON if present, otherwise the global default).\n\n" +
    "Custom security groups (not in the default file) will be cleared.\n\n" +
    "This action is logged in the Permission Audit Log."
  );
  if (!ok) return;

  const btn = document.getElementById("reset-permissions-btn");
  if (btn) btn.disabled = true;
  try {
    const resp = await fetch("/api/permissions/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    const data = await resp.json();
    if (data.success) {
      showNotification(`Reset from ${data.source} default.`, "success");
      // Re-fetch the matrix so checkboxes reflect the new state
      loadPermissionsMatrix();
    } else {
      showNotification(data.message || "Reset failed", "error");
      loadDefaultInfo(); // refresh hint/button state
    }
  } catch (e) {
    showNotification(e.message, "error");
  } finally {
    if (btn) btn.disabled = false;
  }
}

/**
 * Fetches /api/permissions/default-info and updates the "last saved" hint
 * plus the Reset button's enabled state. Silent on error.
 */
async function loadDefaultInfo() {
  const hint = document.getElementById("permissions-default-hint");
  const resetBtn = document.getElementById("reset-permissions-btn");
  try {
    const resp = await fetch("/api/permissions/default-info");
    const data = await resp.json();
    if (!data || !data.success) return;

    const club = data.club || {};
    const globalDefault = data.global_default || {};

    if (hint) {
      if (club.exists) {
        hint.textContent = `Last saved (club): ${formatTimestamp(club.updated_at)}`;
      } else if (globalDefault.exists) {
        hint.textContent = "No club default saved. Global default available.";
      } else {
        hint.textContent = "No default available. Save one to enable Reset.";
      }
    }
    if (resetBtn) {
      resetBtn.disabled = !(club.exists || globalDefault.exists);
    }
  } catch (e) {
    // best-effort; don't surface
  }
}

/** Compact local-time formatter for the default-info hint. */
function formatTimestamp(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString();
  } catch (_) {
    return iso;
  }
}

function loadModules() {
  const tableBody = document.getElementById("modules-table-body");
  if (!tableBody) return;

  fetch("/api/settings/modules")
    .then((r) => r.json())
    .then((data) => {
      if (!data.success) {
        tableBody.innerHTML = `<tr><td colspan="2" class="text-center text-danger">${data.message || 'Error loading modules.'}</td></tr>`;
        return;
      }
      renderModulesTable(data.modules);
    })
    .catch((e) => {
      console.error("Modules load error:", e);
      tableBody.innerHTML = `<tr><td colspan="2" class="text-center text-danger">Error loading modules: ${e.message}</td></tr>`;
    });
}

function renderModulesTable(modules) {
  const tableBody = document.getElementById("modules-table-body");
  if (!tableBody) return;

  if (modules.length === 0) {
    tableBody.innerHTML = `<tr><td colspan="2" class="text-center py-4">No modules found.</td></tr>`;
    return;
  }

  let html = '';
  const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
  modules.forEach((mod) => {
    const isDisabled = mod.is_core || (typeof HAS_SETTINGS_EDIT !== 'undefined' && !HAS_SETTINGS_EDIT);
    const checkedAttr = mod.enabled ? 'checked' : '';
    const disabledAttr = isDisabled ? 'disabled' : '';
    
    const toggleHtml = `
      <div class="switch-container">
        <label class="switch">
          <input type="checkbox" data-module-name="${mod.name}" ${checkedAttr} ${disabledAttr} onchange="toggleModuleState(this)">
          <span class="slider"></span>
        </label>
      </div>
    `;

    html += `
      <tr>
        <td>
          <span style="font-weight: 500;">${isChinese ? translateModuleName(mod.name) : mod.name}</span>
        </td>
        <td>${toggleHtml}</td>
      </tr>
    `;
  });

  tableBody.innerHTML = html;
}

function translateModuleName(name) {
  const translations = {
    'Core': '核心',
    'Booking': '订场',
    'Voting': '投票',
    'Roster': '花名册',
    'Calendar': '日历',
    'Chatbot': '聊天机器人',
    'Journal': '演讲记录',
    'Club Directory': '俱乐部目录',
    'Planner': '规划助手',
    'Lucky Draw': '幸运抽奖',
    'Upload': '上传',
    'Data/Slides Export': '数据/幻灯片导出'
  };
  return translations[name] || name;
}

// Security group description translations. Kept in sync with the English
// descriptions seeded by migration 4b5c6d7e8f90_update_security_group_descriptions
// and the matching entries in app/translations/zh_CN.json. Falling back to the
// original text keeps English mode and any future / custom descriptions working
// without code changes.
function translateRoleDescription(desc) {
  if (!desc) return desc;
  const translations = {
    "System administrator — unrestricted access across all clubs, settings, modules, and data. Hidden from the club-level permissions matrix by design.": "系统管理员 — 在所有俱乐部拥有无限制权限，可访问设置、模块及全部数据。默认在俱乐部层级的权限矩阵中隐藏。",
    "Club leadership team — full configuration of this club: members, security groups, modules, speech logs, and all data. Typically held by the VPE or President.": "俱乐部领导团队 — 可对本俱乐部进行全面配置：成员、安全组、模块、演讲记录及全部数据。通常由 VPE 或主席担任。",
    "Meeting operations lead — owns the weekly meeting: agenda, roster, booking, lucky draw, voting results, and speech-log tracking. Typically held by the SAA and meeting chairs.": "会议运营负责人 — 负责每周例会：日程、花名册、订场、幸运抽奖、投票结果及演讲记录跟踪。通常由 SAA 与例会主持担任。",
    "Club officer — view access across all club data plus the planner and own-profile editing. Held by the seven club officers.": "俱乐部官员 — 可查看俱乐部全部数据，并可使用规划助手与编辑个人资料。由七位俱乐部官员担任。",
    "Club member — view published club content, book own meeting roles, edit own profile, and track own speech-log progress.": "俱乐部成员 — 可查看已发布的俱乐部内容、预订自己的会议角色、编辑个人资料，并跟踪自己的演讲记录进度。",
    "Anonymous visitor — view the public club home page, agenda, and Pathway library. No login required.": "匿名访客 — 可查看俱乐部公开主页、日程表与路径库，无需登录。"
  };
  return translations[desc] || desc;
}

function toggleModuleState(checkbox) {
  const moduleName = checkbox.dataset.moduleName;
  const isEnabled = checkbox.checked;

  checkbox.disabled = true;

  fetch("/api/settings/modules/toggle", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      module_name: moduleName,
      enabled: isEnabled
    })
  })
  .then((r) => r.json())
  .then((data) => {
    checkbox.disabled = false;
    if (data.success) {
      window.location.reload();
    } else {
      checkbox.checked = !isEnabled;
      showNotification(data.message || 'Failed to toggle module.', 'error');
    }
  })
  .catch((e) => {
    checkbox.disabled = false;
    checkbox.checked = !isEnabled;
    console.error("Toggle module error:", e);
    showNotification(e.message || 'Network error occurred.', 'error');
  });
}

window.toggleModuleState = toggleModuleState;


function renderAuthRolesTable(roles) {
  const tableBody = document.getElementById("auth-roles-table-body");
  if (!tableBody) return;

  const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';

  if (roles.length === 0) {
    const emptyMsg = isChinese ? '未找到安全组' : 'No security groups found.';
    tableBody.innerHTML = `<tr><td colspan="4" class="text-center py-4">${emptyMsg}</td></tr>`;
    return;
  }

  const noDescPlaceholder = isChinese
    ? '<em class="text-muted">暂无描述</em>'
    : '<em class="text-muted">No description</em>';

  tableBody.innerHTML = roles.map(role => {
    const isCore = role.is_core;
    const badgeClass = isCore ? `role-${role.name.toLowerCase()}` : 'role-other';
    const badgeHtml = `<span class="roster-role-tag ${badgeClass}">${role.name}</span>`;

    // Core system roles cannot be deleted
    const deleteBtn = isCore
      ? `<button class="delete-btn icon-btn" disabled title="System Core Security Group (Protected)"><i class="fas fa-lock"></i></button>`
      : (typeof HAS_SETTINGS_EDIT !== 'undefined' && HAS_SETTINGS_EDIT)
        ? `<button class="delete-btn icon-btn" onclick="deleteAuthRole(${role.id}, '${role.name.replace(/'/g, "\\'")}')" title="Delete custom security group"><i class="fas fa-trash-alt"></i></button>`
        : `<button class="delete-btn icon-btn" disabled title="No edit permissions"><i class="fas fa-trash-alt"></i></button>`;

    const displayDesc = role.description
      ? (isChinese ? translateRoleDescription(role.description) : role.description)
      : noDescPlaceholder;

    return `
      <tr data-id="${role.id}">
        <td>${badgeHtml}</td>
        <td>Level ${role.level}</td>
        <td>${displayDesc}</td>
        <td>
          <div class="action-links">
            ${deleteBtn}
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

function deleteAuthRole(roleId, roleName) {
  const confirmMsg = `Are you sure you want to delete the security group "${roleName}"?\n\nWARNING: All users currently assigned to this group will be automatically reassigned to the default 'Member' group in bulk. This action cannot be undone.`;
  if (confirm(confirmMsg)) {
    fetch(`/api/settings/auth-roles/delete/${roleId}`, {
      method: "POST"
    })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        loadPermissionsMatrix(); // Refresh roles list and matrix
      } else {
        showNotification(data.message, "error");
      }
    })
    .catch(e => {
      console.error("Error deleting role:", e);
      showNotification(`Error: ${e.message}`, "error");
    });
  }
}
window.deleteAuthRole = deleteAuthRole;

function openAddAuthRoleModal() {
  const modal = document.getElementById("addAuthRoleModal");
  if (modal) {
    modal.style.display = "flex";
  }
}
window.openAddAuthRoleModal = openAddAuthRoleModal;

function toggleLevelGroup(level) {
  const isCollapsed = !collapsedLevels[level];
  collapsedLevels[level] = isCollapsed;
  
  // Find main role and other roles at this level
  const mainRole = mainRoleForLevel[level];
  if (!mainRole) return;
  
  const levelRoles = rolesByLevel[level];
  const customRoleIds = levelRoles.filter(r => r.id !== mainRole.id).map(r => r.id);
  
  // Update Level Header colspan
  const levelHeader = document.querySelector(`.level-header[data-level="${level}"]`);
  if (levelHeader) {
    levelHeader.colSpan = isCollapsed ? 1 : levelRoles.length;
  }
  
  // Toggle columns visibility in DOM
  customRoleIds.forEach(roleId => {
    const subHeader = document.querySelector(`.role-header[data-role-id="${roleId}"]`);
    if (subHeader) {
      subHeader.style.display = isCollapsed ? "none" : "";
    }
    
    document.querySelectorAll(`.perm-checkbox-cell[data-role-id="${roleId}"]`).forEach(cell => {
      cell.style.display = isCollapsed ? "none" : "";
    });
  });
  
  // Update toggle button icon
  const toggleBtn = document.querySelector(`.toggle-level-btn[data-level="${level}"]`);
  if (toggleBtn) {
    const icon = isCollapsed ? 'fa-chevron-right' : 'fa-chevron-down';
    toggleBtn.innerHTML = `<i class="fas ${icon}"></i>`;
  }
}
function toggleCategory(categorySlug, rowElement) {
  const permRows = document.querySelectorAll(`.category-group-${categorySlug}`);
  const isCollapsed = rowElement.classList.contains('collapsed');
  const icon = rowElement.querySelector('.toggle-icon');
  
  if (isCollapsed) {
    const searchInput = document.getElementById('global-settings-search');
    const filter = (searchInput && searchInput.value) ? searchInput.value.toUpperCase().trim() : '';
    
    permRows.forEach(row => {
      if (filter.length > 0) {
        const isSearchHidden = row.getAttribute('data-search-hidden') === 'true';
        row.style.display = isSearchHidden ? 'none' : '';
      } else {
        row.style.display = '';
      }
    });
    rowElement.classList.remove('collapsed');
    if (icon) {
      icon.className = 'fas fa-chevron-down toggle-icon';
    }
  } else {
    permRows.forEach(row => {
      row.style.display = 'none';
    });
    rowElement.classList.add('collapsed');
    if (icon) {
      icon.className = 'fas fa-chevron-right toggle-icon';
    }
  }
}
window.toggleCategory = toggleCategory;

function renderPermissionsMatrix(data) {
  const container = document.getElementById("permissions-matrix");
  const saveBtn = document.getElementById("save-permissions-btn");
  const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
  const { roles, permissions, role_perms } = data;

  // Store original state
  originalPermissions = JSON.parse(JSON.stringify(role_perms));
  // Note: save-permissions-btn is now the "Save as Default" (export) button —
  // it stays enabled. Disable only while an export request is in flight.

  // Group roles by level in descending order
  matrixRoles = roles;
  rolesByLevel = {};
  roles.forEach(r => {
    if (!rolesByLevel[r.level]) rolesByLevel[r.level] = [];
    rolesByLevel[r.level].push(r);
  });

  const sortedLevels = Object.keys(rolesByLevel).map(Number).sort((a, b) => b - a);

  const coreRoleNames = ['ClubAdmin', 'Operator', 'Staff', 'Member', 'Guest'];
  mainRoleForLevel = {};
  sortedLevels.forEach(level => {
    const levelRoles = rolesByLevel[level];
    let main = levelRoles.find(r => coreRoleNames.includes(r.name));
    if (!main) {
      main = levelRoles[0];
    }
    mainRoleForLevel[level] = main;
  });

  // Header row 1: Level Groups
  let levelHeadersHtml = `<th class="level-group-header">${isChinese ? '安全组' : 'Security Group'}</th>`;
  // Header row 2: Role Names
  let roleHeadersHtml = `<th>Permission</th>`;

  sortedLevels.forEach(level => {
    const levelRoles = rolesByLevel[level];
    const isCollapsed = collapsedLevels[level] || false;
    const mainRole = mainRoleForLevel[level];

    let groupLabel = `Level ${level}`;
    if (level === 4) groupLabel = "Level 4 (Admin)";
    else if (level === 3) groupLabel = "Level 3 (Operator)";
    else if (level === 2) groupLabel = "Level 2 (Staff)";
    else if (level === 1) groupLabel = "Level 1 (Member)";
    else if (level === 0) groupLabel = "Level 0 (Guest)";

    const hasMultiple = levelRoles.length > 1;
    let toggleBtn = "";
    if (hasMultiple) {
      const icon = isCollapsed ? 'fa-chevron-right' : 'fa-chevron-down';
      toggleBtn = `<button type="button" class="toggle-level-btn" data-level="${level}" onclick="toggleLevelGroup(${level})"><i class="fas ${icon}"></i></button>`;
    }

    const colSpan = isCollapsed ? 1 : levelRoles.length;
    levelHeadersHtml += `<th class="level-group-header level-header" data-level="${level}" colspan="${colSpan}">${groupLabel}${toggleBtn}</th>`;

    levelRoles.forEach(r => {
      const isMain = r.id === mainRole.id;
      const hideStyle = (!isMain && isCollapsed) ? 'style="display: none;"' : '';
      roleHeadersHtml += `<th class="role-header" data-role-id="${r.id}" ${hideStyle}>${r.name}</th>`;
    });
  });

  let html = `
    <div class="table-responsive">
      <table class="table matrix-table">
        <thead>
          <tr>
            ${levelHeadersHtml}
          </tr>
          <tr>
            ${roleHeadersHtml}
          </tr>
        </thead>
        <tbody>
  `;

  let currentCategory = "";
  permissions.forEach((p) => {
    // Handle null/undefined category safely
    const safeCategory = p.category || "General";
    const catSlug = safeCategory.toLowerCase().replace(/[^a-z0-9]/g, '-');

    if (safeCategory !== currentCategory) {
      currentCategory = safeCategory;
      let totalColumns = 1;
      sortedLevels.forEach(level => {
        const levelRoles = rolesByLevel[level];
        const isCollapsed = collapsedLevels[level] || false;
        totalColumns += isCollapsed ? 1 : levelRoles.length;
      });

      html += `
        <tr class="category-row collapsed" onclick="toggleCategory('${catSlug}', this)" style="cursor: pointer;">
          <td colspan="${totalColumns}">
            <i class="fas fa-chevron-right toggle-icon" style="margin-right: 8px;"></i>
            <strong>${currentCategory.toUpperCase()}</strong>
          </td>
        </tr>
      `;
    }

    html += `
      <tr data-perm-id="${p.id}" class="perm-row category-group-${catSlug}" style="display: none;">
        <td title="${p.description || ""}">
          ${p.name}
          <div class="small text-muted">${p.resource ? p.resource + ':' : ''}${p.description || ""}</div>
        </td>
    `;

    sortedLevels.forEach(level => {
      const levelRoles = rolesByLevel[level];
      const isCollapsed = collapsedLevels[level] || false;
      const mainRole = mainRoleForLevel[level];
      
      levelRoles.forEach(r => {
        const isMain = r.id === mainRole.id;
        const hideStyle = (!isMain && isCollapsed) ? 'style="display: none;"' : '';
        const checked = role_perms[r.id]?.includes(p.id) ? "checked" : "";
        const disabled = (typeof HAS_SETTINGS_EDIT !== 'undefined' && !HAS_SETTINGS_EDIT) ? "disabled" : "";
        html += `<td class="perm-checkbox-cell" data-role-id="${r.id}" ${hideStyle}><input type="checkbox" class="perm-checkbox" data-role-id="${r.id}" data-perm-id="${p.id}" ${checked} ${disabled}></td>`;
      });
    });

    html += `</tr>`;
  });

  html += `
        </tbody>
      </table>
    </div>
  `;

  container.innerHTML = html;

  // Add change listener to save just-in-time
  container.addEventListener("change", (e) => {
    if (e.target.classList.contains("perm-checkbox")) {
      savePermissions();
    }
  });
}

/**
 * Saves current permission checks to the server.
 */
function savePermissions() {
  if (isSavingPermissions) {
    hasPendingPermissionsSave = true;
    return;
  }

  isSavingPermissions = true;
  const container = document.getElementById("permissions-matrix");
  if (!container) {
    isSavingPermissions = false;
    return;
  }

  const roleIds = new Set();
  const checkboxes = container.querySelectorAll(".perm-checkbox");
  checkboxes.forEach((cb) => {
    roleIds.add(cb.dataset.roleId);
    cb.disabled = true; // Disable during save to prevent race conditions
  });

  const payload = Array.from(roleIds).map((rid) => {
    const checkedPerms = Array.from(
      container.querySelectorAll(`.perm-checkbox[data-role-id="${rid}"]:checked`)
    ).map((cb) => parseInt(cb.dataset.permId));
    return { role_id: parseInt(rid), permission_ids: checkedPerms };
  });

  fetch("/api/permissions/update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
    .then((r) => r.json())
    .then((data) => {
      isSavingPermissions = false;

      // If a new change event was queued while saving, start another save immediately
      if (hasPendingPermissionsSave) {
        hasPendingPermissionsSave = false;
        savePermissions();
        return;
      }

      // Re-enable checkboxes if user has permission
      const shouldEnable = typeof HAS_SETTINGS_EDIT !== 'undefined' && HAS_SETTINGS_EDIT;
      checkboxes.forEach(cb => {
        cb.disabled = !shouldEnable;
      });

      if (data.success) {
        // Update original state to current state
        originalPermissions = {};
        payload.forEach(item => {
          originalPermissions[item.role_id] = item.permission_ids.sort();
        });
      } else {
        showNotification(data.message, "error");
        // Rollback checkboxes on error
        checkboxes.forEach(cb => {
          const rid = cb.dataset.roleId;
          const pid = parseInt(cb.dataset.permId);
          cb.checked = (originalPermissions[rid] || []).includes(pid);
        });
      }
    })
    .catch((e) => {
      isSavingPermissions = false;

      if (hasPendingPermissionsSave) {
        hasPendingPermissionsSave = false;
        savePermissions();
        return;
      }

      showNotification(e.message, "error");
      // Re-enable and rollback checkboxes on error
      const shouldEnable = typeof HAS_SETTINGS_EDIT !== 'undefined' && HAS_SETTINGS_EDIT;
      checkboxes.forEach(cb => {
        cb.disabled = !shouldEnable;
        const rid = cb.dataset.roleId;
        const pid = parseInt(cb.dataset.permId);
        cb.checked = (originalPermissions[rid] || []).includes(pid);
      });
    });
}

/**
 * Formats a technical action string (e.g. UPDATE_ROLE_PERMS) into human-readable text.
 */
function formatActionString(action) {
  if (!action) return "";
  return action
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

/**
 * Fetches and renders the audit log.
 */
function loadAuditLog() {
  const body = document.getElementById("audit-log-body");
  if (!body) return;

  fetch("/api/audit-log")
    .then((r) => r.json())
    .then((data) => {
      body.innerHTML = data
        .map(
          (log) => `
        <tr>
          <td class="small">${log.timestamp}</td>
          <td>${log.admin_name}</td>
          <td>${formatActionString(log.action)}</td>
          <td><small>${log.target_type}:</small> ${log.target_name}</td>
          <td class="small">${log.changes}</td>
        </tr>
      `
        )
        .join("");
    })
    .catch((e) => {
      body.innerHTML = `<tr><td colspan="5" class="text-danger">Error: ${e.message}</td></tr>`;
    });
}

// Attach event listeners for the new tabs
document.addEventListener("DOMContentLoaded", () => {
  // Save as Default button -> exports current matrix to club JSON
  const saveBtn = document.getElementById("save-permissions-btn");
  if (saveBtn) {
    saveBtn.addEventListener("click", exportPermissionsDefault);
  }

  // Reset to Default button -> reads club JSON (or global), applies to DB
  const resetBtn = document.getElementById("reset-permissions-btn");
  if (resetBtn) {
    resetBtn.addEventListener("click", resetPermissionsToDefault);
  }

  // Populate the "last saved" hint + reset button state for the current club
  loadDefaultInfo();

  // Add auth role button disable check
  const addAuthRoleBtn = document.getElementById("add-auth-role-btn");
  if (addAuthRoleBtn && typeof HAS_SETTINGS_EDIT !== 'undefined') {
    if (!HAS_SETTINGS_EDIT) {
      addAuthRoleBtn.disabled = true;
      addAuthRoleBtn.title = "Permission denied";
    }
  }

  // Add auth role form submit
  const addAuthRoleForm = document.getElementById("addAuthRoleForm");
  if (addAuthRoleForm) {
    addAuthRoleForm.addEventListener("submit", function (event) {
      event.preventDefault();
      const formData = new FormData(this);
      const url = this.action;
      
      fetch(url, {
        method: "POST",
        body: formData
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          closeModal("addAuthRoleModal");
          this.reset();
          loadPermissionsMatrix(); // Refresh matrix and roles table
        } else {
          showNotification(data.message, "error");
        }
      })
      .catch(error => {
        console.error("Error:", error);
        showNotification(`An error occurred: ${error.message}`, "error");
      });
    });
  }

  // Load matrix when tab is clicked
  const tabs = document.querySelectorAll(".nav-item");
  tabs.forEach((tab) => {
    tab.addEventListener("click", (e) => {
      const tabName = e.currentTarget
        .getAttribute("onclick")
        .match(/'([^']+)'/)[1];
      if (tabName === "roles-permissions") {
        loadPermissionsMatrix();
      } else if (tabName === "audit-log") {
        loadAuditLog();
      }
    });
  });

  // Initial load if tab is deep-linked
  const activeTab = localStorage.getItem("settings_active_tab");
  if (activeTab === "roles-permissions") {
    loadPermissionsMatrix();
  } else if (activeTab === "audit-log") {
    loadAuditLog();
  }

  // Audit log search (local filter)
  const auditSearch = document.getElementById("audit-search");
  if (auditSearch) {
    auditSearch.addEventListener("keyup", () => {
      const filter = auditSearch.value.toUpperCase();
      const rows = document.querySelectorAll("#audit-log-body tr");
      rows.forEach(row => {
        const text = row.textContent.toUpperCase();
        row.style.display = text.includes(filter) ? "" : "none";
      });
    });
  }

  // --- 8. Initialize Paginators ---
  window.activePaginators = {
    'user-settings': new TablePaginator({
      tableId: 'user-settings-table',
      containerId: 'user-pagination',
      pageSize: 10,
      storageKey: 'user_settings'
    })
  };


  // Re-run filter once to apply initial pagination
  setTimeout(() => {
    const searchInput = document.getElementById('global-settings-search');
    if (searchInput) {
      const event = new Event('keyup');
      searchInput.dispatchEvent(event);
    }
  }, 100);
});

/**
 * Opens the role modal in edit mode and populates it with data from the table row.
 */
function openEditRoleModal(roleId) {
  const row = document.querySelector(`#roles-table tr[data-id="${roleId}"]`);
  if (!row) return;

  const modal = document.getElementById("addRoleModal");
  const title = document.getElementById("role-modal-title");
  const submitBtn = document.getElementById("role-modal-submit");
  const form = document.getElementById("addRoleForm");

  if (!modal || !title || !submitBtn || !form) return;

  // Set modal to edit mode
  const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
  title.textContent = isChinese ? "编辑角色" : "Edit Role";
  submitBtn.textContent = isChinese ? "保存" : "Save";
  document.getElementById("role_id_input").value = roleId;

  // Populate fields
  form.name.value = row.querySelector('[data-field="name"]').textContent.trim();
  // Populate fields
  form.name.value = row.querySelector('[data-field="name"]').textContent.trim();

  // Type Radio Population
  const typeCell = row.querySelector('[data-field="type"]');
  const typeValue = typeCell ? (typeCell.dataset.type || typeCell.textContent.trim()) : "";
  const typeRadio = form.querySelector(`input[name="type"][value="${typeValue}"]`);
  if (typeRadio) typeRadio.checked = true;

  // Award Category Radio Population
  const categoryCell = row.querySelector('[data-field="award_category"]');
  const categoryValue = categoryCell ? (categoryCell.dataset.category || categoryCell.textContent.trim()) : "";
  const categoryRadio = form.querySelector(`input[name="award_category"][value="${categoryValue}"]`);
  if (categoryRadio) {
    categoryRadio.checked = true;
  } else if (categoryValue === "" || categoryValue === "None" || categoryValue === "无") {
    const noneRadio = form.querySelector(`input[name="award_category"][value=""]`);
    if (noneRadio) noneRadio.checked = true;
  }

  // Logic for Type selector visibility based on Club ID when EDITING
  // Consistent with Add logic:
  // Club 1: All visible
  // Other: Hide "standard", show others
  const typeRadios = form.querySelectorAll('input[name="type"]');
  if (typeof CURRENT_CLUB_ID !== 'undefined') {
    typeRadios.forEach(radio => {
      const label = radio.parentElement;
      if (!label) return;

      if (CURRENT_CLUB_ID === 1) {
        // Club 1: Hide "club-specific", show others
        if (radio.value === 'club-specific') {
          label.style.display = 'none';
        } else {
          label.style.display = 'flex';
        }
      } else {
        if (radio.value === 'standard') {
          label.style.display = 'none';
        } else {
          label.style.display = 'flex';
        }
      }
    });
  }

  form.needs_approval.checked = row.querySelector('[data-field="needs_approval"] input').checked;
  form.has_single_owner.checked = row.querySelector('[data-field="has_single_owner"] input').checked;
  form.is_member_only.checked = row.querySelector('[data-field="is_member_only"] input').checked;

  // Handle Ticket Type
  const ticketTypeCell = row.querySelector('[data-field="ticket_type"]');
  const ticketTypeValue = ticketTypeCell ? (ticketTypeCell.dataset.ticketType || ticketTypeCell.textContent.trim()) : "";
  if (form.ticket_type) {
    form.ticket_type.value = ticketTypeValue;
  }

  // Icon handling — the icon now lives inside the name cell as <i class="fas fa-X">.
  // We extract the FA class from the <i> element's classList rather than reading
  // textContent (the old [data-field="icon"] cell was merged into the name cell).
  let iconValue = "";
  const iconEl = row.querySelector('[data-field="name"] i.fas');
  if (iconEl) {
    for (const cls of iconEl.classList) {
      if (cls.startsWith("fa-") && cls !== "fas" && cls !== "far" && cls !== "fab" && cls !== "fal" && cls !== "fad") {
        iconValue = cls;
        break;
      }
    }
  }
  const container = document.getElementById("icon-matrix-container");
  if (container) {
    container.querySelectorAll(".icon-item").forEach(i => i.classList.remove("active"));
    const item = container.querySelector(`.icon-item[data-value="${iconValue}"]`);
    if (item) item.classList.add("active");
    document.getElementById("icon").value = iconValue;
  }

  modal.style.display = "flex";
}

/**
 * Opens the session modal in edit mode and populates it with data from the table row.
 */
function openEditSessionModal(sessionId) {
  const row = document.querySelector(`#sessions-table tr[data-id="${sessionId}"]`);
  if (!row) return;

  const modal = document.getElementById("addSessionModal");
  const title = document.getElementById("session-modal-title");
  const submitBtn = document.getElementById("session-modal-submit");
  const form = document.getElementById("addSessionForm");

  if (!modal || !title || !submitBtn || !form) return;

  // Set modal to edit mode
  const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
  title.textContent = isChinese ? "编辑会议环节类型" : "Edit Session Type";
  submitBtn.textContent = isChinese ? "保存" : "Save";
  document.getElementById("session_id_input").value = sessionId;

  // Populate fields
  form.title.value = row.querySelector('[data-field="Title"]').textContent.trim();
  form.role_id.value = row.querySelector('[data-field="role_id"]').dataset.roleId || "";
  const durationCell = row.querySelector('[data-field="Duration"]');
  form.duration_min.value = durationCell ? (durationCell.dataset.min || "") : "";
  form.duration_max.value = durationCell ? (durationCell.dataset.max || "") : "";

  form.is_section.checked = row.querySelector('[data-field="Is_Section"] input').checked;
  form.valid_for_project.checked = row.querySelector('[data-field="Valid_for_Project"] input').checked;
  form.is_hidden.checked = row.querySelector('[data-field="Is_Hidden"] input').checked;
  const featuredInput = row.querySelector('[data-field="Featured"] input');
  form.featured.checked = featuredInput ? featuredInput.checked : false;

  modal.style.display = "flex";
}


/**
 * Toggles the visibility of an achievement group.
 */
function toggleAchievementGroup(groupId) {
  const parentId = `group-${groupId}`;
  const rows = document.querySelectorAll(`tr[data-parent-id="${parentId}"]`);
  const header = document.querySelector(`tr[data-id="${parentId}"]`);
  const icon = header ? header.querySelector(".toggle-icon") : null;

  if (!header) return;

  // Toggle expanded class
  const isExpanding = !header.classList.contains('expanded');
  if (isExpanding) {
    header.classList.add('expanded');
  } else {
    header.classList.remove('expanded');
  }

  // Update Icon
  if (icon) {
    if (isExpanding) {
      icon.classList.remove("fa-chevron-right");
      icon.classList.add("fa-chevron-down");
    } else {
      icon.classList.remove("fa-chevron-down");
      icon.classList.add("fa-chevron-right");
    }
  }

  // If paginator exists, let it handle the row visibility
  if (window.activePaginators && window.activePaginators['achievements']) {
    window.activePaginators['achievements'].update();
  } else {
    // Fallback: manually toggle display
    rows.forEach((row) => {
      row.style.display = isExpanding ? "table-row" : "none";
    });
  }
}

// Export to window for inline onclick


/**
 * Achievement Modal Logic
 */
function initAchievementModal() {
  const input = document.getElementById('achievement_contact_search');
  const hidden = document.getElementById('contact_id');
  const memberIdDisplay = document.getElementById('member_id');
  const typeSelect = document.getElementById('achievement_type');
  const pathSelect = document.getElementById('path_name');
  const levelInput = document.getElementById('level');
  const form = document.getElementById('achievementForm');

  if (input && hidden && typeof ALL_CONTACTS !== 'undefined') {
    initAutocomplete(input, hidden, ALL_CONTACTS, {
      onSelect: (contact) => {
        if (memberIdDisplay) memberIdDisplay.value = contact.Member_ID || '';
      }
    });
  }

  if (typeSelect) {
    typeSelect.addEventListener('change', handleAchievementTypeChange);
  }

  if (form) {
    form.addEventListener('submit', handleAchievementSubmit);
  }

  // Initialize custom selects for modal if CustomSelect class exists
  if (typeof CustomSelect !== 'undefined') {
    window.achievementTypeSelect = new CustomSelect('achievement_type');
    window.achievementPathSelect = new CustomSelect('path_name');
  }
}

function openAchievementModal(id = null) {
  const modal = document.getElementById('achievementModal');
  const title = document.getElementById('achievement-modal-title');
  const form = document.getElementById('achievementForm');
  const idInput = document.getElementById('achievement-id');
  const submitBtn = document.getElementById('save-achievement-btn');

  if (!modal || !form) return;

  form.reset();
  document.getElementById('contact_id').value = '';
  if (document.getElementById('member_id')) document.getElementById('member_id').value = '';

  // Reset custom selects if they exist
  if (window.achievementTypeSelect) window.achievementTypeSelect.refresh();
  if (window.achievementPathSelect) window.achievementPathSelect.refresh();

  if (id) {
    const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
    title.textContent = isChinese ? "编辑成就" : "Edit Achievement";
    submitBtn.textContent = isChinese ? "保存修改" : "Save Changes";
    idInput.value = id;

    // Fetch achievement data – we can find it in the table or fetch via API
    // Finding in table is faster for UI parity
    const row = document.querySelector(`.achievement-row[onclick*="openAchievementModal('${id}')"]`) ||
      document.querySelector(`.action-links [onclick*="openAchievementModal('${id}')"]`).closest('tr');

    if (row) {
      const date = row.cells[1].textContent.trim();
      const memberId = row.cells[2].textContent.trim();
      const typeText = row.cells[3].textContent.trim();
      const path = row.cells[4].textContent.trim();
      const level = row.cells[5].textContent.trim();
      const notes = row.cells[6].textContent.trim();

      // Map type text back to values
      let typeValue = "";
      if (typeText.includes("Level Completion")) typeValue = "level-completion";
      else if (typeText.includes("Path Completion")) typeValue = "path-completion";
      else if (typeText.includes("Program Completion")) typeValue = "program-completion";
      else typeValue = typeText.toLowerCase().replace(/\s+/g, '-');

      // Find contact by Member ID or Name from the group header
      const parentId = row.getAttribute('data-parent-id');
      const groupHeader = document.querySelector(`tr[data-id="${parentId}"]`);
      const contactName = groupHeader ? groupHeader.querySelector('strong').textContent.trim() : "";

      const contact = ALL_CONTACTS.find(c => c.Name === contactName);
      if (contact) {
        document.getElementById('contact_id').value = contact.id;
        document.getElementById('achievement_contact_search').value = contact.Name;
        document.getElementById('member_id').value = contact.Member_ID || "";
      }

      document.getElementById('award_date').value = date;
      document.getElementById('achievement_type').value = typeValue;
      document.getElementById('path_name').value = (path === "-" ? "" : path);
      document.getElementById('level').value = (level === "-" ? "" : level);
      document.getElementById('notes').value = (notes === "-" ? "" : notes);

      handleAchievementTypeChange(); // Run visibility logic

      if (window.achievementTypeSelect) window.achievementTypeSelect.refresh();
      if (window.achievementPathSelect) window.achievementPathSelect.refresh();
    }
  } else {
    const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
    title.textContent = isChinese ? "添加新成就" : "Add New";
    submitBtn.textContent = isChinese ? "保存" : "Save";
    idInput.value = "";
  }

  modal.style.display = 'flex';
}

function closeAchievementModal() {
  closeModal('achievementModal');
}

function handleAchievementTypeChange() {
  const typeSelect = document.getElementById('achievement_type');
  const pathSelect = document.getElementById('path_name');
  const levelInput = document.getElementById('level');

  if (!typeSelect) return;
  const type = typeSelect.value;

  // Enable/Disable Level
  if (levelInput) {
    if (type === 'level-completion') {
      levelInput.disabled = false;
    } else {
      levelInput.disabled = true;
      levelInput.value = '';
    }
  }

  // Dynamic Pathways
  if (pathSelect && typeof PATHWAYS_DATA !== 'undefined' && typeof PROGRAMS_DATA !== 'undefined') {
    let targetList = [];
    if (type === 'level-completion' || type === 'path-completion') {
      targetList = PATHWAYS_DATA;
    } else if (type === 'program-completion') {
      targetList = PROGRAMS_DATA;
    }

    const savedValue = pathSelect.value;
    pathSelect.innerHTML = '<option value="">Select Path...</option>';
    targetList.forEach(name => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.text = name;
      opt.dataset.icon = 'fa-map-signs'; // Ensure icon is preserved
      if (name === savedValue) opt.selected = true;
      pathSelect.appendChild(opt);
    });

    if (window.achievementPathSelect) window.achievementPathSelect.refresh();
  }
}

async function handleAchievementSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const id = document.getElementById('achievement-id').value;
  const contactId = document.getElementById('contact_id').value;
  const typeSelect = document.getElementById('achievement_type').value;

  if (!contactId) {
    alert('Please select a valid member.');
    return;
  }

  // Prevent silent HTML5 validation failure by checking hidden inputs explicitly
  if (!typeSelect) {
    alert('Please select an Achievement Type.');
    return;
  }

  const formData = new FormData(form);
  const url = id ? `/achievement/form/${id}` : '/achievement/form';

  try {
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    });

    // Check if it's a 400 Bad Request (duplicate)
    if (!response.ok) {
      const data = await response.json();
      if (data.message) {
        alert(data.message);
      } else {
        alert('An error occurred while saving.');
      }
      return;
    }

    if (response.redirected) {
      window.location.href = response.url;
      return;
    }

    // If it's a standard redirect from achievement_form, it goes back to settings
    window.location.reload();
  } catch (error) {
    console.error('Error saving achievement:', error);
    alert('An error occurred while saving.');
  }
}

window.openEditRoleModal = openEditRoleModal;
window.openEditSessionModal = openEditSessionModal;

/**
 * User Management Modal Logic
 */
function openUserModal(userId = null, btn = null) {
  const modal = document.getElementById('userModal');
  const title = document.getElementById('user-modal-title');
  const form = document.getElementById('user-form');

  if (!modal || !form) return;

  // Reset form
  form.reset();
  document.getElementById('user_id').value = '';
  document.getElementById('user_contact_id').value = '';

  // Reset select input
  const roleSelect = document.getElementById('role_id_select');
  if (roleSelect) {
    Array.from(roleSelect.options).forEach(opt => {
      if (opt.dataset.name === 'Member' || opt.text.trim() === 'Member') {
        opt.selected = true;
      } else {
        opt.selected = false;
      }
    });
  }

  if (userId && btn) {
    const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
    const tr = btn.closest('tr');
    title.textContent = isChinese ? '编辑用户' : 'Edit User';
    document.getElementById('user_id').value = userId;
    document.getElementById('user_contact_id').value = tr.dataset.contactId || '';
    document.getElementById('username').value = tr.dataset.username || '';
    document.getElementById('first_name').value = tr.dataset.firstName || '';
    document.getElementById('last_name').value = tr.dataset.lastName || '';
    document.getElementById('email').value = tr.dataset.email || '';
    document.getElementById('phone').value = tr.dataset.phone || '';

    // Populate role
    try {
      const userRoles = JSON.parse(tr.dataset.roles || '[]');
      if (userRoles.length > 0 && roleSelect) {
        Array.from(roleSelect.options).forEach(opt => {
          if (userRoles.includes(parseInt(opt.value))) {
            opt.selected = true;
          } else {
            opt.selected = false;
          }
        });
      }
    } catch (e) {
      console.error('Error parsing user roles:', e);
    }

    // Password placeholder
    document.getElementById('password').placeholder = isChinese ? '留空以保持当前密码' : 'Leave blank to keep current';
  } else {
    const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
    title.textContent = isChinese ? '添加新用户' : 'Add New User';
    document.getElementById('password').placeholder = isChinese ? '输入密码...' : 'Enter password...';
  }

  modal.style.display = 'flex';
}

function closeUserModal() {
  const modal = document.getElementById('userModal');
  if (modal) modal.style.display = 'none';
}

async function handleUserSubmit(e) {
  e.preventDefault();

  // Prevent submission if duplicate modal is open
  const duplicateModal = document.getElementById('duplicateModal');
  if (duplicateModal && duplicateModal.style.display === 'flex') {
    return;
  }

  const form = e.target;
  const userId = document.getElementById('user_id').value;
  const url = userId ? `/user/form/${userId}` : '/user/form';

  const formData = new FormData(form);

  try {
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    });

    if (response.redirected) {
      window.location.href = response.url;
      return;
    }

    // Usually redirects back to settings
    window.location.reload();
  } catch (error) {
    console.error('Error saving user:', error);
    window.location.reload();
  }
}

window.openUserModal = openUserModal;
window.closeUserModal = closeUserModal;
window.handleUserSubmit = handleUserSubmit;

/**
 * Remove User from Club confirmation modal.
 * Reuses the generic delete modal but with a descriptive message.
 */
function openRemoveUserModal(actionUrl, userName) {
  const deleteModal = document.getElementById("deleteModal");
  const deleteForm = document.getElementById("deleteForm");
  const deleteModalText = document.getElementById("deleteModalText");
  
  if (deleteForm && deleteModal && deleteModalText) {
    deleteForm.action = actionUrl;
    deleteModalText.innerHTML = `
      <strong>Remove "${userName}" from this club?</strong><br><br>
      <span style="font-size: 0.9em; color: #666;">
        Their contact record will be converted from <em>Member</em> to <em>Guest</em>.<br>
        If the user has no other club memberships, their account will also be removed.
      </span>
    `;
    deleteModal.style.display = "flex";
  }
}
window.openRemoveUserModal = openRemoveUserModal;

/**
 * Duplicate Detection for Users in Modal
 */
let lastCheckedUserValues = { username: '', first_name: '', last_name: '', email: '', phone: '' };

async function checkUserDuplicates() {
  const userId = document.getElementById('user_id').value;
  const contactId = document.getElementById('user_contact_id').value;
  const clubIdElement = document.querySelector('input[name="club_id"]');
  const clubId = clubIdElement ? clubIdElement.value : '';

  // Only check for NEW users or users not linked to contact.
  // Also skip once a contact has been picked from the duplicate dialog
  // (Convert to User) — the dialog has done its job, re-firing is noise.
  if (contactId) return;
  if (userId) return;

  const username = document.getElementById('username').value.trim();
  const firstName = document.getElementById('first_name').value.trim();
  const lastName = document.getElementById('last_name').value.trim();
  const email = document.getElementById('email').value.trim();
  const phone = document.getElementById('phone').value.trim();

  // Don't check if all fields are empty
  if (!username && !firstName && !lastName && !email && !phone) return;

  // Check if anything has actually changed to avoid redundant checks
  if (username === lastCheckedUserValues.username &&
    firstName === lastCheckedUserValues.first_name &&
    lastName === lastCheckedUserValues.last_name &&
    email === lastCheckedUserValues.email &&
    phone === lastCheckedUserValues.phone) {
    return;
  }

  lastCheckedUserValues = { username, first_name: firstName, last_name: lastName, email, phone };

  try {
    const response = await fetch('/user/check_duplicates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username, first_name: firstName, last_name: lastName,
        full_name: `${firstName} ${lastName}`.trim(),
        email, phone
      })
    });

    const data = await response.json();
    const duplicateModal = document.getElementById('duplicateModal');
    const duplicateList = document.getElementById('duplicateList');
    const modalTitle = duplicateModal ? duplicateModal.querySelector('h3') : null;
    const proceedWithNewBtn = document.getElementById('proceedWithNew');

    if (data.duplicates && data.duplicates.length > 0) {
      if (!duplicateList || !duplicateModal) return;

      duplicateList.innerHTML = '';
      let hasHardDuplicate = false;

      data.duplicates.forEach(dup => {
        const div = document.createElement('div');
        div.className = 'duplicate-item';

        const info = document.createElement('div');
        info.className = 'duplicate-info';
        const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
        const clubsText = dup.clubs && dup.clubs.length > 0 ? dup.clubs.join(', ') : (isChinese ? '无俱乐部成员身份' : 'No club memberships');

        let membershipNotice = '';
        let buttonText = isChinese ? '邀请用户' : 'Invite User';

        if (dup.in_current_club) {
          if (dup.type === 'User' || dup.has_user) {
            membershipNotice = `<div class="status-text" style="color: #dc3545;">${isChinese ? '已经是该俱乐部的成员。' : 'Already a member of this club.'}</div>`;
            buttonText = isChinese ? '查看成员' : 'View Member';
            hasHardDuplicate = true;
          } else {
            membershipNotice = `<div class="status-text" style="color: #28a745;">${isChinese ? '该俱乐部的现有宾客。' : 'Existing guest in this club.'}</div>`;
            buttonText = isChinese ? '转为用户' : 'Convert to User';
          }
        }

        let nameDisplay = dup.username;
        const first = dup.first_name || '';
        const last = dup.last_name || '';
        if (first || last) nameDisplay = `${first} ${last}`.trim();

        const hasUsername = dup.username && dup.username.toLowerCase() !== 'n/a' && dup.username.trim() !== '';
        const displayNameHtml = (hasUsername && nameDisplay.toLowerCase() !== dup.username.toLowerCase())
          ? `<div class="dup-name">${nameDisplay}</div><div class="dup-username">(${dup.username})</div>`
          : `<div class="dup-name">${nameDisplay}</div>`;

        info.innerHTML = `
          <div class="dup-header">${displayNameHtml}</div>
          <div class="dup-details">
            <div class="dup-club-list"><i class="fas fa-university"></i> ${clubsText}</div>
            ${membershipNotice}
          </div>
        `;

        const actionDiv = document.createElement('div');
        actionDiv.className = 'duplicate-actions';

        const pickBtn = document.createElement('button');
        pickBtn.type = 'button';
        pickBtn.className = 'planner-btn planner-btn-sm planner-btn-info';
        pickBtn.textContent = buttonText;
        pickBtn.addEventListener('click', async () => {
          if (dup.type === 'Contact' && !dup.has_user && dup.in_current_club) {
            // Convert guest to user 
            document.getElementById('user_contact_id').value = dup.id;
            if (dup.first_name) document.getElementById('first_name').value = dup.first_name;
            if (dup.last_name) document.getElementById('last_name').value = dup.last_name;
            if (dup.email) document.getElementById('email').value = dup.email;
            if (dup.phone) document.getElementById('phone').value = dup.phone;
            duplicateModal.style.display = 'none';
          } else {
            const targetId = dup.type === 'User' ? dup.id : dup.user_id;
            if (!targetId) return;

            if (!dup.in_current_club) {
              // Request to join
              try {
                const res = await fetch('/user/request_join', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ target_user_id: targetId, club_id: clubId })
                });
                const joinData = await res.json();
                if (joinData.success) {
                  window.location.reload();
                } else {
                  alert(joinData.error || 'Failed to send request.');
                }
              } catch (err) {
                alert('Error sending request.');
              }
            } else {
              duplicateModal.style.display = 'none';
            }
          }
        });

        actionDiv.appendChild(pickBtn);
        div.appendChild(info);
        div.appendChild(actionDiv);
        duplicateList.appendChild(div);
      });

      if (modalTitle) {
        const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
        modalTitle.textContent = hasHardDuplicate 
          ? (isChinese ? '用户已存在' : 'User Already Exists') 
          : (isChinese ? '发现潜在的重复用户' : 'Potential Duplicate Found');
      }
      if (proceedWithNewBtn) {
        proceedWithNewBtn.style.display = hasHardDuplicate ? 'none' : 'block';
      }

      duplicateModal.style.display = 'flex';
    }
  } catch (err) {
    console.error("Duplication check failed", err);
  }
}

// Attach duplicate check and modal controls
document.addEventListener('DOMContentLoaded', () => {
  ['username', 'first_name', 'last_name', 'email', 'phone'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('blur', checkUserDuplicates);
  });

  // Duplicate modal buttons
  const proceedBtn = document.getElementById('proceedWithNew');
  if (proceedBtn) proceedBtn.onclick = () => document.getElementById('duplicateModal').style.display = 'none';

  const cancelBtn = document.getElementById('cancelSave');
  if (cancelBtn) cancelBtn.onclick = () => {
    document.getElementById('duplicateModal').style.display = 'none';
    closeUserModal();
  };

  const closeDup = document.getElementById('closeDuplicateModal');
  if (closeDup) closeDup.onclick = () => document.getElementById('duplicateModal').style.display = 'none';
});

/* --- Async User Loading --- */
async function loadUsersAsync() {
  const tableBody = document.getElementById('users-table-body');
  if (!tableBody) return;

  try {
    const response = await fetch('/api/settings/users');
    const data = await response.json();

    if (data.success) {
      tableBody.innerHTML = ''; // Clear loading row

      data.users.forEach((user, index) => {
        const tr = document.createElement('tr');
        tr.className = user.status === 'inactive' ? 'inactive-user' : '';
        tr.dataset.id = user.id;
        tr.dataset.username = user.username;
        tr.dataset.firstName = user.first_name;
        tr.dataset.lastName = user.last_name;
        tr.dataset.email = user.email;
        tr.dataset.phone = user.phone;
        tr.dataset.contactId = user.contact_id;
        tr.dataset.roles = user.roles_json;

        // Roles HTML
        const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
        let rolesHtml = '';
        if (user.best_role) {
          const roleName = user.best_role.name;
          const roleNameLower = roleName.toLowerCase();
          const knownRoles = ['sysadmin', 'clubadmin', 'operator', 'staff', 'user'];
          const badgeClass = knownRoles.includes(roleNameLower) ? `role-${roleNameLower}` : 'role-other';
          let roleDisplay = roleName;
          if (isChinese) {
            if (roleNameLower === 'sysadmin') roleDisplay = '系统管理员';
            else if (roleNameLower === 'clubadmin') roleDisplay = '俱乐部管理员';
            else if (roleNameLower === 'operator') roleDisplay = '操作员';
            else if (roleNameLower === 'staff') roleDisplay = '工作人员';
            else if (roleNameLower === 'user') roleDisplay = '普通用户';
          }
          rolesHtml = `<span class="roster-role-tag ${badgeClass}">${roleDisplay}</span>`;
        } else {
          rolesHtml = `<em class="text-muted">${isChinese ? '无角色' : 'No Role'}</em>`;
        }

        // Path HTML
        let pathHtml = '';
        if (user.current_path) {
          pathHtml = `<span class="badge-path path-${user.path_abbr}">${user.current_path}</span>`;
        }

        const contactDisplay = user.contact_name ? `${user.contact_name} (${user.username})` : `<em class="user-not-linked">${isChinese ? '未关联' : 'Not Linked'}</em>`;

        const escapedName = (user.contact_name || user.username).replace(/'/g, "\\'").replace(/"/g, '&quot;');
        let actionsHtml = `
          <div class="action-links">
            <button type="button" class="icon-btn edit-user-btn" onclick="openUserModal('${user.id}', this)" title="${isChinese ? '编辑' : 'Edit'}">
              <i class="fas fa-edit"></i>
            </button>
            <button class="delete-btn icon-btn" onclick="openRemoveUserModal('/user/delete/${user.id}', '${escapedName}')" title="${isChinese ? '移出俱乐部' : 'Remove from Club'}">
              <i class="fas fa-user-minus"></i>
            </button>
          </div>
        `;

        tr.innerHTML = `
          <td>${index + 1}</td>
          <td>${contactDisplay}</td>
          <td>${rolesHtml}</td>
          <td>${user.email}</td>
          <td>${user.phone || ''}</td>
          <td>${user.mentor_name}</td>
          <td>${pathHtml}</td>
          <td>${(user.next_project && user.next_project !== 'null') ? user.next_project : '-'}</td>
          <td>${actionsHtml}</td>
        `;

        tableBody.appendChild(tr);
      });

      // Initial filtering/pagination call if global search has a value or just to paginate
      if (window.activePaginators && window.activePaginators['user-settings']) {
        window.activePaginators['user-settings'].update();
      }

      // Trigger global search update if there is any filter applied
      const searchInput = document.getElementById('global-settings-search');
      if (searchInput && searchInput.value) {
        searchInput.dispatchEvent(new Event('keyup'));
      }

    } else {
      const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
      tableBody.innerHTML = `<tr><td colspan="9" class="text-danger text-center">${isChinese ? '无法加载用户' : 'Failed to load users'}: ${data.message}</td></tr>`;
    }
  } catch (error) {
    console.error("Error loading users:", error);
    const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
    tableBody.innerHTML = `<tr><td colspan="9" class="text-danger text-center">${isChinese ? '加载用户时出错。' : 'Error loading users.'}</td></tr>`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // If the active tab is user-settings (or no active tab set), load the users immediately
  // For simplicity, just fetch it in the background on DOMContentLoaded
  loadUsersAsync();

  // Settings initializations
  setupTableSorting("tickets-table");
  setupTableSorting("global-tickets-table");

  if (document.getElementById("tickets-table")) {
    window.activePaginators = window.activePaginators || {};
    window.activePaginators["tickets-settings"] = new TablePaginator({
      tableId: "tickets-table",
      containerId: "tickets-settings", // using the tab as container but we might need a paginator DOM if long. The global filter will just hide rows.
      pageSize: 25,
      storageKey: "tickets_table"
    });
  }

  // Add Ticket Form Submission
  const ticketForm = document.getElementById("ticket-form");
  if (ticketForm) {
    ticketForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const submitBtn = document.getElementById("ticketModalSubmitBtn");
      const errorDiv = document.getElementById("ticket-modal-error");
      const id = document.getElementById("ticket-id").value;
      const isEdit = id && id !== "";

      errorDiv.style.display = 'none';
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

      const formData = new FormData(ticketForm);
      const url = isEdit ? '/settings/tickets/update' : '/settings/tickets/add';

      try {
        let response;
        if (isEdit) {
          // update endpoint expects a list of objects based on settings_routes.py we wrote
          const payload = [{
            id: id,
            name: formData.get('name'),
            type: formData.get('type') || '',
            price: formData.get('price') || 0,
            icon: formData.get('icon') || '',
            color: formData.get('color') || '',
            expired_at: formData.get('expired_at') || null
          }];
          response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
        } else {
          response = await fetch(url, {
            method: 'POST',
            body: formData
          });
        }

        const data = await response.json();
        if (data.success) {
          window.location.reload();
        } else {
          errorDiv.textContent = data.message || "An error occurred.";
          errorDiv.style.display = 'block';
        }
      } catch (error) {
        errorDiv.textContent = "Network error: " + error.message;
        errorDiv.style.display = 'block';
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Save Ticket';
      }
    });
  }
});

/* --- Ticket Modal Logic --- */

function initTicketIconMatrix() {
  const container = document.getElementById("ticket-icon-matrix-container");
  const hiddenInput = document.getElementById("ticket-icon");

  if (!container || !hiddenInput) return;

  // Clear existing content except the hidden input
  Array.from(container.children).forEach(child => {
    if (child.id !== "ticket-icon") child.remove();
  });

  // Collect icons in use
  const inUseIcons = new Set();
  document.querySelectorAll('#tickets-table tbody tr').forEach(row => {
    const iconCell = row.querySelector('td[data-field="icon"] i');
    if (iconCell) {
      const match = iconCell.className.match(/(fa-[a-z0-9\-]+)/);
      if (match) inUseIcons.add(match[1]);
    }
  });

  const fullIconList = [];
  if (inUseIcons.size > 0) {
    const inUseArray = Array.from(inUseIcons).map(val => {
      let label = val;
      for (const group of ICON_LIST) {
        const found = group.icons.find(i => i.value === val);
        if (found) { label = found.label; break; }
      }
      return { value: val, label: label };
    });
    fullIconList.push({ group: "In Use", icons: inUseArray });
  }
  fullIconList.push(...ICON_LIST);

  // Add Grouped Icons
  fullIconList.forEach((group) => {
    const title = document.createElement("div");
    title.className = "icon-group-title";
    title.textContent = group.group;
    container.appendChild(title);

    const grid = document.createElement("div");
    grid.className = "icon-matrix";

    if (group.group === "Core Roles") {
      const noneItem = document.createElement("div");
      noneItem.className = "icon-item active";
      noneItem.dataset.value = "";
      noneItem.title = "None";
      noneItem.innerHTML = `<i class="fas fa-ban"></i>`;
      noneItem.addEventListener("click", () => {
        container.querySelectorAll(".icon-item").forEach(i => i.classList.remove("active"));
        noneItem.classList.add("active");
        hiddenInput.value = "";
      });
      grid.appendChild(noneItem);
    }

    group.icons.forEach((icon) => {
      const item = document.createElement("div");
      item.className = "icon-item";
      item.dataset.value = icon.value;
      item.title = icon.label;
      item.innerHTML = `<i class="fas ${icon.value}"></i>`;

      item.addEventListener("click", () => {
        container.querySelectorAll(".icon-item").forEach(i => i.classList.remove("active"));
        item.classList.add("active");
        hiddenInput.value = icon.value;
      });
      grid.appendChild(item);
    });
    container.appendChild(grid);
  });
}

function filterTicketIcons(searchText) {
  const lowerSearch = searchText.toLowerCase();
  const container = document.getElementById("ticket-icon-matrix-container");
  if (!container) return;

  const items = container.querySelectorAll(".icon-item");
  const groupTitles = container.querySelectorAll(".icon-group-title");

  items.forEach(item => {
    const title = (item.title || "").toLowerCase();
    const val = (item.dataset.value || "").toLowerCase();
    if (title.includes(lowerSearch) || val.includes(lowerSearch) || val === "") {
      item.style.display = "flex";
    } else {
      item.style.display = "none";
    }
  });

  // Hide empty groups
  groupTitles.forEach(title => {
    const grid = title.nextElementSibling;
    if (grid && grid.classList.contains("icon-matrix")) {
      const visibleItems = Array.from(grid.querySelectorAll(".icon-item")).filter(i => i.style.display !== "none");
      if (visibleItems.length === 0) {
        title.style.display = "none";
        grid.style.display = "none";
      } else {
        title.style.display = "block";
        grid.style.display = "grid";
      }
    }
  });
}

function openAddTicketModal() {
  document.getElementById("ticket-modal-title").innerText = "Add New Ticket";
  const form = document.getElementById("ticket-form");
  form.reset();
  document.getElementById("ticket-id").value = "";
  document.getElementById("ticket-icon").value = "";
  document.getElementById("ticket-expired-at").value = "";
  initTicketIconMatrix();
  document.getElementById("ticket-modal").style.display = "flex";
}

function openEditTicketModal(id, name, type, price, iconValue, color, expiredAt) {
  document.getElementById("ticket-modal-title").innerText = "Edit Ticket";
  const form = document.getElementById("ticket-form");
  form.reset();

  document.getElementById("ticket-id").value = id;
  document.getElementById("ticket-name").value = name;
  document.getElementById("ticket-type").value = type;
  document.getElementById("ticket-price").value = price;

  // Normalize color to 7-character hex for HTML5 input
  let normalizedColor = "#000000";
  if (color && typeof color === 'string' && color.trim() !== "" && color !== "None") {
    let raw = color.trim();
    if (raw.charAt(0) !== '#') raw = '#' + raw;
    if (raw.length === 4) { // e.g. #FFF
      raw = '#' + raw[1] + raw[1] + raw[2] + raw[2] + raw[3] + raw[3];
    }
    normalizedColor = raw.toLowerCase();
  }
  document.getElementById("ticket-color").value = normalizedColor;

  document.getElementById("ticket-icon").value = iconValue || "";

  initTicketIconMatrix();
  const container = document.getElementById("ticket-icon-matrix-container");
  if (container) {
    container.querySelectorAll(".icon-item").forEach(i => i.classList.remove("active"));
    const activeItem = container.querySelector(`.icon-item[data-value="${iconValue || ""}"]`);
    if (activeItem) activeItem.classList.add("active");
  }

  document.getElementById("ticket-expired-at").value = expiredAt || "";

  document.getElementById("ticket-modal").style.display = "flex";
}


