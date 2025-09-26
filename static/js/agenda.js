document.addEventListener('DOMContentLoaded', () => {
    'use strict';

    // --- DOM Elements ---
    const editButton = document.getElementById('edit-logs-btn');
    const cancelButton = document.getElementById('cancel-edit-btn');
    const addRowButton = document.getElementById('add-row-btn');
    const createButton = document.getElementById('create-btn');
    const meetingFilter = document.getElementById('meeting-filter');
    const exportButton = document.getElementById('export-btn');
    const tableContainer = document.getElementById('table-container');
    const tableBody = document.querySelector('#logs-table tbody');
    const contactForm = document.getElementById("contactForm");

    // --- Data from Template ---
    const sessionTypes = JSON.parse(tableContainer.dataset.sessionTypes);
    let contacts = JSON.parse(tableContainer.dataset.contacts);
    let projectSpeakers = JSON.parse(tableContainer.dataset.projectSpeakers);

    // --- State ---
    let isEditing = false;
    let sortable = null;
    let activeOwnerInput = null;

    const sessionPairs = {
        'Ah-Counter Introduction': 'Ah-Counter Report',
        'Grammarian Introduction': 'Grammarian Report',
        'Timer Introduction': 'Timer Report',
        "General Evaluator's Address": 'General Evaluation Report',
        "Toastmaster of the Evening's Address": 'Voting and Announcements',
        "President's Address": 'Awards / Meeting Closing'
    };

    // --- Constants ---
    const fieldsOrder = ['Meeting_Seq', 'Start_Time', 'Type_ID', 'Session_Title', 'Owner_ID', 'Designation', 'Duration_Min', 'Duration_Max'];

    // --- Event Listeners ---
    function initializeEventListeners() {

        if (contactForm) {
            contactForm.addEventListener('submit', handleContactFormSubmit);
        }
        if (meetingFilter) {
            meetingFilter.addEventListener('change', () => {
                window.location.href = `/agenda?meeting_number=${meetingFilter.value}`;
            });
        }
        if (editButton) {
            editButton.addEventListener('click', () => isEditing ? saveChanges() : toggleEditMode(true));
        }
        if (cancelButton) {
            cancelButton.addEventListener('click', () => {
                if (isEditing) {
                    toggleEditMode(false);
                    window.location.reload();
                }
            });
        }
        if (addRowButton) {
            addRowButton.addEventListener('click', addNewRow);
        }
        if (exportButton) {
            exportButton.addEventListener('click', exportAgenda);
        }
        if (createButton) {
            createButton.addEventListener('click', () => {
                 const createAgendaModal = document.getElementById('createAgendaModal');
                 if (createAgendaModal) {
                    createAgendaModal.style.display = 'flex';
                }
            });
        }
        if (tableBody) {
            tableBody.addEventListener('click', (event) => {
                if (event.target.closest('.delete-btn')) {
                    deleteLogRow(event.target.closest('tr'));
                }
            });
        }
    }

    // --- Core Functions ---

    function toggleEditMode(enable) {
        isEditing = enable;
        tableContainer.classList.toggle('edit-mode-active', enable);
        updateHeaderVisibility(enable);
        updateRowsForEditMode(enable);
        updateActionButtonsVisibility(enable);
        meetingFilter.disabled = enable;
        initializeSortable(enable);
    }

    function saveChanges() {
        const dataToSave = Array.from(tableBody.querySelectorAll('tr')).map(getRowData);

        if (dataToSave.length === 0) {
            console.log('No data to save. Ignoring request.');
            toggleEditMode(false);
            window.location.reload();
            if (meetingFilter && meetingFilter.options.length > 0) {
                meetingFilter.value = meetingFilter.options[0].value;
                // Trigger the change event to load the agenda for the new selection
                meetingFilter.dispatchEvent(new Event('change'));
            }
            return;
        }

        fetch("/agenda/update", {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dataToSave),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.reload();
            } else {
                alert('Error saving changes: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while saving.');
        });
    }

    function addNewRow() {
        if (!meetingFilter.value) {
            alert('Please select a meeting to add a session to.');
            return;
        }

        const newRow = tableBody.insertRow();
        Object.assign(newRow.dataset, {
            id: 'new',
            isSection: 'false',
            meetingNumber: meetingFilter.value,
            projectId: '',
            status: 'Booked',
            typeId: sessionTypes.find(st => st.Title === 'Opening')?.id || '',
            sessionTitle: '',
            ownerId: '',
            durationMin: '',
            durationMax: ''
        });

        buildEditableRow(newRow, tableBody.children.length);
        renumberRows();
    }

    function deleteLogRow(row) {
        if (row.dataset.id === 'new') {
            row.remove();
            renumberRows();
            return;
        }

        if (confirm('Are you sure you want to delete this log?')) {
            fetch(`/agenda/delete/${row.dataset.id}`, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    row.remove();
                    renumberRows();
                } else {
                    alert('Error deleting log: ' + data.message);
                }
            })
            .catch(error => console.error('Error:', error));
        }
    }

    // --- Helper Functions ---

    function handleContactFormSubmit(event) {
        event.preventDefault(); // Stop the default redirect
        const form = event.target;
        const formData = new FormData(form);

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                // This header tells your Flask backend it's an AJAX request
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Add the new contact to our local JavaScript array
                contacts.push(data.contact);
                closeContactModal(); // Close the modal
                if (activeOwnerInput) {
                    activeOwnerInput.value = data.contact.Name;
                    const hiddenInput = activeOwnerInput.nextElementSibling;
                    if (hiddenInput && hiddenInput.type === 'hidden' && hiddenInput.name === 'owner_id') {
                        hiddenInput.value = data.contact.id;
                    }
                }
            } else {
                alert('Error saving contact.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while saving the contact.');
        });
    }


    function updateHeaderVisibility(isEditMode) {
        const header = document.querySelector('#logs-table thead');
        header.querySelector('.edit-mode-header').style.display = isEditMode ? 'table-row' : 'none';
        header.querySelector('.non-edit-mode-header').style.display = isEditMode ? 'none' : 'table-row';
    }


    function updateRowsForEditMode(isEditMode) {
        const rows = tableBody.querySelectorAll('tr');
        rows.forEach((row, index) => {
            row.classList.toggle('draggable-row', isEditMode);
            if (isEditMode) {
                const ownerId = row.dataset.ownerId;
                let designation = row.dataset.designation;

                if (ownerId && !designation) {
                    const contact = contacts.find(c => c.id == ownerId);
                    if (contact) {
                        if (contact.DTM) {
                            designation = 'DTM';
                        } else if (contact.Type === 'Guest') {
                            designation = contact.Club ? `Guest@${contact.Club}` : 'Guest';
                        } else if (contact.Type === 'Member') {
                            designation = contact.Completed_Levels ? contact.Completed_Levels.replace(/ /g, '/') : null;
                        }
                    }
                }
                // Fallback for null/undefined to empty string
                row.dataset.designation = designation || '';
                buildEditableRow(row, index + 1);
            }
        });
    }


    function buildEditableRow(row, seq) {
        const originalData = { ...row.dataset };
        row.innerHTML = '';

        if (originalData.isSection === 'true') {
            const seqCell = createEditableCell('Meeting_Seq', seq, true, null);
            const titleCell = createEditableCell('Session_Title', originalData.sessionTitle, true, null);
            titleCell.colSpan = 7;
            titleCell.classList.add('section-row');

            row.append(seqCell, titleCell, createActionsCell(originalData.typeId));
        } else {
            fieldsOrder.forEach((field, index) => {
                const value = (field === 'Meeting_Seq') ? seq : originalData[field.toLowerCase().replace(/_([a-z])/g, g => g[1].toUpperCase())];
                const cell = createEditableCell(field, value, false, originalData.typeId);
                if (index < 3) { // Check if it's one of the first three columns
                    cell.classList.add('drag-handle');
                }
                row.appendChild(cell);
            });
            row.appendChild(createActionsCell(originalData.typeId));
        }
    }

    function updateActionButtonsVisibility(isEditMode) {
        editButton.textContent = isEditMode ? 'Save' : 'Edit';
        cancelButton.style.display = isEditMode ? 'inline-block' : 'none';
        addRowButton.style.display = isEditMode ? 'inline-block' : 'none';
        createButton.style.display = isEditMode ? 'none' : 'inline-block';
        exportButton.style.display = isEditMode ? 'none' : 'inline-block';
    }

    function initializeSortable(enable) {
        if (enable) {
            if(sortable) sortable.destroy();
            sortable = new Sortable(tableBody, {
                animation: 150,
                handle: '.drag-handle',
                onEnd: renumberRows,
            });
        } else {
            if (sortable) {
                sortable.destroy();
                sortable = null;
            }
        }
    }

    function getRowData(row) {
        const isSection = row.dataset.isSection === 'true';
        const titleCell = row.querySelector('[data-field="Session_Title"]');
        const titleControl = titleCell.querySelector('input, select');
        const sessionTitleValue = titleControl ? titleControl.value : titleCell.textContent.trim();
        const seqInput = row.querySelector('[data-field="Meeting_Seq"] input');

        if (isSection) {
            return {
                id: row.dataset.id,
                meeting_number: row.dataset.meetingNumber,
                meeting_seq: seqInput ? seqInput.value : '',
                type_id: row.dataset.typeId,
                session_title: sessionTitleValue,
            };
        }
        return {
            id: row.dataset.id,
            meeting_number: row.dataset.meetingNumber,
            meeting_seq: seqInput ? seqInput.value : '',
            start_time: row.querySelector('[data-field="Start_Time"] input').value,
            type_id: row.querySelector('[data-field="Type_ID"] select').value,
            session_title: sessionTitleValue,
            owner_id: row.querySelector('input[name="owner_id"]').value,
            designation: row.querySelector('[data-field="Designation"] input')?.value || null,
            duration_min: row.querySelector('[data-field="Duration_Min"] input')?.value || null,
            duration_max: row.querySelector('[data-field="Duration_Max"] input')?.value || null,
            project_id: row.dataset.projectId,
            status: row.dataset.status,
        };
    }

    function renumberRows() {
        const rows = tableBody.querySelectorAll('tr');
        rows.forEach((row, index) => {
            const seqCell = row.querySelector('[data-field="Meeting_Seq"]');
            if (seqCell) {
                const input = seqCell.querySelector('input');
                if (input) input.value = index + 1;
            }
        });
    }

    function exportAgenda() {
        const meetingNumber = meetingFilter.value;
        if (meetingNumber) {
            window.location.href = `/agenda/export/${meetingNumber}`;
        } else {
            alert('Please select a meeting to export.');
        }
    }

    function updateProjectSpeakers() {
        const currentSpeakers = new Set();
        tableBody.querySelectorAll('tr').forEach(row => {
            if (parseInt(row.dataset.projectId, 10) > 0) {
                const ownerInput = row.querySelector('.autocomplete-container input[type="text"]');
                if (ownerInput && ownerInput.value) {
                    currentSpeakers.add(ownerInput.value);
                }
            }
        });
        projectSpeakers = [...currentSpeakers];
    }

    function handleSectionChange(selectElement) {
        const row = selectElement.closest('tr');
        const typeId = selectElement.value;
        const sessionType = sessionTypes.find(st => st.id == typeId);

        const titleCell = row.querySelector('[data-field="Session_Title"]');
        titleCell.innerHTML = '';
        titleCell.appendChild(createSessionTitleControl(typeId, sessionType ? sessionType.Title : ''));

        const projectBtn = row.querySelector('.project-btn');
        if (projectBtn) {
            projectBtn.style.display = (sessionType && sessionType.Valid_for_Project) ? 'inline-block' : 'none';
        }
    }

    // --- DOM Creation ---

    function createEditableCell(field, value, isSection, typeId) {
        const cell = document.createElement('td');
        cell.dataset.field = field;

        if (isSection) {
            const input = document.createElement('input');
            input.type = 'text';
            input.value = value || '';
            if (field === 'Meeting_Seq') {
                 input.readOnly = true;
            }
            cell.appendChild(input);
            return cell;
        }

        switch (field) {
            case 'Meeting_Seq':
            case 'Start_Time':
                const input = document.createElement('input');
                input.type = 'text';
                input.value = value || '';
                input.readOnly = true;
                cell.appendChild(input);
                break;
            case 'Type_ID':
                cell.appendChild(createTypeSelect(value));
                break;
            case 'Session_Title':
                cell.appendChild(createSessionTitleControl(typeId, value));
                break;
            case 'Owner_ID':
                cell.appendChild(createOwnerInput(value));
                break;
            default:
                const defaultInput = document.createElement('input');
                defaultInput.type = 'text';
                defaultInput.value = value || '';
                cell.appendChild(defaultInput);
        }
        return cell;
    }

    function createTypeSelect(selectedValue) {
        const select = document.createElement('select');
        sessionTypes.forEach(type => select.add(new Option(type.Title, type.id)));
        select.value = selectedValue;
        select.addEventListener('change', () => handleSectionChange(select));
        return select;
    }

    function createSessionTitleControl(typeId, originalValue) {
        const sessionType = sessionTypes.find(st => st.id == typeId);
        if (sessionType?.Title === 'Evaluation') {
            updateProjectSpeakers();
            const select = document.createElement('select');
            select.add(new Option('-- Select Speaker --', ''));
            projectSpeakers.forEach(name => select.add(new Option(name, name)));
            select.value = originalValue;
            return select;
        } else if (sessionType?.Title === 'Pathway Speech') {
            const span = document.createElement('span');
            span.textContent = originalValue;
            span.title = 'Edit speech title in the project modal';
            return span;
        }
        const input = document.createElement('input');
        input.type = 'text';
        input.value = originalValue;
        return input;
    }

    function createOwnerInput(ownerId) {
        const wrapper = document.createElement('div');
        wrapper.className = 'owner-cell-wrapper';

        const autocompleteContainer = document.createElement('div');
        autocompleteContainer.className = 'autocomplete-container';

        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.placeholder = 'Search...';
        const contact = contacts.find(c => c.id == ownerId);
        if (contact) searchInput.value = contact.Name;

        const hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = 'owner_id';
        hiddenInput.value = ownerId || '';

        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.innerHTML = '<i class="fas fa-plus"></i>';
        addBtn.className = 'btn btn-primary btn-sm';
        addBtn.addEventListener('click', () => {
            activeOwnerInput = searchInput;
            openContactModal();
        });

        setupAutocomplete(searchInput, hiddenInput);

        autocompleteContainer.append(searchInput, hiddenInput);
        wrapper.append(autocompleteContainer, addBtn);
        return wrapper;
    }

    function setupAutocomplete(searchInput, hiddenInput) {
        let currentFocus;
        searchInput.addEventListener("input", function() {
            if (this.readOnly) return;

            if (this.value === '') {
                hiddenInput.value = '';
                const currentRow = searchInput.closest('tr');
                const designationInput = currentRow.querySelector('[data-field="Designation"] input');
                if (designationInput) {
                    designationInput.value = '';
                }
            }
            let container, item, val = this.value;
            closeAllLists();
            if (!val) return;
            currentFocus = -1;
            container = document.createElement("div");
            container.setAttribute("class", "autocomplete-items");
            this.parentNode.appendChild(container);

            contacts.filter(c => c.Name.toUpperCase().includes(val.toUpperCase()))
            .forEach(contact => {
                item = document.createElement("div");
                item.innerHTML = `<strong>${contact.Name.substr(0, val.length)}</strong>${contact.Name.substr(val.length)}`;
                item.innerHTML += `<input type='hidden' value='${contact.Name}' data-id='${contact.id}'>`;
                item.addEventListener("click", function() {
                    searchInput.value = this.querySelector("input").value;
                    hiddenInput.value = this.querySelector("input").dataset.id;
                    closeAllLists();

                    const selectedContactId = this.getElementsByTagName('input')[0].dataset.id;
                    const currentRow = searchInput.closest('tr');
                    const designationInput = currentRow.querySelector('[data-field="Designation"] input');
                    const selectedContact = contacts.find(c => c.id == selectedContactId);

                    if (designationInput && selectedContact) {
                        designationInput.value = selectedContact.Completed_Levels || '';
                    }

                    const currentSessionType = sessionTypes.find(st => st.id == currentRow.querySelector('[data-field="Type_ID"] select').value);

                    if (currentSessionType && sessionPairs[currentSessionType.Title]) {
                        const pairedSessionTitle = sessionPairs[currentSessionType.Title];
                        const allRows = document.querySelectorAll('#logs-table tbody tr');
                        allRows.forEach(row => {
                            const typeSelect = row.querySelector('[data-field="Type_ID"] select');
                            if (typeSelect) {
                                const sessionType = sessionTypes.find(st => st.id == typeSelect.value);
                                if (sessionType && sessionType.Title === pairedSessionTitle) {
                                    const pairedHiddenInput = row.querySelector('input[name="owner_id"]');
                                    const pairedSearchInput = row.querySelector('.autocomplete-container input[type="text"]');
                                    if (pairedHiddenInput && pairedSearchInput) {
                                        const newContact = contacts.find(c => c.id == selectedContactId);
                                        if (newContact) {
                                            pairedHiddenInput.value = newContact.id;
                                            pairedSearchInput.value = newContact.Name;

                                            pairedSearchInput.readOnly = true;
                                            pairedSearchInput.style.pointerEvents = 'none'; // This is a powerful trick
                                        }
                                    }
                                }
                            }
                        });
                    }
                });
                container.appendChild(item);
            });
        });

        function closeAllLists(elmnt) {
            const items = document.getElementsByClassName("autocomplete-items");
            for (let i = 0; i < items.length; i++) {
                if (elmnt != items[i] && elmnt != searchInput) {
                    items[i].parentNode.removeChild(items[i]);
                }
            }
        }
        document.addEventListener("click", (e) => closeAllLists(e.target));
    }


    function createActionsCell(typeId) {
        const cell = document.createElement('td');
        cell.className = 'actions-column';

        const projectBtn = document.createElement('button');
        projectBtn.innerHTML = '<i class="fas fa-project-diagram"></i>';
        projectBtn.className = 'icon-btn project-btn';
        projectBtn.type = 'button';
        projectBtn.onclick = function() {
            const row = this.closest('tr');
            const logId = row.dataset.id;
            const ownerId = row.querySelector('input[name="owner_id"]').value;
            const contact = contacts.find(c => c.id == ownerId);
            const workingPath = contact ? contact.Working_Path : null;
            openSpeechEditModal(logId, workingPath);
        };
        const sessionType = sessionTypes.find(st => st.id == typeId);
        projectBtn.style.display = (sessionType && sessionType.Valid_for_Project) ? 'inline-block' : 'none';

        const deleteBtn = document.createElement('button');
        deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i>';
        deleteBtn.className = 'delete-btn icon-btn';
        deleteBtn.type = 'button';

        cell.append(projectBtn, deleteBtn);
        return cell;
    }

    // --- Init ---
    initializeEventListeners();
});

function closeCreateAgendaModal() {
    const createAgendaModal = document.getElementById('createAgendaModal');
    if (createAgendaModal) {
        createAgendaModal.style.display = 'none';
    }
}
