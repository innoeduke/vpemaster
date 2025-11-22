// static/js/main.js

/**
 * Initializes a search input with autocomplete functionality.
 * @param {string} inputId The ID of the search input element.
 * @param {Array<Object>} data The array of objects to search through (e.g., contacts).
 * @param {string} searchKey The key in the data objects to search against (e.g., 'Name').
 * @param {function(Object)} onSelect A callback function to execute when an item is selected.
 */
function initializeAutocomplete(inputId, data, searchKey, onSelect) {
  const searchInput = document.getElementById(inputId);
  if (!searchInput) return;

  let currentFocus;
  searchInput.addEventListener("input", function () {
    const val = this.value;
    closeAllLists();
    if (!val) {
      onSelect(null); // Clear selection if input is empty
      return false;
    }
    currentFocus = -1;

    const suggestions = document.createElement("div");
    suggestions.id = this.id + "autocomplete-list";
    suggestions.classList.add("autocomplete-items");
    this.parentNode.appendChild(suggestions);

    const filteredData = data.filter((item) =>
      item[searchKey].toUpperCase().includes(val.toUpperCase())
    );

    filteredData.forEach((item) => {
      const itemDiv = document.createElement("div");
      itemDiv.innerHTML =
        "<strong>" + item[searchKey].substr(0, val.length) + "</strong>";
      itemDiv.innerHTML += item[searchKey].substr(val.length);
      itemDiv.innerHTML += `<input type='hidden' value='${JSON.stringify(
        item
      )}'>`;
      itemDiv.addEventListener("click", function () {
        const selectedItem = JSON.parse(
          this.getElementsByTagName("input")[0].value
        );
        searchInput.value = selectedItem[searchKey];
        onSelect(selectedItem);
        closeAllLists();
      });
      suggestions.appendChild(itemDiv);
    });
  });

  function closeAllLists(elmnt) {
    const items = document.getElementsByClassName("autocomplete-items");
    for (let i = 0; i < items.length; i++) {
      if (elmnt != items[i] && elmnt != searchInput) {
        items[i].parentNode.removeChild(items[i]);
      }
    }
  }

  document.addEventListener("click", function (e) {
    closeAllLists(e.target);
  });
}

/**
 * Initializes a standard table or list filter search box.
 * @param {string} inputId The ID of the search input element.
 * @param {string} clearBtnId The ID of the clear button for the search input.
 * @param {string} targetSelector The CSS selector for the items to be filtered (e.g., '.speech-log-entry' or '#contactsTable tbody tr').
 * @param {string} textSelector The CSS selector within the target item where the text to be searched is located.
 */
function initializeSearchFilter(
  inputId,
  clearBtnId,
  targetSelector,
  textSelector
) {
  const searchInput = document.getElementById(inputId);
  const clearBtn = document.getElementById(clearBtnId);

  if (!searchInput || !clearBtn) return;

  const filterItems = () => {
    const filter = searchInput.value.toUpperCase();
    const items = document.querySelectorAll(targetSelector);

    clearBtn.style.display = searchInput.value.length > 0 ? "block" : "none";

    items.forEach((item) => {
      const textElement = item.querySelector(textSelector);
      if (textElement) {
        const txtValue = textElement.textContent || textElement.innerText;
        if (txtValue.toUpperCase().indexOf(filter) > -1) {
          item.style.display = "";
        } else {
          item.style.display = "none";
        }
      }
    });
  };

  const clearSearch = () => {
    searchInput.value = "";
    filterItems();
  };

  searchInput.addEventListener("keyup", filterItems);
  clearBtn.addEventListener("click", clearSearch);

  // Initial call to set button visibility
  filterItems();
}

// --- Shared Modal Functions ---

