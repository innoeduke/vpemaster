document.addEventListener('DOMContentLoaded', () => {
    'use strict';

    // --- DOM Elements ---
    const editButton = document.getElementById('edit-logs-btn');
    const cancelButton = document.getElementById('cancel-edit-btn');
    const addRowButton = document.getElementById('add-row-btn');
    const loadButton = document.getElementById('load-btn');
    const createButton = document.getElementById('create-btn');
    const meetingFilter = document.getElementById('meeting-filter');
    const exportButton = document.getElementById('export-btn');
    const tableContainer = document.getElementById('table-container');
    const tableBody = document.querySelector('#logs-table tbody');

    // --- Data from Template ---
    const sessionTypes = JSON.parse(tableContainer.dataset.sessionTypes);
    const contacts = JSON.parse(tableContainer.dataset.contacts);
    let projectSpeakers = JSON.parse(tableContainer.dataset.projectSpeakers);

    // --- State ---
    let isEditing = false;
    let sortable = null;

    // --- Constants ---
    const fieldsOrder = ['Meeting_Seq', 'Start_Time', 'Type_ID', 'Session_Title', 'Owner_ID', 'Duration_Min', 'Duration_Max'];

    // --- Event Listeners ---
    function initializeEventListeners() {
        if (meetingFilter) {
            meetingFilter.addEventListener('change', () => {
                window.location.href = `/agenda?meeting_number=${meetingFilter.value}`;
            });
        }
        if (editButton) {
            editButton.addEventListener('click', () => isEditing ? saveChanges() : toggleEditMode(true));
        }
        if (cancelButton) {
            cancelButton.addEventListener('click', () => window.location.reload());
        }
        if (addRowButton) {
            addRowButton.addEventListener('click', addNewRow);
        }
        if (exportButton) {
            exportButton.addEventListener('click', exportAgenda);
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
                buildEditableRow(row, index + 1);
            }
        });
    }

    /**
     * Rebuilds a table row for edit mode, handling regular and section rows.
     */
    function buildEditableRow(row, seq) {
        const originalData = { ...row.dataset };
        row.innerHTML = ''; // Clear existing content

        if (originalData.isSection === 'true') {
            // *** THIS IS THE CORRECTED LOGIC FOR SECTION ROWS ***
            const seqCell = createEditableCell('Meeting_Seq', seq, true, null);
            const titleCell = createEditableCell('Session_Title', originalData.sessionTitle, true, null);
            titleCell.colSpan = 6;
            titleCell.classList.add('section-row'); // Apply styling

            row.append(seqCell, titleCell, createActionsCell(originalData.typeId));
        } else {
            // Logic for regular rows remains the same
            fieldsOrder.forEach(field => {
                const value = (field === 'Meeting_Seq') ? seq : originalData[field.toLowerCase().replace(/_([a-z])/g, g => g[1].toUpperCase())];
                row.appendChild(createEditableCell(field, value, false, originalData.typeId));
            });
            row.appendChild(createActionsCell(originalData.typeId));
        }
    }

    function updateActionButtonsVisibility(isEditMode) {
        editButton.textContent = isEditMode ? 'Save' : 'Edit';
        cancelButton.style.display = isEditMode ? 'inline-block' : 'none';
        addRowButton.style.display = isEditMode ? 'inline-block' : 'none';
        createButton.style.display = isEditMode ? 'none' : 'inline-block';
        loadButton.style.display = isEditMode ? 'none' : 'inline-block';
        exportButton.style.display = isEditMode ? 'none' : 'inline-block';
    }

    function initializeSortable(enable) {
        if (enable) {
            if(sortable) sortable.destroy();
            sortable = new Sortable(tableBody, {
                animation: 150,
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
            const typeSelect = row.querySelector('[data-field="Type_ID"] select');
            if (typeSelect) {
                const sessionType = sessionTypes.find(st => st.id == typeSelect.value);
                if (sessionType && sessionType.Title === 'Pathway Speech') {
                    const ownerInput = row.querySelector('.autocomplete-container input[type="text"]');
                    if (ownerInput && ownerInput.value) {
                        currentSpeakers.add(ownerInput.value);
                    }
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
            input.value = value;
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
                input.value = value;
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
                defaultInput.value = value;
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
        addBtn.onclick = () => openContactModal(); // Assumes openContactModal is defined globally

        setupAutocomplete(searchInput, hiddenInput);

        autocompleteContainer.append(searchInput, hiddenInput);
        wrapper.append(autocompleteContainer, addBtn);
        return wrapper;
    }

    function setupAutocomplete(searchInput, hiddenInput) {
        let currentFocus;
        searchInput.addEventListener("input", function() {
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
        projectBtn.onclick = function() { openSpeechEditModal(this.closest('tr').dataset.id); }; // Assumes openSpeechEditModal is global
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