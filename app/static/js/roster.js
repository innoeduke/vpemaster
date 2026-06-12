// --- Global Helpers ---
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

function handleJsonResponse(response) {
  return response.text().then((text) => {
    let data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      // If it's not JSON, return the text or a generic message
      return { ok: response.ok, error: text || "Unknown server error", status: response.status };
    }
    return { ok: response.ok, data, status: response.status };
  });
}

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
    formContainer: document.querySelector(".roster-form-container"),
    quantityInput: document.getElementById("quantity"),
    isPopulating: false // Flag to prevent auto-calculations during form population
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

  elements.contactNameInput.value = contact.Name;
  elements.contactIdInput.value = contact.id;

  // Default logic for new entry
  const isOfficer = contact.is_officer === true || contact.is_officer === "true" || contact.Type === "Officer";
  if (isOfficer) {
    elements.contactTypeSelect.value = "Officer";
  } else {
    elements.contactTypeSelect.value = contact.Type || "Guest";
  }

  // Trigger change handler to set ticket and order number
  elements.contactTypeSelect.dispatchEvent(new Event('change', { bubbles: true }));
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
function calculateNextOrder(isFree, tableBody) {
  if (!tableBody) return 1;
  const rows = tableBody.querySelectorAll("tr[data-entry-id]");
  let maxRegular = 0;
  let maxFree = 0;

  rows.forEach((row) => {
    const orderCell = row.querySelector("td:first-child");
    if (orderCell && orderCell.textContent) {
      const order = parseInt(orderCell.textContent.trim(), 10);
      if (!isNaN(order)) {
        if (order >= 1000) {
            if (order > maxFree) maxFree = order;
        } else {
            if (order > maxRegular) maxRegular = order;
        }
      }
    }
  });

  if (isFree) {
    return maxFree < 1000 ? 1000 : maxFree + 1;
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
    const currentTicketId = elements.ticketSelect.value;

    // Find all ticket options associated with the elements.ticketSelect custom UI
    const ticketResultsContainer = document.getElementById("ticket-results");
    const ticketOptions = ticketResultsContainer ? Array.from(ticketResultsContainer.querySelectorAll(".autocomplete-result-item")) : [];

    // Filter tickets based on contact type
    let isCurrentTicketValid = false;
    let officerTicketId = "";
    let earlyBirdTicketId = "";
    let currentTicketText = "";

    if (currentTicketId) {
      const currentOpt = ticketOptions.find(o => o.dataset.value === currentTicketId);
      if (currentOpt) currentTicketText = currentOpt.dataset.text;
    }

    // Get meeting date and server-now from page container
    const pageContainer = document.querySelector(".page-container");
    const meetingDateStr = pageContainer ? pageContainer.dataset.meetingDate : "";
    const serverNowStr = pageContainer ? pageContainer.dataset.serverNow : "";
    
    // Use server now if available, otherwise fallback to local browser time
    const now = serverNowStr ? new Date(serverNowStr.replace(' ', 'T')) : new Date();

    let isCurrentTicketExpired = false;

    ticketOptions.forEach(option => {
      const type = option.dataset.type;
      const value = option.dataset.value;
      const text = (option.dataset.text || "").trim().toLowerCase();
      const expiredAt = option.dataset.expiredAt;

      // Show ticket if its type matches contactType or if the ticket type is empty/null (generic)
      const isTypeValid = !type || type === "None" || type === contactType;
      
      let isExpired = false;
      if (expiredAt && meetingDateStr) {
        const [hours, minutes] = expiredAt.split(':').map(Number);
        const [y, m, d] = meetingDateStr.split('-').map(Number);
        const expiryDatetime = new Date(y, m - 1, d, hours, minutes, 0, 0);
        isExpired = now > expiryDatetime;
        
        if (value === currentTicketId) {
            isCurrentTicketExpired = isExpired;
        }
      }

      if (isTypeValid) {
        option.style.display = "flex";
        
        // Priority defaults
        if (text === "officer") officerTicketId = value;
        
        // Potential defaults for Members/Guests
        // Only set if NOT expired
        if (!isExpired) {
            const isGuest = contactType === "Guest";
            const isMember = contactType === "Member" || contactType === "Officer";
            const isOfficer = contactType === "Officer";

            // If we find an exact match or clear prefix for the type name, prioritize it
            if (isGuest && (text === "guest" || text.startsWith("guest"))) earlyBirdTicketId = value;
            else if (isOfficer && (text === "officer" || text.startsWith("officer"))) earlyBirdTicketId = value;
            else if (isMember && (text === "member" || text.startsWith("member"))) earlyBirdTicketId = value;
            
            // Fallback to Early-bird if no exact type match yet
            if (!earlyBirdTicketId && (text.includes("early-bird") || text.includes("early bird"))) {
                earlyBirdTicketId = value;
            }
            
            // Further fallbacks
            if (!earlyBirdTicketId) {
                if (text.includes("walk-in")) earlyBirdTicketId = value;
                if (text.includes("role-taker") && contactType === "Guest") earlyBirdTicketId = value;
            }
        }

        if (value === currentTicketId) isCurrentTicketValid = true;
      } else {
        option.style.display = "none";
      }
    });

    const currentTicketLower = (currentTicketText || "").trim().toLowerCase();
    // Check if current ticket is considered a "default" ticket name
    const isDefaultTicket = !currentTicketId || 
                           currentTicketLower.startsWith("early-bird") || 
                           currentTicketLower === "early bird" ||
                           currentTicketLower.startsWith("officer");

    // Swap logic:
    const shouldSwap = !currentTicketId || !isCurrentTicketValid || isCurrentTicketExpired || isDefaultTicket;

    if (shouldSwap) {
      const newDefaultId = (contactType === "Officer") ? officerTicketId : earlyBirdTicketId;
      if (currentTicketId !== newDefaultId && newDefaultId) {
        elements.ticketSelect.value = newDefaultId;
        elements.ticketSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }
    }

    // Auto-reassign order number upon updates to the ticket/contact_type, 
    // but only if we are NOT in the middle of populating the form for an existing entry.
    if (!elements.isPopulating) {
        updateOrderNumber(elements);
    }
  });

  // Track manual ticket changes
  elements.ticketSelect.addEventListener("change", function (e) {
    if (e.target !== elements.ticketSelect) return;
    
    // Auto-reassign order number upon updates to the ticket/contact_type
    if (!elements.isPopulating) {
        updateOrderNumber(elements);
    }
  });
}

