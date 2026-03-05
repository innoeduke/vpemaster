// Cache DOM elements once for better performance
function cacheElements() {
  return {
    meetingFilter: document.getElementById("meeting-filter"),
    rosterForm: document.getElementById("roster-form"),
    tableBody: document.querySelector(".table tbody"),
    cancelEditBtn: document.getElementById("cancel-edit"),
    formTitle: document.getElementById("form-title"),
    entryIdInput: document.getElementById("entry-id"),
    orderNumberInput: document.getElementById("order_number"),
    contactNameInput: document.getElementById("contact_name"),
    contactIdInput: document.getElementById("contact_id"),
    contactTypeSelect: document.getElementById("contact_type"),
    ticketSelect: document.getElementById("ticket"),
    submitBtn: document.getElementById("submit-roster"),
    formContainer: document.querySelector(".roster-form-container")
  };
}

// Shared state
let contacts = [];
let suggestionsContainer = null;

// Fetch contacts from the server
async function fetchContacts() {
  // Try to use pre-loaded contacts from the window object first
  if (window.rosterContacts && Array.isArray(window.rosterContacts) && window.rosterContacts.length > 0) {
    contacts = window.rosterContacts;
    console.log("Using pre-loaded contacts for roster autocomplete.");
    return;
  }

  try {
    const response = await fetch('/contacts/search');
    if (!response.ok) throw new Error('Failed to fetch contacts.');
    contacts = await response.json();
  } catch (error) {
    console.error("Error fetching contacts:", error);
    // Non-blocking error: autocomplete just won't work
  }
}

// Show autocomplete suggestions
function showSuggestions(filteredContacts, elements) {
  if (!suggestionsContainer) {
    suggestionsContainer = document.createElement('div');
    suggestionsContainer.className = 'autocomplete-suggestions';
    // Append to the relative parent (.input-name) for reliable absolute positioning
    const parent = elements.contactNameInput.closest('.input-name');
    if (parent) {
      parent.appendChild(suggestionsContainer);
    } else {
      elements.contactNameInput.parentNode.appendChild(suggestionsContainer);
    }
  }

  suggestionsContainer.innerHTML = '';
  if (filteredContacts.length === 0) {
    suggestionsContainer.style.display = 'none';
    return;
  }

  // Use absolute positioning relative to .input-name
  suggestionsContainer.style.position = 'absolute';
  // Position just below the input box (which is inside .contact-input-container)
  suggestionsContainer.style.top = '100%';
  suggestionsContainer.style.left = '0';
  suggestionsContainer.style.width = '100%';
  suggestionsContainer.style.zIndex = '1000';
  suggestionsContainer.style.backgroundColor = '#fff';
  suggestionsContainer.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
  suggestionsContainer.style.maxHeight = '200px';
  suggestionsContainer.style.overflowY = 'auto';

  filteredContacts.forEach(contact => {
    const div = document.createElement('div');
    div.className = 'autocomplete-suggestion';

    let displayText = contact.Name;
    if (contact.Type === 'Guest' && contact.Phone_Number) {
      const phone = contact.Phone_Number;
      const last4 = phone.length > 4 ? phone.slice(-4) : phone;
      displayText += ` (${last4})`;
    }
    div.textContent = displayText;

    // Use mousedown instead of click to fire before input blur
    div.addEventListener('mousedown', (e) => {
      e.preventDefault(); // Prevent input blur from hiding suggestions
      selectContact(contact, elements);
      hideSuggestions();
    });

    suggestionsContainer.appendChild(div);
  });
  suggestionsContainer.style.display = 'block';
}

// Hide autocomplete suggestions
function hideSuggestions() {
  if (suggestionsContainer) {
    suggestionsContainer.style.display = 'none';
  }
}

