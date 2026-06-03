// static/js/voting.js

// Global variables (initialized with defaults)
let isAdminView = false;
let selectedMeetingId = null;
let userRole = null;
let canTrackProgress = false;
let localVotes = {};
let localMeetingRating = null;
let localMeetingFeedback = "";
let clubId = null;
let meetingStatus = null;
let dbStatus = null;

// Function to initialize configuration
function initVotingConfig() {
	const votingDataEl = document.getElementById('voting-data');
	if (votingDataEl) {
		try {
			const votingConfig = JSON.parse(votingDataEl.textContent);
			isAdminView = votingConfig.isAdminView;
			selectedMeetingId = votingConfig.selectedMeetingId;
			userRole = votingConfig.userRole;
			canTrackProgress = votingConfig.canTrackProgress;
			clubId = votingConfig.clubId;
			meetingStatus = votingConfig.meetingStatus;
			dbStatus = votingConfig.dbStatus;

			// Initialize rating if provided
			if (votingConfig.initialMeetingRating !== undefined && votingConfig.initialMeetingRating !== null) {
				localMeetingRating = parseInt(votingConfig.initialMeetingRating, 10);
			}
			// Initialize feedback if provided
			if (votingConfig.initialMeetingFeedback !== undefined && votingConfig.initialMeetingFeedback !== null) {
				localMeetingFeedback = votingConfig.initialMeetingFeedback;
			}
		} catch (e) {
			console.error("Failed to parse voting configuration:", e);
		}
	}
}

// Attempt initialization immediately
initVotingConfig();


