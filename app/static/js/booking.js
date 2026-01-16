// static/js/booking.js

// Note: This script assumes the following global variables are defined in the HTML:
// - isAdminView (Boolean)
// - selectedMeetingNumber (String or Number)


document.addEventListener("DOMContentLoaded", function () {
  if (isAdminView) {
    document.querySelectorAll(".autocomplete-container").forEach((container) => {
      const input = container.querySelector(".admin-assign-input");
      const results = container.querySelector(".autocomplete-results");
      const sessionId = container.dataset.sessionId;
      const isMemberOnly = container.dataset.isMemberOnly === "true";

      input.addEventListener("focus", function () {
        this.dataset.previousValue = this.value;
        this.dataset.previousId = this.dataset.currentId;
        showResults("", results, sessionId, input, isMemberOnly);
      });

      input.addEventListener("input", function () {
        showResults(this.value, results, sessionId, input, isMemberOnly);
      });

      input.addEventListener("keydown", function (e) {
        if (e.key === "Escape") {
          results.classList.remove("active");
        }
      });
    });

    // Close results when clicking outside
    document.addEventListener("click", function (e) {
      if (!e.target.closest(".autocomplete-container")) {
        document.querySelectorAll(".autocomplete-results").forEach((res) => {
          res.classList.remove("active");
        });
      }
    });

    function showResults(query, resultsContainer, sessionId, input, isMemberOnly) {
      const filteredContacts = allContacts.filter((c) => {
        const matchesQuery = c.name.toLowerCase().includes(query.toLowerCase());
        const matchesType = !isMemberOnly || c.type === "Member";
        return matchesQuery && matchesType;
      }).slice(0, 5);

      resultsContainer.innerHTML = "";

      // Add "Unassign" option if query is empty or matches "none" or "unassign"
      if (query === "" || "unassign".includes(query.toLowerCase()) || "none".includes(query.toLowerCase())) {
        const unassignItem = document.createElement("div");
        unassignItem.className = "autocomplete-item unassign-item";
        unassignItem.innerHTML = `<i class="fas fa-undo"></i> --- Unassign ---`;
        unassignItem.addEventListener("click", () => {
          selectContact(sessionId, "0", "", input, resultsContainer);
        });
        resultsContainer.appendChild(unassignItem);
      }

      filteredContacts.forEach((contact) => {
        const item = document.createElement("div");
        item.className = "autocomplete-item";
        item.innerHTML = `
          <div class="item-avatar">
              ${contact.avatar_url ? `<img src="${contact.avatar_url}" alt="">` : `<i class="fas fa-user-circle"></i>`}
          </div>
          <div class="item-name">${contact.name}</div>
          <div class="item-type ${contact.type.toLowerCase()}">${contact.type}</div>
        `;
        item.addEventListener("click", () => {
          selectContact(sessionId, contact.id, contact.name, input, resultsContainer);
        });
        resultsContainer.appendChild(item);
      });

      if (resultsContainer.children.length > 0) {
        resultsContainer.classList.add("active");
      } else {
        resultsContainer.classList.remove("active");
      }
    }

    function selectContact(sessionId, contactId, contactName, input, resultsContainer) {
      input.value = contactName;
      input.dataset.currentId = contactId;
      resultsContainer.classList.remove("active");
      if (contactId === "0") {
        input.classList.add("unassigned-role");
      } else {
        input.classList.remove("unassigned-role");
      }
      assignRole(sessionId, contactId, input);
    }
  }

  // Accordion functionality
  let accordionState = {};
  try {
    accordionState = JSON.parse(sessionStorage.getItem('bookingAccordionState')) || {};
  } catch (e) {
    console.warn("Session storage not available:", e);
  }

  const accordionHeaders = document.querySelectorAll(".accordion-header");

  accordionHeaders.forEach(header => {
    const accordionItem = header.parentElement;
    const category = accordionItem.dataset.category;
    const accordionContent = header.nextElementSibling;

    // Restore state on page load
    if (category && accordionState[category]) {
      header.classList.add("active");
      accordionContent.style.maxHeight = accordionContent.scrollHeight + "px";
    }

    header.addEventListener("click", () => {
      const isActive = header.classList.toggle("active");

      if (accordionContent.style.maxHeight) {
        accordionContent.style.maxHeight = null;
        if (category) {
          delete accordionState[category];
        }
      } else {
        accordionContent.style.maxHeight = accordionContent.scrollHeight + "px";
        if (category) {
          accordionState[category] = true;
        }
      }
      try {
        sessionStorage.setItem('bookingAccordionState', JSON.stringify(accordionState));
      } catch (e) {
        // Ignore session storage errors
      }
    });
  });

  // Meeting Filter Logic
  const meetingFilter = document.getElementById("meeting-filter");
  if (meetingFilter) {
    meetingFilter.addEventListener("change", function () {
      if (this.value) {
        window.location.href = '/booking/' + this.value;
      }
    });
  }

  document.querySelectorAll(".timeline-event").forEach((item) => {
    item.addEventListener("click", function () {
      const meetingNumber = this.dataset.meetingNumber;
      if (meetingNumber) {
        window.location.href = "/booking/" + meetingNumber;
      }
    });
  });

});
 // End of DOMContentLoaded listener


