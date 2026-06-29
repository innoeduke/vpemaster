/**
 * Shared Planner Modal Logic — role-first flow
 *
 * Step 1: Select a Role  (loads from /api/planner/roles)
 * Step 2: Select a Meeting (loads from /api/planner/role/<id>/meetings,
 *          each option carries data-available, data-needs-approval, data-session-id,
 *          data-booked-by-me so we can show icons and decide how to book)
 * Book button: calls `book` if slot is open + no approval required,
 *              otherwise calls `join_waitlist` (waitlist).
 */

const modal = document.getElementById('planModal');
const form = document.getElementById('planForm');
const roleSelect = document.getElementById('meeting_role_id');
const meetingSelect = document.getElementById('meeting_id');
const pathwayGroup = document.getElementById('planner-pathway-group');
const pathwaySelect = document.getElementById('planner_pathway');
const projectGroup = document.getElementById('planner-project-group');
const projectIdSelect = document.getElementById('project_id');
const projectChkGroup = document.getElementById('planner-project-checkbox-group');
const projectChk = document.getElementById('has_project_chk');
const titleGroup = document.getElementById('title-group');
const titleInput = document.getElementById('title');
const bookBtn = document.getElementById('book-btn');
const savePlanBtn = document.getElementById('save-plan-btn');

// CustomSelect instances
let customRoleSelect, customMeetingSelect, customPathwaySelect, customProjectSelect;

// Planner-page date-range params (read from URL) forwarded to API calls for consistency
const _urlParams = new URLSearchParams(window.location.search);
const _plannerStartDate = _urlParams.get('start_date') || '';
const _plannerEndDate = _urlParams.get('end_date') || '';

const roleProjectMapping = {
    'Prepared Speaker': { formats: ['Prepared Speech', 'Presentation'] },
    'Keynote Speaker': { ids: [51] },
    'Topicsmaster': { ids: [10] },
    'Individual Evaluator': { ids: [4, 5, 6] },
    'Meeting Manager': { formats: ['Meeting Manager'] },
    'Moderator': { ids: [57] },
    'Panelist': { ids: [57] }
};

// State for all roles loaded from the API
let allPlannerRoles = [];

// State tracking for the currently selected meeting slot
let currentMeetingRoles = []; // kept for compat with updateProjectVisibility

// Flag to suppress event-driven onRoleChanged when setting value programmatically
let _suppressRoleChange = false;

document.addEventListener('DOMContentLoaded', function () {
    if (document.getElementById('meeting_role_id')) {
        customRoleSelect = new CustomSelect('meeting_role_id');
    }
    if (document.getElementById('meeting_id')) {
        customMeetingSelect = new CustomSelect('meeting_id');
    }
    if (document.getElementById('planner_pathway')) {
        customPathwaySelect = new CustomSelect('planner_pathway');
    }
    if (document.getElementById('project_id')) {
        customProjectSelect = new CustomSelect('project_id');
    }

    // Role change → load meetings for that role
    if (roleSelect) {
        roleSelect.addEventListener('change', () => {
            if (_suppressRoleChange) return;
            onRoleChanged();
        });
    }

    // Meeting change → update book button
    if (meetingSelect) {
        meetingSelect.addEventListener('change', () => {
            updateBookButtonVisibility();
        });
    }

    if (pathwaySelect) {
        pathwaySelect.addEventListener('change', () => {
            updateProjectDropdownOptions();
        });
    }

    if (projectChk) {
        projectChk.addEventListener('change', updateProjectVisibility);
    }

    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    }

    const helpToggle = document.getElementById('planner-help-toggle');
    const usageInfo = document.getElementById('planner-usage-info');
    if (helpToggle && usageInfo) {
        helpToggle.addEventListener('click', () => {
            if (usageInfo.style.display === 'none') {
                usageInfo.style.display = 'flex';
                helpToggle.style.opacity = '1';
            } else {
                usageInfo.style.display = 'none';
                helpToggle.style.opacity = '0.7';
            }
        });
    }
});

// ─── Role population ─────────────────────────────────────────────────────────

