let currentUsageId = null;
let currentUsageType = null;

function closeUsageWarningModal() {
    const modal = document.getElementById('usageWarningModal');
    if (modal) modal.style.display = 'none';
    currentUsageId = null;
    currentUsageType = null;
}

function showUsageWarningModal(message, logs, id, type) {
    const modal = document.getElementById('usageWarningModal');
    const msgEl = document.getElementById('usageWarningMessage');
    const tbody = document.getElementById('usageWarningBody');
    const footerLabel = document.querySelector('.usage-footer');

    if (!modal || !msgEl || !tbody) return;

    currentUsageId = id;
    currentUsageType = type || 'session';
    msgEl.textContent = message;
    tbody.innerHTML = '';

    if (footerLabel) {
        footerLabel.textContent = currentUsageType === 'session'
            ? "Please reassign or delete these logs before deleting the session type."
            : "Please reassign or unassign these roles before deleting the role.";
    }

    logs.forEach(log => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><a href="/agenda?meeting_number=${log.meeting_number}" class="usage-meeting-link" target="_blank">#${log.meeting_number}</a></td>
            <td>${log.session_title}</td>
            <td><span class="usage-owner">${log.owner_name || 'Unassigned'}</span></td>
        `;
        tbody.appendChild(tr);
    });

    modal.style.display = 'flex';
}

function deleteAllBlockingLogs() {
    if (!currentUsageId) {
        alert('ID not found.');
        return;
    }

    const endpoint = currentUsageType === 'session'
        ? `/settings/sessions/delete-logs/${currentUsageId}`
        : `/settings/roles/delete-logs/${currentUsageId}`;

    fetch(endpoint, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            closeUsageWarningModal();
            location.reload();
        } else {
            alert(data.message || 'An error occurred while clearing the usage.');
        }
    })
    .catch(error => {
        console.error('Usage clearing error:', error);
        alert('An error occurred while clearing the usage.');
    });
}