function openContactModal(contactId) {
  const contactModal = document.getElementById("contactModal");
  const contactForm = document.getElementById("contactForm");
  const contactModalTitle = document.getElementById("contactModalTitle");

  contactForm.reset();
  if (contactId) {
    contactModalTitle.textContent = "Edit Contact";
    contactForm.action = `/contact/form/${contactId}`;
    fetch(`/contact/form/${contactId}`, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then((response) => response.json())
      .then((data) => {
        document.getElementById("name").value = data.contact.Name || "";
        document.getElementById("email").value = data.contact.Email || "";
        document.getElementById("type").value = data.contact.Type || "Member";
        document.getElementById("club").value = data.contact.Club || "";
        document.getElementById("phone_number").value =
          data.contact.Phone_Number || "";
        document.getElementById("bio").value = data.contact.Bio || "";
        document.getElementById("completed_levels").value =
          data.contact.Completed_Levels || "";
        document.getElementById("dtm").checked = data.contact.DTM;
      });
  } else {
    contactModalTitle.textContent = "Add New Contact";
    contactForm.action = "/contact/form";
  }
  contactModal.style.display = "flex";
}

function closeContactModal() {
  const contactModal = document.getElementById("contactModal");
  contactModal.style.display = "none";
}

document.addEventListener("DOMContentLoaded", function () {
  const navPane = document.getElementById("nav-pane");
  const navOverlay = document.getElementById("nav-overlay");
  const mobileNavToggle = document.getElementById("mobile-nav-toggle");

  // Function to close the nav
  function closeNav() {
    if (navPane.classList.contains("expanded")) {
      navPane.classList.remove("expanded");
    }
  }

  // Add click listener to the overlay
  if (navOverlay) {
    navOverlay.addEventListener("click", closeNav);
  }
});

/**
 * Sorts an HTML table.
 * @param {HTMLTableElement} table The table to sort
 * @param {number} columnIndex The index of the column to sort
 * @param {boolean} asc Whether to sort in ascending order
 */
function sortTableByColumn(table, columnIndex, asc = true) {
  const tbody = table.querySelector("tbody");
  const rows = Array.from(tbody.querySelectorAll("tr"));
  const direction = asc ? 1 : -1;

  // Check column type based on the first data cell
  const firstCell =
    rows[0] && rows[0].querySelector(`td:nth-child(${columnIndex + 1})`);
  let colType = "text"; // Default
  if (firstCell) {
    const firstCellCheckbox = firstCell.querySelector('input[type="checkbox"]');
    const firstCellText = firstCell.textContent.trim();

    if (firstCellCheckbox) {
      colType = "checkbox";
    } else if (firstCellText.length > 0 && !isNaN(parseFloat(firstCellText))) {
      colType = "numeric";
    }
  }

  const sortedRows = rows.sort((a, b) => {
    const aCell = a.querySelector(`td:nth-child(${columnIndex + 1})`);
    const bCell = b.querySelector(`td:nth-child(${columnIndex + 1})`);
    if (!aCell || !bCell) return 0;

    switch (colType) {
      case "checkbox":
        const aChecked = aCell.querySelector('input[type="checkbox"]').checked;
        const bChecked = bCell.querySelector('input[type="checkbox"]').checked;
        return (aChecked - bChecked) * direction;

      case "numeric":
        const aNum = parseFloat(aCell.textContent.trim()) || 0;
        const bNum = parseFloat(bCell.textContent.trim()) || 0;
        return (aNum - bNum) * direction;

      default: // "text"
        const aVal = aCell.textContent.trim();
        const bVal = bCell.textContent.trim();
        return aVal.localeCompare(bVal) * direction;
    }
  });

  // Remove all existing rows from tbody
  while (tbody.firstChild) {
    tbody.removeChild(tbody.firstChild);
  }

  // Re-add the sorted rows
  tbody.append(...sortedRows);
}

/**
 * REUSABLE HELPER: Attaches click listeners to a table's sortable headers.
 */
function setupTableSorting(tableId) {
  const table = document.getElementById(tableId);
  if (!table) return;

  table.querySelectorAll("th.sortable").forEach((headerCell) => {
    headerCell.addEventListener("click", () => {
      // Adjust column index to be 0-based for the sort function
      // HTML data-column-index is 1-based, but sort function expects 0-based
      const columnIndex = parseInt(headerCell.dataset.columnIndex, 10) - 1;
      const currentDir = headerCell.dataset.sortDir;
      const newDir = currentDir === "asc" ? "desc" : "asc";

      if (typeof sortTableByColumn === "function") {
        sortTableByColumn(table, columnIndex, newDir === "asc");
      } else {
        console.error(
          "sortTableByColumn function not found. Was main.js loaded?"
        );
        return;
      }

      table
        .querySelectorAll("th.sortable")
        .forEach((th) => delete th.dataset.sortDir);

      headerCell.dataset.sortDir = newDir;
    });
  });
}

/**
 * REUSABLE HELPER: Attaches keyup/click listeners to a search box for filtering a table.
 */
function setupTableFilter(tableId, inputId, clearId) {
  const table = document.getElementById(tableId);
  const searchInput = document.getElementById(inputId);
  const clearButton = document.getElementById(clearId);

  if (!table || !searchInput || !clearButton) return;

  const tbody = table.querySelector("tbody");
  if (!tbody) return;

  const filterTable = () => {
    const filter = searchInput.value.toUpperCase().trim();
    const rows = tbody.querySelectorAll("tr");
    clearButton.style.display = filter.length > 0 ? "block" : "none";

    rows.forEach((row) => {
      let rowText = "";
      // Get text from all cells except the last one (Actions)
      row.querySelectorAll("td:not(:last-child)").forEach((cell) => {
        rowText += cell.textContent.toUpperCase() + " ";
      });

      if (rowText.includes(filter)) {
        row.style.display = "";
      } else {
        row.style.display = "none";
      }
    });
  };

  const clearSearch = () => {
    searchInput.value = "";
    filterTable();
  };

  searchInput.addEventListener("keyup", filterTable);
  clearButton.addEventListener("click", clearSearch);

  // Initial setup
  filterTable();
}