async function loadPlannerRoles(selectedRoleId = null) {
    if (!roleSelect) return;

    let url = '/api/planner/roles';
    const params = new URLSearchParams();
    if (_plannerStartDate) params.set('start_date', _plannerStartDate);
    if (_plannerEndDate) params.set('end_date', _plannerEndDate);
    if (params.toString()) url += '?' + params.toString();

    try {
        const response = await fetch(url);
        const data = await response.json();
        allPlannerRoles = data.roles || [];

        roleSelect.innerHTML = '<option value="">Select Role</option>';
        allPlannerRoles.forEach(role => {
            const opt = document.createElement('option');
            opt.value = role.id;
            opt.innerText = role.name;
            if (role.icon) opt.dataset.icon = role.icon;
            opt.dataset.validProject = role.valid_for_project ? '1' : '';
            opt.dataset.roleName = role.name;
            roleSelect.appendChild(opt);
        });

        if (customRoleSelect) customRoleSelect.refresh();

        if (selectedRoleId) {
            _suppressRoleChange = true;
            if (customRoleSelect) {
                customRoleSelect.setValue(selectedRoleId);
            } else {
                roleSelect.value = selectedRoleId;
            }
            _suppressRoleChange = false;
            // Now call onRoleChanged ourselves so we can await it properly
            await onRoleChanged();
        }
    } catch (err) {
        console.error('Error loading planner roles:', err);
    }
}

// ─── Meeting population (after role chosen) ───────────────────────────────────

async function loadMeetingsForRole(roleId, selectedMeetingId = null) {
    if (!meetingSelect || !roleId) {
        meetingSelect.innerHTML = '<option value="">Select Meeting</option>';
        if (customMeetingSelect) customMeetingSelect.refresh();
        updateBookButtonVisibility();
        return;
    }

    let url = `/api/planner/role/${roleId}/meetings`;
    const params = new URLSearchParams();
    if (_plannerStartDate) params.set('start_date', _plannerStartDate);
    if (_plannerEndDate) params.set('end_date', _plannerEndDate);
    if (params.toString()) url += '?' + params.toString();

    try {
        const response = await fetch(url);
        const data = await response.json();
        const meetings = data.meetings || [];

        meetingSelect.innerHTML = '<option value="">Select Meeting</option>';
        meetings.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.id;
            opt.dataset.number = m.number;
            opt.dataset.sessionId = m.session_id;
            opt.dataset.available = m.is_available ? '1' : '';
            opt.dataset.bookedByMe = m.is_booked_by_me ? '1' : '';
            opt.dataset.needsApproval = m.needs_approval ? '1' : '';

            // Icon: green check-circle = open slot; orange lock = taken or approval required
            const isTaken = !m.is_available || m.needs_approval;
            const iconClass = isTaken
                ? 'fas fa-lock'
                : 'fas fa-check-circle';
            const iconColor = isTaken ? '#e07000' : '#2a9d5c';
            opt.dataset.icon = iconClass;
            opt.dataset.iconColor = iconColor;

            opt.innerText = `#${m.number}  ${m.date}`;
            meetingSelect.appendChild(opt);
        });

        if (customMeetingSelect) customMeetingSelect.refresh();

        if (selectedMeetingId) {
            if (customMeetingSelect) {
                customMeetingSelect.setValue(selectedMeetingId);
            } else {
                meetingSelect.value = selectedMeetingId;
            }
        }

        updateBookButtonVisibility();
    } catch (err) {
        console.error('Error loading meetings for role:', err);
    }
}

// ─── Event handlers ───────────────────────────────────────────────────────────

async function onRoleChanged() {
    const roleId = roleSelect.value;
    if (customRoleSelect) customRoleSelect.updateTrigger();

    // Reset meeting select while loading
    meetingSelect.innerHTML = '<option value="">Select Meeting</option>';
    if (customMeetingSelect) customMeetingSelect.refresh();
    if (bookBtn) bookBtn.style.display = 'none';

    // Sync currentMeetingRoles so updateProjectVisibility can work
    // Find the selected role by id in allPlannerRoles
    const roleObj = allPlannerRoles.find(r => r.id == roleId);
    currentMeetingRoles = roleObj ? [{ id: roleObj.id, name: roleObj.name, valid_for_project: roleObj.valid_for_project }] : [];

    updateProjectVisibility();

    if (roleId) {
        await loadMeetingsForRole(roleId);
    }
}

