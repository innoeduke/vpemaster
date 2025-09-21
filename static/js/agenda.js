document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const editButton = document.getElementById('edit-logs-btn');
    const cancelButton = document.getElementById('cancel-edit-btn');
    const addRowButton = document.getElementById('add-row-btn');
    const loadButton = document.getElementById('load-btn');
    const meetingFilter = document.getElementById('meeting-filter');
    const exportButton = document.getElementById('export-btn');
    const tableContainer = document.getElementById('table-container');

    // --- Data passed from the template ---
    const sessionTypes = JSON.parse(tableContainer.dataset.sessionTypes);
    const contacts = JSON.parse(tableContainer.dataset.contacts);
    const projects = JSON.parse(tableContainer.dataset.projects);
    const projectSpeakers = JSON.parse(tableContainer.dataset.projectSpeakers);

    let isEditing = false;
    let activeRowForProject = null;

    // --- Global Functions (attached to window) ---
    window.completeLog = function(button, logId) {
        fetch(`/speech_log/complete/${logId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const statusCell = button.parentNode;
                statusCell.innerHTML = '<i class="fas fa-check-circle" style="color: green;" title="Completed"></i>';
            } else {
                alert('Error updating status: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while updating the status.');
        });
    };

    window.openSpeechLogModal = function(button) {
        activeRowForProject = button.closest('tr');
        const speechLogModal = document.getElementById('speechLogModal');
        const speechLogForm = document.getElementById('speechLogForm');
        speechLogForm.reset();
        document.getElementById('log_id').value = activeRowForProject.dataset.id;
        document.getElementById('project_id').value = activeRowForProject.dataset.projectId;
        document.getElementById('session_title').value = activeRowForProject.dataset.sessionTitle;
        speechLogModal.style.display = 'flex';
    };

    window.closeSpeechLogModal = function() {
        document.getElementById('speechLogModal').style.display = 'none';
        activeRowForProject = null;
    };

    window.saveProjectDetails = function() {
        const logId = document.getElementById('log_id').value;
        const projectId = document.getElementById('project_id').value;
        const sessionTitle = document.getElementById('session_title').value;

        if(activeRowForProject) {
            activeRowForProject.dataset.projectId = projectId;
            activeRowForProject.dataset.sessionTitle = sessionTitle;
            const cell = activeRowForProject.querySelector('[data-field="Session_Title"] input');
            if (cell) {
                cell.value = sessionTitle;
            }
        }
        closeSpeechLogModal();
    };

    window.deleteLogRow = function(btn) {
        const row = btn.parentNode.parentNode;
        const logId = row.dataset.id;

        if (logId === 'new') {
            row.remove();
            return;
        }

        if (confirm('Are you sure you want to delete this log?')) {
            fetch(`/agenda/delete/${logId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    row.remove();
                } else {
                    alert('Error deleting log: '.concat(data.message));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred while deleting the log.');
            });
        }
    };

    // --- Event Listeners ---
    if (meetingFilter) {
        meetingFilter.addEventListener('change', () => {
            const selectedMeeting = meetingFilter.value;
            window.location.href = `/agenda?meeting_number=${selectedMeeting}`;
        });
    }

    if (editButton && cancelButton && addRowButton && loadButton) {
        editButton.addEventListener('click', function() {
            if (isEditing) {
                saveChanges();
            } else {
                toggleEditMode(true);
            }
        });
        cancelButton.addEventListener('click', () => window.location.reload());
        addRowButton.addEventListener('click', addNewRow);
    }

    if (exportButton) {
        exportButton.addEventListener('click', function() {
            const meetingNumber = meetingFilter.value;
            if (meetingNumber) {
                window.location.href = `/agenda/export/${meetingNumber}`;
            } else {
                alert('Please select a meeting to export.');
            }
        });
    }


    // --- Global Functions (attached to window) ---
    // These functions need to be global to be called from the HTML onclick attribute
    window.completeLog = function(button, logId) {
        fetch(`/speech_log/complete/${logId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const statusCell = button.parentNode;
                statusCell.innerHTML = '<i class="fas fa-check-circle" style="color: green;" title="Completed"></i>';
            } else {
                alert('Error updating status: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while updating the status.');
        });
    };

    // --- Core Functions ---
    function createSessionTitleControl(typeId, originalValue) {
        const sessionType = sessionTypes.find(st => st.id === parseInt(typeId, 10));

        if (sessionType && sessionType.Title === 'Evaluation') {
            const select = document.createElement('select');
            select.options.add(new Option('-- Select Speaker --', ''));

            projectSpeakers.forEach(speakerName => {
                select.options.add(new Option(speakerName, speakerName));
            });

            if (originalValue) {
                select.value = originalValue;
            }
            return select;
        } else {
            const input = document.createElement('input');
            input.type = 'text';
            input.value = originalValue;
            input.style.width = '100%';
            input.style.boxSizing = 'border-box';
            return input;
        }
    }

    function createEditableCell(field, originalValue, isSection, typeId) {
        const cell = document.createElement('td');
        cell.dataset.field = field;

        if (isSection && ['Owner_ID', 'Duration_Min', 'Duration_Max'].includes(field)) {
            cell.textContent = '';
            return cell;
        }

        if (field === 'Start_Time') {
            cell.textContent = originalValue;
            return cell;
        }

        if (field === 'Session_Title') {
            const control = createSessionTitleControl(typeId, originalValue);
            cell.appendChild(control);
        } else if (field === 'Type_ID') {
            const select = document.createElement('select');
            sessionTypes.forEach(type => {
                select.options.add(new Option(type.Title, type.id));
            });
            select.value = originalValue;
            select.onchange = () => handleSectionChange(select);
            cell.appendChild(select);
        } else if (field === 'Owner_ID') {
            const cellContentWrapper = document.createElement('div');
            cellContentWrapper.style.display = 'flex';
            cellContentWrapper.style.alignItems = 'center';

            const select = document.createElement('select');
            select.style.flexGrow = '1';
            select.options.add(new Option('-- Select Owner --', ''));
            contacts.forEach(contact => {
                select.options.add(new Option(contact.Name, contact.id));
            });
            select.value = originalValue;

            const addButton = document.createElement('button');
            addButton.type = 'button';
            addButton.innerHTML = '+';
            addButton.classList.add('btn-success');
            addButton.style.marginLeft = '5px';
            addButton.style.padding = '0 8px';
            addButton.style.border = 'none';
            addButton.onclick = (e) => openContactModal(e.target);

            cellContentWrapper.appendChild(select);
            cellContentWrapper.appendChild(addButton);
            cell.appendChild(cellContentWrapper);
        } else {
            const input = document.createElement('input');
            input.type = 'text';
            input.value = originalValue;
            input.style.width = '100%';
            input.style.boxSizing = 'border-box';
            cell.appendChild(input);
        }
        return cell;
    }

    function createActionsCell(typeId) {
        const actionsCell = document.createElement('td');
        actionsCell.classList.add('actions-column');

        const deleteBtn = document.createElement('button');
        deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i>';
        deleteBtn.className = 'delete-btn icon-btn';
        deleteBtn.onclick = function() { deleteLogRow(this); };
        actionsCell.appendChild(deleteBtn);

        const projectBtn = document.createElement('button');
        projectBtn.innerHTML = '<i class="fas fa-project-diagram"></i>';
        projectBtn.className = 'icon-btn project-btn';
        projectBtn.title = 'Select Project';
        projectBtn.onclick = function() { openSpeechLogModal(this); };

        const sessionType = sessionTypes.find(st => st.id === parseInt(typeId, 10));
        if (sessionType && sessionType.Valid_for_Project) {
            projectBtn.style.display = 'inline-block';
        } else {
            projectBtn.style.display = 'none';
        }
        actionsCell.appendChild(projectBtn);
        return actionsCell;
    }
});