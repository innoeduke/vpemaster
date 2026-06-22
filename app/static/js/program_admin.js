/**
 * Javascript for program templates administration page
 */

document.addEventListener('DOMContentLoaded', function() {
    const listContainer = document.getElementById('templates-list-container');
    const modal = document.getElementById('programTemplateModal');
    const form = document.getElementById('programTemplateForm');
    const addTemplateBtn = document.getElementById('add-template-btn');
    const cancelTemplateBtn = document.getElementById('cancel-template-btn');
    const closeTemplateModalBtn = document.getElementById('close-template-modal-btn');
    const modalTitle = document.getElementById('template-modal-title');
    
    // Task elements
    const tasksSection = document.getElementById('tasks-editor-section');
    const tasksList = document.getElementById('tasks-list-container');
    const addTaskRowBtn = document.getElementById('add-task-row-btn');
    const taskTemplate = document.getElementById('task-row-template');

    // Task modal elements
    const taskModal = document.getElementById('programTaskModal');
    const taskForm = document.getElementById('programTaskForm');
    const closeTaskModalBtn = document.getElementById('close-task-modal-btn');
    const cancelTaskBtn = document.getElementById('cancel-task-btn');
    const modalTaskTitle = document.getElementById('modal-task-title');
    const modalTaskDesc = document.getElementById('modal-task-desc');
    const modalTaskPhase = document.getElementById('modal-task-phase');
    const modalTaskCompletionType = document.getElementById('modal-task-completion-type');
    const modalTaskCompletionConfig = document.getElementById('modal-task-completion-config');
    const modalTaskCompletionConfigGroup = document.getElementById('modal-task-completion-config-group');
    const modalTaskIsRequired = document.getElementById('modal-task-is-required');

    let deletedTaskIds = [];
    let activeTaskRow = null;

    // Load templates on page load
    loadTemplates();

    // Event listeners
    if (addTemplateBtn) {
        addTemplateBtn.addEventListener('click', () => openTemplateModal());
    }

    if (cancelTemplateBtn) {
        cancelTemplateBtn.addEventListener('click', closeTemplateModal);
    }

    if (closeTemplateModalBtn) {
        closeTemplateModalBtn.addEventListener('click', closeTemplateModal);
    }

    if (addTaskRowBtn) {
        addTaskRowBtn.addEventListener('click', () => openTaskModal());
    }

    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    }

    if (closeTaskModalBtn) {
        closeTaskModalBtn.addEventListener('click', closeTaskModal);
    }

    if (cancelTaskBtn) {
        cancelTaskBtn.addEventListener('click', closeTaskModal);
    }

    if (modalTaskCompletionType) {
        modalTaskCompletionType.addEventListener('change', function() {
            if (this.value === 'sessionlog') {
                modalTaskCompletionConfigGroup.style.display = 'block';
            } else {
                modalTaskCompletionConfigGroup.style.display = 'none';
            }
        });
    }

    if (taskForm) {
        taskForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const title = modalTaskTitle.value;
            const desc = modalTaskDesc.value;
            const phase = modalTaskPhase.value;
            const type = modalTaskCompletionType.value;
            const config = modalTaskCompletionConfig.value;
            const required = modalTaskIsRequired.checked;

            if (type === 'sessionlog' && config) {
                try {
                    JSON.parse(config);
                } catch (err) {
                    alert('Invalid JSON config. Example config: {"role_name": "Timer"}');
                    return;
                }
            }

            if (activeTaskRow) {
                // Update hidden inputs
                activeTaskRow.querySelector('.task-title').value = title;
                activeTaskRow.querySelector('.task-desc').value = desc;
                activeTaskRow.querySelector('.task-phase').value = phase;
                activeTaskRow.querySelector('.task-completion-type').value = type;
                activeTaskRow.querySelector('.task-completion-config').value = config;
                activeTaskRow.querySelector('.task-is-required-val').value = required ? 'true' : 'false';
                
                updateRowDisplay(activeTaskRow);
            } else {
                // Add new row
                addTaskRow({
                    title: title,
                    description: desc,
                    phase_label: phase,
                    completion_type: type,
                    completion_config: config ? JSON.parse(config) : null,
                    is_required: required
                });
            }

            closeTaskModal();
        });
    }

    // Handle task movement, deletion, and editing
    tasksList.addEventListener('click', function(e) {
        const row = e.target.closest('.task-editor-row');
        if (!row) return;

        if (e.target.closest('.btn-delete-task')) {
            const taskId = row.querySelector('.task-id').value;
            if (taskId) {
                deletedTaskIds.push(taskId);
            }
            row.remove();
            return;
        }

        if (e.target.closest('.btn-edit-task')) {
            openTaskModal(row);
            return;
        }

        if (e.target.closest('.btn-move-up')) {
            const prev = row.previousElementSibling;
            if (prev) {
                tasksList.insertBefore(row, prev);
            }
            return;
        }

        if (e.target.closest('.btn-move-down')) {
            const next = row.nextElementSibling;
            if (next) {
                tasksList.insertBefore(next, row);
            }
            return;
        }
    });

    // Fetch and render templates
    async function loadTemplates() {
        try {
            const response = await fetch('/api/programs');
            if (!response.ok) throw new Error('Failed to load templates');
            const data = await response.json();
            renderTemplatesList(data);
        } catch (error) {
            console.error('Error:', error);
            listContainer.innerHTML = `
                <div style="text-align: center; grid-column: 1/-1; padding: 40px; color: var(--danger-color, #d9534f);">
                    <i class="fas fa-exclamation-triangle fa-2x"></i>
                    <p>Failed to load program templates. Please reload the page.</p>
                </div>
            `;
        }
    }

    function renderTemplatesList(programs) {
        if (programs.length === 0) {
            listContainer.innerHTML = `
                <div style="text-align: center; grid-column: 1/-1; padding: 40px; color: var(--text-muted);">
                    <i class="fas fa-inbox fa-2x"></i>
                    <p>No program templates created yet. Start by adding one!</p>
                </div>
            `;
            return;
        }

        listContainer.innerHTML = '';
        programs.forEach(p => {
            const card = document.createElement('div');
            card.className = 'template-card';
            card.innerHTML = `
                <div>
                    <div class="template-card-header">
                        <h4 class="template-card-title">${escapeHTML(p.name)}</h4>
                        <span class="status-badge ${p.is_active ? 'status-completed' : 'status-cancelled'}">
                            ${p.is_active ? 'Active' : 'Inactive'}
                        </span>
                    </div>
                    <p class="template-card-desc" style="margin-bottom: 8px;">${escapeHTML(p.description || 'No description provided.')}</p>
                    ${p.phases && p.phases.length > 0 ? `
                    <div class="template-card-phases" style="margin-bottom: 12px; display: flex; flex-wrap: wrap; gap: 6px;">
                        ${p.phases.map(ph => `<span class="phase-tag" style="background: var(--bg-hover, #f0f4f8); color: var(--primary-color, #005a9c); border: 1px solid var(--border-color, #d0e0f0); border-radius: 4px; padding: 2px 6px; font-size: 0.75rem; font-weight: 600;">${escapeHTML(ph)}</span>`).join('')}
                    </div>
                    ` : ''}
                </div>
                <div>
                    <div class="template-card-meta">
                        <span><i class="fas fa-tasks"></i> ${p.tasks_count} Tasks</span>
                        <span><i class="fas fa-globe"></i> ${p.club_id ? 'Club-level' : 'System Global'}</span>
                    </div>
                    <div class="template-card-actions">
                        <button class="tm-action-btn btn-edit edit-template-btn" data-id="${p.id}" title="Edit Template">
                            <i class="fas fa-edit"></i>
                        </button>
                        ${p.club_id ? `
                        <button class="tm-action-btn btn-delete delete-template-btn" data-id="${p.id}" title="Deactivate Template" style="color: var(--danger-color, #d9534f);">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                        ` : ''}
                    </div>
                </div>
            `;
            listContainer.appendChild(card);
        });

        // Add card actions listeners
        document.querySelectorAll('.edit-template-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-id');
                const program = programs.find(p => p.id == id);
                if (program) openTemplateModal(program);
            });
        });

        document.querySelectorAll('.delete-template-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-id');
                deactivateProgram(id);
            });
        });
    }

    async function deactivateProgram(id) {
        if (confirm('Are you sure you want to deactivate this template? Members will no longer be able to enroll in it.')) {
            try {
                const response = await fetch(`/api/programs/${id}`, {
                    method: 'DELETE'
                });
                if (response.ok) {
                    loadTemplates();
                } else {
                    alert('Failed to deactivate template');
                }
            } catch (error) {
                console.error('Error:', error);
            }
        }
    }

    // Modal management
    function openTemplateModal(program = null) {
        deletedTaskIds = [];
        tasksList.innerHTML = '';
        form.reset();
        
        if (program) {
            modalTitle.innerText = 'Edit Program Template';
            document.getElementById('template-id').value = program.id;
            document.getElementById('template-name').value = program.name;
            document.getElementById('template-description').value = program.description || '';
            document.getElementById('template-is-active').checked = program.is_active;
            tasksSection.style.display = 'block';
            loadProgramTasks(program.id);
        } else {
            modalTitle.innerText = 'New Program Template';
            document.getElementById('template-id').value = '';
            document.getElementById('template-is-active').checked = true;
            tasksSection.style.display = 'none'; // Only show tasks editor after program is saved/exists
        }
        
        modal.style.display = 'flex';
    }

    function closeTemplateModal() {
        modal.style.display = 'none';
    }

    async function loadProgramTasks(programId) {
        try {
            const response = await fetch(`/api/programs/${programId}/tasks`);
            if (!response.ok) throw new Error('Failed to load tasks');
            const tasks = await response.json();
            
            tasksList.innerHTML = '';
            tasks.forEach(t => addTaskRow(t));
        } catch (error) {
            console.error('Error:', error);
        }
    }

    function addTaskRow(task = null) {
        const clone = taskTemplate.content.cloneNode(true);
        const row = clone.querySelector('.task-editor-row');
        
        // Default values for new task
        let id = '';
        let title = 'New Task';
        let desc = '';
        let phase = '';
        let type = 'manual';
        let config = '';
        let required = true;

        if (task) {
            id = task.id || '';
            title = task.title || '';
            desc = task.description || '';
            phase = task.phase_label || '';
            type = task.completion_type || 'manual';
            config = task.completion_type === 'sessionlog' ? JSON.stringify(task.completion_config || {}) : '';
            required = task.is_required !== false;
        }

        row.querySelector('.task-id').value = id;
        row.querySelector('.task-title').value = title;
        row.querySelector('.task-desc').value = desc;
        row.querySelector('.task-phase').value = phase;
        row.querySelector('.task-completion-type').value = type;
        row.querySelector('.task-completion-config').value = config;
        row.querySelector('.task-is-required-val').value = required ? 'true' : 'false';

        updateRowDisplay(row);
        tasksList.appendChild(row);
    }

    function openTaskModal(row = null) {
        activeTaskRow = row;
        taskForm.reset();
        modalTaskCompletionConfigGroup.style.display = 'none';

        if (row) {
            document.getElementById('task-modal-title').innerText = 'Edit Program Task';
            modalTaskTitle.value = row.querySelector('.task-title').value;
            modalTaskDesc.value = row.querySelector('.task-desc').value;
            modalTaskPhase.value = row.querySelector('.task-phase').value;
            modalTaskCompletionType.value = row.querySelector('.task-completion-type').value;
            
            const configVal = row.querySelector('.task-completion-config').value;
            modalTaskCompletionConfig.value = configVal;
            if (modalTaskCompletionType.value === 'sessionlog') {
                modalTaskCompletionConfigGroup.style.display = 'block';
            }
            modalTaskIsRequired.checked = row.querySelector('.task-is-required-val').value === 'true';
        } else {
            document.getElementById('task-modal-title').innerText = 'New Program Task';
            modalTaskIsRequired.checked = true;
        }

        taskModal.style.display = 'flex';
    }

    function closeTaskModal() {
        taskModal.style.display = 'none';
        activeTaskRow = null;
    }

    function updateRowDisplay(row) {
        const title = row.querySelector('.task-title').value;
        const desc = row.querySelector('.task-desc').value;
        const phase = row.querySelector('.task-phase').value;
        const type = row.querySelector('.task-completion-type').value;
        const required = row.querySelector('.task-is-required-val').value === 'true';
        
        row.querySelector('.display-task-title').innerText = title;
        row.querySelector('.display-task-desc').innerText = desc;
        
        const phaseEl = row.querySelector('.display-task-phase');
        if (phase) {
            phaseEl.innerText = phase;
            phaseEl.style.display = 'inline-block';
        } else {
            phaseEl.style.display = 'none';
        }
        
        const option = document.querySelector(`#modal-task-completion-type option[value="${type}"]`);
        row.querySelector('.display-task-type').innerText = option ? option.text : type;
        
        row.querySelector('.display-task-required').innerHTML = required 
            ? '<i class="fas fa-check text-success" style="color: #28a745;"></i>' 
            : '<i class="fas fa-times text-muted" style="color: #6c757d;"></i>';
    }

    // Save template changes
    async function handleFormSubmit(e) {
        e.preventDefault();
        
        const templateId = document.getElementById('template-id').value;
        const name = document.getElementById('template-name').value;
        const description = document.getElementById('template-description').value;
        const isActive = document.getElementById('template-is-active').checked;
        
        const programData = {
            name: name,
            description: description,
            is_active: isActive
        };

        try {
            let programId = templateId;
            let response;
            
            if (templateId) {
                // Update program details
                response = await fetch(`/api/programs/${templateId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(programData)
                });
            } else {
                // Create new program details
                response = await fetch('/api/programs', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(programData)
                });
                const result = await response.json();
                programId = result.id;
            }

            if (!response.ok) throw new Error('Failed to save program details');

            // Handle tasks if program ID exists (i.e. not a fresh unsaved program)
            if (programId) {
                // 1. Process deletions
                for (const tid of deletedTaskIds) {
                    await fetch(`/api/programs/${programId}/tasks/${tid}`, { method: 'DELETE' });
                }

                // 2. Process updates/creations
                const taskRows = tasksList.querySelectorAll('.task-editor-row');
                const savedTaskIds = [];

                for (let i = 0; i < taskRows.length; i++) {
                    const row = taskRows[i];
                    const tid = row.querySelector('.task-id').value;
                    const title = row.querySelector('.task-title').value;
                    const desc = row.querySelector('.task-desc').value;
                    const phase = row.querySelector('.task-phase').value;
                    const type = row.querySelector('.task-completion-type').value;
                    const configStr = row.querySelector('.task-completion-config').value;
                    const required = row.querySelector('.task-is-required-val').value === 'true';

                    let configObj = null;
                    if (type === 'sessionlog' && configStr) {
                        try {
                            configObj = JSON.parse(configStr);
                        } catch (err) {
                            alert(`Invalid JSON config in task "${title}". Example config: {"role_name": "Timer"}`);
                            return;
                        }
                    }

                    const taskData = {
                        title: title,
                        description: desc,
                        phase_label: phase,
                        completion_type: type,
                        completion_config: configObj,
                        is_required: required,
                        display_order: i
                    };

                    let taskRes;
                    if (tid) {
                        // Update
                        taskRes = await fetch(`/api/programs/${programId}/tasks/${tid}`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(taskData)
                        });
                        savedTaskIds.push(parseInt(tid));
                    } else {
                        // Create
                        taskRes = await fetch(`/api/programs/${programId}/tasks`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(taskData)
                        });
                        const taskResult = await taskRes.json();
                        savedTaskIds.push(taskResult.id);
                    }

                    if (!taskRes.ok) throw new Error(`Failed to save task "${title}"`);
                }

                // 3. Process reorder mapping
                if (savedTaskIds.length > 0) {
                    await fetch(`/api/programs/${programId}/tasks/reorder`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ task_ids: savedTaskIds })
                    });
                }
            }

            closeTemplateModal();
            loadTemplates();
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred while saving the program template details.');
        }
    }

    function escapeHTML(str) {
        if (!str) return '';
        return str.replace(/[&<>'"]/g, 
            tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag] || tag)
        );
    }
});
