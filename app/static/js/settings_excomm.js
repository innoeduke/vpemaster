// Excomm Term Modal Controls
function openExcommModal() {
    const form = document.getElementById('excomm-form');
    if (form) form.reset();
    
    document.getElementById('excomm-id').value = '';
    document.getElementById('excommModal-title').textContent = 'Add Excomm Team';
    
    openActionModal('excommModal');
}

function closeExcommModal() {
    closeActionModal('excommModal');
}

function openEditExcommModal(btn) {
    const id = btn.dataset.id;
    const term = btn.dataset.term;
    const name = btn.dataset.name;
    const start = btn.dataset.start;
    const end = btn.dataset.end;
    
    document.getElementById('excomm-id').value = id;
    document.getElementById('excomm-term').value = term;
    document.getElementById('excomm-name').value = name;
    document.getElementById('excomm-start').value = start;
    document.getElementById('excomm-end').value = end;
    
    document.getElementById('excommModal-title').textContent = 'Edit Excomm Team';
    
    openActionModal('excommModal');
}

// Officer Modal Controls
function openOfficerModal() {
    const form = document.getElementById('officer-form');
    if (form) form.reset();
    
    document.getElementById('officer-link-id').value = '';
    document.getElementById('officer-contact-id').value = '';
    document.getElementById('officer-search').value = '';
    document.getElementById('officer-is-assistant').checked = false;
    document.getElementById('officerModal-title').textContent = 'Add Officer';
    
    openActionModal('officerModal');
}

function closeOfficerModal() {
    closeActionModal('officerModal');
}

function openEditOfficerModal(btn) {
    const id = btn.dataset.id;
    const roleId = btn.dataset.roleId;
    const contactId = btn.dataset.contactId;
    const contactName = btn.dataset.contactName;
    const isAssistant = btn.dataset.assistant === 'true';
    
    document.getElementById('officer-link-id').value = id;
    document.getElementById('officer-role').value = roleId;
    document.getElementById('officer-contact-id').value = contactId;
    document.getElementById('officer-search').value = contactName;
    document.getElementById('officer-is-assistant').checked = isAssistant;
    
    document.getElementById('officerModal-title').textContent = 'Edit Officer';
    
    openActionModal('officerModal');
}

document.addEventListener('DOMContentLoaded', function() {
    // 1. Submit Excomm Term Form
    const excommForm = document.getElementById('excomm-form');
    if (excommForm) {
        excommForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const id = document.getElementById('excomm-id').value;
            const url = id ? '/settings/excomm/update' : '/settings/excomm/add';
            
            const data = {
                id: id,
                term: document.getElementById('excomm-term').value,
                name: document.getElementById('excomm-name').value,
                start_date: document.getElementById('excomm-start').value,
                end_date: document.getElementById('excomm-end').value
            };
            
            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrf_token')
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    location.reload();
                } else {
                    alert('Error: ' + result.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred while saving.');
            });
        });
    }

    // 2. Submit Officer Form
    const officerForm = document.getElementById('officer-form');
    if (officerForm) {
        officerForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const id = document.getElementById('officer-link-id').value;
            const url = id ? '/settings/excomm/officer/update' : '/settings/excomm/officer/add';
            
            const data = {
                id: id,
                excomm_id: document.getElementById('officer-excomm-id').value,
                role_id: document.getElementById('officer-role').value,
                contact_id: document.getElementById('officer-contact-id').value,
                is_assistant: document.getElementById('officer-is-assistant').checked
            };
            
            if (!data.excomm_id) {
                alert('Please select or create an Excomm term first.');
                return;
            }
            if (!data.contact_id) {
                alert('Please select a valid member from the search autocomplete.');
                return;
            }
            
            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrf_token')
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    location.reload();
                } else {
                    alert('Error: ' + result.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred while saving.');
            });
        });
    }

    // Initialize Autocomplete for Officer Modal search input
    const officerSearch = document.getElementById('officer-search');
    const officerContactId = document.getElementById('officer-contact-id');
    if (officerSearch && officerContactId && typeof initAutocomplete === 'function' && typeof ALL_CONTACTS !== 'undefined') {
        initAutocomplete(officerSearch, officerContactId, ALL_CONTACTS);
    }
});

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