function updateBookButtonVisibility() {
    if (!meetingSelect || !bookBtn) return;

    // In edit mode for a non-draft plan, hide book button
    const planId = document.getElementById('plan-id').value;
    const planStatus = document.getElementById('plan-status')?.value || 'draft';
    if (planId && planStatus !== 'draft') {
        bookBtn.style.display = 'none';
        return;
    }

    const selectedOpt = meetingSelect.options[meetingSelect.selectedIndex];
    if (!selectedOpt || !selectedOpt.value || !roleSelect.value) {
        bookBtn.style.display = 'none';
        return;
    }

    const isAvailable = !!selectedOpt.dataset.available;
    const needsApproval = !!selectedOpt.dataset.needsApproval;
    const isBookedByMe = !!selectedOpt.dataset.bookedByMe;

    if (isBookedByMe) {
        // Already booked or on waitlist — no book button
        bookBtn.style.display = 'none';
        return;
    }

    bookBtn.style.display = 'inline-flex';

    if (isAvailable && !needsApproval) {
        bookBtn.innerText = 'Book';
    } else {
        bookBtn.innerText = 'Join Waitlist';
    }
}

// ─── Project visibility (unchanged logic, adapted for role-first) ─────────────

function populatePathwayDropdown() {
    if (!pathwaySelect) return;

    pathwaySelect.innerHTML = '<option value="">Select Pathway</option>';

    if (typeof groupedPathways !== 'undefined' && groupedPathways) {
        for (const [groupLabel, items] of Object.entries(groupedPathways)) {
            const optgroup = document.createElement('optgroup');
            optgroup.label = groupLabel;
            items.forEach(item => {
                const value = typeof item === 'object' ? item.name : item;
                const text = typeof item === 'object' ? item.name : item;
                optgroup.appendChild(new Option(text, value));
            });
            pathwaySelect.appendChild(optgroup);
        }
    } else if (typeof pathwayMap !== 'undefined' && pathwayMap) {
        const pathways = Object.keys(pathwayMap).map(name => ({ name }));
        pathways.forEach(p => {
            pathwaySelect.add(new Option(p.name, p.name));
        });
    }

    if (customPathwaySelect) customPathwaySelect.refresh();
}

function updateProjectDropdownOptions(selectedProjectId = null) {
    if (!projectIdSelect) return;

    projectIdSelect.innerHTML = '<option value="">Select Project</option>';

    const pathwayName = pathwaySelect ? pathwaySelect.value : '';
    if (!pathwayName) {
        if (customProjectSelect) customProjectSelect.refresh();
        return;
    }

    const pathwayAbbr = typeof pathwayMap !== 'undefined' ? pathwayMap[pathwayName] : null;
    if (!pathwayAbbr) {
        if (customProjectSelect) customProjectSelect.refresh();
        return;
    }

    // Find selected role's allowed project formats or IDs
    const roleId = roleSelect ? roleSelect.value : '';
    const selectedRole = currentMeetingRoles.find(r => r.id == roleId);
    const mapping = selectedRole ? roleProjectMapping[selectedRole.name] : null;

    const pathwayProjects = [];
    if (typeof allProjects !== 'undefined') {
        allProjects.forEach(proj => {
            if (proj.path_codes && proj.path_codes[pathwayAbbr]) {
                if (mapping) {
                    if (mapping.ids && !mapping.ids.includes(proj.id)) return;
                    if (mapping.formats && (!proj.Format || !mapping.formats.includes(proj.Format))) return;
                }
                const meta = proj.path_codes[pathwayAbbr];
                pathwayProjects.push({
                    id: proj.id,
                    name: proj.Project_Name,
                    level: meta.level || 1,
                    code: `${pathwayAbbr}${meta.code}`,
                    is_completed: proj.is_completed || false,
                    format: proj.Duration_Min && proj.Duration_Max ? `${proj.Duration_Min}-${proj.Duration_Max} Min` : ''
                });
            }
        });
    }

    const projectsByLevel = {};
    pathwayProjects.forEach(p => {
        if (!projectsByLevel[p.level]) projectsByLevel[p.level] = [];
        projectsByLevel[p.level].push(p);
    });

    Object.keys(projectsByLevel).forEach(level => {
        projectsByLevel[level].sort((a, b) => {
            if (a.code && b.code) return a.code.localeCompare(b.code, undefined, { numeric: true, sensitivity: 'base' });
            return 0;
        });
    });

    const sortedLevels = Object.keys(projectsByLevel).sort((a, b) => a - b);
    sortedLevels.forEach(level => {
        const optgroup = document.createElement('optgroup');
        optgroup.label = `Level ${level}`;
        projectsByLevel[level].forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.innerText = p.name;
            if (p.is_completed) {
                opt.classList.add('project-completed');
                opt.dataset.icon = 'fas fa-check-circle';
                opt.dataset.iconColor = '#2a9d5c';
            } else {
                opt.dataset.icon = 'far fa-circle';
                opt.dataset.iconColor = '#9ca3af';
            }
            opt.dataset.format = p.format;
            opt.dataset.code = p.code;
            optgroup.appendChild(opt);
        });
        projectIdSelect.appendChild(optgroup);
    });

    if (selectedProjectId) {
        if (customProjectSelect) {
            customProjectSelect.setValue(selectedProjectId);
        } else {
            projectIdSelect.value = selectedProjectId;
        }
    } else {
        if (customProjectSelect) customProjectSelect.refresh();
    }
}

