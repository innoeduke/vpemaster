// --- Modal Variables ---
// These are needed by the openContactModal() function in base.html
const contactModal = document.getElementById("contactModal");
const contactForm = document.getElementById("contactForm");
const contactModalTitle = document.getElementById("contactModalTitle");

/**
 * Sets up the search and sort functionality for the contacts table.
 */
document.addEventListener("DOMContentLoaded", function () {
  // Call the reusable functions from main.js
  setupTableSorting("contactsTable");
  setupTableFilter("contactsTable", "searchInput", "clear-searchInput");
});
