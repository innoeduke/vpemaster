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
    // ===== USER SEARCH (for adding existing users to club) =====
    const userSearch = document.getElementById('user_search');
    const userDropdown = document.getElementById('user_dropdown');
    const userDataScript = document.getElementById('user_data');
    
    if (userSearch && userDropdown && userDataScript) {
        let users = [];
        try {
            users = JSON.parse(userDataScript.textContent);
        } catch (e) {
            console.error("Failed to parse user data", e);
        }
        
        userSearch.addEventListener('input', function () {
            const val = this.value.toLowerCase().trim();
            userDropdown.innerHTML = '';
            
            if (!val) {
                userDropdown.style.display = 'none';
                return;
            }
            
            // Search by username, email, phone, or contact name
            const filtered = users.filter(u => {
                const username = (u.username || '').toLowerCase();
                const email = (u.email || '').toLowerCase();
                const phone = (u.phone || '').toLowerCase();
                const contactName = (u.contact_name || '').toLowerCase();
                
                return username.includes(val) || 
                       email.includes(val) || 
                       phone.includes(val) || 
                       contactName.includes(val);
            }).slice(0, 10); // Limit to top 10
            
            if (filtered.length > 0) {
                filtered.forEach(u => {
                    const div = document.createElement('div');
                    div.className = 'autocomplete-suggestion';
                    
                    // Build display text - show only name information for privacy
                    let displayText = u.contact_name || u.username;
                    if (u.contact_name && u.username) {
                        displayText = `${u.contact_name} (${u.username})`;
                    }
                    
                    div.textContent = displayText;
                    div.addEventListener('click', function () {
                        // Redirect to edit this user (add to club)
                        window.location.href = `/user/form/${u.id}`;
                    });
                    userDropdown.appendChild(div);
                });
                userDropdown.style.display = 'block';
            } else {
                userDropdown.style.display = 'none';
            }
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', function (e) {
            if (e.target !== userSearch && e.target !== userDropdown) {
                userDropdown.style.display = 'none';
            }
        });
    }

    // ===== AUTO-GENERATE FULL NAME =====
    const firstName = document.getElementById('first_name');
    const lastName = document.getElementById('last_name');
    const fullName = document.getElementById('full_name');

    if (firstName && lastName && fullName) {
        let isManuallyEdited = false;

        fullName.addEventListener('input', () => {
            isManuallyEdited = true;
        });

        const updateFullName = () => {
            if (isManuallyEdited) return;
            
            const first = firstName.value.trim();
            const last = lastName.value.trim();
            fullName.value = `${first} ${last}`.trim();
        };

        firstName.addEventListener('input', updateFullName);
        lastName.addEventListener('input', updateFullName);
    }

    // ===== DUPLICATE DETECTION LOGIC =====
    const userForm = document.querySelector('form');
    const duplicateModal = document.getElementById('duplicateModal');
    const duplicateList = document.getElementById('duplicateList');
    const proceedWithNewBtn = document.getElementById('proceedWithNew');
    const cancelSaveBtn = document.getElementById('cancelSave');
    const closeDuplicateModal = document.getElementById('closeDuplicateModal');
    
    let isEditing = window.location.pathname.includes('/user/form/') && !window.location.pathname.endsWith('/form');
    let hasCheckedDuplicates = false;

    if (userForm && duplicateModal) {
        userForm.addEventListener('submit', async function (e) {
            // Only check duplicates for new users
            if (isEditing || hasCheckedDuplicates) {
                return;
            }

            e.preventDefault();

            const username = document.getElementById('username').value;
            const fullName = document.getElementById('full_name').value;
            const email = document.getElementById('email').value;
            const phone = document.getElementById('phone').value;

            try {
                const response = await fetch('/user/check_duplicates', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        username: username,
                        full_name: fullName,
                        email: email,
                        phone: phone
                    })
                });

                const data = await response.json();

                if (data.duplicates && data.duplicates.length > 0) {
                    // Show duplicates in modal
                    duplicateList.innerHTML = '';
                    data.duplicates.forEach(dup => {
                        const div = document.createElement('div');
                        div.style.cssText = 'padding: 10px; border: 1px solid #eee; margin-bottom: 10px; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; background: #fafafa;';
                        
                        const info = document.createElement('div');
                        info.innerHTML = `
                            <strong>${dup.full_name}</strong> (${dup.username})<br>
                            <small>${dup.email} | ${dup.phone}</small><br>
                            <span class="badge ${dup.type === 'User' ? 'btn-primary' : 'btn-secondary'}" style="font-size: 0.7em; padding: 2px 5px; border-radius: 3px; color: white;">${dup.type}</span>
                        `;
                        
                        const pickBtn = document.createElement('button');
                        pickBtn.type = 'button';
                        pickBtn.className = 'btn btn-sm btn-info';
                        pickBtn.textContent = 'Pick This User';
                        pickBtn.style.minWidth = '100px';
                        pickBtn.addEventListener('click', () => {
                            if (dup.type === 'User') {
                                window.location.href = `/user/form/${dup.id}`;
                            } else {
                                // For contact-only matches, we might want to link it, 
                                // but for now let's just go to the user creation with this contact context?
                                // Actually, let's just suggest the user record if it exists.
                                // If it's just a contact, we should maybe allow linking.
                                // For simplicity, if it's a contact, let's just proceed or pick if it has a user.
                                if (dup.has_user) {
                                     // This shouldn't happen with our backend logic but just in case
                                     alert("This contact already has a user account. Redirecting...");
                                } else {
                                     // Proceeding with new user but maybe we should link it? 
                                     // The backend _create_or_update_user creates a new contact always currently.
                                     // Let's just create new for now as requested.
                                }
                            }
                        });
                        
                        div.appendChild(info);
                        div.appendChild(pickBtn);
                        duplicateList.appendChild(div);
                    });
                    
                    duplicateModal.style.display = 'flex';
                } else {
                    // No duplicates, proceed
                    hasCheckedDuplicates = true;
                    userForm.submit();
                }
            } catch (err) {
                console.error("Duplication check failed", err);
                hasCheckedDuplicates = true;
                userForm.submit();
            }
        });

        proceedWithNewBtn.addEventListener('click', () => {
            hasCheckedDuplicates = true;
            userForm.submit();
        });

        cancelSaveBtn.addEventListener('click', () => {
            duplicateModal.style.display = 'none';
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
