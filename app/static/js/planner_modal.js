/**
 * Shared Planner Modal Logic
 */

const modal = document.getElementById('planModal');
const form = document.getElementById('planForm');
const meetingSelect = document.getElementById('meeting_id');
const roleSelect = document.getElementById('meeting_role_id');
const pathwayGroup = document.getElementById('planner-pathway-group');
const pathwaySelect = document.getElementById('planner_pathway');
const projectGroup = document.getElementById('planner-project-group');
const projectIdSelect = document.getElementById('project_id');
const dateDisplay = document.getElementById('meeting-date-display');
const dateRow = document.getElementById('meeting-date-row');
const projectChkGroup = document.getElementById('planner-project-checkbox-group');
const projectChk = document.getElementById('has_project_chk');
const titleGroup = document.getElementById('title-group');
const titleInput = document.getElementById('title');
const bookBtn = document.getElementById('book-btn');

let currentMeetingRoles = [];
let customMeetingSelect, customRoleSelect, customPathwaySelect, customProjectSelect;

const savePlanBtn = document.getElementById('save-plan-btn');

const roleProjectMapping = {
    'Prepared Speaker': { formats: ['Prepared Speech', 'Presentation'] },
    'Keynote Speaker': { ids: [51] },
    'Topicsmaster': { ids: [10] },
    'Individual Evaluator': { ids: [4, 5, 6] },
    'Meeting Manager': { formats: ['Meeting Manager'] },
    'Moderator': { ids: [57] },
    'Panelist': { ids: [57] }
};

