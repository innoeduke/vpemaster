// const allProjects = {{ projects|tojson|safe }};

function openSpeechEditModal(logId) {
    fetch(`/speech_log/details/${logId}`)
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document.getElementById('edit-log-id').value = data.log.id;
            document.getElementById('edit-speech-title').value = data.log.Session_Title;
            document.getElementById('edit-pathway').value = data.log.pathway;
            document.getElementById('edit-level').value = data.log.level;
            updateProjectOptions(data.log.Project_ID);
            document.getElementById('speechEditModal').style.display = 'flex';
        } else {
            alert('Error fetching speech log details.');
        }
    });
}

function closeSpeechEditModal() {
    document.getElementById('speechEditModal').style.display = 'none';
}

function updateProjectOptions(selectedProjectId = null) {
    const pathwaySelect = document.getElementById('edit-pathway');
    const levelSelect = document.getElementById('edit-level');
    const projectSelect = document.getElementById('edit-project');

    const selectedPathway = pathwaySelect.value;
    const selectedLevel = levelSelect.value;
    const codeAttr = pathwayMap[selectedPathway];

    projectSelect.innerHTML = '<option value="">-- Select a Project --</option>';

    if (selectedPathway && selectedLevel && codeAttr) {
        const filteredProjects = allProjects.filter(p => p[codeAttr] && p[codeAttr].startsWith(selectedLevel + '.'));

        filteredProjects.sort((a, b) => {
            const codeA = a[codeAttr];
            const codeB = b[codeAttr];
            if (codeA < codeB) return -1;
            if (codeA > codeB) return 1;
            return 0;
        });

        filteredProjects.forEach(p => {
            const option = new Option(p.Project_Name, p.ID);
            projectSelect.add(option);
        });

        if (selectedProjectId) {
            projectSelect.value = selectedProjectId;
        }
    }
}

function saveSpeechChanges(event) {
    event.preventDefault();
    const logId = document.getElementById('edit-log-id').value;
    const form = document.getElementById('speechEditForm');
    const data = {
        session_title: form.querySelector('#edit-speech-title').value,
        project_id: form.querySelector('#edit-project').value,
        pathway: form.querySelector('#edit-pathway').value
    };

    fetch(`/speech_log/update/${logId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (window.location.pathname.includes('/agenda')) {
                const agendaRow = document.querySelector(`tr[data-id="${logId}"]`);
                if (agendaRow) {
                    agendaRow.dataset.projectId = data.project_id;
                    const sessionTitleCell = agendaRow.querySelector('[data-field="Session_Title"]');
                    if (sessionTitleCell) {
                        const titleControl = sessionTitleCell.querySelector('input, select');
                        if (titleControl) {
                            titleControl.value = data.session_title;
                        } else {
                            sessionTitleCell.textContent = data.session_title;
                        }
                    }
                }
                closeSpeechEditModal();
            } else {
                const card = document.getElementById(`log-card-${logId}`);
                if (card) {
                    card.querySelector('.speech-title').innerText = `"${data.session_title.replace(/"/g, '')}"`;
                    card.querySelector('.project-name').innerText = data.project_name;
                    card.querySelector('.project-code').innerText = data.project_code ? `(${data.project_code})` : '';
                    card.querySelector('.pathway-info').innerText = data.pathway;
                }
                closeSpeechEditModal();
            }
        } else {
            alert('Error updating speech log: ' + data.message);
        }
    });
}