// static/js/booking.js

// Note: This script assumes the following global variables are defined in the HTML:
// - isAdminView (Boolean)
// - selectedMeetingNumber (String or Number)


document.addEventListener("DOMContentLoaded", function () {
  if (isAdminView) {
    document.querySelectorAll(".admin-assign-select").forEach((select) => {
      select.addEventListener("focus", function () {
        // Store the current value to support reverting on error
        this.dataset.previousValue = this.value;
      });
      select.addEventListener("change", function () {
        const sessionId = this.dataset.sessionId;
        const contactId = this.value;
        assignRole(sessionId, contactId, this);
      });
    });
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

}); // End of DOMContentLoaded listener


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
              const selectElement = row.querySelector(".admin-assign-select");
              if (selectElement) {
                selectElement.value = "0";
                const previouslySelected =
                  selectElement.querySelector("option[selected]");
                if (previouslySelected) {
                  previouslySelected.removeAttribute("selected");
                }
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

        // Revert the dropdown if provided
        if (selectElement && selectElement.dataset.previousValue !== undefined) {
          selectElement.value = selectElement.dataset.previousValue;
        } else if (selectElement) {
          // Fallback: try to match DOM state or reload? 
          // If we don't have previousValue, we can't easily revert accurately without a fetch.
          // But we added the focus listener so it should exist.
          selectElement.value = selectElement.dataset.previousValue || "0";
        }
      }
    });
}


function updateSessionRow(sessionData) {
  const row = document.querySelector(`tr[data-session-id="${sessionData.session_id}"]`);
  if (!row) return;

  // Update Dropdown (if present - Admin Book / Assign View)
  const selectElement = row.querySelector(".admin-assign-select");
  if (selectElement) {
    selectElement.value = sessionData.owner_id !== null ? sessionData.owner_id : "0";
    Array.from(selectElement.options).forEach(option => {
      if (option.value == selectElement.value) {
        option.setAttribute('selected', 'selected');
      } else {
        option.removeAttribute('selected');
      }
    });
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