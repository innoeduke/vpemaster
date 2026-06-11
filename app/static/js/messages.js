let currentTab = 'inbox';
let currentMessages = [];
let currentMessageId = null;

document.addEventListener('DOMContentLoaded', () => {
    loadMessages(currentTab);
    setInterval(() => loadMessages(currentTab, true), 60000);

    // Server-Sent Events to refresh message list in real-time
    if (typeof messageEventSource !== 'undefined') {
        messageEventSource.addEventListener('message', (event) => {
            if (event.data === 'new_message') {
                loadMessages(currentTab, true);
            }
        });
    }

    // Check for recipient in URL
    const urlParams = new URLSearchParams(window.location.search);
    const recipientId = urlParams.get('recipient_id');
    const recipientName = urlParams.get('recipient_name');
    const subject = urlParams.get('subject');
    const mode = urlParams.get('mode');
    if (recipientId && recipientName) {
        openComposeModal(recipientId, recipientName, subject, mode);
    }
});

function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.msg-nav-item').forEach(t => t.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');
    document.getElementById('current-view-title').textContent = tab.charAt(0).toUpperCase() + tab.slice(1);
    
    // Toggle Empty Trash button visibility
    const emptyTrashBtn = document.getElementById('empty-trash-btn');
    if (emptyTrashBtn) {
        emptyTrashBtn.style.display = tab === 'trash' ? 'inline-flex' : 'none';
    }

    loadMessages(tab);
}

function loadMessages(tab, silent=false) {
    const list = document.getElementById('messages-list');
    if (!silent) {
        list.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Loading messages...</p>
            </div>
        `;
    }

    fetch(`/api/messages/${tab}`)
        .then(response => response.json())
        .then(data => {
            currentMessages = data.messages;
            if (data.messages.length === 0) {
                list.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-${tab === 'inbox' ? 'inbox' : (tab === 'sent' ? 'paper-plane' : 'trash-alt')}"></i>
                        <p>No messages in ${tab}</p>
                    </div>
                `;
                return;
            }

            list.innerHTML = data.messages.map(msg => {
                let avatarSrc = msg.avatar_url;
                if (avatarSrc && avatarSrc.indexOf('/') === -1) {
                    const root = (typeof avatarRootDir !== 'undefined') ? avatarRootDir : 'avatars';
                    avatarSrc = `/static/${root}/${avatarSrc}`;
                }
                const isReceived = tab === 'inbox' || (tab === 'trash' && msg.type === 'inbox');
                const party = isReceived ? msg.sender : msg.recipient;
                return `
                <div class="msg-item ${!msg.read && isReceived ? 'unread' : ''}" onclick="showDetail(${msg.id})">
                    <div class="msg-avatar-wrap">
                        ${avatarSrc
                            ? `<img src="${avatarSrc}" class="msg-avatar" alt="" onerror="this.outerHTML='<div class=\\'msg-avatar-placeholder\\'>${getInitials(party).replace(/'/g, "\\'")}</div>'">`
                            : `<div class="msg-avatar-placeholder">${getInitials(party)}</div>`
                        }
                    </div>
                    <div class="msg-content">
                        <div class="msg-row-top">
                            <span class="msg-sender">${isReceived ? msg.sender : 'To: ' + msg.recipient}</span>
                            <span class="msg-time">${msg.timestamp.split(' ')[0]}</span>
                        </div>
                        <div class="msg-subject">${formatSubjectWithBadge(msg.subject)}</div>
                        <div class="msg-preview">${escapeHtml(msg.body)}</div>
                    </div>
                    <button class="msg-row-delete-btn" onclick="event.stopPropagation(); deleteMessageFromRow(${msg.id})" title="Delete Message">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
            `;}).join('');
        })
        .catch(error => {
            console.error('Error loading messages:', error);
            if (!silent) {
                list.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-exclamation-circle" style="color:#e53e3e;"></i>
                        <p>Error loading messages</p>
                    </div>
                `;
            }
        });
}

