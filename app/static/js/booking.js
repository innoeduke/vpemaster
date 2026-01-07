// static/js/booking.js

// Note: This script assumes the following global variables are defined in the HTML:
// - isAdminView (Boolean)
// - selectedMeetingNumber (String or Number)

var localVotes = {}; // Store votes locally before batch submission


document.addEventListener("DOMContentLoaded", function () {
  // Find elements inside DOMContentLoaded
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





  document.querySelectorAll(".timeline-event").forEach((item) => {
    item.addEventListener("click", function () {
      const meetingNumber = this.dataset.meetingNumber;
      if (meetingNumber) {
        window.location.href = "/booking/" + meetingNumber;
      }
    });
  });

  // Accordion functionality
  const accordionState = JSON.parse(sessionStorage.getItem('accordionState')) || {};
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
      sessionStorage.setItem('accordionState', JSON.stringify(accordionState));
    });
  });

  // Set the initial UI state for all voting buttons on page load.
  const categories = new Set();
  const allVoteButtons = document.querySelectorAll('button.icon-btn[data-award-category]');

  allVoteButtons.forEach(btn => {
    categories.add(btn.dataset.awardCategory);
  });

  categories.forEach(category => {
    const votedButton = document.querySelector(`button.icon-btn-voted[data-award-category="${category}"]`);
    const winnerId = votedButton ? parseInt(votedButton.dataset.contactId, 10) : null;
    if (winnerId) {
      localVotes[category] = winnerId;
    }
    updateVoteButtonsUI(category, winnerId);
  });


  // Allow clicking anywhere on the row to vote (for all devices)
  document.querySelectorAll('.is-running-meeting').forEach(table => {
    table.addEventListener('click', function (event) {
      // Find the clicked row by traversing up from the event target
      const row = event.target.closest('tr');
      if (!row) return; // Exit if the click was not inside a row

      // Find the vote button within that row
      const voteButton = row.querySelector('button.icon-btn[onclick^="handleVoteClick"]');

      // If there's a vote button and the click didn't originate from the button itself, trigger the action.
      if (voteButton && !voteButton.contains(event.target)) {
        // Instead of voteButton.click(), call the handler function directly
        // to avoid issues with clicking a hidden element.
        handleVoteClick(voteButton);
      }
    });
  });

  // NEW: Done button listener
  const doneBtn = document.getElementById('done-voting-btn');
  if (doneBtn) {
    doneBtn.addEventListener('click', function () {
      submitBatchVotes();
    });
  }

}); // End of DOMContentLoaded listener