function bookOrCancelRole(sessionId, action) {
  fetch("/booking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      action: action,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        window.location.reload(true);
      } else {
        alert("Error: " + data.message);
      }
    });
}


function assignRole(sessionId, contactId, selectElement) {
  fetch("/booking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      action: "assign",
      contact_id: contactId,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        if (data.updated_sessions) {
          data.updated_sessions.forEach(session => {
            updateSessionRow(session);
          });
        } else {
          if (contactId === "0") {
            const row = document.querySelector(
              `tr[data-session-id="${sessionId}"]`
            );
            if (row) {
              const inputElement = row.querySelector(".admin-assign-input");
              if (inputElement) {
                inputElement.value = "";
                inputElement.dataset.currentId = "0";
                inputElement.classList.add("unassigned-role");
              }

              const roleActions = row.querySelector(".role-cell-actions");
              if (roleActions) {
                roleActions.innerHTML = "";
              }
            }
          } else {
            window.location.reload();
          }
        }
      } else {
        showFlashMessage(data.message, "error", selectElement); // Display message inline if possible

        // Revert the input if provided
        if (selectElement && selectElement.dataset.previousValue !== undefined) {
          selectElement.value = selectElement.dataset.previousValue;
          selectElement.dataset.currentId = selectElement.dataset.previousId;
          if (selectElement.dataset.currentId === "0") {
              selectElement.classList.add("unassigned-role");
          } else {
              selectElement.classList.remove("unassigned-role");
          }
        }
      }
    });
}


function updateSessionRow(sessionData) {
  const row = document.querySelector(`tr[data-session-id="${sessionData.session_id}"]`);
  if (!row) return;

  // Update Input (if present - Admin Book / Assign View)
  const inputElement = row.querySelector(".admin-assign-input");
  if (inputElement) {
    inputElement.value = sessionData.owner_name || '';
    inputElement.dataset.currentId = sessionData.owner_id !== null ? sessionData.owner_id : "0";
    if (sessionData.owner_id && sessionData.owner_id != 0) {
      inputElement.classList.remove('unassigned-role');
    } else {
      inputElement.classList.add('unassigned-role');
    }
  }

  // Update Text Display (if present)
  const ownerDisplay = row.querySelector('.owner-display');
  if (ownerDisplay) {
    ownerDisplay.textContent = sessionData.owner_name || 'Unassigned';
  }

  // Update Avatar
  const avatarContainer = row.querySelector('.role-avatar:not(.waitlist-avatar)');
  if (avatarContainer) {
    if (sessionData.owner_name) {
      avatarContainer.title = sessionData.owner_name;
    } else {
      avatarContainer.removeAttribute('title');
    }

    if (sessionData.owner_avatar_url) {
      avatarContainer.innerHTML = `<img src="/static/${sessionData.owner_avatar_url}" alt="User Avatar">`;
    } else {
      avatarContainer.innerHTML = '<i class="fas fa-user-circle"></i>';
    }
  }

  // Clear icons if unassigned
  if (!sessionData.owner_id || sessionData.owner_id == 0) {
    const roleActions = row.querySelector(".role-cell-actions");
    if (roleActions) {
      roleActions.innerHTML = "";
    }
  }
}


