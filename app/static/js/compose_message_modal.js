
    let searchTimeout = null;
    const selectedRecipients = []; // {id, name, home_club}

    function openComposeModal(recipientId = null, recipientName = null, subject = null, mode = null) {
        const modal = document.getElementById('composeModal');
        const modalTitle = modal.querySelector('.compose-title');

        // Reset selection
        selectedRecipients.length = 0;
        renderRecipientChips();
        hideRecipientError();

        if (recipientId && recipientName) {
            selectedRecipients.push({ id: recipientId, name: recipientName, home_club: '' });
            renderRecipientChips();
            modalTitle.textContent = (mode === 'new') ? 'New Message' : 'Reply';
        } else {
            modalTitle.textContent = 'New Message';
        }

        if (subject) {
            document.getElementById('subject').value = subject;
        }

        modal.classList.add('flex');

        if (selectedRecipients.length === 0) {
            document.getElementById('recipient_search').focus();
        } else if (!subject) {
            document.getElementById('subject').focus();
        } else {
            document.getElementById('body').focus();
        }

        const content = modal.querySelector('.compose-modal-content');
        content.style.animation = 'none';
        content.offsetHeight;
        content.style.animation = '';
    }

    function closeComposeModal() {
        const modal = document.getElementById('composeModal');
        modal.classList.remove('flex');
        setTimeout(() => {
            document.getElementById('composeForm').reset();
            selectedRecipients.length = 0;
            renderRecipientChips();
            hideRecipientError();
            document.getElementById('recipient_results').style.display = 'none';
            document.getElementById('char_count').textContent = '0';
            modal.querySelector('.compose-title').textContent = 'New Message';
        }, 300);
    }

    function renderRecipientChips() {
        const field = document.getElementById('recipient_field');
        const search = document.getElementById('recipient_search');
        // Remove existing chips
        field.querySelectorAll('.recipient-chip').forEach(c => c.remove());
        // Insert chips before the search input
        selectedRecipients.forEach((r, idx) => {
            const chip = document.createElement('span');
            chip.className = 'recipient-chip';
            const initials = (r.name || '?').trim().substring(0, 2).toUpperCase();
            chip.innerHTML = `
                <span class="chip-avatar">${escapeAttr(initials)}</span>
                <span>${escapeAttr(r.name)}</span>
                <button type="button" class="chip-remove" aria-label="Remove ${escapeAttr(r.name)}" data-idx="${idx}">
                    <i class="fas fa-times"></i>
                </button>
            `;
            field.insertBefore(chip, search);
        });
        // Toggle placeholder visibility
        search.placeholder = selectedRecipients.length === 0
            ? 'Search for a recipient…'
            : (selectedRecipients.length === 1 ? 'Add another recipient…' : 'Add more…');
        if (selectedRecipients.length > 0) hideRecipientError();
    }

    function showRecipientError() {
        const err = document.getElementById('recipient_error');
        const field = document.getElementById('recipient_field');
        if (err) err.hidden = false;
        if (field) field.classList.add('has-error');
    }

    function hideRecipientError() {
        const err = document.getElementById('recipient_error');
        const field = document.getElementById('recipient_field');
        if (err) err.hidden = true;
        if (field) field.classList.remove('has-error');
    }

    function removeRecipient(idx) {
        selectedRecipients.splice(idx, 1);
        renderRecipientChips();
        document.getElementById('recipient_search').focus();
    }

    function escapeAttr(s) {
        return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }

    const searchInput = document.getElementById('recipient_search');
    const resultsDiv = document.getElementById('recipient_results');
    const recipientField = document.getElementById('recipient_field');

    // Click on the field focuses the input
    recipientField.addEventListener('click', function(e) {
        if (e.target === recipientField || e.target.classList.contains('recipient-chip-input') === false) {
            // Only focus if click is not on the remove button
            if (!e.target.closest('.chip-remove')) {
                searchInput.focus();
            }
        }
    });

    searchInput.addEventListener('focus', function() {
        recipientField.classList.add('is-focused');
    });

    searchInput.addEventListener('blur', function() {
        // Delay removing focus style to allow clicks on results to register
        setTimeout(() => {
            if (document.activeElement !== searchInput) {
                recipientField.classList.remove('is-focused');
            }
        }, 150);
    });

    searchInput.addEventListener('input', function() {
        const query = this.value.trim();

        // Clear previous timeout
        if (searchTimeout) clearTimeout(searchTimeout);

        if (query.length < 1) {
            resultsDiv.style.display = 'none';
            return;
        }

        searchTimeout = setTimeout(() => {
            fetch(`/api/messages/recipients?q=${encodeURIComponent(query)}`)
                .then(res => res.json())
                .then(users => {
                    if (!Array.isArray(users) || users.length === 0) {
                        resultsDiv.innerHTML = '<div class="recipient-empty">No recipients found</div>';
                    } else {
                        resultsDiv.innerHTML = users
                            .filter(u => !selectedRecipients.some(r => r.id === u.id))
                            .map(u => {
                                const initials = (u.name || '?').trim().substring(0, 2).toUpperCase();
                                return `
                                    <div class="recipient-option" data-id="${u.id}" data-name="${escapeAttr(u.name)}" data-club="${escapeAttr(u.home_club || '')}">
                                        <span class="option-avatar">${escapeAttr(initials)}</span>
                                        <div>
                                            <div class="option-main">${escapeAttr(u.name)}</div>
                                            <div class="option-sub">${escapeAttr(u.home_club || 'No Club')}</div>
                                        </div>
                                    </div>
                                `;
                            }).join('');
                    }
                    resultsDiv.style.display = 'block';
                })
                .catch(err => console.error('Error fetching recipients:', err));
        }, 300);
    });

    // Delegate clicks on result options
    resultsDiv.addEventListener('click', function(e) {
        const opt = e.target.closest('.recipient-option');
        if (!opt) return;
        const id = opt.getAttribute('data-id');
        const name = opt.getAttribute('data-name');
        const home_club = opt.getAttribute('data-club');
        if (id && name) addRecipient({ id: parseInt(id, 10), name, home_club });
    });

    // Delegate clicks on chip remove buttons
    recipientField.addEventListener('click', function(e) {
        const btn = e.target.closest('.chip-remove');
        if (!btn) return;
        e.preventDefault();
        const idx = parseInt(btn.getAttribute('data-idx'), 10);
        if (!isNaN(idx)) removeRecipient(idx);
    });

    function addRecipient(user) {
        if (selectedRecipients.some(r => r.id === user.id)) return;
        selectedRecipients.push(user);
        searchInput.value = '';
        resultsDiv.style.display = 'none';
        renderRecipientChips();
        searchInput.focus();
    }

    // Keyboard support: Enter to add first result
    searchInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && resultsDiv.style.display === 'block') {
            e.preventDefault();
            const first = resultsDiv.querySelector('.recipient-option');
            if (first) first.click();
        } else if (e.key === 'Backspace' && searchInput.value === '' && selectedRecipients.length > 0) {
            // Remove last chip on backspace when input is empty
            e.preventDefault();
            removeRecipient(selectedRecipients.length - 1);
        }
    });

    document.addEventListener('click', function(e) {
        if (!recipientField.contains(e.target) && !resultsDiv.contains(e.target)) {
            resultsDiv.style.display = 'none';
        }
    });

    document.getElementById('body').addEventListener('input', function() {
        document.getElementById('char_count').textContent = this.value.length.toLocaleString();
    });

    function sendMessage(e) {
        e.preventDefault();
        if (selectedRecipients.length === 0) {
            showRecipientError();
            searchInput.focus();
            return;
        }
        hideRecipientError();
        const btn = e.target.querySelector('button[type="submit"]');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span>Sending…</span><span class="send-arrow"><i class="fas fa-spinner fa-spin"></i></span>';

        const data = {
            recipient_ids: selectedRecipients.map(r => r.id),
            subject: document.getElementById('subject').value,
            body: document.getElementById('body').value
        };

        fetch('/messages/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(res => res.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = originalText;
            if (data.success) {
                closeComposeModal();
                if (typeof switchTab === 'function') switchTab('sent');
            } else {
                alert('Error: ' + data.error);
            }
        })
        .catch(err => {
            btn.disabled = false;
            btn.innerHTML = originalText;
            alert('Failed to send message');
        });
    }

    window.addEventListener('click', function(event) {
        const modal = document.getElementById('composeModal');
        if (event.target == modal) closeComposeModal();
    });
