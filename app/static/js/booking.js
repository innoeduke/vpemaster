// static/js/booking.js

// Note: This script assumes the following global variables are defined in the HTML:
// - isAdminView (Boolean)
// - selectedMeetingNumber (String or Number)


document.addEventListener("DOMContentLoaded", function () {
  if (isAdminView) {
    document.querySelectorAll(".admin-assign-select").forEach((select) => {
      select.addEventListener("change", function () {
        const sessionId = this.dataset.sessionId;
        const contactId = this.value;
        assignRole(sessionId, contactId);
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


function assignRole(sessionId, contactId) {
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
        alert("Error: " + data.message);
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
        alert("Synced successfully!");
      } else {
        alert("Error: " + data.message);
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      alert("An error occurred.");
    });
}