// Select a contact from autocomplete
function selectContact(contact, elements) {
  if (!contact) return;

  console.log(`[Roster] Selecting contact: ${contact.Name} (ID: ${contact.id}, is_officer: ${contact.is_officer})`);

  // Check if contact already exists in the roster table for this meeting
  // Try ID first, then fallback to Name if ID is missing or not found
  let existingRow = contact.id ? elements.tableBody.querySelector(`tr[data-contact-id="${contact.id}"]`) : null;

  if (!existingRow) {
    existingRow = Array.from(elements.tableBody.querySelectorAll('tr')).find(tr => {
      const nameCell = tr.querySelector('.cell-name');
      return nameCell && nameCell.textContent.trim().toLowerCase() === contact.Name.toLowerCase();
    });
  }

  if (existingRow) {
    const entryId = existingRow.dataset.entryId;
    // Avoid re-populating if we're already editing this entry
    if (elements.entryIdInput.value !== entryId) {
      console.log(`[Roster] Found existing roster entry ${entryId} for ${contact.Name}. Loading for editing.`);
      populateRosterEditForm(entryId, elements);
    }
    return;
  }

  // If not in roster, ensure we are in "Add" mode for this new contact
  if (elements.entryIdInput.value) {
    elements.entryIdInput.value = "";
    elements.formTitle.textContent = "Add Entry";
    if (elements.cancelEditBtn) elements.cancelEditBtn.style.display = "none";
    if (elements.rosterForm) elements.rosterForm.classList.remove("editing-mode");
  }

  elements.contactNameInput.value = contact.Name;
  elements.contactIdInput.value = contact.id;

  // Default logic for new entry
  const isOfficer = contact.is_officer === true || contact.is_officer === "true" || contact.Type === "Officer";
  if (isOfficer) {
    elements.contactTypeSelect.value = "Officer";
  } else if (contact.Type) {
    elements.contactTypeSelect.value = contact.Type;
  }

  // Trigger change handler to set ticket and order number
  if (elements.contactTypeSelect.value) {
    elements.contactTypeSelect.dispatchEvent(new Event('change', { bubbles: true }));
  }
}

// Initialize roster-specific autocomplete functionality
function initializeRosterAutocomplete(elements) {
  if (!elements.contactNameInput) return;

  elements.contactNameInput.addEventListener('input', () => {
    const query = elements.contactNameInput.value.toLowerCase();
    if (query.length < 1) {
      hideSuggestions();
      elements.contactIdInput.value = ""; // Clear ID if input is empty
      return;
    }
    const filteredContacts = contacts.filter(c => c && c.Name && c.Name.toLowerCase().includes(query));
    showSuggestions(filteredContacts, elements);

    // Auto-resolve ID if exact match is typed
    const exactMatch = contacts.find(c => c.Name.toLowerCase() === query);
    if (exactMatch) {
      elements.contactIdInput.value = exactMatch.id;
    } else {
      elements.contactIdInput.value = "";
    }
  });

  // Handle blur/change for exact match resolution (auto-loading existing)
  elements.contactNameInput.addEventListener('change', () => {
    const val = elements.contactNameInput.value.trim().toLowerCase();
    if (!val) return;

    const exactMatch = contacts.find(c => c.Name.toLowerCase() === val);
    if (exactMatch) {
      selectContact(exactMatch, elements);
    }
  });

  document.addEventListener('click', (e) => {
    if (e.target !== elements.contactNameInput) {
      hideSuggestions();
    }
  });
}

// Initialize meeting filter dropdown
function initializeMeetingFilter(elements) {
  if (!elements.meetingFilter) return;

  elements.meetingFilter.addEventListener("change", () => {
    window.location.href = `/roster?meeting_id=${elements.meetingFilter.value}`;
  });
}

// Calculate next order number for roster entries
function calculateNextOrder(isOfficer, tableBody) {
  if (!tableBody) return 1;
  const rows = tableBody.querySelectorAll("tr[data-entry-id]");
  let maxRegular = 0;
  let maxOverall = 0;

  rows.forEach((row) => {
    const orderCell = row.querySelector("td:first-child");
    if (orderCell && orderCell.textContent) {
      const order = parseInt(orderCell.textContent.trim(), 10);
      if (!isNaN(order)) {
        if (order > maxOverall) maxOverall = order;
        if (order < 1000 && order > maxRegular) maxRegular = order;
      }
    }
  });

  if (isOfficer) {
    return maxOverall < 1000 ? 1000 : maxOverall + 1;
  } else {
    return maxRegular > 0 ? maxRegular + 1 : 1;
  }
}

