/**
 * Logic for the User Form - user search functionality and tooltips.
 */

/**
 * Show tooltip on click for info icons
 */
function initTooltips() {
    // Remove any existing tooltip
    const existingTooltip = document.querySelector('.custom-tooltip');
    if (existingTooltip) {
        existingTooltip.remove();
    }

    const infoIcons = document.querySelectorAll('.info-icon-tooltip');
    
    infoIcons.forEach(icon => {
        icon.addEventListener('click', function(e) {
            e.preventDefault(); // Prevent label from focusing input
            e.stopPropagation();
            
            // Remove any existing tooltip
            const existingTooltip = document.querySelector('.custom-tooltip');
            if (existingTooltip) {
                existingTooltip.remove();
            }
            
            // Create new tooltip
            const tooltip = document.createElement('div');
            tooltip.className = 'custom-tooltip';
            tooltip.textContent = this.getAttribute('data-tooltip');
            
            // Style the tooltip
            tooltip.style.cssText = `
                position: absolute;
                background-color: #333;
                color: white;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 0.85em;
                max-width: 300px;
                z-index: 10000;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                line-height: 1.4;
            `;
            
            // Position tooltip near the icon
            document.body.appendChild(tooltip);
            const iconRect = this.getBoundingClientRect();
            tooltip.style.left = (iconRect.left + window.scrollX) + 'px';
            tooltip.style.top = (iconRect.bottom + window.scrollY + 5) + 'px';
            
            // Adjust if tooltip goes off screen
            const tooltipRect = tooltip.getBoundingClientRect();
            if (tooltipRect.right > window.innerWidth) {
                tooltip.style.left = (window.innerWidth - tooltipRect.width - 10) + 'px';
            }
        });
    });
    
    // Close tooltip when clicking anywhere else
    document.addEventListener('click', function(e) {
        if (!e.target.classList.contains('info-icon-tooltip')) {
            const tooltip = document.querySelector('.custom-tooltip');
            if (tooltip) {
                tooltip.remove();
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', function () {
    // Initialize tooltips
    initTooltips();
    
    // ===== DUPLICATE DETECTION LOGIC =====
    const userForm = document.querySelector('form');
    const duplicateModal = document.getElementById('duplicateModal');
    const duplicateList = document.getElementById('duplicateList');
    const proceedWithNewBtn = document.getElementById('proceedWithNew');
    const cancelSaveBtn = document.getElementById('cancelSave');
    const closeDuplicateModal = document.getElementById('closeDuplicateModal');
    
    let isEditing = window.location.pathname.includes('/user/form/') && !window.location.pathname.endsWith('/form');

    if (userForm && duplicateModal) {
        let lastCheckedValues = {
            username: '',
            first_name: '',
            last_name: '',
            email: '',
            phone: ''
        };
        
        let currentSuggestion = null;

        const checkDuplicates = async () => {
            // Only check duplicates for new users who haven't selected a contact yet
            const contactId = document.querySelector('input[name="contact_id"]')?.value;
            if (isEditing || (contactId && contactId !== '')) return;

            const username = document.getElementById('username')?.value || '';
            const firstName = document.getElementById('first_name')?.value || '';
            const lastName = document.getElementById('last_name')?.value || '';
            const email = document.getElementById('email')?.value || '';
            const phone = document.getElementById('phone')?.value || '';
            const clubId = document.querySelector('input[name="club_id"]')?.value || '';

            // Check if anything has actually changed to avoid redundant popups
            if (username === lastCheckedValues.username && 
                firstName === lastCheckedValues.first_name && 
                lastName === lastCheckedValues.last_name && 
                email === lastCheckedValues.email && 
                phone === lastCheckedValues.phone) {
                return;
            }
            
            // Don't check if all fields are empty
            if (!username && !firstName && !lastName && !email && !phone) return;

            // Construct full name for backend compatibility
            const fullName = `${firstName} ${lastName}`.trim();

            try {
                const response = await fetch('/user/check_duplicates', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: username,
                        first_name: firstName,
                        last_name: lastName,
                        full_name: fullName,
                        email: email,
                        phone: phone,
                        club_id: clubId
                    })
                });

                const data = await response.json();

                if (data.duplicates && data.duplicates.length > 0) {
                    currentSuggestion = data.suggested_username;
                    // Update last checked values to prevent immediate re-popup for same data
                    lastCheckedValues = { username, first_name: firstName, last_name: lastName, email, phone };
                    
                    let hasHardDuplicate = false;
                    const modalTitle = document.querySelector('#duplicateModal h2');
                    
                    // Show duplicates in modal
                    duplicateList.innerHTML = '';
                    data.duplicates.forEach(dup => {
                        const div = document.createElement('div');
                        div.className = 'duplicate-item';
                        
                        const info = document.createElement('div');
                        info.className = 'duplicate-info';
                        const clubsText = dup.clubs && dup.clubs.length > 0 ? dup.clubs.join(', ') : 'No club memberships';
                        
                        let membershipNotice = '';
                        let buttonText = 'Invite User';
                        
                        if (dup.in_current_club) {
                            if (dup.type === 'User' || dup.has_user) {
                                membershipNotice = `<br><span style="color: #dc3545; font-size: 0.85em; font-weight: 500;">Already a member of this club.</span>`;
                                buttonText = 'View Member';
                                hasHardDuplicate = true;
                            } else {
                                membershipNotice = `<br><span style="color: #28a745; font-size: 0.85em; font-weight: 500;">Existing guest in this club.</span>`;
                                buttonText = 'Convert to User';
                            }
                        }

                        // Construct name from parts if available to ensure we show "First Last"
                        let nameDisplay = dup.username;
                        const first = dup.first_name || '';
                        const last = dup.last_name || '';
                        
                        if (first || last) {
                            nameDisplay = `${first} ${last}`.trim();
                        } else if (dup.full_name && dup.full_name.toLowerCase() !== dup.username.toLowerCase()) {
                            nameDisplay = dup.full_name;
                        }

                        const displayName = nameDisplay.toLowerCase() !== dup.username.toLowerCase() 
                            ? `<strong>${nameDisplay}</strong> (${dup.username})`
                            : `<strong>${nameDisplay}</strong>`;

                        info.innerHTML = `
                            ${displayName}<br>
                            <small>${clubsText}</small>
                            ${membershipNotice}
                        `;
                        
                        const actionDiv = document.createElement('div');
                        actionDiv.className = 'duplicate-actions';
                        
                        const pickBtn = document.createElement('button');
                        pickBtn.type = 'button';
                        pickBtn.className = 'btn btn-sm btn-info';
                        pickBtn.textContent = buttonText;
                        pickBtn.style.minWidth = '120px';
                        pickBtn.addEventListener('click', () => {
                            if (dup.type === 'Contact' && !dup.has_user && dup.in_current_club) {
                                // Requirement 4: Convert guest to user WITHOUT reload to preserve data
                                document.querySelector('input[name="contact_id"]').value = dup.id;
                                
                                // Update fields only if contact has data to offer
                                if (dup.first_name) document.getElementById('first_name').value = dup.first_name;
                                if (dup.last_name) document.getElementById('last_name').value = dup.last_name;
                                if (dup.email) document.getElementById('email').value = dup.email;
                                if (dup.phone) document.getElementById('phone').value = dup.phone;
                                
                                duplicateModal.style.display = 'none';
                                
                                // Notify user
                                const msg = document.createElement('div');
                                msg.className = 'flash success';
                                msg.innerHTML = `Linked to existing contact: ${dup.full_name} <span class="close-flash" onclick="this.parentElement.remove();">&times;</span>`;
                                document.querySelector('h1').after(msg);
                            } else {
                                const targetId = dup.type === 'User' ? dup.id : dup.user_id;
                                if (targetId) {
                                    // Logic for adding user from another club
                                    // Logic for adding user from another club
                                    if (!dup.in_current_club) {
                                        // Removed confirm dialog as per user request
                                        fetch('/user/request_join', {
                                            method: 'POST',
                                            headers: { 'Content-Type': 'application/json' },
                                            body: JSON.stringify({
                                                target_user_id: targetId,
                                                club_id: clubId
                                            })
                                        })
                                        .then(res => res.json())
                                        .then(data => {
                                            if (data.success) {
                                                duplicateModal.style.display = 'none';
                                                // Alert user and redirect to close the form
                                                window.location.href = '/settings?default_tab=user-settings';
                                            } else {
                                                alert(data.error || 'Failed to send request.');
                                            }
                                        })
                                        .catch(err => alert('Error sending request.'));
                                        return; // Stop further execution
                                    }

                                    // Preserve club_id and role
                                    const urlParams = new URLSearchParams(window.location.search);
                                    const role = urlParams.get('role');
                                    
                                    let targetUrl = `/user/form/${targetId}`;
                                    const params = [];
                                    
                                    // Utilise clubId from the parent scope (checkDuplicates)
                                    if (clubId) params.push(`club_id=${clubId}`);
                                    if (role) params.push(`role=${role}`);
                                    
                                    if (params.length > 0) {
                                        targetUrl += `?${params.join('&')}`;
                                    }
                                    
                                    window.location.href = targetUrl;
                                } else {
                                    duplicateModal.style.display = 'none';
                                }
                            }
                        });
                        
                        actionDiv.appendChild(pickBtn);
                        div.appendChild(info);
                        div.appendChild(actionDiv);
                        duplicateList.appendChild(div);
                    });
                    
                    // Update modal UI based on whether we have a hard duplicate
                    if (hasHardDuplicate) {
                        modalTitle.textContent = 'User Already Exists';
                        proceedWithNewBtn.style.display = 'none';
                    } else {
                        modalTitle.textContent = 'Existing User Found';
                        proceedWithNewBtn.style.display = 'block';
                    }
                    
                    duplicateModal.style.display = 'flex';
                }
            } catch (err) {
                console.error("Duplication check failed", err);
            }
        };

        // Attachment of event listeners for real-time check
        ['username', 'first_name', 'last_name', 'email', 'phone'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('blur', checkDuplicates);
            }
        });

        // Simple submit without interception (or minor check)
        userForm.addEventListener('submit', function (e) {
            // If modal is open, prevent submission
            if (duplicateModal.style.display === 'flex') {
                e.preventDefault();
                return;
            }
        });

        proceedWithNewBtn.addEventListener('click', () => {
            if (currentSuggestion) {
                const unElement = document.getElementById('username');
                if (unElement) {
                    unElement.value = currentSuggestion;
                    // Trigger flash or simple color change to notify user
                    unElement.style.backgroundColor = '#e8f0fe';
                    setTimeout(() => unElement.style.backgroundColor = '', 2000);
                }
            }
            duplicateModal.style.display = 'none';
        });

        cancelSaveBtn.addEventListener('click', () => {
            // Abort creation and go back to user settings or home
            const cancelUrl = isEditing ? 
                '/settings?tab=user-settings' : 
                '/settings?tab=user-settings';
            window.location.href = cancelUrl;
        });

        closeDuplicateModal.addEventListener('click', () => {
            duplicateModal.style.display = 'none';
        });

        window.addEventListener('click', (e) => {
            if (e.target === duplicateModal) {
                duplicateModal.style.display = 'none';
            }
        });
    }
});