/**
 * Reassigns the order number based on the currently selected ticket's price.
 * Paid tickets (price > 0) -> 1-999 range.
 * Free tickets (price = 0) -> 1000+ range.
 */
function updateOrderNumber(elements) {
  if (!elements.ticketSelect || !elements.orderNumberInput) return;

  const isEditing = elements.entryIdInput && elements.entryIdInput.value.trim() !== "";
  // If editing an existing entry that already has an order number, do not overwrite it.
  if (isEditing && elements.orderNumberInput.value.trim() !== "") {
    return;
  }

  const ticketResultsContainer = document.getElementById("ticket-results");
  const ticketOptions = ticketResultsContainer ? Array.from(ticketResultsContainer.querySelectorAll(".autocomplete-result-item")) : [];
  const selectedTicketOpt = ticketOptions.find(o => o.dataset.value === elements.ticketSelect.value);
  
  // If no ticket is selected yet, we can't reliably determine the range, 
  // but usually one is auto-selected before this is called.
  if (selectedTicketOpt) {
    const isFree = parseFloat(selectedTicketOpt.dataset.price) === 0;
    const nextOrder = calculateNextOrder(isFree, elements.tableBody);
    
    // Only auto-reassign if currently empty, or we want to force it?
    // The user requested that order_number should be REASSIGNED when updated, 
    // but if we are in Add mode and it's already set, maybe we leave it?
    // Actually, let's keep the logic but ensure we can submit empty values.
    elements.orderNumberInput.value = nextOrder;
  }
}