// Initialize contact type change handler
function initializeContactTypeHandler(elements) {
  if (!elements.contactTypeSelect) return;

  elements.contactTypeSelect.addEventListener("change", function (e) {
    if (e.target !== elements.contactTypeSelect) return;

    const contactType = this.value;
    const currentTicket = elements.ticketSelect.value;

    // A "default" ticket is one that is empty, "Early-bird", "Role-taker", or "Officer"
    const isDefaultTicket = !currentTicket || currentTicket === "Early-bird" || currentTicket === "Role-taker" || currentTicket === "Officer";

    console.log(`[Roster] Contact type -> ${contactType}. Ticket was: ${currentTicket || 'empty'} (isDefault: ${isDefaultTicket})`);

    if (isDefaultTicket) {
      const newDefault = (contactType === "Officer") ? "Officer" : "Early-bird";
      if (currentTicket !== newDefault) {
        console.log(`[Roster] Auto-defaulting ticket to: ${newDefault}`);
        elements.ticketSelect.value = newDefault;
        // Triggering change event so custom_select UI updates
        elements.ticketSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }
    } else {
      console.log(`[Roster] Preserving manual ticket selection: ${currentTicket}`);
    }

    // Update order number if necessary
    const isOfficer = contactType === "Officer";
    const currentOrder = parseInt(elements.orderNumberInput.value, 10);
    const orderIsNone = isNaN(currentOrder);
    const rangeMismatch = isOfficer ? (currentOrder < 1000) : (currentOrder >= 1000);

    if (orderIsNone || rangeMismatch) {
      elements.orderNumberInput.value = calculateNextOrder(isOfficer, elements.tableBody);
      console.log(`[Roster] Updated order number to: ${elements.orderNumberInput.value}`);
    }
  });

  // Track manual ticket changes for debugging
  elements.ticketSelect.addEventListener("change", function (e) {
    if (e.target !== elements.ticketSelect) return;
    console.log(`[Roster] Ticket value is now: ${this.value}`);
  });
}

// Reset the roster form to default state
function resetRosterForm(elements) {
  if (!elements.rosterForm) return;
  elements.rosterForm.reset();
  elements.entryIdInput.value = "";
  elements.formTitle.textContent = "Add Entry";
  elements.contactNameInput.value = "";
  elements.contactIdInput.value = "";
  elements.contactTypeSelect.value = "";
  elements.contactTypeSelect.dispatchEvent(new Event('change', { bubbles: true }));
  elements.ticketSelect.value = "";
  elements.ticketSelect.dispatchEvent(new Event('change', { bubbles: true }));
  if (elements.cancelEditBtn) elements.cancelEditBtn.style.display = "none";
  if (elements.rosterForm) elements.rosterForm.classList.remove("editing-mode");
  if (elements.submitBtn) {
    elements.submitBtn.innerHTML = '<i class="fas fa-save"></i> <span class="btn-label-text">Register</span>';
  }

  // Default to regular order
  elements.orderNumberInput.value = calculateNextOrder(false, elements.tableBody);
}

