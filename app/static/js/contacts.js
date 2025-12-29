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

  const filterTable = () => {
    const activeTabItem = document.querySelector(".nav-item.active");
    if (!activeTabItem) return;

    const activeTab = activeTabItem.dataset.type;

    // Toggle guest-view class for column hiding
    if (activeTab === 'Guest') {
      table.classList.add('guest-view');
    } else {
      table.classList.remove('guest-view');
    }

    const searchTerm = searchInput.value.toUpperCase().trim();
    const rows = table.querySelectorAll("tbody tr");

    clearBtn.style.display = searchTerm.length > 0 ? "block" : "none";

    rows.forEach((row) => {
      const rowType = row.dataset.type;
      const typeMatch = activeTab === "All" || rowType === activeTab;

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
});
