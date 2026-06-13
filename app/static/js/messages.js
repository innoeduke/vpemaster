let currentTab = 'inbox';
let currentMessages = [];
let currentMessageId = null;
let currentPage = 1;
let currentPerPage = 10;

document.addEventListener('DOMContentLoaded', () => {
    currentPerPage = getAdaptivePerPage();
    loadMessages(currentTab, false, 1);
    setInterval(() => loadMessages(currentTab, true, currentPage), 60000);

    // Server-Sent Events to refresh message list in real-time
    if (typeof messageEventSource !== 'undefined') {
        messageEventSource.addEventListener('message', (event) => {
            if (event.data === 'new_message') {
                loadMessages(currentTab, true, currentPage);
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
    currentPage = 1;
    document.querySelectorAll('.msg-nav-item').forEach(t => t.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');
    document.getElementById('current-view-title').textContent = tab.charAt(0).toUpperCase() + tab.slice(1);
    
    // Toggle Empty Trash button visibility
    const emptyTrashBtn = document.getElementById('empty-trash-btn');
    if (emptyTrashBtn) {
        emptyTrashBtn.style.display = tab === 'trash' ? 'inline-flex' : 'none';
    }

    loadMessages(tab, false, 1);
}

function loadMessages(tab, silent=false, page=1) {
    currentPage = page;
    const list = document.getElementById('messages-list');
    if (!silent) {
        list.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Loading messages...</p>
            </div>
        `;
    }

    const perPage = getAdaptivePerPage();
    currentPerPage = perPage;

    fetch(`/api/messages/${tab}?page=${page}&per_page=${perPage}`)
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
                renderPagination(0, 0, 1);
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
                const isMember = msg.is_member !== false;
                const memberClass = isMember ? '' : 'non-member';
                return `
                <div class="msg-item ${!msg.read && isReceived ? 'unread' : ''}" onclick="showDetail(${msg.id})">
                    <div class="msg-avatar-wrap">
                        ${avatarSrc
                            ? `<img src="${avatarSrc}" class="msg-avatar" alt="" onerror="this.outerHTML='<div class=\\'msg-avatar-placeholder ${memberClass}\\'">${getInitials(party).replace(/'/g, "\\'")}</div>'">`
                            : `<div class="msg-avatar-placeholder ${memberClass}">${getInitials(party)}</div>`
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
                    ${tab === 'trash'
                        ? `<button class="msg-row-restore-btn" onclick="event.stopPropagation(); restoreMessage(${msg.id})" title="Restore Message">
                               <i class="fas fa-trash-restore"></i>
                           </button>`
                        : ''
                    }
                    <button class="msg-row-delete-btn" onclick="event.stopPropagation(); deleteMessageFromRow(${msg.id})" title="Delete Message">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
            `;}).join('');

            renderPagination(data.total, data.pages, data.current_page);
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
    const isMember = msg.is_member !== false;
    const memberClass = isMember ? '' : 'non-member';

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
        ? `<img src="${detailAvatarSrc}" class="msg-avatar" alt="" onerror="this.outerHTML='<div class=\\'msg-avatar-placeholder ${memberClass}\\'">${getInitials(otherParty).replace(/'/g, "\\'")}</div>'">`
        : `<div class="msg-avatar-placeholder ${memberClass}">${getInitials(otherParty)}</div>`;
    

    // Handle Join Requests
    const requestMatch = msg.body.match(/\[CLUB_ID:(\d+)\]/);
    // Handle Home Club Requests
    const homeRequestMatch = msg.body.match(/\[HOME_CLUB_REQUEST:(\d+):(\d+)\]/);
    // Handle Home Club Proposals (Admin -> User)
    const homeProposalMatch = msg.body.match(/\[HOME_CLUB_PROPOSAL:(\d+):(\d+)\]/);
    // Handle User Join Requests (User requesting Admin)
    const joinRequestMatch = msg.body.match(/\[JOIN_REQUEST:(\d+):(\d+)\]/);
    // Handle User Quit Requests
    const quitRequestMatch = msg.body.match(/\[QUIT_REQUEST:(\d+):(\d+)\]/);
    // Handle Issue links
    const issueLinkMatch = msg.body.match(/\[ISSUE_LINK:(\d+):([^\]]+)\]/);
    // Handle responded state (post-action marker)
    const respondedMatch = msg.body.match(/\[Responded:\s*(JOIN|REJECT|APPROVE|ACCEPT|QUIT)(?::\s*([^\]]+))?\]/i);

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
    if (quitRequestMatch) {
        displayBody = displayBody.replace(quitRequestMatch[0], '');
    }
    if (issueLinkMatch) {
        displayBody = displayBody.replace(issueLinkMatch[0], '');
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
        const statusVerb = (verb === 'JOIN' || verb === 'ACCEPT' || verb === 'APPROVE' || verb === 'QUIT') ? 'Accepted' : 'Declined';
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

    if (quitRequestMatch && isInbox) {
         const actionsHtml = `
            <div class="message-actions join-request-card join-request-card--primary">
                <div class="join-request-header">
                    <span class="join-request-icon"><i class="fas fa-user-minus"></i></span>
                    <h3 class="join-request-title">Club Quit Request</h3>
                </div>
                <div class="join-request-actions">
                    <button onclick="respondToUserQuitRequest(${msg.id}, 'approve')" class="btn btn-join btn-join-reject">
                        <i class="fas fa-check"></i> Approve
                    </button>
                    <button onclick="respondToUserQuitRequest(${msg.id}, 'reject')" class="btn btn-join btn-join-accept">
                        <i class="fas fa-times"></i> Reject
                    </button>
                </div>
            </div>
        `;
        bodyEl.insertAdjacentHTML('beforeend', actionsHtml);
    }

    if (issueLinkMatch) {
         const issueId = issueLinkMatch[1];
         const issueUrl = escapeHtml(issueLinkMatch[2]);
         const actionsHtml = `
            <div class="message-actions join-request-card join-request-card--primary">
                <div class="join-request-header">
                    <span class="join-request-icon"><i class="fas fa-tasks"></i></span>
                    <h3 class="join-request-title">Issue Assignment</h3>
                </div>
                <div class="join-request-actions">
                    <a href="${issueUrl}" class="btn btn-join btn-join-accept" style="text-decoration: none; display: inline-flex; align-items: center; justify-content: center;">
                        <i class="fas fa-external-link-alt" style="margin-right: 5px;"></i> View Issue #${issueId}
                    </a>
                </div>
            </div>
        `;
        bodyEl.insertAdjacentHTML('beforeend', actionsHtml);
    }

    const replyBtn = document.getElementById('detail-reply-btn');
    const restoreBtn = document.getElementById('detail-restore-btn');
    const deleteBtn = document.getElementById('detail-delete-btn');
    
    if (currentTab === 'trash') {
        if (replyBtn) replyBtn.style.display = 'none';
        if (restoreBtn) restoreBtn.style.display = 'inline-flex';
        if (deleteBtn) {
            deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i> Delete Permanently';
        }
    } else {
        if (replyBtn) replyBtn.style.display = 'inline-flex';
        if (restoreBtn) restoreBtn.style.display = 'none';
        if (deleteBtn) {
            deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i> Delete';
        }
    }
    
    modal.classList.add('flex'); // Custom class to show flex
    
    if (isInbox && !msg.read) {
        fetch(`/messages/${id}/read`, { method: 'POST' })
            .then(() => {
                updateUnreadCount(); // Global function
                msg.read = true;
                // Optimistically update list item style
                loadMessages(currentTab, true, currentPage);
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

function restoreMessage(msgId) {
    fetch(`/messages/${msgId}/restore`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast('Message restored successfully', 'success');
                if (currentMessageId === msgId) {
                    closeMessageDetailModal();
                }
                loadMessages(currentTab, false, currentPage);
            } else {
                showToast(data.error || 'Error restoring message', 'error');
            }
        })
        .catch(err => {
            showToast('Error restoring message', 'error');
        });
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
                loadMessages(currentTab, false, currentPage);
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
                loadMessages(currentTab, false, 1);
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
    if (!name || name === 'N/A') return '??';
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) {
        return parts[0].substring(0, 2).toUpperCase();
    }
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
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
            loadMessages(currentTab, false, currentPage);
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
            loadMessages(currentTab, false, currentPage);
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
            loadMessages(currentTab, false, currentPage);
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
            loadMessages(currentTab, false, currentPage);
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

function respondToUserQuitRequest(messageId, action) {
    const btn = event.target.closest('button');
    const container = btn.closest('.message-actions');
    if (container) {
        container.querySelectorAll('button').forEach(b => b.disabled = true);
    } else {
         btn.disabled = true;
    }
    
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    fetch('/clubs/respond_quit_request', {
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
            loadMessages(currentTab, false, currentPage);
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
    toast.innerHTML = `<i class="fas fa-${type === 'success' ? 'check-circle' : (type === 'error' ? 'exclamation-circle' : 'info-circle')}"></i> <span>${message}</span>`;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
        toast.addEventListener('transitionend', () => toast.remove());
    }, 3000);
}

function renderPagination(total, pages, currentPage) {
    const container = document.getElementById('messages-pagination');
    if (!container) return;

    const displayPages = Math.max(1, pages);
    const displayCurrentPage = currentPage || 1;

    container.style.display = 'flex';
    
    let html = '';
    
    // Previous button
    html += `
        <button class="msg-pagination-btn" ${displayCurrentPage === 1 ? 'disabled' : ''} onclick="loadMessages(currentTab, false, ${displayCurrentPage - 1})" title="Previous Page">
            <i class="fas fa-chevron-left"></i> Prev
        </button>
    `;
    
    const maxVisible = 5;
    let startPage = Math.max(1, displayCurrentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(displayPages, startPage + maxVisible - 1);
    
    if (endPage - startPage + 1 < maxVisible) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }
    
    if (startPage > 1) {
        html += `<button class="msg-pagination-btn" onclick="loadMessages(currentTab, false, 1)">1</button>`;
        if (startPage > 2) {
            html += `<span class="msg-pagination-info">...</span>`;
        }
    }
    
    for (let p = startPage; p <= endPage; p++) {
        html += `
            <button class="msg-pagination-btn ${p === displayCurrentPage ? 'active' : ''}" onclick="loadMessages(currentTab, false, ${p})">
                ${p}
            </button>
        `;
    }
    
    if (endPage < displayPages) {
        if (endPage < displayPages - 1) {
            html += `<span class="msg-pagination-info">...</span>`;
        }
        html += `<button class="msg-pagination-btn" onclick="loadMessages(currentTab, false, ${displayPages})">${displayPages}</button>`;
    }
    
    // Next button
    html += `
        <button class="msg-pagination-btn" ${displayCurrentPage === displayPages ? 'disabled' : ''} onclick="loadMessages(currentTab, false, ${displayCurrentPage + 1})" title="Next Page">
            Next <i class="fas fa-chevron-right"></i>
        </button>
    `;
    
    container.innerHTML = html;
}

function getAdaptivePerPage() {
    const list = document.getElementById('messages-list');
    if (!list) return 10;

    const isMobile = window.innerWidth <= 768;
    if (isMobile) {
        return 10;
    }

    const containerHeight = list.clientHeight;
    // Estimate average item height (108px height + 8px margin = 116px)
    const itemHeight = 116;
    const perPage = Math.max(1, Math.floor(containerHeight / itemHeight));
    return perPage;
}

let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        const newPerPage = getAdaptivePerPage();
        if (newPerPage !== currentPerPage && window.innerWidth > 768) {
            currentPerPage = newPerPage;
            loadMessages(currentTab, false, 1);
        }
    }, 250);
});