// Populate form with data for editing
function populateRosterEditForm(rosterId, elements) {
  fetch(`/roster/api/entry/${rosterId}`)
    .then(response => {
      if (!response.ok) {
        throw new Error('Failed to fetch entry details.');
      }
      return response.json();
    })
    .then(entry => {
      elements.entryIdInput.value = entry.id;

      // Load order number if not null, otherwise set to empty string
      // Setting to empty string will trigger automatic calculation in the type change handler
      elements.orderNumberInput.value = (entry.order_number !== null && entry.order_number !== undefined) ? entry.order_number : "";

      elements.contactIdInput.value = entry.contact_id;
      elements.contactNameInput.value = entry.contact_name;
      elements.ticketSelect.value = entry.ticket;

      if (entry.contact_type) {
        elements.contactTypeSelect.value = entry.contact_type;

        // Force ticket to Officer if type is Officer (fix for existing data)
        if (entry.contact_type === 'Officer') {
          elements.ticketSelect.value = 'Officer';
        }

        // This dispatch will handle correctly updating the order number if it was null
        elements.contactTypeSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }

      // Also sync ticket dropdown
      if (elements.ticketSelect.value) {
        elements.ticketSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }

      elements.formTitle.textContent = 'Edit Entry';
      if (elements.cancelEditBtn) elements.cancelEditBtn.style.display = 'inline-block';
      if (elements.rosterForm) elements.rosterForm.classList.add("editing-mode");
      if (elements.submitBtn) {
        elements.submitBtn.innerHTML = '<i class="fas fa-check"></i> <span class="btn-label-text">Save</span>';
      }
      elements.formContainer.scrollIntoView({ behavior: 'smooth' });
    })
    .catch(error => {
      console.error('Error fetching entry for edit:', error);
      showNotification('Error fetching entry for edit: ' + error.message, 'error');
    });
}

// Initialize form submit and cancel handlers
function initializeFormHandlers(elements) {
  if (elements.cancelEditBtn) {
    elements.cancelEditBtn.addEventListener("click", () => resetRosterForm(elements));
  }

  if (elements.rosterForm) {
    elements.rosterForm.addEventListener("submit", function (e) {
      e.preventDefault();

      const entryId = elements.entryIdInput.value;
      const url = entryId
        ? `/roster/api/entry/${entryId}`
        : "/roster/api/entry";
      const method = entryId ? "PUT" : "POST";

      const formData = {
        meeting_id: elements.meetingFilter.value,
        order_number: elements.orderNumberInput.value,
        contact_id: elements.contactIdInput.value,
        contact_type: elements.contactTypeSelect.value,
        ticket: elements.ticketSelect.value,
      };

      // Validation
      if (!formData.contact_id) {
        showNotification("Please select a name from the suggestions or add a new guest.", "warning");
        return;
      }
      if (!formData.contact_type) {
        showNotification("Please select a Contact Type.", "warning");
        return;
      }
      if (!formData.ticket) {
        showNotification("Please select a Ticket type.", "warning");
        return;
      }

      fetch(url, {
        method: method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      })
        .then((response) =>
          response.json().then((data) => ({ ok: response.ok, data }))
        )
        .then(({ ok, data }) => {
          if (!ok) throw new Error(data.error || "Failed to save the entry.");
          window.location.reload();
        })
        .catch((error) => {
          console.error("Error:", error);
          showNotification(`An error occurred: ${error.message}`, "error");
        });
    });
  }
}

