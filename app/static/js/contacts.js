// --- Modal Variables ---
// These are needed by the openContactModal() function in base.html
const contactModal = document.getElementById("contactModal");
const contactForm = document.getElementById("contactForm");
const contactModalTitle = document.getElementById("contactModalTitle");

/**
 * Sets up the search and sort functionality for the contacts table.
 */
/**
 * Sets up the search, sort, and tab functionality for the contacts table.
 */
document.addEventListener("DOMContentLoaded", function () {
  const table = document.getElementById("contactsTable");
  const searchInput = document.getElementById("searchInput");
  const clearBtn = document.getElementById("clear-searchInput");
  const tabs = document.querySelectorAll(".nav-item");

  if (!table || !searchInput || !clearBtn) return;

  // Initialize sorting
  setupTableSorting("contactsTable");

  // Default sort by Participation (Index 1) - Descending
  if (typeof sortTableByColumn === "function") {
    sortTableByColumn(table, 1, false, "string");
  }

  const filterTable = () => {
    const activeTabItem = document.querySelector(".nav-item.active");
    if (!activeTabItem) return;

    const activeTab = activeTabItem.dataset.type;

    // Toggle guest-view class for column hiding
    if (activeTab === "Guest") {
      table.classList.add("guest-view");
      table.classList.remove("member-view");
    } else if (activeTab === "Member") {
      table.classList.remove("guest-view");
      table.classList.add("member-view");
    } else {
      table.classList.remove("guest-view", "member-view");
    }

    const searchTerm = searchInput.value.toUpperCase().trim();
    const rows = table.querySelectorAll("tbody tr");

    clearBtn.style.display = searchTerm.length > 0 ? "block" : "none";

    rows.forEach((row) => {
      const rowType = row.dataset.type;
      const typeMatch = rowType === activeTab;

      let rowText = "";
      row.querySelectorAll("td:not(:last-child)").forEach((cell) => {
        rowText += cell.textContent.toUpperCase() + " ";
      });
      const searchMatch = rowText.includes(searchTerm);

      if (typeMatch && searchMatch) {
        row.style.display = "";
      } else {
        row.style.display = "none";
      }
    });

    // Save state
    localStorage.setItem("contacts_active_tab", activeTab);
  };

  // Tab click logic
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      filterTable();
    });
  });

  // Search input logic
  searchInput.addEventListener("keyup", filterTable);
  clearBtn.addEventListener("click", () => {
    searchInput.value = "";
    filterTable();
  });

  // Restore saved tab
  const savedTab = localStorage.getItem("contacts_active_tab");
  if (savedTab) {
    const tabToActivate = Array.from(tabs).find(t => t.dataset.type === savedTab);
    if (tabToActivate) {
      tabs.forEach(t => t.classList.remove("active"));
      tabToActivate.classList.add("active");
    }
  }

  // Initial filter
  filterTable();

  // --- Auto-open Contact Modal via ID param ---
  const urlParams = new URLSearchParams(window.location.search);
  const contactIdToOpen = urlParams.get('id');

  if (contactIdToOpen) {
    // Find the row for this contact to get its type
    const rows = table.querySelectorAll("tbody tr");
    let targetRow = null;
    rows.forEach(row => {
      // We don't have a data-id on the row, but we can look for the edit button or just find by id if we added it.
      // Let's assume we can find it by checking if an edit button with this id exists in the row.
      const editBtn = row.querySelector(`button[onclick^="openContactModal(${contactIdToOpen})"]`);
      if (editBtn) {
        targetRow = row;
      }
    });

    if (targetRow) {
      const contactType = targetRow.dataset.type;
      const tabToActivate = Array.from(tabs).find(t => t.dataset.type === contactType);
      
      if (tabToActivate) {
        tabs.forEach(t => t.classList.remove("active"));
        tabToActivate.classList.add("active");
        filterTable(); // Refresh table to show the target row's tab
      }
      
      // Open the modal
      if (typeof openContactModal === 'function') {
        openContactModal(contactIdToOpen);
      }
    }
  }
});
