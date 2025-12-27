document.addEventListener("DOMContentLoaded", function () {
  const meetingFilter = document.getElementById("meeting-filter");
  const rosterForm = document.getElementById("roster-form");
  const tableBody = document.querySelector(".table tbody");
  const cancelEditBtn = document.getElementById("cancel-edit");
  const formTitle = document.getElementById("form-title");
  const entryIdInput = document.getElementById("entry-id");
  const orderNumberInput = document.getElementById("order_number");
  const contactNameInput = document.getElementById("contact_name");
  const contactIdInput = document.getElementById("contact_id");
  const contactTypeSelect = document.getElementById("contact_type");
  const ticketSelect = document.getElementById("ticket");

  let contacts = [];
  let suggestionsContainer = null;

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

  function showSuggestions(filteredContacts) {
    if (!suggestionsContainer) {
      suggestionsContainer = document.createElement('div');
      suggestionsContainer.className = 'autocomplete-suggestions';
      contactNameInput.parentNode.insertBefore(suggestionsContainer, contactNameInput.nextSibling);
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
        selectContact(contact);
        hideSuggestions();
      });
      suggestionsContainer.appendChild(div);
    });
    suggestionsContainer.style.display = 'block';
  }

  function hideSuggestions() {
    if (suggestionsContainer) {
      suggestionsContainer.style.display = 'none';
    }
  }

  function selectContact(contact) {
    contactNameInput.value = contact.Name;
    contactIdInput.value = contact.id;

    // Prioritize Officer if UserRole indicates they are an officer
    const isOfficer = contact.is_officer;
    if (isOfficer) {
      contactTypeSelect.value = "Officer";
    } else if (contact.Type) {
      contactTypeSelect.value = contact.Type;
    }

    if (contactTypeSelect.value) {
      contactTypeSelect.dispatchEvent(new Event('change'));
    }
  }

  contactNameInput.addEventListener('input', () => {
    const query = contactNameInput.value.toLowerCase();
    if (query.length < 1) {
      hideSuggestions();
      return;
    }
    const filteredContacts = contacts.filter(c => c.Name.toLowerCase().includes(query));
    showSuggestions(filteredContacts);
  });

  document.addEventListener('click', (e) => {
    if (e.target !== contactNameInput) {
      hideSuggestions();
    }
  });


  if (meetingFilter) {
    meetingFilter.addEventListener("change", () => {
      window.location.href = `/roster?meeting_number=${meetingFilter.value}`;
    });
  }

  if (contactTypeSelect) {
    contactTypeSelect.addEventListener("change", function () {
      if (this.value === "Officer") {
        ticketSelect.value = "Officer";
      } else {
        ticketSelect.value = "Early-bird";
      }
    });
  }

  function resetRosterForm() {
    if (!rosterForm) return;
    rosterForm.reset();
    entryIdInput.value = "";
    formTitle.textContent = "Add Entry";
    contactNameInput.value = "";
    contactIdInput.value = "";
    contactTypeSelect.value = "";

    const rows = tableBody.querySelectorAll("tr[data-entry-id]");
    let maxOrder = 0;
    rows.forEach((row) => {
      const orderCell = row.querySelector("td:first-child");
      if (orderCell && orderCell.textContent) {
        const order = parseInt(orderCell.textContent.trim(), 10);
        if (!isNaN(order) && order > maxOrder) {
          maxOrder = order;
        }
      }
    });
    const nextOrder = maxOrder > 0 ? maxOrder + 1 : 1;
    orderNumberInput.value = nextOrder;
  }

  function populateRosterEditForm(rosterId) {
    fetch(`/roster/api/roster/${rosterId}`)
      .then(response => {
        if (!response.ok) {
          throw new Error('Failed to fetch entry details.');
        }
        return response.json();
      })
      .then(entry => {
        entryIdInput.value = entry.id;
        orderNumberInput.value = entry.order_number;
        contactIdInput.value = entry.contact_id;
        contactNameInput.value = entry.contact_name;
        ticketSelect.value = entry.ticket;

        if (entry.contact_type) {
          contactTypeSelect.value = entry.contact_type;
          contactTypeSelect.dispatchEvent(new Event('change'));
        }

        formTitle.textContent = 'Edit Entry';
        rosterForm.scrollIntoView({ behavior: 'smooth' });
      })
      .catch(error => {
        console.error('Error fetching entry for edit:', error);
        alert('Error fetching entry for edit: ' + error.message);
      });
  }

  if (cancelEditBtn) {
    cancelEditBtn.addEventListener("click", resetRosterForm);
  }

  if (rosterForm) {
    rosterForm.addEventListener("submit", function (e) {
      e.preventDefault();

      const entryId = entryIdInput.value;
      const url = entryId
        ? `/roster/api/roster/${entryId}`
        : "/roster/api/roster";
      const method = entryId ? "PUT" : "POST";

      const formData = {
        meeting_number: meetingFilter.value,
        order_number: orderNumberInput.value,
        contact_id: contactIdInput.value,
        ticket: ticketSelect.value,
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



  if (typeof setupTableSorting === "function") {
    setupTableSorting("rosterTable");
  }

  initializeLuckyDraw();

  fetchContacts().then(() => {
    if (tableBody) {
      resetRosterForm();

      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.has("new_contact_id") && urlParams.has("new_contact_name")) {
        const contactId = urlParams.get("new_contact_id");
        const contactName = decodeURIComponent(urlParams.get("new_contact_name"));
        const contactType = decodeURIComponent(
          urlParams.get("new_contact_type") || ""
        );

        const newContact = { id: contactId, Name: contactName, Type: contactType };
        contacts.push(newContact);
        selectContact(newContact);

        const url = new URL(window.location);
        url.searchParams.delete("new_contact_id");
        url.searchParams.delete("new_contact_name");
        url.searchParams.delete("new_contact_type");
        window.history.replaceState({}, document.title, url.toString());
      }

      tableBody.addEventListener("click", function (e) {
        const editButton = e.target.closest(".edit-entry");
        const cancelButton = e.target.closest(".cancel-entry");

        if (editButton) {
          e.preventDefault();
          const entryId = editButton.dataset.id;
          populateRosterEditForm(entryId);
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
  });
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

function initializeLuckyDraw() {
  const drawButton = document.getElementById('drawButton');
  if (drawButton) {
    drawButton.addEventListener('click', performLuckyDraw);
  }
}

let drawnWinners = [];

function performLuckyDraw() {
  const validEntries = [];
  const rows = document.querySelectorAll("#rosterTable tbody tr");

  rows.forEach(row => {
    const orderCell = row.querySelector('td:first-child');
    if (orderCell && orderCell.textContent.trim() !== '' && orderCell.textContent.trim() !== 'N/A') {
      const ticketCell = row.querySelector('td:nth-child(4)');
      if (ticketCell && ticketCell.textContent.trim() !== 'Cancelled') {
        const order = orderCell.textContent.trim();
        const name = row.querySelector('td:nth-child(2)').textContent.trim();

        const isAlreadyDrawn = drawnWinners.some(winner =>
          winner.order === order && winner.name === name
        );

        if (!isAlreadyDrawn) {
          validEntries.push({
            order: order,
            name: name
          });
        }
      }
    }
  });

  if (validEntries.length === 0) {
    document.getElementById('luckyDrawResult').innerHTML =
      '<div class="no-entries">No valid entries for drawing</div>';
    return;
  }

  const randomIndex = Math.floor(Math.random() * validEntries.length);
  const selectedEntry = validEntries[randomIndex];

  drawnWinners.push(selectedEntry);

  document.getElementById('luckyDrawResult').innerHTML =
    '<div class="winner-order">' + selectedEntry.order + '</div>' +
    '<div class="winner-name">' + selectedEntry.name + '</div>';

  const winnersList = document.getElementById('winnersList');
  if (winnersList) {
    const winnerElement = document.createElement('div');
    winnerElement.textContent = selectedEntry.order + '# ' + selectedEntry.name;
    winnersList.appendChild(winnerElement);
  }
}