// Initialize table interaction handlers (edit/delete)
function initializeTableInteractions(elements) {
  if (!elements.tableBody) return;

  resetRosterForm(elements);

  // Handle URL parameters for newly created contacts
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.has("new_contact_id") && urlParams.has("new_contact_name")) {
    const contactId = urlParams.get("new_contact_id");
    const contactName = decodeURIComponent(urlParams.get("new_contact_name"));
    const contactType = decodeURIComponent(
      urlParams.get("new_contact_type") || ""
    );

    const newContact = { id: contactId, Name: contactName, Type: contactType };
    contacts.push(newContact);
    selectContact(newContact, elements);

    const url = new URL(window.location);
    url.searchParams.delete("new_contact_id");
    url.searchParams.delete("new_contact_name");
    url.searchParams.delete("new_contact_type");
    window.history.replaceState({}, document.title, url.toString());
  }

  // Event delegation for edit and delete buttons
  elements.tableBody.addEventListener("click", function (e) {
    const editButton = e.target.closest(".edit-entry");
    const cancelButton = e.target.closest(".cancel-entry");
    const restoreButton = e.target.closest(".restore-entry");
    const deleteButton = e.target.closest(".delete-entry");

    if (editButton) {
      e.preventDefault();
      const entryId = editButton.dataset.id;
      populateRosterEditForm(entryId, elements);
    }

    if (restoreButton) {
      e.preventDefault();
      const entryId = restoreButton.dataset.id;
      if (confirm("Are you sure you want to restore this roster entry?")) {
        fetch(`/roster/api/entry/${entryId}/restore`, { method: "POST" })
          .then((response) =>
            response.json().then((data) => ({ ok: response.ok, data }))
          )
          .then(({ ok, data }) => {
            if (!ok) throw new Error(data.error || "Failed to restore entry.");
            window.location.reload();
          })
          .catch((error) => {
            console.error("Error restoring entry:", error);
            alert(`Error: ${error.message}`);
          });
      }
    }

    if (cancelButton) {
      e.preventDefault();
      const entryId = cancelButton.dataset.id;
      if (confirm("Are you sure you want to cancel this roster entry?")) {
        fetch(`/roster/api/entry/${entryId}`, { method: "DELETE" })
          .then((response) =>
            response.json().then((data) => ({ ok: response.ok, data }))
          )
          .then(({ ok, data }) => {
            if (!ok) throw new Error(data.error || "Failed to cancel entry.");
            window.location.reload();
          })
          .catch((error) => {
            console.error("Error cancelling entry:", error);
            alert(`Error: ${error.message}`);
          });
      }
    }

    if (deleteButton) {
      e.preventDefault();
      const entryId = deleteButton.dataset.id;
      if (confirm("Are you sure you want to permanently DELETE this roster entry? This cannot be undone.")) {
        fetch(`/roster/api/entry/${entryId}?hard_delete=true`, { method: "DELETE" })
          .then((response) =>
            response.json().then((data) => ({ ok: response.ok, data }))
          )
          .then(({ ok, data }) => {
            if (!ok) throw new Error(data.error || "Failed to delete entry.");
            window.location.reload();
          })
          .catch((error) => {
            console.error("Error deleting entry:", error);
            alert(`Error: ${error.message}`);
          });
      }
    }
  });
}

function handleContactFormSubmit(event) {
  event.preventDefault();
  const form = event.target;
  const formData = new FormData(form);

  fetch(form.action, {
    method: "POST",
    body: formData,
    headers: {
      "X-Requested-With": "XMLHttpRequest",
    },
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        // Build the return URL with new contact details
        const url = new URL(window.location.href);
        url.searchParams.set("new_contact_id", data.contact.id);
        url.searchParams.set("new_contact_name", data.contact.Name);
        url.searchParams.set("new_contact_type", data.contact.Type);
        window.location.href = url.toString();
      } else {
        if (data.duplicate_contact) {
          showDuplicateModal(data.message, data.duplicate_contact);
        } else {
          showNotification(data.message || "An error occurred while saving the contact.", "error");
        }
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("An error occurred while saving the contact.", "error");
    });
}

// Main initialization
document.addEventListener("DOMContentLoaded", async function () {
  // Cache all DOM elements once
  const elements = cacheElements();

  // Attach contact form listener
  const contactForm = document.getElementById("contactForm");
  if (contactForm) {
    contactForm.addEventListener("submit", handleContactFormSubmit);
  }

  // Fetch contacts before initializing autocomplete
  await fetchContacts();

  // Initialize all modules
  initializeRosterAutocomplete(elements);
  initializeMeetingFilter(elements);
  initializeContactTypeHandler(elements);
  initializeFormHandlers(elements);
  initializeTableInteractions(elements);

  // Initialize external features
  if (typeof setupTableSorting === "function") {
    setupTableSorting("rosterTable");
  }

  // Setup export handler
  const exportBtn = document.getElementById("roster-export-btn");
  if (exportBtn) {
    exportBtn.addEventListener("click", function (e) {
      const isMobile = window.innerWidth <= 768;
      if (isMobile) {
        handleDirectMobilePDF(e.currentTarget);
      } else {
        openExportModal();
      }
    });
  }
});

