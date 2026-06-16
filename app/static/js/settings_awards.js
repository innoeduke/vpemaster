/**
 * JavaScript for Club Awards Management in settings.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Setup form submit listener
    const form = document.getElementById('award-edit-form');
    if (form) {
        form.addEventListener('submit', handleAwardFormSubmit);
    }
});

// Module-level state
const AP_ROLE_TYPES = [
    { value: 'officer',    label: 'Officer',    icon: 'fa-user-tie' },
    { value: 'leading',    label: 'Leading',    icon: 'fa-flag' },
    { value: 'functional', label: 'Functional', icon: 'fa-tools' },
    { value: 'other',      label: 'Other',      icon: 'fa-circle' },
];
let selectedAwardRoleIds = new Set();

function rolesOfType(type) {
    return (window.ROLES_DATA || []).filter(r => r.type === type);
}

function buildRoleRow(role) {
    const row = document.createElement('label');
    row.className = 'ap-checkbox-row ap-role-row';
    
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.className = 'ap-role-cb';
    cb.dataset.roleId = String(role.id);
    cb.checked = selectedAwardRoleIds.has(role.id);
    cb.addEventListener('change', () => {
        if (cb.checked) selectedAwardRoleIds.add(role.id);
        else selectedAwardRoleIds.delete(role.id);
        syncAwardPickerTriStates();
    });
    row.appendChild(cb);
    
    const name = document.createElement('span');
    name.textContent = role.name;
    row.appendChild(name);
    return row;
}

function buildTypeGroup(type, list) {
    const group = document.createElement('div');
    group.className = 'st-section ap-section ap-type-group';
    group.dataset.type = type.value;

    const header = document.createElement('div');
    header.className = 'st-section-header';

    const headerInfo = document.createElement('div');
    headerInfo.className = 'ap-type-header-info';
    
    let iconClass = 'st-icon--media';
    if (type.value === 'leading') iconClass = 'st-icon--info';
    else if (type.value === 'other') iconClass = 'st-icon--featured';
    
    headerInfo.innerHTML = `
      <div class="st-section-icon ${iconClass}"><i class="fas ${type.icon}"></i></div>
      <div>
        <div class="st-section-title">${type.label} <span class="ap-count">(${list.length})</span></div>
      </div>
    `;
    header.appendChild(headerInfo);

    const groupAll = document.createElement('input');
    groupAll.type = 'checkbox';
    groupAll.className = 'ap-type-group-all ap-select-all-inline';
    groupAll.title = 'Select all ' + type.label;
    groupAll.setAttribute('aria-label', 'Select all ' + type.label);
    groupAll.addEventListener('change', () => {
        list.forEach(r => {
            if (groupAll.checked) selectedAwardRoleIds.add(r.id);
            else selectedAwardRoleIds.delete(r.id);
        });
        group.querySelectorAll('.ap-role-cb').forEach(cb => {
            const id = parseInt(cb.dataset.roleId, 10);
            cb.checked = selectedAwardRoleIds.has(id);
        });
        syncAwardPickerTriStates();
    });
    header.appendChild(groupAll);
    group.appendChild(header);

    const listContainer = document.createElement('div');
    listContainer.className = 'ap-type-group-roles';
    list.forEach(r => listContainer.appendChild(buildRoleRow(r)));
    group.appendChild(listContainer);

    return group;
}

function syncAwardPickerTriStates() {
    const modal = document.getElementById('award-edit-modal');
    if (!modal) return;

    // Per-type section "select all"
    modal.querySelectorAll('.ap-type-group').forEach(group => {
        const groupAll = group.querySelector('.ap-type-group-all');
        if (!groupAll) return;
        const ids = Array.from(group.querySelectorAll('.ap-role-cb'))
            .map(cb => parseInt(cb.dataset.roleId, 10));
        const selectedCount = ids.filter(id => selectedAwardRoleIds.has(id)).length;
        if (ids.length === 0 || selectedCount === 0) {
            groupAll.checked = false; groupAll.indeterminate = false;
        } else if (selectedCount === ids.length) {
            groupAll.checked = true;  groupAll.indeterminate = false;
        } else {
            groupAll.checked = false; groupAll.indeterminate = true;
        }
    });

    // Top-level "select all roles"
    const topAllCb = modal.querySelector('.ap-top-all');
    if (topAllCb) {
        const allIds = (window.ROLES_DATA || []).map(r => r.id);
        const allSelected = allIds.length > 0 && allIds.every(id => selectedAwardRoleIds.has(id));
        const someSelected = allIds.some(id => selectedAwardRoleIds.has(id));
        topAllCb.checked = allSelected;
        topAllCb.indeterminate = !allSelected && someSelected;
    }
}

function populateRoleCheckboxes(selectedRoleIdsList = []) {
    const container = document.getElementById('award-roles-container');
    if (!container) return;
    container.innerHTML = '';

    selectedAwardRoleIds = new Set(selectedRoleIdsList);

    if (window.ROLES_DATA && window.ROLES_DATA.length > 0) {
        // Top-level "Select all roles" bar
        const topBar = document.createElement('label');
        topBar.className = 'ap-top-bar';
        topBar.style.marginTop = '10px';
        const topAllCb = document.createElement('input');
        topAllCb.type = 'checkbox';
        topAllCb.className = 'ap-top-all ap-select-all-inline';
        topAllCb.title = 'Select all roles';
        topAllCb.setAttribute('aria-label', 'Select all roles');
        topAllCb.addEventListener('change', () => {
            const allIds = (window.ROLES_DATA || []).map(r => r.id);
            allIds.forEach(id => {
                if (topAllCb.checked) selectedAwardRoleIds.add(id);
                else selectedAwardRoleIds.delete(id);
            });
            container.querySelectorAll('.ap-role-cb').forEach(cb => {
                const id = parseInt(cb.dataset.roleId, 10);
                cb.checked = selectedAwardRoleIds.has(id);
            });
            syncAwardPickerTriStates();
        });
        topBar.appendChild(topAllCb);
        const topLabel = document.createElement('span');
        topLabel.className = 'ap-top-label';
        topLabel.textContent = 'SELECT ALL ROLES';
        topBar.appendChild(topLabel);
        container.appendChild(topBar);

        // One section per role type, stacked vertically
        AP_ROLE_TYPES.forEach(t => {
            const list = rolesOfType(t.value);
            if (list.length === 0) return;
            container.appendChild(buildTypeGroup(t, list));
        });

        syncAwardPickerTriStates();
    } else {
        container.innerHTML = `<div style="color: #94a3b8; font-style: italic;">No roles available</div>`;
    }
}

function openAwardModal(awardId = null) {
    const modal = document.getElementById('award-edit-modal');
    if (!modal) return;

    const modalTitle = document.getElementById('award-modal-title');
    const idInput = document.getElementById('edit-award-id');
    const nameInput = document.getElementById('edit-award-name');
    const categoryInput = document.getElementById('edit-award-category');
    const maxWinnersInput = document.getElementById('edit-award-max-winners');
    const maxVotesInput = document.getElementById('edit-award-max-votes');
    
    // Auto-slugify listener for new awards
    const slugifyListener = function() {
        categoryInput.value = nameInput.value
            .toLowerCase()
            .replace(/\s+/g, '-')
            .replace(/[^a-z0-9-]/g, '');
    };

    if (awardId) {
        // Edit Mode
        modalTitle.textContent = 'Edit Club Award';
        idInput.value = awardId;
        
        // Find award row in the table
        const row = document.querySelector(`tr[data-award-id="${awardId}"]`);
        if (row) {
            nameInput.value = row.querySelector('.award-name').textContent.trim();
            categoryInput.value = row.querySelector('.award-category').textContent.trim();
            maxWinnersInput.value = row.querySelector('.award-max-winners').textContent.trim();
            maxVotesInput.value = row.querySelector('.award-max-votes').textContent.trim();
            
            // Disable category editing in edit mode to preserve references
            categoryInput.readOnly = true;
            categoryInput.style.backgroundColor = '#e2e8f0';
            
            // Unbind slugify listener
            nameInput.removeEventListener('input', slugifyListener);

            // Fetch and check roles
            let selectedRoleIdsList = [];
            try {
                const rolesTd = row.querySelector('.award-roles');
                selectedRoleIdsList = JSON.parse(rolesTd.dataset.roleIds || '[]');
            } catch(e) {
                console.error('Failed to parse role ids', e);
            }
            populateRoleCheckboxes(selectedRoleIdsList);
        }
    } else {
        // Create Mode
        modalTitle.textContent = 'Add Club Award';
        idInput.value = '';
        nameInput.value = '';
        categoryInput.value = '';
        maxWinnersInput.value = '1';
        maxVotesInput.value = '1';

        categoryInput.readOnly = false;
        categoryInput.style.backgroundColor = '';

        // Bind auto-slugify
        nameInput.addEventListener('input', slugifyListener);

        populateRoleCheckboxes([]);
    }

    modal.style.display = 'flex';
}

function closeAwardModal() {
    const modal = document.getElementById('award-edit-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function handleAwardFormSubmit(e) {
    e.preventDefault();

    const id = document.getElementById('edit-award-id').value;
    const name = document.getElementById('edit-award-name').value.trim();
    const category = document.getElementById('edit-award-category').value.trim();
    const maxWinners = document.getElementById('edit-award-max-winners').value;
    const maxVotes = document.getElementById('edit-award-max-votes').value;

    const selectedRoleIdsArray = Array.from(selectedAwardRoleIds);

    const isEdit = !!id;
    const url = isEdit ? '/api/settings/awards/update' : '/api/settings/awards/add';
    const payload = {
        name: name,
        max_winners: maxWinners,
        max_votes: maxVotes,
        selected_role_ids: selectedRoleIdsArray
    };

    if (isEdit) {
        payload.id = parseInt(id);
    } else {
        payload.category = category;
    }

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        } else {
            alert('Error: ' + data.message);
        }
    })
    .catch(err => {
        console.error('Request failed', err);
        alert('An unexpected error occurred.');
    });
}

function deleteAward(awardId) {
    if (!confirm('Are you sure you want to delete this award? Meetings using this award will still preserve their legacy category references, but the award definition will be deleted.')) {
        return;
    }

    fetch(`/api/settings/awards/delete/${awardId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        } else {
            alert('Error: ' + data.message);
        }
    })
    .catch(err => {
        console.error('Request failed', err);
        alert('An unexpected error occurred.');
    });
}

function saveDefaultAwards() {
    const defaultAwardIds = [];
    document.querySelectorAll('.default-award-checkbox:checked').forEach(cb => {
        defaultAwardIds.push(parseInt(cb.value));
    });

    fetch('/api/settings/awards/default/save', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            default_award_ids: defaultAwardIds
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        } else {
            alert('Error: ' + data.message);
        }
    })
    .catch(err => {
        console.error('Request failed', err);
        alert('An unexpected error occurred.');
    });
}
