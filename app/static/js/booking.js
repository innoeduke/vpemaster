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
        const contactId = this.value;
        assignRole(sessionId, contactId);
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

  const isFinishedMeeting = document.querySelector('.is-finished-meeting') !== null;

  // For finished meetings in admin view, hide vote buttons for roles in categories that already have a winner
  if (isAdminView && !isFinishedMeeting) {
    hideVotedCategoryButtons();
  }

  // Accordion functionality
  const accordionHeaders = document.querySelectorAll(".accordion-header");
  accordionHeaders.forEach(header => {
    header.addEventListener("click", () => {
      const accordionItem = header.parentElement;
      const accordionContent = header.nextElementSibling;

      // Toggle active class for styling
      header.classList.toggle("active");

      // Toggle content display
      if (accordionContent.style.maxHeight) {
        accordionContent.style.maxHeight = null;
      } else {
        accordionContent.style.maxHeight = accordionContent.scrollHeight + "px";
      }
    });
  });

  // For mobile devices, allow clicking anywhere on the row to vote
  if (window.innerWidth <= 768) {
    document.querySelectorAll('.is-running-meeting tbody tr').forEach(row => {
      row.addEventListener('click', function() {
        // Find the vote button within the row
        const voteButton = this.querySelector('button.icon-btn[onclick^="handleVoteClick"]');
        if (voteButton) {
          // Trigger the vote
          voteButton.click();
        }
      });
    });
  }

}); // End of DOMContentLoaded listener

// Functions remain global (or could be wrapped in an IIFE)
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
        updateVoteButtonsUI(result.award_category, result.your_vote_id);
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
    const row = button.closest('tr'); // Get the parent row

    if (newWinnerId === null) {
      // A vote was CANCELED. Make all buttons in this category visible and votable.
      button.style.setProperty("display", "inline-block", "important");
      button.classList.remove("icon-btn-voted");
      button.title = "Vote";
      if (row) row.classList.remove('voted'); // Remove voted class from row
    } else {
      // A vote was CAST.
      if (buttonContactId === newWinnerId) {
        // This is the new winner. Make it visible and styled as voted.
        button.style.display = "inline-block";
        button.classList.add("icon-btn-voted");
        button.title = `Cancel Vote (${category})`;
        if (row) row.classList.add('voted'); // Add voted class to row
      } else {
        // This is another role in the same category. Hide it.
        button.style.display = "none";
        if (row) row.classList.remove('voted'); // Ensure other rows are not styled as voted
      }
    }
  });
}

// New function to hide vote buttons for roles in categories that already have a winner
function hideVotedCategoryButtons() {
  // Find all voted buttons (with the icon-btn-voted class)
  const votedButtons = document.querySelectorAll(
    "button.icon-btn-voted[data-award-category]"
  );

  // For each voted button, hide all other buttons in the same award category
  votedButtons.forEach((votedButton) => {
    const category = votedButton.dataset.awardCategory;
    const winnerId = parseInt(votedButton.dataset.contactId, 10);

    // Find all buttons in this award category
    const allButtonsInCategory = document.querySelectorAll(
      `button[data-award-category="${category}"]`
    );

    // Hide all buttons except the winner
    allButtonsInCategory.forEach((button) => {
      const buttonContactId = parseInt(button.dataset.contactId, 10);
      if (buttonContactId !== winnerId) {
        button.style.display = "none";
      }
    });
  });
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
        // Reload the page to ensure all role statuses and buttons are correctly updated from the server.
        // This is more robust than trying to manage complex state on the client side.
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
        // Reload the page to ensure all role statuses and buttons are correctly updated from the server.
        window.location.reload(true);
      } else {
        alert("Error: " + data.message);
      }
    });
}