// Helper to handle direct PDF export on mobile without showing modal
async function handleDirectMobilePDF(btn) {
  const originalHTML = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

  const modal = document.getElementById("roster-export-modal");
  if (!modal) return;

  // Temporarily make modal "rendered" but off-screen and invisible to user
  const originalDisplay = modal.style.display;
  const originalOpacity = modal.style.opacity;
  const originalPosition = modal.style.position;
  const originalLeft = modal.style.left;
  const originalTop = modal.style.top;
  const originalZIndex = modal.style.zIndex;

  modal.style.display = "block";
  modal.style.opacity = "1";
  modal.style.position = "fixed";
  modal.style.left = "-9999px";
  modal.style.top = "0";
  modal.style.zIndex = "-1000";

  try {
    // Populate the hidden pages inside the modal container
    populateExportPages();

    // Trigger the PDF export directly
    // Increase timeout slightly to ensure full DOM rendering
    await new Promise(resolve => setTimeout(resolve, 300));
    await exportFromModalPDF();
  } catch (err) {
    console.error("Mobile direct export error:", err);
    alert("Failed to export PDF.");
  } finally {
    // Restore modal state
    modal.style.display = originalDisplay;
    modal.style.opacity = originalOpacity;
    modal.style.position = originalPosition;
    modal.style.left = originalLeft;
    modal.style.top = originalTop;
    modal.style.zIndex = originalZIndex;

    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHTML;
    }
  }
}

