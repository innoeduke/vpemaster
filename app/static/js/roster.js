// Cache DOM elements once for better performance
function cacheElements() {
  return {
    meetingFilter: document.getElementById("meeting-filter") || document.getElementById("roster-meeting-filter"),
    rosterForm: document.getElementById("roster-form"),
    tableBody: document.querySelector(".table tbody"),
    cancelEditBtn: document.getElementById("cancel-edit"),
    formTitle: document.getElementById("form-title"),
    entryIdInput: document.getElementById("entry-id"),
    orderNumberInput: document.getElementById("order_number"),
    contactNameInput: document.getElementById("contact_name"),
    contactIdInput: document.getElementById("contact_id"),
    contactTypeSelect: document.getElementById("contact_type"),
    ticketSelect: document.getElementById("ticket")
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
  // Check if contact already exists in the roster table for this meeting
  const existingRow = elements.tableBody.querySelector(`tr[data-contact-id="${contact.id}"]`);
  
  if (existingRow) {
    const entryId = existingRow.dataset.entryId;
    populateRosterEditForm(entryId, elements);
    return;
  }

  // If not in roster, ensure we are in "Add" mode for this new contact
  if (elements.entryIdInput.value) {
    elements.entryIdInput.value = "";
    elements.formTitle.textContent = "Add Entry";
    if (elements.cancelEditBtn) elements.cancelEditBtn.style.display = "none";
  }

  elements.contactNameInput.value = contact.Name;
  elements.contactIdInput.value = contact.id;

  // Default logic for new entry
  const isOfficer = contact.is_officer;
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
      return;
    }
    const filteredContacts = contacts.filter(c => c && c.Name && c.Name.toLowerCase().includes(query));
    showSuggestions(filteredContacts, elements);
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
    window.location.href = `/tools?tab=roster&meeting_number=${elements.meetingFilter.value}`;
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

  elements.contactTypeSelect.addEventListener("change", function () {
    const isOfficer = this.value === "Officer";
    if (isOfficer) {
      elements.ticketSelect.value = "Officer";
    } else {
      // Don't overwrite complex tickets (like Online/Voucher) if they already have one
      const currentTicket = elements.ticketSelect.value;
      
      // Determine default ticket based on type (Member gets Member price, others get Guest price)
      // Note: "Guest" is default if type is unknown or not Member
      const defaultTicket = (elements.contactTypeSelect.value === 'Member') 
                            ? "Early-bird (Member)" 
                            : "Early-bird (Guest)";

      // List of special tickets that shouldn't be overwritten automatically
      const specialTickets = ["Online", "Voucher", "Unpaid", "Walk-in (Guest)", "Walk-in (Member)", "Role-taker", "Officer"];
      
      // Check if current ticket is one of the special ones. 
      // We also check against the "Officer" value specifically because previously it forced Officer ticket.
      // If NOT special, or if it WAS Officer (and we are no longer Officer type), reset to default.
      if (!specialTickets.includes(currentTicket) || currentTicket === "Officer") {
          elements.ticketSelect.value = defaultTicket;
          elements.ticketSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }
    }

    // Processing logic for order number:
    // Update if: 
    // 1. It's empty (None)
    // 2. We are switching ranges (Regular to Officer or vice-versa)
    const currentOrder = parseInt(elements.orderNumberInput.value, 10);
    const orderIsNone = isNaN(currentOrder);
    const rangeMismatch = isOfficer ? (currentOrder < 1000) : (currentOrder >= 1000);

    if (orderIsNone || rangeMismatch) {
      elements.orderNumberInput.value = calculateNextOrder(isOfficer, elements.tableBody);
    }
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

  // Default to regular order
  elements.orderNumberInput.value = calculateNextOrder(false, elements.tableBody);
}

// Populate form with data for editing
function populateRosterEditForm(rosterId, elements) {
  fetch(`/tools/api/roster/${rosterId}`)
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
        // This dispatch will handle correctly updating the order number if it was null
        elements.contactTypeSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }
      
      // Also sync ticket dropdown
      if (elements.ticketSelect.value) {
        elements.ticketSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }

      elements.formTitle.textContent = 'Edit Entry';
      if (elements.cancelEditBtn) elements.cancelEditBtn.style.display = 'inline-block';
      elements.rosterForm.scrollIntoView({ behavior: 'smooth' });
    })
    .catch(error => {
      console.error('Error fetching entry for edit:', error);
      alert('Error fetching entry for edit: ' + error.message);
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
        ? `/tools/api/roster/${entryId}`
        : "/tools/api/roster";
      const method = entryId ? "PUT" : "POST";

      const formData = {
        meeting_number: elements.meetingFilter.value,
        order_number: elements.orderNumberInput.value,
        contact_id: elements.contactIdInput.value,
        contact_type: elements.contactTypeSelect.value,
        ticket: elements.ticketSelect.value,
      };

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
          alert(`An error occurred while saving the entry: ${error.message}`);
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
        fetch(`/tools/api/roster/${entryId}/restore`, { method: "POST" })
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
        fetch(`/tools/api/roster/${entryId}`, { method: "DELETE" })
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
        fetch(`/tools/api/roster/${entryId}?hard_delete=true`, { method: "DELETE" })
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
          alert(data.message || "An error occurred while saving the contact.");
        }
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      alert("An error occurred while saving the contact.");
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
});

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
