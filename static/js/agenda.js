document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const editButton = document.getElementById('edit-logs-btn');
    const cancelButton = document.getElementById('cancel-edit-btn');
    const addRowButton = document.getElementById('add-row-btn');
    const loadButton = document.getElementById('load-btn');
    const createButton = document.getElementById('create-btn');
    const meetingFilter = document.getElementById('meeting-filter');
    const exportButton = document.getElementById('export-btn');
    const tableContainer = document.getElementById('table-container');

    // --- Data passed from the template ---
    const sessionTypes = JSON.parse(tableContainer.dataset.sessionTypes);
    const contacts = JSON.parse(tableContainer.dataset.contacts);
    const projects = JSON.parse(tableContainer.dataset.projects);
    let projectSpeakers = JSON.parse(tableContainer.dataset.projectSpeakers);

    let isEditing = false;
    let sortable = null; // Variable to hold the sortable instance
    let activeOwnerInput = null;

    const sessionPairs = {
        'Ah-Counter Introduction': 'Ah-Counter Report',
        'Grammarian Introduction': 'Grammarian Report',
        'Timer Introduction': 'Timer Report',
        "General Evaluator's Address": 'General Evaluation Report',
        "Toastmaster of the Evening's Address": 'Voting and Awards',
        "President's Address": 'Announcements / Meeting Closing'
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
        cancelButton.addEventListener('click', () => {
             if (sortable) {
                sortable.destroy(); // De-activate drag & drop on cancel
                sortable = null;
            }
            window.location.reload()
        });
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

    // --- Core Functions ---

    function renumberRows() {
        const rows = document.querySelectorAll('#logs-table tbody tr');
        rows.forEach((row, index) => {
            const seqCell = row.querySelector('[data-field="Meeting_Seq"]');
            if (seqCell) {
                seqCell.textContent = index + 1;
            }
        });
    }

    // --- New function to update the speaker list dynamically ---
    function updateProjectSpeakers() {
        const currentSpeakers = [];
        const rows = document.querySelectorAll('#logs-table tbody tr');
        rows.forEach(row => {
            const typeSelect = row.querySelector('[data-field="Type_ID"] select');
            if (typeSelect) {
                const sessionType = sessionTypes.find(st => st.id == typeSelect.value);
                if (sessionType && sessionType.Title === 'Pathway Speech') {
                    const ownerInput = row.querySelector('.autocomplete-container input[type="text"]');
                    if (ownerInput && ownerInput.value) {
                        currentSpeakers.push(ownerInput.value);
                    }
                }
            }
        });
        projectSpeakers = [...new Set(currentSpeakers)]; // Update the global list
    }


    function toggleEditMode(enable) {
        isEditing = enable;
        const tableContainer = document.getElementById('table-container');
        if (enable) {
            tableContainer.classList.add('edit-mode-active');
        } else {
            tableContainer.classList.remove('edit-mode-active');
        }

        const table = document.getElementById('logs-table');
        const header = table.querySelector('thead');
        const rows = table.querySelectorAll('tbody tr');

        header.querySelector('.edit-mode-header').style.display = enable ? 'table-row' : 'none';
        header.querySelector('.non-edit-mode-header').style.display = enable ? 'none' : 'table-row';

        let seqCounter = 1;

        rows.forEach(row => {
            if (enable) {
                row.classList.add('draggable-row');
            }
            const isSection = row.dataset.isSection === 'true';
            const typeId = row.dataset.typeId;
            row.innerHTML = '';

            const fieldsMap = {
                'Meeting_Seq': 'meetingSeq', 'Start_Time': 'startTime',
                'Type_ID': 'typeId', 'Session_Title': 'sessionTitle',
                'Owner_ID': 'ownerId', 'Duration_Min': 'durationMin',
                'Duration_Max': 'durationMax'
            };
            const fieldsOrder = ['Meeting_Seq', 'Start_Time', 'Type_ID', 'Session_Title', 'Owner_ID', 'Duration_Min', 'Duration_Max'];

            if (isSection) {
                 // Correctly build section rows with separate cells
                 const seqCell = createEditableCell('Meeting_Seq', seqCounter, false, typeId);
                 const titleCell = createEditableCell('Session_Title', row.dataset.sessionTitle, true, typeId);
                 titleCell.colSpan = 6; // Span across the middle columns
                 titleCell.classList.add('section-row'); // Apply the dark red style to the title cell

                 row.appendChild(seqCell);
                 row.appendChild(titleCell);
                 row.appendChild(createActionsCell(typeId));
            } else {
                fieldsOrder.forEach(field => {
                    const datasetKey = fieldsMap[field];
                    const value = (field === 'Meeting_Seq') ? seqCounter : row.dataset[datasetKey];
                    const cell = createEditableCell(field, value, isSection, typeId);
                    row.appendChild(cell);
                });
                row.appendChild(createActionsCell(typeId));
            }
            seqCounter++;
        });

        editButton.textContent = 'Save';
        cancelButton.style.display = 'inline-block';
        addRowButton.style.display = 'inline-block';
        createButton.style.display = 'none';
        loadButton.style.display = 'none';
        exportButton.style.display = 'none';
        meetingFilter.disabled = true;

        const tableBody = table.querySelector('tbody');
        if (enable && tableBody) {
            sortable = new Sortable(tableBody, {
                animation: 150,
                onEnd: function() {
                    renumberRows();
                }
            });
        }
    }

    function saveChanges() {
        const rows = document.querySelectorAll('#logs-table tbody tr');
        const dataToSave = [];

        rows.forEach(row => {
            const isSection = row.dataset.isSection === 'true';
            let rowData;

            const titleCell = row.querySelector('[data-field="Session_Title"]');
            const titleControl = titleCell.querySelector('input, select');
            let sessionTitleValue;

            if (titleControl) {
                sessionTitleValue = titleControl.value;
            } else {
                sessionTitleValue = titleCell.textContent.trim();
            }

            if (isSection) {
                rowData = {
                    id: row.dataset.id,
                    meeting_number: row.dataset.meetingNumber,
                    meeting_seq: row.querySelector('[data-field="Meeting_Seq"]').textContent.trim(),
                    type_id: row.dataset.typeId,
                    session_title: sessionTitleValue,
                    start_time: '',
                    owner_id: null,
                    duration_min: null,
                    duration_max: null,
                    project_id: null,
                    status: null
                };
            } else {
                rowData = {
                    id: row.dataset.id,
                    meeting_number: row.dataset.meetingNumber,
                    meeting_seq: row.querySelector('[data-field="Meeting_Seq"]').textContent.trim(),
                    start_time: row.querySelector('[data-field="Start_Time"]').textContent.trim(),
                    type_id: row.querySelector('[data-field="Type_ID"] select').value,
                    session_title: sessionTitleValue,
                    owner_id: row.querySelector('input[name="owner_id"]').value,
                    duration_min: row.querySelector('[data-field="Duration_Min"] input') ? row.querySelector('[data-field="Duration_Min"] input').value : null,
                    duration_max: row.querySelector('[data-field="Duration_Max"] input') ? row.querySelector('[data-field="Duration_Max"] input').value : null,
                    project_id: row.dataset.projectId,
                    status: row.dataset.status
                };
            }
            dataToSave.push(rowData);
        });

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
                alert('Error saving changes: '.concat(data.message));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while saving.');
        });
    }

    function addNewRow() {
        const tableBody = document.querySelector('#logs-table tbody');
        const meetingNumber = meetingFilter.value;
        if (!meetingNumber) {
            alert('Please select a meeting to add a session to.');
            return;
        }

        const newRow = document.createElement('tr');
        newRow.dataset.id = 'new';
        newRow.dataset.isSection = 'false';
        newRow.dataset.meetingNumber = meetingNumber;
        newRow.dataset.projectId = '';
        newRow.dataset.status = 'Booked';

        const fields = [
            { name: 'Meeting_Seq', value: tableBody.children.length + 1 },
            { name: 'Start_Time', value: '' }, { name: 'Type_ID', value: '' },
            { name: 'Session_Title', value: '' }, { name: 'Owner_ID', value: '' },
            { name: 'Duration_Min', value: '' }, { name: 'Duration_Max', value: '' }
        ];

        fields.forEach(field => {
            const cell = createEditableCell(field.name, field.value, false, '');
            newRow.appendChild(cell);
        });

        newRow.appendChild(createActionsCell(''));
        tableBody.appendChild(newRow);
    }

    function handleSectionChange(selectElement) {
        const selectedTypeId = parseInt(selectElement.value, 10);
        const sessionType = sessionTypes.find(st => st.id === selectedTypeId);
        const row = selectElement.closest('tr');

        const titleCell = row.querySelector('[data-field="Session_Title"]');
        titleCell.innerHTML = '';
        const newTitleControl = createSessionTitleControl(selectedTypeId, sessionType ? sessionType.Title : '');
        titleCell.appendChild(newTitleControl);

        const projectBtn = row.querySelector('.project-btn');
        if (projectBtn) {
            projectBtn.style.display = (sessionType && sessionType.Valid_for_Project) ? 'inline-block' : 'none';
        }
    }

    function createSessionTitleControl(typeId, originalValue) {
        const sessionType = sessionTypes.find(st => st.id === parseInt(typeId, 10));

        if (sessionType && sessionType.Title === 'Evaluation') {
            updateProjectSpeakers(); // Refresh the list before creating the dropdown
            const select = document.createElement('select');
            select.options.add(new Option('-- Select Speaker --', ''));
            projectSpeakers.forEach(speakerName => {
                select.options.add(new Option(speakerName, speakerName));
            });
            if (originalValue) {
                select.value = originalValue;
            }
            return select;
        } else if (sessionType && sessionType.Title === 'Pathway Speech') {
            const span = document.createElement('span');
            span.textContent = originalValue;
            span.title = 'Edit the speech title in the project modal';
            span.classList.add('readonly-title');
            return span;
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
        cell.classList.add('edit-mode-cell');
        cell.dataset.field = field;

        if (field === 'Meeting_Seq' || field === 'Start_Time') {
            const input = document.createElement('input');
            input.type = 'text';
            input.value = originalValue;
            input.readOnly = true;
            input.classList.add('non-editable-input');
            cell.appendChild(input);
            return cell;
        }

        if (isSection) {
            const input = document.createElement('input');
            input.type = 'text';
            input.value = originalValue;
            cell.appendChild(input);
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
            const ownerCellWrapper = document.createElement('div');
            ownerCellWrapper.classList.add('owner-cell-wrapper');

            const autocompleteContainer = document.createElement('div');
            autocompleteContainer.classList.add('autocomplete-container');
            autocompleteContainer.style.flexGrow = '1';

            const searchInput = document.createElement('input');
            searchInput.type = 'text';
            searchInput.placeholder = 'Search for owner...';
            const contact = contacts.find(c => c.id == originalValue);
            if (contact) {
                searchInput.value = contact.Name;
            }

            const hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = 'owner_id';
            hiddenInput.value = originalValue || '';

            autocompleteContainer.appendChild(searchInput);
            autocompleteContainer.appendChild(hiddenInput);

            const addBtn = document.createElement('button');
            addBtn.type = 'button';
            addBtn.innerHTML = '<i class="fas fa-plus"></i>';
            addBtn.className = 'btn btn-primary btn-sm';
            addBtn.title = 'Add New Contact';
            addBtn.onclick = () => openContactModal();

            ownerCellWrapper.appendChild(autocompleteContainer);
            ownerCellWrapper.appendChild(addBtn);
            cell.appendChild(ownerCellWrapper);

            let currentFocus;
            searchInput.addEventListener('input', function() {
                const val = this.value;
                closeAllLists();
                if (!val) { return false; }
                currentFocus = -1;

                const suggestions = document.createElement('div');
                suggestions.id = this.id + 'autocomplete-list';
                suggestions.classList.add('autocomplete-items');
                this.parentNode.appendChild(suggestions);

                const filteredContacts = contacts.filter(c => c.Name.toUpperCase().includes(val.toUpperCase()));

                filteredContacts.forEach(c => {
                    const item = document.createElement('div');
                    item.innerHTML = "<strong>" + c.Name.substr(0, val.length) + "</strong>";
                    item.innerHTML += c.Name.substr(val.length);
                    item.innerHTML += "<input type='hidden' value='" + c.Name + "' data-id='" + c.id + "'>";
                    item.addEventListener('click', function() {
                        searchInput.value = this.getElementsByTagName('input')[0].value;
                        hiddenInput.value = this.getElementsByTagName('input')[0].dataset.id;
                        closeAllLists();

                        const selectedContactId = this.getElementsByTagName('input')[0].dataset.id;
                        const currentRow = searchInput.closest('tr');
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
                                            }
                                        }
                                    }
                                }
                            });
                        }
                    });
                    suggestions.appendChild(item);
                });
            });


            const sessionType = sessionTypes.find(st => st.id == typeId);
            if(sessionType) {
                const pairedSession = Object.values(sessionPairs).includes(sessionType.Title);
                if (pairedSession) {
                    searchInput.readOnly = true;
                    searchInput.classList.add('non-editable-input');
                    addBtn.style.display = 'none';
                }
            }


            function closeAllLists(elmnt) {
                const items = document.getElementsByClassName('autocomplete-items');
                for (let i = 0; i < items.length; i++) {
                    if (elmnt != items[i] && elmnt != searchInput) {
                        items[i].parentNode.removeChild(items[i]);
                    }
                }
            }
            document.addEventListener('click', function(e) {
                closeAllLists(e.target);
            });
        } else {
            const input = document.createElement('input');
            input.type = 'text';
            input.value = originalValue;

            // Make the sequence number field read-only and apply the new style
            if (field === 'Meeting_Seq') {
                input.readOnly = true;
                input.classList.add('seq-no-readonly');
            }

            cell.appendChild(input);
        }
        return cell;
    }

    function createActionsCell(typeId) {
        const actionsCell = document.createElement('td');
        actionsCell.classList.add('actions-column');

        const projectBtn = document.createElement('button');
        projectBtn.innerHTML = '<i class="fas fa-project-diagram"></i>';
        projectBtn.className = 'icon-btn project-btn';
        projectBtn.title = 'Select Project';
        projectBtn.onclick = function() {
            const logId = this.closest('tr').dataset.id;
            // This is the key change: call the new global modal function
            openSpeechEditModal(logId);
        };

        const sessionType = sessionTypes.find(st => st.id === parseInt(typeId, 10));
        if (sessionType && sessionType.Valid_for_Project) {
            projectBtn.style.display = 'inline-block';
        } else {
            projectBtn.style.display = 'none';
        }
        actionsCell.appendChild(projectBtn);

        const deleteBtn = document.createElement('button');
        deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i>';
        deleteBtn.className = 'delete-btn icon-btn';
        deleteBtn.onclick = function() { deleteLogRow(this); };
        actionsCell.appendChild(deleteBtn);

        return actionsCell;
    }

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

    // --- Contact Modal Logic from agenda.html ---
    const contactModal = document.getElementById("contactModal");
    const contactForm = document.getElementById("contactForm");
    const contactModalTitle = document.getElementById("contactModalTitle");

    function openContactModal(searchInput, hiddenInput) {
        activeOwnerInput = { search: searchInput, hidden: hiddenInput };
        contactForm.reset();
        contactModalTitle.textContent = 'Add New Contact';
        contactForm.action = "{{ url_for('contacts_bp.contact_form') }}";
        contactModal.style.display = "flex";
    }

    function closeContactModal() {
        contactModal.style.display = "none";
    }

    if (contactForm) {
        contactForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            fetch(this.action, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            }).then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (activeOwnerInput) {
                        activeOwnerInput.search.value = data.contact.Name;
                        activeOwnerInput.hidden.value = data.contact.id;
                    }
                    contacts.push(data.contact);
                    closeContactModal();
                } else {
                    alert('Failed to save contact.');
                }
            }).catch(error => {
                console.error('Error:', error);
                alert('An error occurred while saving the contact.');
            });
        });
    }
});