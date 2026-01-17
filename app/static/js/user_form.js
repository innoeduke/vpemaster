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
});
