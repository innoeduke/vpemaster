/**
 * Shared Planner Modal Logic
 */

const modal = document.getElementById('planModal');
const form = document.getElementById('planForm');
const meetingSelect = document.getElementById('meeting_number');
const roleSelect = document.getElementById('meeting_role_id');
const projectGroup = document.getElementById('project-group');
const projectIdSelect = document.getElementById('project_id');
const dateDisplay = document.getElementById('meeting-date-display');
const dateRow = document.getElementById('meeting-date-row');
const projectChkGroup = document.getElementById('project-checkbox-group');
const projectChk = document.getElementById('has_project_chk');
const bookBtn = document.getElementById('book-btn');

let currentMeetingRoles = [];
let customMeetingSelect, customRoleSelect, customProjectSelect;

document.addEventListener("DOMContentLoaded", function () {
    if (document.getElementById('meeting_number')) {
        customMeetingSelect = new CustomSelect('meeting_number');
    }
    if (document.getElementById('meeting_role_id')) {
        customRoleSelect = new CustomSelect('meeting_role_id');
    }
    if (document.getElementById('project_id')) {
        customProjectSelect = new CustomSelect('project_id');
    }

    if (meetingSelect) {
        meetingSelect.addEventListener('change', loadMeetingRoles);
    }

    if (roleSelect) {
        roleSelect.addEventListener('change', () => {
            if (projectChk) projectChk.checked = false;
            updateProjectVisibility();
            updateBookButtonVisibility();
        });
    }

    if (projectChk) {
        projectChk.addEventListener('change', updateProjectVisibility);
    }

    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    }
});

function openPlanModal(planData = null) {
    if (!modal) return;

    form.reset();
    document.getElementById('plan-id').value = '';

    if (projectGroup) projectGroup.style.display = 'none';
    if (projectChkGroup) projectChkGroup.style.display = 'none';
    if (projectChk) projectChk.checked = false;
    if (dateRow) dateRow.style.display = 'none';
    if (bookBtn) bookBtn.style.display = 'none';
    if (roleSelect) roleSelect.innerHTML = '<option value="">Select Role</option>';

    if (planData) {
        // Edit Mode
        document.getElementById('plan-id').value = planData.id;
        if (customMeetingSelect) customMeetingSelect.setValue(planData.meeting_number);
        document.getElementById('notes').value = planData.notes || '';

        // Trigger meeting change to load roles, then set role
        loadMeetingRoles().then(() => {
            if (customRoleSelect) customRoleSelect.setValue(planData.role_id);

            if (projectChk) projectChk.checked = !!planData.project_id;
            updateProjectVisibility();
            if (customProjectSelect) customProjectSelect.setValue(planData.project_id);
        });
    } else {
        if (customMeetingSelect) customMeetingSelect.updateTrigger();
        if (customRoleSelect) customRoleSelect.refresh();
    }

    modal.style.display = 'flex';
}

function closeModal() {
    if (modal) modal.style.display = 'none';
}

// Custom Select Class (Removed: using shared component in static/js/components/custom_select.js)

async function loadMeetingRoles() {
    const meetingNumber = meetingSelect.value;
    if (customMeetingSelect) customMeetingSelect.updateTrigger();

    if (!meetingNumber) {
        roleSelect.innerHTML = '<option value="">Select Role</option>';
        if (customRoleSelect) customRoleSelect.refresh();
        if (dateRow) dateRow.style.display = 'none';
        if (bookBtn) bookBtn.style.display = 'none';
        return;
    }

    try {
        const response = await fetch(`/api/meeting/${meetingNumber}`);
        const data = await response.json();

        if (dateDisplay) dateDisplay.innerText = `Meeting Date: ${data.date}`;
        if (dateRow) dateRow.style.display = 'flex';
        currentMeetingRoles = data.roles;

        roleSelect.innerHTML = '<option value="">Select Role</option>';
        data.roles.forEach(role => {
            const opt = document.createElement('option');
            opt.value = role.id;
            opt.innerText = role.name;
            opt.dataset.validProject = role.valid_for_project;
            opt.dataset.sessionId = role.session_id;
            opt.dataset.available = role.is_available;
            roleSelect.appendChild(opt);
        });
        if (customRoleSelect) customRoleSelect.refresh();

        updateBookButtonVisibility();
    } catch (error) {
        console.error('Error fetching meeting info:', error);
    }
}