document.addEventListener("DOMContentLoaded", function () {
	// Re-run init to be sure (in case script ran before body/voting-data was ready)
	initVotingConfig();

	// Accordion functionality
	const accordionState = JSON.parse(sessionStorage.getItem('accordionState')) || {};
	const accordionHeaders = document.querySelectorAll(".accordion-header");

	accordionHeaders.forEach(header => {
		const accordionItem = header.parentElement;
		const category = accordionItem.dataset.category;
		const accordionContent = header.nextElementSibling;
		const isDisabled = header.classList.contains('disabled');

		// Restore state on page load, but only if not disabled
		if (!isDisabled && category && accordionState[category]) {
			header.classList.add("active");
			accordionContent.style.maxHeight = accordionContent.scrollHeight + "px";
		}

		header.addEventListener("click", () => {
			if (header.classList.contains('disabled')) return; // Prevent interaction if disabled

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

	// Set the initial UI state for all voting buttons on page load
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

	// Initialize Meeting Rating UI
	if (localMeetingRating !== null) {
		updateRatingUI(localMeetingRating);
	}

	// Initialize Meeting Feedback UI
	if (localMeetingFeedback) {
		const feedbackInput = document.getElementById('feedback-input');
		if (feedbackInput) {
			feedbackInput.value = localMeetingFeedback;
		}
	}


	// Allow clicking anywhere on the row to vote (for all devices)
	document.querySelectorAll('.is-running-meeting').forEach(table => {
		table.addEventListener('click', function (event) {
			// Find the clicked row by traversing up from the event target
			const row = event.target.closest('tr');
			if (!row) return; // Exit if the click was not inside a row

			// Find the vote button within that row
			const voteButton = row.querySelector('button.icon-btn[onclick^="handleVoteClick"]');

			// If there's a vote button and the click didn't originate from the button itself, trigger the action
			if (voteButton && !voteButton.contains(event.target)) {
				handleVoteClick(voteButton);
			}
		});
	});

	// Done button listener
	const doneBtn = document.getElementById('done-voting-btn');
	if (doneBtn) {
		doneBtn.addEventListener('click', function () {
			submitBatchVotes();
		});
		// Initial status check
		updateDoneButtonState();
	}

	// Start live vote refresh if eligible
	startLiveVoteRefresh();

	// Start/Stop Meeting Status Button
	const startStopBtn = document.getElementById('start-stop-btn');
	if (startStopBtn) {
		startStopBtn.addEventListener('click', function () {
			handleMeetingStatusToggle(startStopBtn);
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

	if (localMeetingRating !== null) {
		votes.push({
			question: "How likely are you to recommend this meeting to a friend or colleague?",
			score: localMeetingRating
		});
	}

	if (localMeetingFeedback.trim() !== "") {
		votes.push({
			question: "More feedback/comments",
			comments: localMeetingFeedback
		});
	}

	let fetchUrl = "/voting/batch_vote";
	if (typeof window.clubId !== 'undefined' && window.clubId) {
		fetchUrl += `?club_id=${window.clubId}`;
	}

	fetch(fetchUrl, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			meeting_id: selectedMeetingId,
			votes: votes
		}),
	})
		.then((response) => response.json())
		.then((data) => {
			if (data.success) {
				if (canTrackProgress) {
					window.location.reload(true);
				} else {
					// Transition to Thank You state
					const accordion = document.querySelector('.accordion-list');
					if (accordion) accordion.style.display = 'none';

					const actions = document.getElementById('batch-vote-actions');
					if (actions) actions.style.display = 'none';

					const instruction = document.querySelector('.voting-instruction-alert');
					if (instruction) instruction.style.display = 'none';

					document.querySelectorAll('.voting-section').forEach(section => {
						section.style.display = 'none';
					});

					const thanks = document.getElementById('thank-you-message');
					if (thanks) {
						thanks.style.display = 'block';
						thanks.scrollIntoView({ behavior: 'smooth' });
					}

					// Reload after a short delay
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


function handleVoteClick(buttonEl) {
	const meetingId = buttonEl.dataset.meetingId;
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

	updateDoneButtonState();
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

	// Update accordion header color and label
	const accordionItem = document.querySelector(`.accordion-item[data-category="${category}"]`);
	if (accordionItem) {
		const header = accordionItem.querySelector('.accordion-header');
		if (header) {
			// Find or create the header-right container
			let headerRight = header.querySelector('.accordion-header-right');
			if (!headerRight) {
				// If it doesn't exist, create it and move the chevron into it
				headerRight = document.createElement('div');
				headerRight.className = 'accordion-header-right';
				const chevron = header.querySelector('.fa-chevron-down');
				if (chevron) {
					headerRight.appendChild(chevron);
				}
				header.appendChild(headerRight);
			}

			if (newWinnerId !== null) {
				header.classList.add('voted');

				// Find or create status-wrapper
				let statusWrapper = headerRight.querySelector('.status-wrapper');
				if (!statusWrapper) {
					statusWrapper = document.createElement('div');
					statusWrapper.className = 'status-wrapper';
					const chevron = headerRight.querySelector('.fa-chevron-down');
					if (chevron) {
						headerRight.insertBefore(statusWrapper, chevron);
					} else {
						headerRight.appendChild(statusWrapper);
					}
				}

				// Add VOTED label if it doesn't exist inside the wrapper
				let votedLabel = statusWrapper.querySelector('.voted-label');
				if (!votedLabel) {
					votedLabel = document.createElement('span');
					votedLabel.className = 'voted-label';
					votedLabel.innerHTML = '<i class="fas fa-trophy"></i> VOTED';
					statusWrapper.appendChild(votedLabel);
				}
			} else {
				header.classList.remove('voted');

				// Remove VOTED label if it exists in wrapper
				const statusWrapper = headerRight.querySelector('.status-wrapper');
				if (statusWrapper) {
					const votedLabel = statusWrapper.querySelector('.voted-label');
					if (votedLabel) {
						votedLabel.remove();
					}
				}
			}
		}
	}
}

function handleRatingClick(btn) {
	const score = parseInt(btn.dataset.score, 10);
	localMeetingRating = score;
	updateRatingUI(score);
	updateDoneButtonState();
}

function updateRatingUI(selectedScore) {
	const buttons = document.querySelectorAll('.rating-btn');
	buttons.forEach(btn => {
		const score = parseInt(btn.dataset.score, 10);
		if (score === selectedScore) {
			btn.classList.add('selected');
		} else {
			btn.classList.remove('selected');
		}
	});
}

function handleFeedbackInput(input) {
	localMeetingFeedback = input.value;
	updateDoneButtonState();
}

function updateDoneButtonState() {
	const doneBtn = document.getElementById('done-voting-btn');
	if (!doneBtn) return;

	// 1. Validate Award Categories (Q1-Q4, or Q1-Q5 with debater)
	let allCategoriesValid = true;
	const accordionItems = document.querySelectorAll('.accordion-item');

	accordionItems.forEach(item => {
		const category = item.dataset.category;
		if (!category) return;

		// Check if this category is disabled (e.g., insufficient candidates)
		const header = item.querySelector('.accordion-header');
		const isDisabled = header && (header.classList.contains('disabled') || header.hasAttribute('disabled'));

		if (!isDisabled) {
			// If active, user MUST have voted
			if (!localVotes[category]) {
				allCategoriesValid = false;
			}
		}
	});

	// 2. Validate Meeting Rating (Q5)
	// Must be selected (not null)
	const hasRating = localMeetingRating !== null;

	// 3. Feedback (Q6) is optional usually, but let's stick to user request "Q1 to Q5"
	// So we don't enforce feedback.

	if (allCategoriesValid && hasRating) {
		doneBtn.removeAttribute('disabled');
	} else {
		doneBtn.setAttribute('disabled', 'disabled');
	}
}


function startLiveVoteRefresh() {
	if (!canTrackProgress || meetingStatus !== 'running' || !selectedMeetingId) {
		return;
	}

	// Poll every 5 seconds
	setInterval(fetchLiveResults, 5000);
}

function fetchLiveResults() {
	let fetchUrl = `/voting/${selectedMeetingId}/live_results`;
	if (typeof clubId !== 'undefined' && clubId) {
		fetchUrl += `?club_id=${clubId}`;
	} else if (typeof window.clubId !== 'undefined' && window.clubId) {
		fetchUrl += `?club_id=${window.clubId}`;
	}

	fetch(fetchUrl)
		.then(response => {
			if (!response.ok) {
				throw new Error(`HTTP error! status: ${response.status}`);
			}
			return response.json();
		})
		.then(data => {
			if (data.success) {
				updateLiveResultsUI(data.total_voters, data.votes);
			}
		})
		.catch(error => {
			console.error("Error fetching live vote results:", error);
		});
}

function updateLiveResultsUI(totalVoters, votesList) {
	// 1. Update total voters count badge if present
	const totalVotersCountEl = document.querySelector('.vote-count-badge .count');
	if (totalVotersCountEl) {
		totalVotersCountEl.textContent = totalVoters;
	}

	// Create a lookup map for faster access: contactId_category -> count
	const votesMap = {};
	votesList.forEach(v => {
		const key = `${v.contact_id}_${v.award_category}`;
		votesMap[key] = v.count;
	});

	// Find all vote brick containers
	const brickContainers = document.querySelectorAll('.vote-bricks-container[data-contact-id][data-award-category]');
	brickContainers.forEach(container => {
		const contactId = container.dataset.contactId;
		const category = container.dataset.awardCategory;
		const key = `${contactId}_${category}`;
		const count = votesMap[key] || 0;

		// Update title
		container.title = `${count} Votes`;

		if (count > 0) {
			// Update bricks (ensure the count matches)
			let currentBricks = container.querySelectorAll('.vote-brick');
			if (currentBricks.length !== count) {
				container.innerHTML = '';
				for (let i = 0; i < count; i++) {
					const brick = document.createElement('div');
					brick.className = 'vote-brick';
					container.appendChild(brick);
				}
			}
			container.style.display = '';
		} else {
			container.innerHTML = '';
			container.style.display = 'none';
		}
	});
}

function handleMeetingStatusToggle(button) {
	const meetingId = button.dataset.meetingId;
	const currentStatus = button.dataset.currentStatus;

	if (!meetingId) {
		alert("No meeting selected.");
		return;
	}

	let confirmMessage = "";
	if (currentStatus === "unpublished") {
		confirmMessage = "Please make sure the meeting theme and structure are finalized before publishing.\n\nPublishing opens booking roles and speeches to all members. Do you want to proceed?";
	} else if (currentStatus === "not started") {
		confirmMessage = "Please only click this when the meeting has already started.\n\nStarting will open voting to the audience. Do you want to proceed?";
	} else if (currentStatus === "running") {
		confirmMessage = "Stopping the meeting ends voting and shows the final vote results.\n\nDo you want to proceed?";
	} else {
		return;
	}

	if (!confirm(confirmMessage)) {
		return;
	}

	// Perform Status Update
	fetch(`/agenda/status/${meetingId}`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
		},
	})
	.then((response) => response.json())
	.then((data) => {
		if (data.success) {
			const newStatus = data.new_status;
			if (currentStatus === "unpublished" && newStatus === "not started") {
				// Transitioned to "not started", ask if they want to start it now
				if (confirm("Meeting published successfully. Do you want to start the meeting now?")) {
					// Recursively transition to 'running'
					button.dataset.currentStatus = "not started";
					handleMeetingStatusToggle(button);
					return;
				}
			}
			window.location.reload();
		} else {
			alert("Error updating status: " + data.message);
		}
	})
	.catch((error) => {
		console.error("Error:", error);
		alert("An error occurred while updating the meeting status.");
	});
}