// Populate the print pages (shared by modal and direct export)
function populateExportPages() {
  const pagesContainer = document.getElementById("print-pages-container");
  const pageContainerPrimary = document.querySelector(".page-container");
  if (!pagesContainer) return;

  // Clear existing pages
  pagesContainer.innerHTML = '';

  // Get metadata for header
  const meetingNum = pageContainerPrimary ? pageContainerPrimary.dataset.meetingNumber || "0" : "0";
  const meetingDateOriginal = pageContainerPrimary ? pageContainerPrimary.dataset.meetingDate || "" : "";
  let formattedDate = meetingDateOriginal;
  if (meetingDateOriginal && meetingDateOriginal.length === 10) {
    const parts = meetingDateOriginal.split('-');
    if (parts.length === 3) {
      const d = new Date(parts[0], parseInt(parts[1]) - 1, parts[2]);
      const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
      // Use &nbsp; for the date spaces to prevent html2canvas collapsing them
      formattedDate = `${months[d.getMonth()]}&nbsp;${d.getDate()},&nbsp;${d.getFullYear()}`;
    }
  }

  // Get all valid rows from the original table
  const originalRows = document.querySelectorAll("#rosterTable tbody tr");
  const extractedRows = [];

  originalRows.forEach(row => {
    // Check if it's the 15 empty rows placeholder
    if (!row.dataset.entryId && !row.dataset.contactId && !row.querySelector('.roster-roles')) return;

    const orderCell = row.querySelector('.cell-order');
    const nameCell = row.querySelector('.cell-name');
    const ticketCell = row.querySelector('.cell-ticket');
    const rolesCell = row.querySelector('.cell-roles');

    // Create new row for print table
    const tr = document.createElement("tr");

    const tdOrder = document.createElement("td");
    tdOrder.className = "print-cell-order";
    tdOrder.innerHTML = orderCell ? orderCell.innerHTML : '';
    tr.appendChild(tdOrder);

    const tdName = document.createElement("td");
    tdName.innerHTML = nameCell ? nameCell.innerHTML : '';
    tr.appendChild(tdName);

    const tdTicket = document.createElement("td");
    tdTicket.innerHTML = ticketCell ? ticketCell.innerHTML : '';
    tr.appendChild(tdTicket);

    const tdRoles = document.createElement("td");
    tdRoles.innerHTML = rolesCell ? rolesCell.innerHTML : '';
    tr.appendChild(tdRoles);

    const tdV = document.createElement("td");
    tdV.className = "print-cell-v";
    tdV.innerHTML = '<div style="width: 20px; height: 20px; border: 2px solid #ccc; border-radius: 4px; display: inline-block; margin-top: 5px;"></div>';
    tr.appendChild(tdV);

    extractedRows.push(tr);
  });

  // Paginate rows into multiple A4 DOM containers (max ~12 rows per page for safety to fit taller rows with tags)
  const rowsPerPage = 12;
  const numPages = Math.ceil(extractedRows.length / rowsPerPage) || 1; // At least 1 empty page

  for (let i = 0; i < numPages; i++) {
    const pageDiv = document.createElement('div');
    pageDiv.className = 'print-page';

    // Page Header
    const headerDiv = document.createElement('div');
    headerDiv.className = 'print-header';
    headerDiv.style = "text-align: center; margin-bottom: 20px;";
    headerDiv.innerHTML = `
      <h2 style="word-spacing: 0.3em; white-space: nowrap;">Meeting&nbsp;Roster</h2>
      <p class="print-subtitle" style="font-weight: bold; color: #555; word-spacing: 0.2em; white-space: nowrap;">
          ${meetingNum ? `Meeting&nbsp;#${meetingNum}&nbsp;|&nbsp;` : ''}${formattedDate}
      </p>
    `;
    pageDiv.appendChild(headerDiv);

    // Page Table
    const table = document.createElement('table');
    table.className = 'table print-table';
    table.innerHTML = `
      <thead>
          <tr>
              <th style="width: 10%;">Order</th>
              <th style="width: 30%;">Name</th>
              <th style="width: 25%;">Ticket</th>
              <th style="width: 25%;">Roles</th>
              <th style="width: 10%; text-align: center;">V</th>
          </tr>
      </thead>
      <tbody></tbody>
    `;
    const tbody = table.querySelector('tbody');

    // Append rows for this page
    const startIdx = i * rowsPerPage;
    const endIdx = Math.min(startIdx + rowsPerPage, extractedRows.length);
    for (let j = startIdx; j < endIdx; j++) {
      tbody.appendChild(extractedRows[j]);
    }

    pageDiv.appendChild(table);
    pagesContainer.appendChild(pageDiv);
  }
}

// Open Export Modal and populate the print table
function openExportModal() {
  const modal = document.getElementById("roster-export-modal");
  if (!modal) return;

  populateExportPages();

  modal.style.display = "block";
  document.body.style.overflow = "hidden"; // Prevent background scrolling
}

// Close Export Modal
window.closeExportModal = function () {
  const modal = document.getElementById("roster-export-modal");
  if (modal) {
    modal.style.display = "none";
    document.body.style.overflow = "";
  }
};

// Ensure clicking outside modal closes it
document.addEventListener("click", function (event) {
  const modal = document.getElementById("roster-export-modal");
  if (event.target === modal) {
    closeExportModal();
  }
});

// Export print-content as JPG Image
window.exportFromModalJPG = async function (event) {
  const container = document.getElementById("print-pages-container");
  const pageContainer = document.querySelector(".page-container");
  if (!container) return;

  const btn = event ? event.currentTarget : null;
  const originalHTML = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Exporting...';
  }

  // Temporarily adjust container to capture full height without scrollbars
  const originalMaxHeight = container.style.maxHeight;
  const originalOverflow = container.style.overflowY;
  const originalBackground = container.style.background;
  const originalPadding = container.style.padding;
  const originalGap = container.style.gap;

  container.style.maxHeight = 'none';
  container.style.overflowY = 'visible';
  container.style.background = '#ffffff';
  container.style.padding = '0';
  container.style.gap = '0';

  // Temporarily remove shadow and roundness from individual pages
  const originalPageStyles = [];
  const pages = container.querySelectorAll(".print-page");
  pages.forEach(p => {
    originalPageStyles.push({
      boxShadow: p.style.boxShadow,
      margin: p.style.margin
    });
    p.style.boxShadow = 'none';
    p.style.margin = '0';
  });

  try {
    const canvas = await html2canvas(container, {
      scale: 3,
      useCORS: true,
      backgroundColor: "#ffffff",
      logging: false,
      windowWidth: 794
    });

    canvas.toBlob((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const clubShortName = pageContainer ? pageContainer.dataset.clubShortName || "club" : "club";
      const meetingNum = pageContainer ? pageContainer.dataset.meetingNumber || "0" : "0";
      const meetingDate = pageContainer ? pageContainer.dataset.meetingDate || "unknown" : "unknown";

      a.href = url;
      a.download = `${clubShortName}-${meetingNum}-Roster-${meetingDate}.jpg`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, "image/jpeg", 0.95);
  } catch (err) {
    console.error("JPG export error:", err);
    alert("Failed to export as image.");
  } finally {
    // Restore
    container.style.maxHeight = originalMaxHeight || '';
    container.style.overflowY = originalOverflow || '';
    container.style.background = originalBackground || '';
    container.style.padding = originalPadding || '';
    container.style.gap = originalGap || '';

    pages.forEach((p, idx) => {
      p.style.boxShadow = originalPageStyles[idx].boxShadow;
      p.style.margin = originalPageStyles[idx].margin;
    });

    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHTML;
    }
  }
};

// Export print-content as multi-page PDF
window.exportFromModalPDF = async function (event) {
  const pages = document.querySelectorAll(".print-page");
  const pageContainer = document.querySelector(".page-container");
  if (pages.length === 0) return;

  const btn = event ? event.currentTarget : null;
  const originalHTML = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Exporting...';
  }

  // Temporarily reset styles that might clip
  const container = document.getElementById("print-pages-container");
  const originalMaxHeight = container.style.maxHeight;
  const originalOverflow = container.style.overflowY;
  const originalBackground = container.style.background;
  const originalPadding = container.style.padding;
  const originalGap = container.style.gap;

  container.style.maxHeight = 'none';
  container.style.overflowY = 'visible';
  container.style.background = '#ffffff';
  container.style.padding = '0';
  container.style.gap = '0';

  // Temporarily remove shadow and roundness from individual pages
  const originalPageStyles = [];
  pages.forEach(p => {
    originalPageStyles.push({
      boxShadow: p.style.boxShadow,
      margin: p.style.margin
    });
    p.style.boxShadow = 'none';
    p.style.margin = '0';
  });

  try {
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF("p", "mm", "a4");
    const pageWidth = 210;
    const pageHeight = 297;

    for (let i = 0; i < pages.length; i++) {
      const page = pages[i];
      const canvas = await html2canvas(page, {
        scale: 3,
        useCORS: true,
        backgroundColor: "#ffffff",
        logging: false,
        windowWidth: 794
      });

      const imgData = canvas.toDataURL("image/jpeg", 0.95);
      if (i > 0) pdf.addPage();

      // Render it full bleed. Since .print-page is an exact A4 dimension ratio 
      // and already contains internal CSS padding, this is 1:1 pixel perfect.
      pdf.addImage(imgData, "JPEG", 0, 0, pageWidth, pageHeight);
    }

    const clubShortName = pageContainer ? pageContainer.dataset.clubShortName || "club" : "club";
    const meetingNum = pageContainer ? pageContainer.dataset.meetingNumber || "0" : "0";
    const meetingDate = pageContainer ? pageContainer.dataset.meetingDate || "unknown" : "unknown";
    pdf.save(`${clubShortName}-${meetingNum}-Roster-${meetingDate}.pdf`);

  } catch (err) {
    console.error("PDF export error:", err);
    alert("Failed to export as PDF.");
  } finally {
    container.style.maxHeight = originalMaxHeight || '';
    container.style.overflowY = originalOverflow || '';
    container.style.background = originalBackground || '';
    container.style.padding = originalPadding || '';
    container.style.gap = originalGap || '';

    pages.forEach((p, idx) => {
      p.style.boxShadow = originalPageStyles[idx].boxShadow;
      p.style.margin = originalPageStyles[idx].margin;
    });

    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHTML;
    }
  }
};

function openContactModalWithReferer() {
  if (typeof openContactModal === "function") {
    openContactModal();
  }
  const contactForm = document.getElementById("contactForm");
  if (contactForm) {
    const actionUrl = new URL(contactForm.action);
    actionUrl.searchParams.set("referer", window.location.href);
    contactForm.action = actionUrl.toString();
  }
}
