// static/js/booking.js

// Note: This script assumes the following global variables are defined in the HTML:
// - isAdminView (Boolean)
// - selectedMeetingNumber (String or Number)
// - selectedLevel (String or Number)

document.addEventListener("DOMContentLoaded", function () {
  // Find elements inside DOMContentLoaded
  const levelFilter = document.getElementById("level-filter");
  const meetingFilter = document.getElementById("meeting-filter");

  if (isAdminView) {
    document.querySelectorAll(".admin-assign-select").forEach((select) => {
      select.addEventListener("change", function () {
        const sessionId = this.dataset.sessionId;
        const roleKey = this.dataset.roleKey;
        const contactId = this.value;
        assignRole(sessionId, roleKey, contactId);
      });
    });
  }

  if (levelFilter) {
    levelFilter.addEventListener("change", function () {
      const newSelectedLevel = this.value;
      // Use the global 'selectedMeetingNumber' as a fallback if the dropdown isn't present
      const currentMeeting = meetingFilter
        ? meetingFilter.value
        : selectedMeetingNumber;
      let url = `/booking/${currentMeeting || ""}`;
      if (newSelectedLevel) {
        url += `?level=${newSelectedLevel}`; // Add level parameter if selected
      }
      window.location.href = url; // Navigate to the new URL
    });
  }

  // Update selected level display if a level is selected
  const selectedLevelDisplay = document.getElementById(
    "selected-level-display"
  );
  // Use the global 'selectedLevel'
  if (selectedLevelDisplay && selectedLevel) {
    selectedLevelDisplay.textContent = selectedLevel;
  }

  document.querySelectorAll(".timeline-event").forEach((item) => {
    item.addEventListener("click", function () {
      const meetingNumber = this.dataset.meetingNumber;
      // Get current level selection *inside* the event listener
      const currentLevel = levelFilter ? levelFilter.value : ""; // Get current level selection or empty string
      if (meetingNumber) {
        let url = "/booking/" + meetingNumber;
        if (currentLevel) {
          url += `?level=${currentLevel}`; // Preserve level filter
        }
        window.location.href = url;
      }
    });
  });
}); // End of DOMContentLoaded listener

// Functions remain global (or could be wrapped in an IIFE)
function bookOrCancelRole(sessionId, action, roleKey) {
  fetch("/booking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      action: action,
      role_key: roleKey,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        // Check if this is a booking action that results in waitlist for approval-required roles
        if (
          action === "book" &&
          data.message &&
          data.message.includes("approval")
        ) {
          // Instead of reloading the page, update the button dynamically
          const row = document.querySelector(
            `tr[data-session-id="${sessionId}"]`
          );
          if (row) {
            // Update the button to Leave Waitlist
            const actionCell = row.querySelector(".action-cell");
            if (actionCell) {
              actionCell.innerHTML = `<button class="btn btn-leave-waitlist" onclick="leaveWaitlist('${sessionId}', '${roleKey}')">Leave Waitlist</button>`;
            }

            // Update the waitlist display
            const waitlistCell = row.querySelector(".waitlist-cell");
            if (waitlistCell) {
              // Get user's name from session
              const currentUser = currentUserName || "Unknown User";

              // Check if waitlist info div exists, if not create it
              let waitlistInfo = waitlistCell.querySelector(".waitlist-info");
              if (!waitlistInfo) {
                waitlistInfo = document.createElement("div");
                waitlistInfo.className = "waitlist-info";
                waitlistInfo.innerHTML =
                  '<span style="font-size:0.5em;">Waitlist:</span>' +
                  '<ul class="waitlist-users"></ul>';
                waitlistCell.appendChild(waitlistInfo);
              }

              // Add current user to the waitlist
              const waitlistUsers =
                waitlistInfo.querySelector(".waitlist-users");
              const newUserItem = document.createElement("li");
              newUserItem.innerHTML =
                '<i class="fas fa-user"></i> ' + currentUser;
              waitlistUsers.appendChild(newUserItem);
            }
          }
        } else {
          window.location.reload(true); // Force reload from server for other cases
        }
      } else {
        alert("Error: " + data.message);
      }
    });
}

function assignRole(sessionId, roleKey, contactId) {
  fetch("/booking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      action: "assign",
      role_key: roleKey,
      contact_id: contactId,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        if (contactId === "0") {
          // If un-assigning, update the UI dynamically without a full page reload.
          const row = document.querySelector(
            `tr[data-session-id="${sessionId}"]`
          );
          if (row) {
            // 1. Reset the dropdown menu
            const selectElement = row.querySelector(".admin-assign-select");
            if (selectElement) {
              selectElement.value = "0";
              const previouslySelected =
                selectElement.querySelector("option[selected]");
              if (previouslySelected) {
                previouslySelected.removeAttribute("selected");
              }
            }

            // 2. Remove any award or voting icons from the role cell actions
            const roleActions = row.querySelector(".role-cell-actions");
            if (roleActions) {
              roleActions.innerHTML = ""; // Clear out the buttons
            }
            if (previouslySelected) {
              previouslySelected.removeAttribute("selected");
            }
          }
        } else {
          window.location.reload();
        }
      } else {
        alert("Error: " + data.message);
      }
    });
}
function handleVoteClick(buttonEl) {
  const data = {
    meeting_number: buttonEl.dataset.meetingNumber,
    contact_id: parseInt(buttonEl.dataset.contactId, 10),
    award_category: buttonEl.dataset.awardCategory,
  };

  fetch("/booking/vote", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
    .then((response) => response.json())
    .then((result) => {
      if (result.success) {
        // Update the UI dynamically without a full page reload
        updateVoteButtonsUI(result.award_category, result.new_winner_id);
      } else {
        alert("Error: " + result.message);
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      alert("An error occurred.");
    });
}

function updateVoteButtonsUI(category, newWinnerId) {
  // Find all buttons in this award category
  const allButtons = document.querySelectorAll(
    `button[data-award-category="${category}"]`
  );

  allButtons.forEach((button) => {
    const buttonContactId = parseInt(button.dataset.contactId, 10);
    const icon = button.querySelector("i");

    if (newWinnerId === null) {
      // A vote was CANCELED. Make all buttons in this category visible and votable.
      button.style.display = "inline-block";
      button.classList.remove("icon-btn-voted");
      button.title = "Vote";
      icon.classList.remove("fa-award");
      icon.classList.add("fa-vote-yea");
    } else {
      // A vote was CAST.
      if (buttonContactId === newWinnerId) {
        // This is the new winner. Make it a trophy.
        button.style.display = "inline-block";
        button.classList.add("icon-btn-voted");
        button.title = `Cancel Vote (${category})`;
        icon.classList.remove("fa-vote-yea");
        icon.classList.add("fa-award");
      } else {
        // This is another role in the same category. Hide it.
        button.style.display = "none";
      }
    }
  });
}

function leaveWaitlist(sessionId, roleKey) {
  fetch("/booking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      action: "leave_waitlist",
      role_key: roleKey,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        // Reload the page to ensure all role statuses and buttons are correctly updated from the server.
        // This is more robust than trying to manage complex state on the client side.
        window.location.reload(true);
      } else {
        alert("Error: " + data.message);
      }
    });
}

function approveWaitlist(sessionId, roleKey) {
  fetch("/booking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      action: "approve_waitlist",
      role_key: roleKey,
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

function joinWaitlist(sessionId, roleKey) {
  fetch("/booking/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      action: "join_waitlist",
      role_key: roleKey,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        // Reload the page to ensure all role statuses and buttons are correctly updated from the server.
        window.location.reload(true);
      } else {
        alert("Error: " + data.message);
      }
    });
}