function submitBatchVotes() {
  const votes = [];
  for (const [category, contactId] of Object.entries(localVotes)) {
    votes.push({
      contact_id: contactId,
      award_category: category
    });
  }

  // Allow empty votes (clearing votes) but maybe prompt?
  // Proceeding to wipe votes if empty logic is desired behavior for "unvoting".

  fetch("/booking/batch_vote", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      meeting_number: selectedMeetingNumber,
      votes: votes
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        if (isOfficer) {
          window.location.reload(true);
        } else {
          // Transition to Thank You state
          const accordion = document.querySelector('.award-accordion');
          if (accordion) accordion.style.display = 'none';

          const actions = document.getElementById('batch-vote-actions');
          if (actions) actions.style.display = 'none';

          const instruction = document.querySelector('.voting-instruction-alert');
          if (instruction) instruction.style.display = 'none';

          const thanks = document.getElementById('thank-you-message');
          if (thanks) {
            thanks.style.display = 'block';
            thanks.scrollIntoView({ behavior: 'smooth' });
          }

          // Optional: Reload after a short delay to ensure server-side 'has_voted' check takes over next time
          setTimeout(() => {
            window.location.reload();
          }, 2000);
        }
      } else {
        alert("Error: " + data.message);
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      alert("An error occurred during voting.");
    });
}

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
        if (data.updated_sessions) {
          data.updated_sessions.forEach(session => {
            updateSessionRow(session);
          });
        } else {
          // Fallback: If un-assigning without updated_sessions (old behavior?) 
          // or just safe fallback.
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
              // (Note: 'role-cell-actions' might strictly be 'icon-cell' children depending on template version, keeping generic safety)
              const roleActions = row.querySelector(".role-cell-actions");
              if (roleActions) {
                roleActions.innerHTML = ""; // Clear out the buttons
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

  // 1. Update Dropdown (if present - usually Admin Book / Assign View)
  const selectElement = row.querySelector(".admin-assign-select");
  if (selectElement) {
    selectElement.value = sessionData.owner_id !== null ? sessionData.owner_id : "0";
    // Update selected attribute for consistency
    Array.from(selectElement.options).forEach(option => {
      if (option.value == selectElement.value) {
        option.setAttribute('selected', 'selected');
      } else {
        option.removeAttribute('selected');
      }
    });
  }

  // 2. Update Text Display (if present - usually Running/Finished/User View)
  const ownerDisplay = row.querySelector('.owner-display');
  if (ownerDisplay) {
    ownerDisplay.textContent = sessionData.owner_name || 'Unassigned';
  }

  // 3. Update Avatar
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

  // 4. Clear icons if unassigned
  if (!sessionData.owner_id || sessionData.owner_id == 0) {
    const roleActions = row.querySelector(".role-cell-actions");
    if (roleActions) {
      roleActions.innerHTML = "";
    }
  }
}

function handleVoteClick(buttonEl) {
  const meetingNumber = buttonEl.dataset.meetingNumber;
  const contactId = parseInt(buttonEl.dataset.contactId, 10);
  const awardCategory = buttonEl.dataset.awardCategory;

  // Toggle logic: if already selected, unselect
  if (localVotes[awardCategory] === contactId) {
    delete localVotes[awardCategory];
    updateVoteButtonsUI(awardCategory, null);
  } else {
    localVotes[awardCategory] = contactId;
    updateVoteButtonsUI(awardCategory, contactId);

    // Auto-collapse accordion
    const accordionItem = buttonEl.closest('.accordion-item');
    if (accordionItem) {
      const header = accordionItem.querySelector('.accordion-header');
      const content = accordionItem.querySelector('.accordion-content');
      if (header && header.classList.contains('active')) {
        // Collapse it
        header.classList.remove('active');
        content.style.maxHeight = null;
        // Update session state
        const category = accordionItem.dataset.category;
        const accordionState = JSON.parse(sessionStorage.getItem('accordionState')) || {};
        if (category) delete accordionState[category];
        sessionStorage.setItem('accordionState', JSON.stringify(accordionState));
      }
    }
  }

  // Show Done button if we have interaction
  const doneBtnContainer = document.getElementById('batch-vote-actions');
  if (doneBtnContainer) {
    doneBtnContainer.style.display = 'block';
  }
}

function updateVoteButtonsUI(category, newWinnerId) {
  // Find all buttons in this award category
  const allButtons = document.querySelectorAll(
    `button[data-award-category="${category}"]`
  );

  allButtons.forEach((button) => {
    const buttonContactId = parseInt(button.dataset.contactId, 10);
    const row = button.closest('tr');

    // Default state: hide button, remove classes, and reset title
    button.style.display = 'none';
    button.classList.remove('icon-btn-voted');
    if (row) row.classList.remove('voted');
    button.title = "Vote";

    // If this button belongs to the winner, show it and apply voted styles
    if (newWinnerId !== null && buttonContactId === newWinnerId) {
      button.style.display = 'inline-block';
      button.classList.add('icon-btn-voted');
      if (row) row.classList.add('voted');
      button.title = `Cancel Vote (${category})`;
    }
  });

  // NEW: Update accordion header color
  const accordionItem = document.querySelector(`.accordion-item[data-category="${category}"]`);
  if (accordionItem) {
    const header = accordionItem.querySelector('.accordion-header');
    if (header) {
      if (newWinnerId !== null) {
        header.classList.add('voted');
      } else {
        header.classList.remove('voted');
      }
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

function syncTally() {
  if (!confirm("Are you sure you want to sync the roles for this meeting to Tally?")) {
    return;
  }

  // Use global selectedMeetingNumber
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