function updateProjectVisibility() {
    if (!projectChkGroup || !projectGroup || !titleGroup) return;

    const selectedRole = currentMeetingRoles.find(r => r.id == roleSelect.value);

    if (selectedRole && (selectedRole.name === 'Prepared Speaker' || selectedRole.name === 'Keynote Speaker')) {
        titleGroup.style.display = 'block';
    } else {
        titleGroup.style.display = 'none';
    }

    if (selectedRole) {
        if (pathwayGroup) pathwayGroup.style.display = 'block';

        let pathwayToSelect = pathwaySelect ? pathwaySelect.value : '';
        if (!pathwayToSelect && typeof workingPath !== 'undefined') {
            pathwayToSelect = workingPath;
            if (pathwaySelect) {
                if (customPathwaySelect) customPathwaySelect.setValue(pathwayToSelect);
                else pathwaySelect.value = pathwayToSelect;
            }
        }

        const isValidForProject = !!roleProjectMapping[selectedRole.name];

        if (isValidForProject) {
            projectChkGroup.style.display = 'block';
            projectChk.disabled = false;
            projectChk.parentElement.style.opacity = '1';
            projectChk.parentElement.style.cursor = 'pointer';
            updateProjectDropdownOptions(projectIdSelect.value);

            if (projectChk.checked) {
                projectGroup.style.display = 'block';
                projectIdSelect.required = true;
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
    } else {
        projectChkGroup.style.display = 'none';
        if (pathwayGroup) pathwayGroup.style.display = 'none';
        projectGroup.style.display = 'none';
        projectChk.checked = false;
        if (customPathwaySelect) customPathwaySelect.setValue('');
        if (customProjectSelect) customProjectSelect.setValue('');
        projectIdSelect.required = false;
    }
}

// ─── Modal open / close ───────────────────────────────────────────────────────

async function openPlanModal(planData = null) {
    if (!modal) return;

    form.reset();
    document.getElementById('plan-id').value = '';
    if (document.getElementById('plan-status')) document.getElementById('plan-status').value = 'draft';

    if (projectGroup) projectGroup.style.display = 'none';
    if (pathwayGroup) pathwayGroup.style.display = 'none';
    if (projectChkGroup) projectChkGroup.style.display = 'none';
    if (titleGroup) titleGroup.style.display = 'none';
    if (titleInput) titleInput.value = '';
    if (projectChk) {
        projectChk.checked = false;
        projectChk.disabled = false;
        projectChk.parentElement.style.opacity = '1';
        projectChk.parentElement.style.cursor = 'pointer';
    }
    if (bookBtn) bookBtn.style.display = 'none';

    // Reset role and meeting selects
    if (roleSelect) {
        roleSelect.innerHTML = '<option value="">Select Role</option>';
        if (customRoleSelect) customRoleSelect.enable();
    }
    if (meetingSelect) {
        meetingSelect.innerHTML = '<option value="">Select Meeting</option>';
        if (customMeetingSelect) customMeetingSelect.enable();
    }

    if (savePlanBtn) savePlanBtn.innerText = 'Draft Box';

    const usageInfo = document.getElementById('planner-usage-info');
    const helpToggle = document.getElementById('planner-help-toggle');
    if (usageInfo) usageInfo.style.display = 'none';
    if (helpToggle) helpToggle.style.opacity = '0.7';

    populatePathwayDropdown();

    if (planData) {
        // Edit Mode
        document.getElementById('plan-id').value = planData.id;
        if (document.getElementById('plan-status')) document.getElementById('plan-status').value = planData.status || 'draft';
        if (savePlanBtn) savePlanBtn.innerText = 'Save';
        document.getElementById('notes').value = planData.notes || '';

        // Load all roles first, then select the current role, then load meetings, then select meeting
        await loadPlannerRoles(planData.role_id);

        // loadPlannerRoles already called onRoleChanged which loads meetings
        // Now select the meeting
        if (planData.meeting_id) {
            if (customMeetingSelect) {
                customMeetingSelect.setValue(planData.meeting_id);
            } else {
                meetingSelect.value = planData.meeting_id;
            }
            updateBookButtonVisibility();
        }

        // For non-draft plans, disable role and meeting selects
        if (planData.status && planData.status !== 'draft') {
            if (customRoleSelect) customRoleSelect.disable();
            if (customMeetingSelect) customMeetingSelect.disable();
            if (bookBtn) bookBtn.style.display = 'none';
        }

        if (projectChk) projectChk.checked = !!planData.project_id;
        updateProjectVisibility();

        // Set pathway
        let pathwayToSelect = '';
        if (planData.pathway) {
            pathwayToSelect = planData.pathway;
        } else if (planData.project_id && typeof allProjects !== 'undefined') {
            const proj = allProjects.find(p => p.id == planData.project_id);
            if (proj && proj.path_codes) {
                const pathAbbr = Object.keys(proj.path_codes)[0];
                if (pathAbbr && typeof pathwayMap !== 'undefined') {
                    pathwayToSelect = Object.keys(pathwayMap).find(name => pathwayMap[name] === pathAbbr) || '';
                }
            }
        }
        if (!pathwayToSelect && typeof workingPath !== 'undefined') {
            pathwayToSelect = workingPath;
        }
        if (pathwaySelect) {
            if (customPathwaySelect) customPathwaySelect.setValue(pathwayToSelect);
            else pathwaySelect.value = pathwayToSelect;
        }

        updateProjectDropdownOptions(planData.project_id);
        if (titleInput) titleInput.value = planData.title || '';
    } else {
        // New plan — load all roles
        await loadPlannerRoles();
        if (customMeetingSelect) customMeetingSelect.refresh();
    }

    modal.style.display = 'flex';
}

function closeModal() {
    if (modal) modal.style.display = 'none';
}

// ─── Form submission (Draft Box) ──────────────────────────────────────────────

async function handleFormSubmit(e) {
    if (e) e.preventDefault();
    const planId = document.getElementById('plan-id').value;
    const planStatus = document.getElementById('plan-status')?.value || 'draft';

    const meetingOpt = meetingSelect.options[meetingSelect.selectedIndex];
    const data = {
        meeting_id: meetingSelect.value || null,
        meeting_number: meetingOpt?.dataset?.number || null,
        meeting_role_id: roleSelect.value || null,
        project_id: projectIdSelect.value || null,
        pathway: pathwaySelect ? pathwaySelect.value || null : null,
        title: titleInput ? titleInput.value : null,
        notes: document.getElementById('notes').value,
        status: planStatus
    };

    const method = planId ? 'PUT' : 'POST';
    const url = planId ? `/api/planner/${planId}` : '/api/planner';

    try {
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            if (!e) return true;
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

// ─── Book button (smart: book vs join_waitlist) ───────────────────────────────

async function bookPlan() {
    const selectedOpt = meetingSelect.options[meetingSelect.selectedIndex];
    if (!selectedOpt || !selectedOpt.value) {
        alert('Please select a meeting first.');
        return;
    }

    const sessionId = selectedOpt.dataset.sessionId;
    if (!sessionId) {
        alert('Cannot book: No session slot found for this role/meeting.');
        return;
    }

    const isAvailable = !!selectedOpt.dataset.available;
    const needsApproval = !!selectedOpt.dataset.needsApproval;

    // Smart booking: direct book if slot open + no approval, else join waitlist
    const action = (isAvailable && !needsApproval) ? 'book' : 'join_waitlist';
    const newPlanStatus = (action === 'book') ? 'booked' : 'waitlist';

    const projectId = projectIdSelect.value || null;
    const pathway = pathwaySelect ? pathwaySelect.value || null : null;
    const title = titleInput ? titleInput.value : null;

    try {
        const response = await fetch('/booking/book', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                action,
                project_id: projectId,
                pathway,
                title
            })
        });

        const result = await response.json();
        if (result.success) {
            const meetingOpt = meetingSelect.options[meetingSelect.selectedIndex];
            const planId = document.getElementById('plan-id').value;
            const planPayload = {
                meeting_id: meetingSelect.value || null,
                meeting_number: meetingOpt?.dataset?.number || null,
                meeting_role_id: roleSelect.value || null,
                project_id: projectId,
                pathway,
                title,
                notes: document.getElementById('notes').value,
                status: newPlanStatus
            };

            const method = planId ? 'PUT' : 'POST';
            const url = planId ? `/api/planner/${planId}` : '/api/planner';

            await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(planPayload)
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