function showDetail(id) {
    const msg = currentMessages.find(m => m.id === id);
    if (!msg) return;

    currentMessageId = id;
    const modal = document.getElementById('messageDetailModal');
    const isReceived = currentTab === 'inbox' || (currentTab === 'trash' && msg.type === 'inbox');
    const otherParty = isReceived ? msg.sender : msg.recipient;

    document.getElementById('detail-subject').innerHTML = formatSubjectWithBadge(msg.subject);
    document.getElementById('detail-sender').textContent = (isReceived ? 'From ' : 'To ') + otherParty;
    document.getElementById('detail-time').textContent = msg.timestamp;
    const avatarContainer = document.getElementById('detail-avatar');
    let detailAvatarSrc = msg.avatar_url;
    if (detailAvatarSrc && detailAvatarSrc.indexOf('/') === -1) {
        const root = (typeof avatarRootDir !== 'undefined') ? avatarRootDir : 'avatars';
        detailAvatarSrc = `/static/${root}/${detailAvatarSrc}`;
    }
    avatarContainer.innerHTML = detailAvatarSrc
        ? `<img src="${detailAvatarSrc}" class="msg-avatar" alt="" onerror="this.outerHTML='<div class=\\'msg-avatar-placeholder\\'>${getInitials(otherParty).replace(/'/g, "\\'")}</div>'">`
        : `<div class="msg-avatar-placeholder">${getInitials(otherParty)}</div>`;
    

    // Handle Join Requests
    const requestMatch = msg.body.match(/\[CLUB_ID:(\d+)\]/);
    // Handle Home Club Requests
    const homeRequestMatch = msg.body.match(/\[HOME_CLUB_REQUEST:(\d+):(\d+)\]/);
    // Handle Home Club Proposals (Admin -> User)
    const homeProposalMatch = msg.body.match(/\[HOME_CLUB_PROPOSAL:(\d+):(\d+)\]/);
    // Handle User Join Requests (User requesting Admin)
    const joinRequestMatch = msg.body.match(/\[JOIN_REQUEST:(\d+):(\d+)\]/);
    // Handle responded state (post-action marker)
    const respondedMatch = msg.body.match(/\[Responded:\s*(JOIN|REJECT|APPROVE|ACCEPT)(?::\s*([^\]]+))?\]/i);

    let displayBody = msg.body;
    if (requestMatch) {
        displayBody = displayBody.replace(requestMatch[0], '');
    }
    if (homeRequestMatch) {
        displayBody = displayBody.replace(homeRequestMatch[0], '');
    }
    if (homeProposalMatch) {
        displayBody = displayBody.replace(homeProposalMatch[0], '');
    }
    if (joinRequestMatch) {
        displayBody = displayBody.replace(joinRequestMatch[0], '');
    }
    if (respondedMatch) {
        displayBody = displayBody.replace(respondedMatch[0], '');
    }

    const bodyEl = document.getElementById('detail-body');
    
    // Escape HTML to prevent XSS
    const escapeHtml = (text) => {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    };
    
    // 1. Escape content
    let safeBody = escapeHtml(displayBody);

    // 2. Wrap each paragraph in <p> for proper spacing
    safeBody = safeBody
        .split(/\n\s*\n/)
        .map(p => p.trim())
        .filter(p => p.length > 0)
        .map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`)
        .join('');

    // 3. Convert **bold** to <strong>bold</strong>
    safeBody = safeBody.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');

    bodyEl.innerHTML = safeBody;

    // Ensure body text is left-aligned (user request), overriding any centering
    bodyEl.style.textAlign = 'left';

    // Suppress the "Please respond using the buttons below" boilerplate
    // when the request has already been responded to (no buttons will follow).
    if (respondedMatch) {
        const paras = bodyEl.querySelectorAll('p');
        paras.forEach(p => {
            if (/please respond using the buttons below/i.test(p.textContent)) {
                p.remove();
            }
        });
    }

    // Render "responded" status card when the request has already been handled
    if (respondedMatch) {
        const verb = respondedMatch[1].toUpperCase();
        const note = respondedMatch[2] ? respondedMatch[2].trim() : '';
        const statusVerb = (verb === 'JOIN' || verb === 'ACCEPT' || verb === 'APPROVE') ? 'Accepted' : 'Declined';
        const statusClass = statusVerb === 'Accepted' ? 'message-status-card accepted' : 'message-status-card declined';
        const statusIcon = statusVerb === 'Accepted' ? 'fa-check-circle' : 'fa-times-circle';
        const noteHtml = note ? `<span class="status-note">${escapeHtml(note)}</span>` : '';
        const statusHtml = `
            <div class="${statusClass}">
                <i class="fas ${statusIcon} status-icon"></i>
                <span class="status-title">You ${statusVerb} this request</span>
                ${noteHtml}
            </div>
        `;
        bodyEl.insertAdjacentHTML('beforeend', statusHtml);
    }

    const isInbox = currentTab === 'inbox';

    if (requestMatch && isInbox) {
         const actionsHtml = `
            <div class="message-actions join-request-card join-request-card--primary">
                <div class="join-request-header">
                    <span class="join-request-icon"><i class="fas fa-user-plus"></i></span>
                    <h3 class="join-request-title">Club Join Request</h3>
                </div>
                <div class="join-request-actions">
                    <button onclick="respondToJoinRequest(${msg.id}, 'join')" class="btn btn-join btn-join-accept">
                        <i class="fas fa-check"></i> Accept
                    </button>
                    <button onclick="respondToJoinRequest(${msg.id}, 'reject')" class="btn btn-join btn-join-reject">
                        <i class="fas fa-times"></i> Reject
                    </button>
                </div>
            </div>
        `;
        bodyEl.insertAdjacentHTML('beforeend', actionsHtml);
    }
    
    if (homeRequestMatch && isInbox) {
         const actionsHtml = `
            <div class="message-actions join-request-card join-request-card--info">
                <div class="join-request-header">
                    <span class="join-request-icon"><i class="fas fa-house-chimney"></i></span>
                    <h3 class="join-request-title">Home Club Request</h3>
                </div>
                <div class="join-request-actions">
                    <button onclick="respondToHomeRequest(${msg.id}, 'approve')" class="btn btn-join btn-join-accept">
                        <i class="fas fa-check"></i> Approve
                    </button>
                    <button onclick="respondToHomeRequest(${msg.id}, 'reject')" class="btn btn-join btn-join-reject">
                        <i class="fas fa-times"></i> Reject
                    </button>
                </div>
            </div>
        `;
        bodyEl.insertAdjacentHTML('beforeend', actionsHtml);
    }

    if (homeProposalMatch && isInbox) {
         const actionsHtml = `
            <div class="message-actions join-request-card join-request-card--warning">
                <div class="join-request-header">
                    <span class="join-request-icon"><i class="fas fa-arrow-right-arrow-left"></i></span>
                    <h3 class="join-request-title">Home Club Change Proposal</h3>
                </div>
                <div class="join-request-actions">
                    <button onclick="respondToHomeProposal(${msg.id}, 'approve')" class="btn btn-join btn-join-accept">
                        <i class="fas fa-check"></i> Approve
                    </button>
                    <button onclick="respondToHomeProposal(${msg.id}, 'reject')" class="btn btn-join btn-join-reject">
                        <i class="fas fa-times"></i> Reject
                    </button>
                </div>
            </div>
        `;
        bodyEl.insertAdjacentHTML('beforeend', actionsHtml);
    }

    if (joinRequestMatch && isInbox) {
         const actionsHtml = `
            <div class="message-actions join-request-card join-request-card--primary">
                <div class="join-request-header">
                    <span class="join-request-icon"><i class="fas fa-user-plus"></i></span>
                    <h3 class="join-request-title">Club Join Request</h3>
                </div>
                <div class="join-request-actions">
                    <button onclick="respondToUserJoinRequest(${msg.id}, 'approve')" class="btn btn-join btn-join-accept">
                        <i class="fas fa-check"></i> Approve
                    </button>
                    <button onclick="respondToUserJoinRequest(${msg.id}, 'reject')" class="btn btn-join btn-join-reject">
                        <i class="fas fa-times"></i> Reject
                    </button>
                </div>
            </div>
        `;
        bodyEl.insertAdjacentHTML('beforeend', actionsHtml);
    }
    
    modal.classList.add('flex'); // Custom class to show flex
    
    if (isInbox && !msg.read) {
        fetch(`/messages/${id}/read`, { method: 'POST' })
            .then(() => {
                updateUnreadCount(); // Global function
                msg.read = true;
                // Optimistically update list item style
                loadMessages(currentTab, true);
            });
    }
}

function closeMessageDetailModal() {
    document.getElementById('messageDetailModal').classList.remove('flex');
    currentMessageId = null;
}

function replyToMessage() {
    if (!currentMessageId) return;
    const msg = currentMessages.find(m => m.id === currentMessageId);
    if (!msg) return;

    const isReceived = currentTab === 'inbox' || (currentTab === 'trash' && msg.type === 'inbox');
    const recipientId = isReceived ? msg.sender_id : msg.recipient_id;
    const recipientName = isReceived ? msg.sender : msg.recipient;
    
    let subject = msg.subject || '';
    if (subject && !subject.toLowerCase().startsWith('re:')) {
        subject = 'Re: ' + subject;
    } else if (!subject) {
        subject = 'Re: (No Subject)';
    }

    closeMessageDetailModal();
    openComposeModal(recipientId, recipientName, subject);
}

// Prompt for deletion (opens 2nd modal)
function deleteCurrentMessage() {
    if (!currentMessageId) return;

    const confirmTitle = document.querySelector('#deleteConfirmModal .confirm-title');
    const confirmSub = document.querySelector('#deleteConfirmModal .confirm-sub');
    
    if (currentTab === 'trash') {
        if (confirmTitle) confirmTitle.textContent = 'Permanently delete this message?';
        if (confirmSub) confirmSub.textContent = 'This action cannot be undone.';
    } else {
        if (confirmTitle) confirmTitle.textContent = 'Delete this message?';
        if (confirmSub) confirmSub.textContent = 'This will move it to the Trash folder.';
    }

    document.getElementById('deleteConfirmModal').classList.add('flex');
}

function deleteMessageFromRow(msgId) {
    currentMessageId = msgId;
    deleteCurrentMessage();
}

function closeDeleteConfirmModal() {
    document.getElementById('deleteConfirmModal').classList.remove('flex');
}

// Actual deletion logic
function confirmDeleteMessage() {
    if (!currentMessageId) return;
    
    // Pass context to ensure correct soft/permanent deletion flags are set
    const context = currentTab; 
    const btn = document.querySelector('#deleteConfirmModal .btn-danger');
    const originalText = btn.textContent;
    btn.textContent = 'Deleting...';
    btn.disabled = true;

    fetch(`/messages/${currentMessageId}/delete?context=${context}`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            btn.textContent = originalText;
            btn.disabled = false;
            closeDeleteConfirmModal();
            
            if (data.success) {
                closeMessageDetailModal();
                loadMessages(currentTab);
            } else {
                alert('Error deleting message');
            }
        })
        .catch(err => {
            btn.textContent = originalText;
            btn.disabled = false;
            closeDeleteConfirmModal();
            alert('Error deleting message');
        });
}

function openEmptyTrashModal() {
    document.getElementById('emptyTrashConfirmModal').classList.add('flex');
}

function closeEmptyTrashConfirmModal() {
    document.getElementById('emptyTrashConfirmModal').classList.remove('flex');
}

function confirmEmptyTrash() {
    const btn = document.querySelector('#emptyTrashConfirmModal .btn-danger');
    const originalText = btn.textContent;
    btn.textContent = 'Emptying...';
    btn.disabled = true;

    fetch('/messages/empty-trash', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            btn.textContent = originalText;
            btn.disabled = false;
            closeEmptyTrashConfirmModal();
            
            if (data.success) {
                showToast('Trash emptied successfully', 'success');
                loadMessages(currentTab);
            } else {
                showToast('Error emptying trash', 'error');
            }
        })
        .catch(err => {
            btn.textContent = originalText;
            btn.disabled = false;
            closeEmptyTrashConfirmModal();
            showToast('Error emptying trash', 'error');
        });
}

// Close modal on outside click
window.onclick = function(event) {
    const detailModal = document.getElementById('messageDetailModal');
    const deleteModal = document.getElementById('deleteConfirmModal');
    const emptyTrashModal = document.getElementById('emptyTrashConfirmModal');
    
    if (event.target == deleteModal) {
        closeDeleteConfirmModal();
    } else if (event.target == detailModal) {
        closeMessageDetailModal();
    } else if (event.target == emptyTrashModal) {
        closeEmptyTrashConfirmModal();
    }
}

function formatSubjectWithBadge(subject) {
    if (!subject) return '(No Subject)';
    
    const patterns = [
        {
            prefix: /^Join Request Response:\s*/i,
            badge: '<span class="badge-msg badge-msg-join-response">Join Response</span> '
        },
        {
            prefix: /^Join Request:\s*/i,
            badge: '<span class="badge-msg badge-msg-join-request">Join Request</span> '
        },
        {
            prefix: /^Invitation to join\s*/i,
            badge: '<span class="badge-msg badge-msg-invite">Invitation</span> '
        },
        {
            prefix: /^Response to Home Club Proposal:\s*/i,
            badge: '<span class="badge-msg badge-msg-home-response">Proposal Response</span> '
        },
        {
            prefix: /^Home Club Change Proposal:\s*/i,
            badge: '<span class="badge-msg badge-msg-home-proposal">Home Club Proposal</span> '
        },
        {
            prefix: /^Request to set Home Club:\s*/i,
            badge: '<span class="badge-msg badge-msg-home-request">Home Club Request</span> '
        },
        {
            prefix: /^Home Club Request:\s*/i,
            badge: '<span class="badge-msg badge-msg-home-request">Home Club Request</span> '
        },
        {
            prefix: /^User Changed Home Club:\s*/i,
            badge: '<span class="badge-msg badge-msg-home-change">Home Club Changed</span> '
        }
    ];

    for (const pattern of patterns) {
        if (pattern.prefix.test(subject)) {
            const rest = subject.replace(pattern.prefix, '');
            return pattern.badge + escapeHtml(rest);
        }
    }
    return escapeHtml(subject);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.innerText = text;
    return div.innerHTML;
}

// Helper to extract initials
function getInitials(name) {
    return name ? name.substring(0, 2).toUpperCase() : '??';
}

function respondToJoinRequest(messageId, action) {
    const btn = event.target.closest('button');
    const container = btn.closest('.message-actions');
    if (container) {
        container.querySelectorAll('button').forEach(b => b.disabled = true);
    } else {
         btn.disabled = true;
    }
    
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    fetch('/user/respond_join', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message_id: messageId,
            action: action
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(action === 'join' ? 'You have joined the club!' : 'Request rejected.', 'success');
            closeMessageDetailModal();
            loadMessages(currentTab);
        } else {
            showToast(data.error || 'Action failed', 'error');
            btn.innerHTML = originalText;
            if (container) {
                 container.querySelectorAll('button').forEach(b => b.disabled = false);
            } else {
                 btn.disabled = false;
            }
        }
    })
    .catch(err => {
        showToast('Error processing request', 'error');
        btn.innerHTML = originalText;
        if (container) {
             container.querySelectorAll('button').forEach(b => b.disabled = false);
        } else {
             btn.disabled = false;
        }
    });
}

function respondToHomeRequest(messageId, action) {
    const btn = event.target.closest('button');
    const container = btn.closest('.message-actions');
    if (container) {
        container.querySelectorAll('button').forEach(b => b.disabled = true);
    } else {
         btn.disabled = true;
    }
    
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    fetch('/clubs/respond_home_request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message_id: messageId,
            action: action
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(action === 'approve' ? 'Request Approved.' : 'Request Rejected.', 'success');
            closeMessageDetailModal();
            loadMessages(currentTab);
        } else {
            showToast(data.error || 'Action failed', 'error');
            btn.innerHTML = originalText;
            if (container) {
                 container.querySelectorAll('button').forEach(b => b.disabled = false);
            } else {
                 btn.disabled = false;
            }
        }
    })
    .catch(err => {
        showToast('Error processing request', 'error');
        btn.innerHTML = originalText;
        if (container) {
             container.querySelectorAll('button').forEach(b => b.disabled = false);
        } else {
             btn.disabled = false;
        }
    });
}

function respondToHomeProposal(messageId, action) {
    const btn = event.target.closest('button');
    const container = btn.closest('.message-actions');
    if (container) {
        container.querySelectorAll('button').forEach(b => b.disabled = true);
    } else {
         btn.disabled = true;
    }
    
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    fetch('/clubs/respond_home_proposal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message_id: messageId,
            action: action
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(action === 'approve' ? 'Proposal Accepted.' : 'Proposal Rejected.', 'success');
            closeMessageDetailModal();
            loadMessages(currentTab);
        } else {
            showToast(data.error || 'Action failed', 'error');
            btn.innerHTML = originalText;
            if (container) {
                 container.querySelectorAll('button').forEach(b => b.disabled = false);
            } else {
                 btn.disabled = false;
            }
        }
    })
    .catch(err => {
        showToast('Error processing proposal', 'error');
        btn.innerHTML = originalText;
        if (container) {
             container.querySelectorAll('button').forEach(b => b.disabled = false);
        } else {
             btn.disabled = false;
        }
    });
}

function respondToUserJoinRequest(messageId, action) {
    const btn = event.target.closest('button');
    const container = btn.closest('.message-actions');
    if (container) {
        container.querySelectorAll('button').forEach(b => b.disabled = true);
    } else {
         btn.disabled = true;
    }
    
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    fetch('/clubs/respond_join_request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message_id: messageId,
            action: action
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(action === 'approve' ? 'Request Approved.' : 'Request Rejected.', 'success');
            closeMessageDetailModal();
            loadMessages(currentTab);
        } else {
            showToast(data.error || 'Action failed', 'error');
            btn.innerHTML = originalText;
            if (container) {
                 container.querySelectorAll('button').forEach(b => b.disabled = false);
            } else {
                 btn.disabled = false;
            }
        }
    })
    .catch(err => {
        showToast('Error processing request', 'error');
        btn.innerHTML = originalText;
        if (container) {
             container.querySelectorAll('button').forEach(b => b.disabled = false);
        } else {
             btn.disabled = false;
        }
    });
}

// Simple toast notification helper
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 12px 24px;
        background: ${type === 'success' ? '#48bb78' : (type === 'error' ? '#f56565' : '#4299e1')};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        z-index: 9999;
        font-weight: 500;
        opacity: 0;
        transform: translateY(20px);
        transition: opacity 0.3s, transform 0.3s;
    `;
    toast.innerHTML = `<i class="fas fa-${type === 'success' ? 'check-circle' : (type === 'error' ? 'exclamation-circle' : 'info-circle')}"></i> ${message}`;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';
    }, 10);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
        toast.addEventListener('transitionend', () => toast.remove());
    }, 3000);
}
