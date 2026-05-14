function openExcommModal() {
    document.getElementById('excomm-form').reset();
    document.getElementById('excomm-id').value = '';
    document.getElementById('excomm-modal-title').textContent = 'Add New Excomm Team';
    document.querySelectorAll('.officer-select').forEach(input => input.value = '');
    document.querySelectorAll('.officer-search-input').forEach(input => input.value = '');
    document.getElementById('excomm-modal').style.display = 'block';
}

function closeExcommModal() {
    document.getElementById('excomm-modal').style.display = 'none';
}

function openEditExcommModal(btn) {
    const tr = btn.closest('tr');
    const id = tr.dataset.id;
    const start = tr.dataset.start;
    const end = tr.dataset.end;
    
    // Parse name and term from cells - careful with badge in term cell
    // Structure: <td>{{ exc.id }}</td>
    //            <td>{{ exc.excomm_term }} <span class...>...</span></td>
    //            <td>{{ exc.excomm_name }}</td>
    
    // Safer to get text content but exclude children logic or robust parsing
    const termCell = tr.cells[1];
    let term = termCell.textContent.trim();
    if (termCell.querySelector('.badge')) {
        // Remove badge text from term string
        const badge = termCell.querySelector('.badge');
        term = term.replace(badge.textContent, '').trim();
    }
    
    const name = tr.cells[2].textContent.trim();
    
    document.getElementById('excomm-id').value = id;
    document.getElementById('excomm-term').value = term;
    document.getElementById('excomm-name').value = name;
    document.getElementById('excomm-start').value = start;
    document.getElementById('excomm-end').value = end;
    
    // Title
    document.getElementById('excomm-modal-title').textContent = 'Edit Excomm Team';
    
    // Populate Officers
    // Iterate over dynamic officer columns (index 3 to length-1)
    // Actually, we can use the data attributes we added to the td cells!
    // <td data-role-id="..." data-contact-id="...">
    
    const officerSelects = document.querySelectorAll('.officer-select');
    const officerSearchInputs = document.querySelectorAll('.officer-search-input');
    // Clear all first
    officerSelects.forEach(select => select.value = "");
    officerSearchInputs.forEach(input => input.value = "");
    
    // The officer cells start at index 3
    // But easier is to query all TDs in this row with data-role-id
    const officerCells = tr.querySelectorAll('td[data-role-id]');
    
    officerCells.forEach(cell => {
        const roleId = cell.dataset.roleId;
        const contactId = cell.dataset.contactId;
        const contactName = cell.textContent.trim();
        
        if (roleId && contactId) {
            const hidden = document.getElementById(`officer-role-${roleId}`);
            const search = document.getElementById(`officer-search-${roleId}`);
            if (hidden) {
                hidden.value = contactId;
            }
            if (search) {
                search.value = contactName;
            }
        }
    });

    document.getElementById('excomm-modal').style.display = 'block';
}

document.addEventListener('DOMContentLoaded', function() {
    const excommForm = document.getElementById('excomm-form');
    if (excommForm) {
        excommForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const id = document.getElementById('excomm-id').value;
            const url = id ? '/settings/excomm/update' : '/settings/excomm/add';
            
            // Gather standard fields
            const data = {
                id: id,
                term: document.getElementById('excomm-term').value,
                name: document.getElementById('excomm-name').value,
                start_date: document.getElementById('excomm-start').value,
                end_date: document.getElementById('excomm-end').value,
                officers: {}
            };
            
            // Gather officers
            const officerSelects = document.querySelectorAll('.officer-select');
            officerSelects.forEach(select => {
                // ID format: officer-role-{role_id}
                const roleId = select.id.split('-')[2];
                data.officers[roleId] = select.value; // contact_id or empty
            });
            
            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrf_token') // Ensure utility available or meta tag? 
                    // settings.js usually handles fetching with generic helpers or we need getCookie
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    location.reload(); // Simple reload to refresh table
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

    // Initialize Autocomplete for Officer Search
    const officerSearchInputs = document.querySelectorAll('.officer-search-input');
    officerSearchInputs.forEach(input => {
        const roleId = input.id.split('-')[2];
        const hidden = document.getElementById(`officer-role-${roleId}`);
        if (hidden && typeof initAutocomplete === 'function' && typeof ALL_CONTACTS !== 'undefined') {
            initAutocomplete(input, hidden, ALL_CONTACTS);
        }
    });
});

// Helper if not in global scope (settings.js might have it, but standard fetch usage)
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