function leaveWaitlist(sessionId) {
  fetch("/booking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      action: "leave_waitlist",
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        window.location.reload(true);
      } else {
        alert("Error: " + data.message);
      }
    });
}


function approveWaitlist(sessionId) {
  fetch("/booking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      action: "approve_waitlist",
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        window.location.reload(true);
      } else {
        alert("Error: " + data.message);
      }
    });
}


function joinWaitlist(sessionId) {
  fetch("/booking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      action: "join_waitlist",
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        window.location.reload(true);
      } else {
        alert("Error: " + data.message);
      }
    });
}


function syncTally() {
  if (!confirm("Are you sure you want to sync the roles for this meeting to Tally?")) {
    return;
  }

  if (!selectedMeetingNumber) {
    alert("No meeting selected.");
    return;
  }

  fetch(`/agenda/sync_tally/${selectedMeetingNumber}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        showFlashMessage("Synced successfully!", "success");
      } else {
        showFlashMessage("Error: " + data.message, "error");
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      showFlashMessage("An error occurred.", "error");
    });
}

function showFlashMessage(message, category, targetElement) {
  let container;
  let isRowInjection = false;

  if (targetElement) {
    const row = targetElement.closest('tr');
    if (row && row.parentNode) {
      // We will create a new row to show the message below the current row
      isRowInjection = true;

      // Check if a flash row already exists below this row
      const nextRow = row.nextElementSibling;
      if (nextRow && nextRow.classList.contains('flash-message-row')) {
        nextRow.remove(); // Remove existing to replace/refresh
      }

      // Create the new row structure
      const flashRow = document.createElement('tr');
      flashRow.className = 'flash-message-row';
      const colCount = row.children.length;

      const cell = document.createElement('td');
      cell.colSpan = colCount;
      cell.style.padding = '0'; // Let the div handle padding
      cell.style.border = 'none';

      container = cell; // We will append the div to this cell
      flashRow.appendChild(cell);

      // Insert after current row
      row.parentNode.insertBefore(flashRow, row.nextSibling);

      // Auto-remove row after 5 seconds
      setTimeout(() => {
        if (flashRow && flashRow.parentElement) {
          flashRow.remove();
        }
      }, 5000);
    }
  }

  // Fallback to global container
  if (!container) {
    container = document.querySelector(".flash-messages");
    if (!container) {
      container = document.createElement("div");
      container.className = "flash-messages";
      document.body.appendChild(container);
    }
  }

  // Create the message element
  const flashDiv = document.createElement("div");
  flashDiv.className = `flash ${category}`;

  if (isRowInjection) {
    flashDiv.style.margin = "5px 10px"; // Add some spacing within the row
    flashDiv.style.borderRadius = "4px";
  }

  flashDiv.innerHTML = `${message}<span class="close-flash" onclick="this.closest('${isRowInjection ? 'tr' : '.flash'}').remove();">&times;</span>`;

  // Append to container
  container.appendChild(flashDiv);

  // Auto-remove (global only, row handled above)
  if (!isRowInjection) {
    setTimeout(() => {
      if (flashDiv.parentElement) {
        flashDiv.remove();
      }
    }, 5000);
  }
}