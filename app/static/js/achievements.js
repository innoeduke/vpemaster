/**
 * Achievements Client Side Logic
 * Handles the achievement modal for recording and revoking achievements
 * from the Member View roadmap.
 */

function openAchievementModal(action, userId, memberName, memberId, achievementType, pathName, level) {
	const modal = document.getElementById('achievementModal');
	if (!modal) return;

	// Set title and button style based on action
	const title = document.getElementById('achievement-modal-title');
	const saveBtn = document.getElementById('save-achievement-btn');
	const form = document.getElementById('achievementForm');

	if (action === 'revoke') {
		title.textContent = 'Revoke Achievement';
		saveBtn.textContent = 'Revoke';
		saveBtn.className = 'planner-btn btn-danger';
	} else {
		title.textContent = 'Record Achievement';
		saveBtn.textContent = 'Save';
		saveBtn.className = 'planner-btn btn-success';
	}

	// Store action in form dataset
	form.dataset.action = action;
	form.dataset.userId = userId;

	// Pre-fill fields
	const searchInput = document.getElementById('achievement_contact_search');
	if (searchInput) {
		searchInput.value = memberName;
		searchInput.readOnly = true; // Lock member field when opened from roadmap
	}

	const contactIdInput = document.getElementById('contact_id');
	if (contactIdInput) contactIdInput.value = '';

	const memberIdInput = document.getElementById('member_id');
	if (memberIdInput) memberIdInput.value = memberId || '';

	const typeSelect = document.getElementById('achievement_type');
	if (typeSelect) typeSelect.value = achievementType || 'level-completion';

	const dateInput = document.getElementById('issue_date');
	if (dateInput && !dateInput.value) {
		dateInput.value = new Date().toISOString().split('T')[0]; // Default to today
	}

	// Pre-fill path from the member view's Pathways selector
	const pathwaySelector = document.getElementById('pathway');
	let actualPathName = pathName; // fallback to passed value
	if (pathwaySelector && pathwaySelector.value && pathwaySelector.value !== 'all') {
		actualPathName = pathwaySelector.value;
	}

	const pathInput = document.getElementById('path_name');
	if (pathInput) pathInput.value = actualPathName || '';

	const levelInput = document.getElementById('level');
	if (levelInput) levelInput.value = level || '';

	const notesInput = document.getElementById('notes');
	if (notesInput) notesInput.value = '';

	// Show modal
	modal.style.display = 'flex';
}

function closeAchievementModal() {
	const modal = document.getElementById('achievementModal');
	if (modal) {
		modal.style.display = 'none';
		// Reset readonly on member search
		const searchInput = document.getElementById('achievement_contact_search');
		if (searchInput) searchInput.readOnly = false;
		// Reset date
		const dateInput = document.getElementById('issue_date');
		if (dateInput) dateInput.value = '';
	}
}

// Handle form submission
document.addEventListener('DOMContentLoaded', function () {
	const form = document.getElementById('achievementForm');
	if (!form) return;

	form.addEventListener('submit', async function (e) {
		e.preventDefault();

		const action = form.dataset.action || 'record';
		const userId = form.dataset.userId;

		const payload = {
			user_id: userId,
			achievement_type: document.getElementById('achievement_type')?.value,
			issue_date: document.getElementById('issue_date')?.value,
			path_name: document.getElementById('path_name')?.value,
			level: document.getElementById('level')?.value,
			notes: document.getElementById('notes')?.value
		};

		const url = `/achievements/${action}`;

		try {
			const response = await fetch(url, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'X-Requested-With': 'XMLHttpRequest'
				},
				body: JSON.stringify(payload)
			});

			const result = await response.json();
			if (result.success) {
				closeAchievementModal();
				if (typeof showNotification === 'function') {
					showNotification(result.message, 'success');
				} else {
					alert(result.message);
				}
				setTimeout(() => location.reload(), 1000);
			} else {
				alert(result.message || `Error during achievement ${action}`);
			}
		} catch (error) {
			console.error(`Error in achievement ${action}:`, error);
			alert(`An unexpected error occurred during achievement ${action}.`);
		}
	});
});