document.addEventListener("DOMContentLoaded", function () {
    if (document.getElementById('meeting_id')) {
        customMeetingSelect = new CustomSelect('meeting_id');
    }
    if (document.getElementById('meeting_role_id')) {
        customRoleSelect = new CustomSelect('meeting_role_id');
    }
    if (document.getElementById('planner_pathway')) {
        customPathwaySelect = new CustomSelect('planner_pathway');
    }
    if (document.getElementById('project_id')) {
        customProjectSelect = new CustomSelect('project_id');
    }

    if (meetingSelect) {
        meetingSelect.addEventListener('change', loadMeetingRoles);
    }

    if (roleSelect) {
        roleSelect.addEventListener('change', () => {
            // Only reset if not disabling
            const selectedRole = currentMeetingRoles.find(r => r.id == roleSelect.value);
            if (!selectedRole || selectedRole.name !== 'Prepared Speaker') {
                if (projectChk) projectChk.checked = false;
            } else {
                if (projectChk) projectChk.checked = true;
            }
            updateProjectVisibility();
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
});

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
    
    // Find all projects that belong to this pathway and match role formats/IDs
    const pathwayProjects = [];
    if (typeof allProjects !== 'undefined') {
        allProjects.forEach(proj => {
            if (proj.path_codes && proj.path_codes[pathwayAbbr]) {
                // If there are allowed project definitions, strictly filter
                if (mapping) {
                    if (mapping.ids && !mapping.ids.includes(proj.id)) {
                        return; // Skip if ID not allowed
                    }
                    if (mapping.formats && (!proj.Format || !mapping.formats.includes(proj.Format))) {
                        return; // Skip if Format not allowed
                    }
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
    
    // Group projects by level
    const projectsByLevel = {};
    pathwayProjects.forEach(p => {
        if (!projectsByLevel[p.level]) {
            projectsByLevel[p.level] = [];
        }
        projectsByLevel[p.level].push(p);
    });
    
    // Sort projects within each level by their code (e.g. 1.4.1, 1.4.2, 1.4.3)
    Object.keys(projectsByLevel).forEach(level => {
        projectsByLevel[level].sort((a, b) => {
            if (a.code && b.code) {
                return a.code.localeCompare(b.code, undefined, { numeric: true, sensitivity: 'base' });
            }
            return 0;
        });
    });
    
    // Populate the dropdown
    const sortedLevels = Object.keys(projectsByLevel).sort((a, b) => a - b);
    sortedLevels.forEach(level => {
        const optgroup = document.createElement('optgroup');
        optgroup.label = `Level ${level}`;
        
        projectsByLevel[level].forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.innerText = p.is_completed ? `✓ ${p.name}` : p.name;
            if (p.is_completed) {
                opt.classList.add('project-completed');
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

function openPlanModal(planData = null) {
    if (!modal) return;

    form.reset();
    document.getElementById('plan-id').value = '';
    const planStatusInput = document.getElementById('plan-status') || { value: 'draft' };
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
    if (dateRow) dateRow.style.display = 'none';
    if (bookBtn) bookBtn.style.display = 'none';
    if (roleSelect) {
        roleSelect.innerHTML = '<option value="">Select Role</option>';
        if (customRoleSelect) customRoleSelect.enable();
    }
    if (customMeetingSelect) customMeetingSelect.enable();

    if (savePlanBtn) savePlanBtn.innerText = 'Draft Box';

    populatePathwayDropdown();

    if (planData) {
        // Edit Mode
        document.getElementById('plan-id').value = planData.id;
        if (document.getElementById('plan-status')) document.getElementById('plan-status').value = planData.status || 'draft';
        if (savePlanBtn) savePlanBtn.innerText = 'Save';

        if (customMeetingSelect) customMeetingSelect.setValue(planData.meeting_id);
        document.getElementById('notes').value = planData.notes || '';

        // If status is not draft, disable meeting and role selects
        if (planData.status && planData.status !== 'draft') {
            if (customMeetingSelect) customMeetingSelect.disable();
        }

        // Trigger meeting change to load roles, then set role
        loadMeetingRoles().then(() => {
            if (customRoleSelect) customRoleSelect.setValue(planData.role_id);
            if (planData.status && planData.status !== 'draft') {
                if (customRoleSelect) customRoleSelect.disable();
                if (bookBtn) bookBtn.style.display = 'none';
            }

            if (projectChk) projectChk.checked = !!planData.project_id;
            updateProjectVisibility();
            
            // Set default pathway
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
                if (customPathwaySelect) {
                    customPathwaySelect.setValue(pathwayToSelect);
                } else {
                    pathwaySelect.value = pathwayToSelect;
                }
            }
            
            updateProjectDropdownOptions(planData.project_id);

            if (titleInput) titleInput.value = planData.title || '';
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

async function loadMeetingRoles() {
    const meetingId = meetingSelect.value;
    if (customMeetingSelect) customMeetingSelect.updateTrigger();

    if (!meetingId) {
        roleSelect.innerHTML = '<option value="">Select Role</option>';
        if (customRoleSelect) customRoleSelect.refresh();
        if (dateRow) dateRow.style.display = 'none';
        if (bookBtn) bookBtn.style.display = 'none';
        return;
    }

    try {
        const response = await fetch(`/api/meeting/${meetingId}`);
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
            opt.dataset.icon = role.icon || '';
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

    // Check if we are in edit mode for a booked plan
    const planId = document.getElementById('plan-id').value;
    const planStatus = document.getElementById('plan-status')?.value || 'draft';

    if (planId && planStatus !== 'draft') {
        bookBtn.style.display = 'none';
        return;
    }

    const selectedOpt = roleSelect.options[roleSelect.selectedIndex];
    if (selectedOpt && selectedOpt.value) {
        bookBtn.style.display = 'inline-flex';
        bookBtn.innerText = 'Book';
    } else {
        bookBtn.style.display = 'none';
    }
}

function updateProjectVisibility() {
    if (!projectChkGroup || !projectGroup || !titleGroup) return;

    const selectedRole = currentMeetingRoles.find(r => r.id == roleSelect.value);

    // Show title for Prepared Speaker or Keynote Speaker
    if (selectedRole && (selectedRole.name === 'Prepared Speaker' || selectedRole.name === 'Keynote Speaker')) {
        titleGroup.style.display = 'block';
    } else {
        titleGroup.style.display = 'none';
    }

    if (selectedRole) {
        if (pathwayGroup) pathwayGroup.style.display = 'block';

        // Re-filter projects based on the current selected pathway
        let pathwayToSelect = pathwaySelect ? pathwaySelect.value : '';
        if (!pathwayToSelect && typeof workingPath !== 'undefined') {
            pathwayToSelect = workingPath;
            if (pathwaySelect) {
                if (customPathwaySelect) {
                    customPathwaySelect.setValue(pathwayToSelect);
                } else {
                    pathwaySelect.value = pathwayToSelect;
                }
            }
        }

        const isValidForProject = selectedRole && !!roleProjectMapping[selectedRole.name];

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

async function handleFormSubmit(e) {
    if (e) e.preventDefault();
    const planId = document.getElementById('plan-id').value;
    const planStatus = document.getElementById('plan-status')?.value || 'draft';

    const data = {
        meeting_id: document.getElementById('meeting_id').value || null,
        meeting_number: document.getElementById('meeting_id').options[document.getElementById('meeting_id').selectedIndex]?.dataset.number || null,
        meeting_role_id: document.getElementById('meeting_role_id').value || null,
        project_id: document.getElementById('project_id').value || null,
        pathway: document.getElementById('planner_pathway').value || null,
        title: titleInput ? titleInput.value : null,
        notes: document.getElementById('notes').value,
        status: planStatus
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

    const projectId = document.getElementById('project_id').value || null;
    const pathway = document.getElementById('planner_pathway').value || null;
    const title = titleInput ? titleInput.value : null;

    try {
        const response = await fetch('/booking/book', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                action: action,
                project_id: projectId,
                pathway: pathway,
                title: title
            })
        });

        const result = await response.json();
        if (result.success) {
            const status = 'waitlist';

            const planId = document.getElementById('plan-id').value;
            const data = {
                meeting_id: document.getElementById('meeting_id').value || null,
                meeting_number: document.getElementById('meeting_id').options[document.getElementById('meeting_id').selectedIndex]?.dataset.number || null,
                meeting_role_id: document.getElementById('meeting_role_id').value || null,
                project_id: document.getElementById('project_id').value || null,
                pathway: pathway,
                title: titleInput ? titleInput.value : null,
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