function updateBookButtonVisibility() {
    if (!roleSelect || !bookBtn) return;

    const selectedOpt = roleSelect.options[roleSelect.selectedIndex];
    if (selectedOpt && selectedOpt.value) {
        bookBtn.style.display = 'inline-block';
        bookBtn.innerText = 'Book';
    } else {
        bookBtn.style.display = 'none';
    }
}

function updateProjectVisibility() {
    if (!projectChkGroup || !projectGroup) return;

    const selectedRole = currentMeetingRoles.find(r => r.id == roleSelect.value);
    if (selectedRole && selectedRole.valid_for_project) {
        projectChkGroup.style.display = 'block';

        if (projectChk.checked) {
            projectGroup.style.display = 'block';
            projectIdSelect.required = true;

            const expectedFormat = selectedRole.expected_format;
            let visibleCount = 0;
            let lastVisibleValue = '';

            // Filter projects by format
            Array.from(projectIdSelect.options).forEach(opt => {
                if (opt.value === "") return;

                const projectFormat = opt.dataset.format;
                let isVisible = false;

                if (expectedFormat) {
                    isVisible = (projectFormat === expectedFormat);
                } else {
                    isVisible = true;
                }

                opt.style.display = isVisible ? 'block' : 'none';
                if (isVisible) {
                    visibleCount++;
                    lastVisibleValue = opt.value;
                }
            });

            if (customProjectSelect) customProjectSelect.refresh();

            // Auto-selection logic
            if (visibleCount === 1 && !projectIdSelect.value) {
                if (customProjectSelect) customProjectSelect.setValue(lastVisibleValue);
                projectIdSelect.dispatchEvent(new Event('change'));
            }
        } else {
            projectGroup.style.display = 'none';
            if (customProjectSelect) customProjectSelect.setValue('');
            projectIdSelect.required = false;
        }
    } else {
        projectChkGroup.style.display = 'none';
        projectGroup.style.display = 'none';
        projectChk.checked = false;
        if (customProjectSelect) customProjectSelect.setValue('');
        projectIdSelect.required = false;
    }
}

async function handleFormSubmit(e) {
    if (e) e.preventDefault();
    const planId = document.getElementById('plan-id').value;
    const data = {
        meeting_number: document.getElementById('meeting_number').value || null,
        meeting_role_id: document.getElementById('meeting_role_id').value || null,
        project_id: document.getElementById('project_id').value || null,
        notes: document.getElementById('notes').value,
        status: 'draft'
    };

    const method = planId ? 'PUT' : 'POST';
    const url = planId ? `/api/planner/${planId}` : '/api/planner';

    try {
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            if (!e) return true; // Internal call from bookPlan
            location.reload();
        } else {
            alert('Failed to save draft');
            return false;
        }
    } catch (error) {
        console.error('Error:', error);
        return false;
    }
}

async function bookPlan() {
    const selectedOpt = roleSelect.options[roleSelect.selectedIndex];
    const sessionId = selectedOpt ? selectedOpt.dataset.sessionId : null;

    if (!sessionId) {
        alert('Cannot book: No session slot found for this role.');
        return;
    }

    const action = 'join_waitlist';

    try {
        const response = await fetch('/booking/book', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                action: action
            })
        });

        const result = await response.json();
        if (result.success) {
            const status = 'waitlist';

            const planId = document.getElementById('plan-id').value;
            const data = {
                meeting_number: document.getElementById('meeting_number').value || null,
                meeting_role_id: document.getElementById('meeting_role_id').value || null,
                project_id: document.getElementById('project_id').value || null,
                notes: document.getElementById('notes').value,
                status: status
            };

            const method = planId ? 'PUT' : 'POST';
            const url = planId ? `/api/planner/${planId}` : '/api/planner';

            await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            location.reload();
        } else {
            alert(result.message || 'Booking failed');
        }
    } catch (error) {
        console.error('Error during booking:', error);
        alert('An error occurred during booking');
    }
}