// Reset the roster form to default state
function resetRosterForm(elements) {
  if (!elements.rosterForm) return;
  elements.rosterForm.reset();
  elements.entryIdInput.value = "";
  elements.formTitle.textContent = "Add Entry";
  elements.contactNameInput.value = "";
  elements.contactIdInput.value = "";
  // Default to Guest for new entries
  if (elements.contactTypeSelect) {
    elements.contactTypeSelect.value = "Guest";
    elements.contactTypeSelect.dispatchEvent(new Event('change', { bubbles: true }));
  }
  
  if (elements.cancelEditBtn) elements.cancelEditBtn.style.display = "none";
  if (elements.rosterForm) elements.rosterForm.classList.remove("editing-mode");
  if (elements.submitBtn) {
    elements.submitBtn.innerHTML = '<i class="fas fa-save"></i> <span class="btn-label-text">Register</span>';
  }
  if (elements.orderNumberInput) elements.orderNumberInput.value = "";
  if (elements.quantityInput) elements.quantityInput.value = "1";
}

// Populate form with data for editing
function populateRosterEditForm(rosterId, elements) {
  fetch(`/roster/api/entry/${rosterId}`)
    .then(handleJsonResponse)
    .then(({ ok, data, error }) => {
      if (!ok) throw new Error(data?.error || error || "Failed to fetch entry details.");
      const entry = data;
      elements.entryIdInput.value = entry.id;

      // Load order number if not null, otherwise set to empty string
      // Setting to empty string will trigger automatic calculation in the type change handler
      elements.orderNumberInput.value = (entry.order_number !== null && entry.order_number !== undefined) ? entry.order_number : "";

      elements.contactIdInput.value = entry.contact_id;
      elements.contactNameInput.value = entry.contact_name;
      if (elements.quantityInput) {
        elements.quantityInput.value = entry.quantity || 1;
      }
      // In roster view row, we set data-ticket-id on the row, but here from API we need the ID directly
      elements.ticketSelect.value = entry.ticket_id || entry.ticket;

      if (entry.contact_type) {
        elements.isPopulating = true;
        try {
            elements.contactTypeSelect.value = entry.contact_type;

            // Force ticket to Officer if type is Officer (fix for existing data where it might be a name)
            if (entry.contact_type === 'Officer') {
                const officerOpt = Array.from(document.querySelectorAll('#ticket-results .autocomplete-result-item')).find(o => o.dataset.text === 'Officer');
                if (officerOpt) elements.ticketSelect.value = officerOpt.dataset.value;
                else elements.ticketSelect.value = 'Officer'; // fallback if IDs are weird
            }

            // This dispatch will handle correctly updating the order number if it was null
            elements.contactTypeSelect.dispatchEvent(new Event('change', { bubbles: true }));

            // Also sync ticket dropdown
            if (elements.ticketSelect.value) {
                elements.ticketSelect.dispatchEvent(new Event('change', { bubbles: true }));
            }
        } finally {
            elements.isPopulating = false;
        }

        // Auto-assign order number if it is missing for this existing entry
        if (!elements.orderNumberInput.value.trim()) {
            updateOrderNumber(elements);
        }
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
        ticket_id: elements.ticketSelect.value,
        quantity: elements.quantityInput ? elements.quantityInput.value : 1,
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
      if (!formData.ticket_id) {
        showNotification("Please select a Ticket type.", "warning");
        return;
      }

      fetch(url, {
        method: method,
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrf_token") || "",
        },
        body: JSON.stringify(formData),
      })
        .then(handleJsonResponse)
        .then(({ ok, data, error }) => {
          if (!ok) throw new Error(data?.error || error || "Failed to save the entry.");
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
        fetch(`/roster/api/entry/${entryId}/restore`, {
          method: "POST",
          headers: {
            "X-CSRFToken": getCookie("csrf_token") || "",
            "X-Requested-With": "XMLHttpRequest",
          },
        })
          .then(handleJsonResponse)
          .then(({ ok, data, error }) => {
            if (!ok) throw new Error(data?.error || error || "Failed to restore entry.");
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
        fetch(`/roster/api/entry/${entryId}`, {
          method: "DELETE",
          headers: {
            "X-CSRFToken": getCookie("csrf_token") || "",
            "X-Requested-With": "XMLHttpRequest",
          },
        })
          .then(handleJsonResponse)
          .then(({ ok, data, error }) => {
            if (!ok) throw new Error(data?.error || error || "Failed to cancel entry.");
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
        fetch(`/roster/api/entry/${entryId}?hard_delete=true`, {
          method: "DELETE",
          headers: {
            "X-CSRFToken": getCookie("csrf_token") || "",
            "X-Requested-With": "XMLHttpRequest",
          },
        })
          .then(handleJsonResponse)
          .then(({ ok, data, error }) => {
            if (!ok) throw new Error(data?.error || error || "Failed to delete entry.");
            window.location.reload();
          })
          .catch((error) => {
            console.error("Error deleting entry:", error);
            alert(`Error: ${error.message}`);
          });
      }
    }

    // Handle clicking contact name to edit
    const contactLink = e.target.closest(".roster-contact-link");
    if (contactLink) {
      e.preventDefault();
      const contactId = contactLink.dataset.contactId;
      if (typeof openContactModal === "function") {
        openContactModal(contactId);
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
      "X-CSRFToken": getCookie("csrf_token") || "",
    },
  })
    .then(handleJsonResponse)
    .then(({ ok, data, error }) => {
      if (ok && data.success) {
        // Build the return URL with new contact details
        const url = new URL(window.location.href);
        url.searchParams.set("new_contact_id", data.contact.id);
        url.searchParams.set("new_contact_name", data.contact.Name);
        url.searchParams.set("new_contact_type", data.contact.Type);
        window.location.href = url.toString();
      } else {
        if (data && data.duplicate_contact) {
          showDuplicateModal(data.message, data.duplicate_contact);
        } else {
          showNotification(
            data?.message || error || "An error occurred while saving the contact.",
            "error"
          );
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
function createPrintPage(titlePrefix, meetingNum, formattedDate, regionText, clubLogoUrl, rows, headerTitle) {
  const pageDiv = document.createElement('div');
  pageDiv.className = 'print-page';

  // Page Header
  const headerDiv = document.createElement('div');
  headerDiv.className = 'print-header';
  headerDiv.style = "display: flex; width: 714px; align-items: center; justify-content: space-between; margin-bottom: 20px;";

  const textDiv = document.createElement('div');
  textDiv.style = "width: 594px; text-align: left; flex-shrink: 0;";

  textDiv.innerHTML = `
    <h2 style="margin: 0; padding: 0; font-size: 24px; word-spacing: 0.3em; white-space: nowrap;">
        ${headerTitle}
        <span style="font-size: 16px; color: #555; word-spacing: 0.2em; font-weight: normal; margin-left: 10px;">
            ${meetingNum ? `Meeting&nbsp;#${meetingNum}&nbsp;|&nbsp;` : ''}${formattedDate}
        </span>
    </h2>
    ${regionText ? `<p style="margin: 5px 0 0 0; font-size: 12px; color: #666; white-space: pre; letter-spacing: 0.5px; word-spacing: 1px;">${regionText}</p>` : ''}
  `;

  const logoDiv = document.createElement('div');
  if (clubLogoUrl) {
    logoDiv.style = "width: 120px; height: 80px; text-align: right; flex-shrink: 0; display: flex; align-items: center; justify-content: flex-end;";
    logoDiv.innerHTML = `<img src="${clubLogoUrl}" style="max-width: 100%; height: auto; max-height: 80px;" alt="Club Logo">`;
  } else {
    logoDiv.style = "width: 120px; text-align: right; flex-shrink: 0;";
  }

  headerDiv.appendChild(textDiv);
  headerDiv.appendChild(logoDiv);
  pageDiv.appendChild(headerDiv);

  const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
  const nameHeader = isChinese ? "姓名" : "Name";
  const ticketHeader = isChinese ? "门票" : "Ticket";
  const priceHeader = isChinese ? "票价" : "Ticket Price";
  const rolesHeader = isChinese ? "角色" : "Roles";
  const qtyHeader = isChinese ? "数量" : "Qty";

  // Page Table
  const table = document.createElement('table');
  table.className = 'table print-table';
  table.innerHTML = `
    <thead>
        <tr>
            <th style="width: 200px;">${nameHeader}</th>
            <th style="width: 130px;">${ticketHeader}</th>
            <th style="width: 100px;">${priceHeader}</th>
            <th style="width: 230px;">${rolesHeader}</th>
            <th style="width: 54px; text-align: center; white-space: nowrap;">${qtyHeader}</th>
        </tr>
    </thead>
    <tbody></tbody>
  `;
  const tbody = table.querySelector('tbody');
  rows.forEach(r => tbody.appendChild(r));

  pageDiv.appendChild(table);
  return pageDiv;
}

function populateExportPages() {
  const modal = document.getElementById("roster-export-modal");
  const pagesContainer = document.getElementById("print-pages-container");
  const pageContainerPrimary = document.querySelector(".page-container");
  if (!pagesContainer || !modal) return;

  // Temporarily make modal rendered for offsetHeight measurements
  const originalDisplay = modal.style.display;
  const originalPosition = modal.style.position;
  const originalLeft = modal.style.left;
  const originalTop = modal.style.top;
  const originalVisibility = modal.style.visibility;

  modal.style.display = "block";
  modal.style.position = "absolute";
  modal.style.left = "-9999px";
  modal.style.top = "-9999px";
  modal.style.visibility = "hidden";

  try {
    // Clear existing pages
    pagesContainer.innerHTML = '';

    // Get metadata for header
    const meetingNum = pageContainerPrimary ? pageContainerPrimary.dataset.meetingNumber || "0" : "0";
    const meetingDateOriginal = pageContainerPrimary ? pageContainerPrimary.dataset.meetingDate || "" : "";
    const clubId = pageContainerPrimary ? pageContainerPrimary.dataset.clubId || "" : "";
    const clubLogoUrl = pageContainerPrimary ? pageContainerPrimary.dataset.clubLogoUrl || "" : "";
    const clubNo = pageContainerPrimary ? pageContainerPrimary.dataset.clubNo || "" : "";
    const clubName = pageContainerPrimary ? pageContainerPrimary.dataset.clubName || "" : "";
    const clubDistrict = pageContainerPrimary ? pageContainerPrimary.dataset.clubDistrict || "" : "";
    const clubDivision = pageContainerPrimary ? pageContainerPrimary.dataset.clubDivision || "" : "";
    const clubArea = pageContainerPrimary ? pageContainerPrimary.dataset.clubArea || "" : "";
    const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
    let formattedDate = meetingDateOriginal;
    if (meetingDateOriginal && meetingDateOriginal.length === 10) {
      const parts = meetingDateOriginal.split('-');
      if (parts.length === 3) {
        const d = new Date(parts[0], parseInt(parts[1]) - 1, parts[2]);
        if (isChinese) {
          formattedDate = `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
        } else {
          const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
          // Use &nbsp; for the date spaces to prevent html2canvas collapsing them
          formattedDate = `${months[d.getMonth()]}&nbsp;${d.getDate()},&nbsp;${d.getFullYear()}`;
        }
      }
    }

    // Get all valid rows from the original table
    const originalRows = document.querySelectorAll("#rosterTable tbody tr");
    const officerRows = [];
    const paidRows = [];
    const unpaidRows = [];

    originalRows.forEach(row => {
      // Check if it's the 15 empty rows placeholder
      if (!row.dataset.entryId && !row.dataset.contactId && !row.querySelector('.roster-roles')) return;

      // Filter out cancelled tickets
      if (row.dataset.ticketName === "Cancelled") return;

      const nameCell = row.querySelector('.cell-name');
      const ticketCell = row.querySelector('.cell-ticket');
      const rolesCell = row.querySelector('.cell-roles');

      // Create new row for print table
      const tr = document.createElement("tr");

      // Column order: Name | Ticket | Ticket Price | Roles | Qty

      const tdName = document.createElement("td");
      if (nameCell) {
        // Strip the live check-in badge — it's a screen-only toggle for officers.
        const nameClone = nameCell.cloneNode(true);
        nameClone.querySelectorAll('.checkin-badge').forEach(el => el.remove());
        tdName.innerHTML = nameClone.innerHTML;
      }
      tr.appendChild(tdName);
      tr._contactName = tdName.textContent.trim().toLowerCase();
 
      const tdTicket = document.createElement("td");
      tdTicket.innerHTML = ticketCell ? ticketCell.innerHTML : '';
      tr.appendChild(tdTicket);
 
      const tdPrice = document.createElement("td");
      tdPrice.className = "print-cell-price";
      const priceVal = row.dataset.ticketPrice;
      tdPrice.innerHTML = (priceVal !== undefined && priceVal !== null && priceVal !== "") ? `¥${parseFloat(priceVal).toFixed(2)}` : "";
      tr.appendChild(tdPrice);
 
      const tdRoles = document.createElement("td");
      tdRoles.innerHTML = rolesCell ? rolesCell.innerHTML : '';
      tr.appendChild(tdRoles);
 
      const tdQty = document.createElement("td");
      tdQty.className = "print-cell-qty";
      const qtyCell = row.querySelector('.cell-quantity');
      tdQty.innerHTML = qtyCell ? qtyCell.innerHTML : '1';
      tr.appendChild(tdQty);
 
      // Grouping
      const ticketType = ticketCell ? ticketCell.querySelector(".ticket-badge")?.dataset.type : "";
      if (ticketType === "Officer") {
        officerRows.push(tr);
      } else {
        const orderVal = row.dataset.order;
        const isOrderNull = (orderVal === undefined || orderVal === null || orderVal === "" || orderVal === "None" || orderVal === "null");
        if (!isOrderNull) {
          paidRows.push(tr);
        } else {
          unpaidRows.push(tr);
        }
      }
    });
 
    // Sort groups alphabetically by name (case-insensitive) for exported roster
    paidRows.sort((a, b) => a._contactName.localeCompare(b._contactName));
    unpaidRows.sort((a, b) => a._contactName.localeCompare(b._contactName));
    officerRows.sort((a, b) => a._contactName.localeCompare(b._contactName));
 
    // Build region string for page header
    const regionParts = [];
    if (clubDistrict && clubDistrict !== 'None') regionParts.push(`D${clubDistrict}`);
    if (clubDivision && clubDivision !== 'None') regionParts.push(`Div ${clubDivision}`);
    if (clubArea && clubArea !== 'None') regionParts.push(`Area ${clubArea}`);
    if (clubNo && clubNo !== 'None') regionParts.push(`Club ${clubNo}`);
    if (clubName && clubName !== 'None') regionParts.push(clubName);
    const regionText = regionParts.length > 0 ? regionParts.join(' / ') : '';

    // Helper to pad page with empty rows until it fills the safely printable area
    function padPageWithEmptyRows(pageDiv) {
      const table = pageDiv.querySelector('table');
      const tbody = table.querySelector('tbody');
      const headerDiv = pageDiv.querySelector('.print-header');
      const maxHeight = 1010;

      while (true) {
        const emptyTr = document.createElement('tr');
        emptyTr.className = 'print-empty-row';
        emptyTr.innerHTML = '<td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>';
        tbody.appendChild(emptyTr);

        const currentHeight = headerDiv.offsetHeight + 20 + table.offsetHeight;
        if (currentHeight > maxHeight) {
          tbody.removeChild(emptyTr);
          break;
        }
      }
    }

    // Helper to paginate a list of rows under a specific group title
    function paginateGroup(rows, groupHeaderTitle) {
      if (rows.length === 0) {
        const pageDiv = createPrintPage(
          null, meetingNum, formattedDate, regionText, clubLogoUrl, [],
          groupHeaderTitle
        );
        pagesContainer.appendChild(pageDiv);
        padPageWithEmptyRows(pageDiv);
        return;
      }

      let pageDiv = createPrintPage(
        null, meetingNum, formattedDate, regionText, clubLogoUrl, [],
        groupHeaderTitle
      );
      pagesContainer.appendChild(pageDiv);

      let table = pageDiv.querySelector('table');
      let tbody = table.querySelector('tbody');
      let headerDiv = pageDiv.querySelector('.print-header');

      const maxHeight = 1010; // Target printable height limit inside print-page

      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        tbody.appendChild(row);

        // Measure current height
        // Header height + margin-bottom (20px) + table height
        const currentHeight = headerDiv.offsetHeight + 20 + table.offsetHeight;

        if (currentHeight > maxHeight && tbody.children.length > 1) {
          // Remove from current page
          tbody.removeChild(row);

          // Before moving to a new page, pad the current page with empty rows
          padPageWithEmptyRows(pageDiv);

          // Start a new page
          pageDiv = createPrintPage(
            null, meetingNum, formattedDate, regionText, clubLogoUrl, [],
            groupHeaderTitle
          );
          pagesContainer.appendChild(pageDiv);

          // Get elements of the new page
          table = pageDiv.querySelector('table');
          tbody = table.querySelector('tbody');
          headerDiv = pageDiv.querySelector('.print-header');

          // Append to new page
          tbody.appendChild(row);
        }
      }

      // Pad the final page of this group with empty rows
      padPageWithEmptyRows(pageDiv);
    }

    // Populate pages for each group (Paid Roster first, then Unpaid Roster, then Officers last)
    if (officerRows.length === 0 && paidRows.length === 0 && unpaidRows.length === 0) {
      paginateGroup([], isChinese ? "会议花名册" : "Meeting Roster");
    } else {
      if (paidRows.length > 0) {
        paginateGroup(paidRows, isChinese ? "已付费名单" : "Paid Roster");
      }
      if (unpaidRows.length > 0) {
        paginateGroup(unpaidRows, isChinese ? "未付费名单" : "Unpaid Roster");
      }
      if (officerRows.length > 0) {
        paginateGroup(officerRows, isChinese ? "官员" : "Officers");
      }
    }
  } finally {
    // Restore original modal styling
    modal.style.display = originalDisplay;
    modal.style.position = originalPosition;
    modal.style.left = originalLeft;
    modal.style.top = originalTop;
    modal.style.visibility = originalVisibility;
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

// -------- Self Check-In: QR modal + officer badge toggle ------------------
(function () {
  function fmtTime(iso) {
    if (!iso) return "";
    var d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
    if (isNaN(d.getTime())) return "";
    var h = String(d.getHours()).padStart(2, "0");
    var m = String(d.getMinutes()).padStart(2, "0");
    return h + ":" + m;
  }

  function refreshBadgeTooltip(badge) {
    var checkedAt = badge.getAttribute("data-checked-at");
    var via = badge.getAttribute("data-checked-via");
    var who = badge.getAttribute("data-checked-by");
    var label;
    if (checkedAt) {
      var t = fmtTime(checkedAt);
      var attribution = who || (via === "self" ? "Self" : "");
      label = "Checked in " + t + (attribution ? " (" + attribution + ")" : "");
    } else {
      label = "Not checked in";
    }
    badge.setAttribute("title", label);
    badge.setAttribute("aria-label", label);
  }

  document.addEventListener("click", function (ev) {
    var badge = ev.target.closest(".checkin-badge");
    if (!badge || badge.disabled) return;
    ev.preventDefault();
    if (badge.dataset.busy === "1") return;
    var id = badge.getAttribute("data-id");
    if (!id) return;

    badge.dataset.busy = "1";
    badge.disabled = true;
    fetch("/roster/api/entry/" + encodeURIComponent(id) + "/checkin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        var checked = !!data.checked_in_at;
        badge.classList.toggle("is-checked", checked);
        badge.setAttribute("data-checked-at", data.checked_in_at || "");
        badge.setAttribute("data-checked-via", data.checked_in_via || "");
        badge.setAttribute("data-checked-by", data.checked_in_by || "");
        var icon = badge.querySelector("i");
        if (icon) {
          icon.classList.toggle("fa-check-circle", checked);
          icon.classList.toggle("fa-circle", !checked);
        }
        refreshBadgeTooltip(badge);
      })
      .catch(function () {
        alert("Could not update check-in. Try again.");
      })
      .finally(function () {
        badge.dataset.busy = "";
        badge.disabled = false;
      });
  });

  var qrBtn = document.getElementById("show-checkin-qr-btn");
  var modal = document.getElementById("checkin-qr-modal");
  var img = document.getElementById("checkin-qr-img");
  var urlInput = document.getElementById("checkin-qr-url");
  var openLink = document.getElementById("checkin-qr-open");
  var copyBtn = document.getElementById("checkin-qr-copy");
  var closeBtn = document.getElementById("checkin-qr-close");

  function openModal() {
    if (!modal || !qrBtn) return;
    var meetingId = qrBtn.getAttribute("data-meeting-id");
    if (!meetingId) return;
    // .custom-modal uses flexbox centering — must be 'flex', not 'block'.
    modal.style.display = "flex";
    if (img) {
      img.removeAttribute("src");
      img.alt = "Loading…";
    }
    if (urlInput) urlInput.value = "";
    if (openLink) openLink.removeAttribute("href");

    fetch("/roster/api/checkin/url/" + encodeURIComponent(meetingId))
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        if (urlInput) urlInput.value = data.url || "";
        if (openLink && data.url) openLink.setAttribute("href", data.url);
        if (img) {
          if (data.qr_data_uri) {
            img.src = data.qr_data_uri;
          } else {
            img.src = "/roster/api/checkin/qr/" + encodeURIComponent(meetingId) + "?t=" + Date.now();
          }
          img.alt = "Check-In QR";
        }
      })
      .catch(function () {
        if (img) img.alt = "Could not load QR";
        alert("Could not load the QR code. Make sure the meeting is active and the Self Check-In module is enabled.");
      });
  }

  function closeModal() {
    if (modal) modal.style.display = "none";
  }

  if (qrBtn) qrBtn.addEventListener("click", openModal);
  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (modal) {
    modal.addEventListener("click", function (ev) {
      if (ev.target === modal) closeModal();
    });
  }
  if (copyBtn && urlInput) {
    copyBtn.addEventListener("click", function () {
      if (!urlInput.value) return;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(urlInput.value);
      } else {
        urlInput.select();
        try { document.execCommand("copy"); } catch (e) {}
      }
      var original = copyBtn.innerHTML;
      copyBtn.innerHTML = '<i class="fas fa-check"></i>';
      setTimeout(function () { copyBtn.innerHTML = original; }, 1200);
    });
  }
})();
