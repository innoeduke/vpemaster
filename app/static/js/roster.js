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
    ticketSelect: document.getElementById("ticket")
  };
}

// Shared state
let contacts = [];
let suggestionsContainer = null;

// Fetch contacts from the server
async function fetchContacts() {
  try {
    const response = await fetch('/contacts/search');
    if (!response.ok) throw new Error('Failed to fetch contacts.');
    contacts = await response.json();
  } catch (error) {
    console.error("Error fetching contacts:", error);
    alert('Could not fetch contacts for autocomplete.');
  }
}

// Show autocomplete suggestions
function showSuggestions(filteredContacts, elements) {
  if (!suggestionsContainer) {
    suggestionsContainer = document.createElement('div');
    suggestionsContainer.className = 'autocomplete-suggestions';
    elements.contactNameInput.parentNode.insertBefore(suggestionsContainer, elements.contactNameInput.nextSibling);
  }
  suggestionsContainer.innerHTML = '';
  if (filteredContacts.length === 0) {
    suggestionsContainer.style.display = 'none';
    return;
  }
  filteredContacts.forEach(contact => {
    const div = document.createElement('div');
    div.className = 'autocomplete-suggestion';
    div.textContent = contact.Name;
    div.dataset.contactId = contact.id;
    div.dataset.contactType = contact.Type;
    div.dataset.userRole = contact.UserRole;
    div.addEventListener('click', () => {
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
  elements.contactNameInput.value = contact.Name;
  elements.contactIdInput.value = contact.id;

  // Prioritize Officer if UserRole indicates they are an officer
  const isOfficer = contact.is_officer;
  if (isOfficer) {
    elements.contactTypeSelect.value = "Officer";
  } else if (contact.Type) {
    elements.contactTypeSelect.value = contact.Type;
  }

  if (elements.contactTypeSelect.value) {
    elements.contactTypeSelect.dispatchEvent(new Event('change'));
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
    const filteredContacts = contacts.filter(c => c.Name.toLowerCase().includes(query));
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
    window.location.href = `/roster?meeting_number=${elements.meetingFilter.value}`;
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
      elements.ticketSelect.value = "Early-bird";
    }

    // Only update order number if adding a new entry (no entry ID)
    if (!elements.entryIdInput.value) {
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

  // Default to regular order
  elements.orderNumberInput.value = calculateNextOrder(false, elements.tableBody);
}

// Populate form with data for editing
function populateRosterEditForm(rosterId, elements) {
  fetch(`/roster/api/roster/${rosterId}`)
    .then(response => {
      if (!response.ok) {
        throw new Error('Failed to fetch entry details.');
      }
      return response.json();
    })
    .then(entry => {
      elements.entryIdInput.value = entry.id;
      elements.orderNumberInput.value = entry.order_number;
      elements.contactIdInput.value = entry.contact_id;
      elements.contactNameInput.value = entry.contact_name;
      elements.ticketSelect.value = entry.ticket;

      if (entry.contact_type) {
        elements.contactTypeSelect.value = entry.contact_type;
        elements.contactTypeSelect.dispatchEvent(new Event('change'));
      }

      elements.formTitle.textContent = 'Edit Entry';
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
        ? `/roster/api/roster/${entryId}`
        : "/roster/api/roster";
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

    if (editButton) {
      e.preventDefault();
      const entryId = editButton.dataset.id;
      populateRosterEditForm(entryId, elements);
    }

    if (cancelButton) {
      e.preventDefault();
      const entryId = cancelButton.dataset.id;
      if (confirm("Are you sure you want to cancel this roster entry?")) {
        fetch(`/roster/api/roster/${entryId}`, { method: "DELETE" })
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
  });
}

// Main initialization
document.addEventListener("DOMContentLoaded", async function () {
  // Cache all DOM elements once
  const elements = cacheElements();

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
