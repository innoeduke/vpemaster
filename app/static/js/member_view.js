
    var selectedRegisterPathwayId = null;
    
    function openRegisterPathwayModal() {
        selectedRegisterPathwayId = null;
        const menu = document.getElementById('pathway-dropdown-menu');
        if (menu) menu.style.display = 'none';
        const trigger = document.querySelector('.pathway-select-trigger');
        if (trigger) trigger.classList.remove('active');
        
        openActionModal('registerPathwayModal');
        
        var regBtn = document.getElementById('btn-confirm-register-pathway');
        if (regBtn) { regBtn.disabled = true; regBtn.style.opacity = '0.5'; }
        var defBtn = document.getElementById('btn-confirm-set-default-pathway');
        if (defBtn) { defBtn.disabled = true; defBtn.style.opacity = '0.5'; }
        
        document.querySelectorAll('.register-pathway-option').forEach(function(el) {
            el.classList.remove('selected');
            var icon = el.querySelector('.select-indicator');
            if (icon) {
                var isDefault = el.getAttribute('data-is-default') === 'true';
                var registered = el.getAttribute('data-registered') === 'true';
                if (isDefault) {
                    icon.className = 'fas fa-star select-indicator';
                } else if (registered) {
                    icon.className = 'far fa-check-circle select-indicator';
                } else {
                    icon.className = 'far fa-circle select-indicator';
                }
            }
        });
    }
    
    function selectRegisterPathway(el, pathwayId, pathwayName) {
        document.querySelectorAll('.register-pathway-option').forEach(function(item) {
            item.classList.remove('selected');
            var icon = item.querySelector('.select-indicator');
            if (icon) {
                var isDefault = item.getAttribute('data-is-default') === 'true';
                var registered = item.getAttribute('data-registered') === 'true';
                if (isDefault) {
                    icon.className = 'fas fa-star select-indicator';
                } else if (registered) {
                    icon.className = 'far fa-check-circle select-indicator';
                } else {
                    icon.className = 'far fa-circle select-indicator';
                }
            }
        });
        
        el.classList.add('selected');
        var icon = el.querySelector('.select-indicator');
        if (icon) {
            icon.className = 'fas fa-check-circle select-indicator';
        }
        
        selectedRegisterPathwayId = pathwayId;
        
        var isRegistered = el.getAttribute('data-registered') === 'true';
        var isDefault = el.getAttribute('data-is-default') === 'true';
        var pathwayType = el.getAttribute('data-pathway-type');
        var isPath = (pathwayType === 'pathway' || pathwayType === 'traditional');
        
        var regBtn = document.getElementById('btn-confirm-register-pathway');
        var defBtn = document.getElementById('btn-confirm-set-default-pathway');
        
        if (regBtn) {
            if (!isRegistered) {
                regBtn.disabled = false;
                regBtn.style.opacity = '1';
            } else {
                regBtn.disabled = true;
                regBtn.style.opacity = '0.5';
            }
        }
        if (defBtn) {
            if (isRegistered && !isDefault && isPath) {
                defBtn.disabled = false;
                defBtn.style.opacity = '1';
            } else {
                defBtn.disabled = true;
                defBtn.style.opacity = '0.5';
            }
        }
    }
    
    function confirmRegisterPathway() {
        if (!selectedRegisterPathwayId) return;
        if (typeof viewedContactId === 'undefined' || !viewedContactId) {
            console.error('viewedContactId is not defined');
            return;
        }
        
        fetch(`/api/contacts/${viewedContactId}/pathways/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pathway_id: parseInt(selectedRegisterPathwayId) })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                window.location.reload();
            } else {
                alert(data.message);
            }
        })
        .catch(err => {
            console.error('Error registering pathway:', err);
            alert('An error occurred. Please try again.');
        });
        
        closeRegisterPathwayModal();
    }
    
    function confirmSetDefaultPathway() {
        if (!selectedRegisterPathwayId) return;
        if (typeof viewedContactId === 'undefined' || !viewedContactId) {
            console.error('viewedContactId is not defined');
            return;
        }
        
        var selectedEl = document.querySelector('.register-pathway-option.selected');
        if (!selectedEl) return;
        
        var isRegistered = selectedEl.getAttribute('data-registered') === 'true';
        
        if (isRegistered) {
            setDefaultPathwayCall(selectedRegisterPathwayId);
        } else {
            // Register first, then set default
            fetch(`/api/contacts/${viewedContactId}/pathways/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pathway_id: parseInt(selectedRegisterPathwayId) })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    setDefaultPathwayCall(selectedRegisterPathwayId);
                } else {
                    alert(data.message);
                }
            })
            .catch(err => {
                console.error('Error registering pathway before setting default:', err);
                alert('An error occurred during registration.');
            });
        }
        
        closeRegisterPathwayModal();
    }
    
    function setDefaultPathwayCall(pathwayId) {
        fetch(`/api/contacts/${viewedContactId}/pathways/${pathwayId}/set_default`, {
            method: 'POST'
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                window.location.reload();
            } else {
                alert(data.message);
            }
        })
        .catch(err => {
            console.error('Error setting default pathway:', err);
            alert('An error occurred while setting the default pathway.');
        });
    }
    
    function closeRegisterPathwayModal() {
        closeActionModal('registerPathwayModal');
    }

    // Expose functions globally
    window.openRegisterPathwayModal = openRegisterPathwayModal;
    window.selectRegisterPathway = selectRegisterPathway;
    window.confirmRegisterPathway = confirmRegisterPathway;
    window.confirmSetDefaultPathway = confirmSetDefaultPathway;
    window.closeRegisterPathwayModal = closeRegisterPathwayModal;

    document.addEventListener("DOMContentLoaded", function() {
        const pSelect = document.getElementById('pathway');
        if (pSelect) new CustomSelectAdapter(pSelect);

        const addBtn = document.getElementById('add-plan-btn');
        if (addBtn) {
            addBtn.onclick = () => {
                // Initialize modal if not already via auto-run in planner_modal.js (it runs on DOMContentLoaded)
                // But we need to open it
                if (typeof openPlanModal === 'function') {
                    openPlanModal();
                } else {
                    console.error('openPlanModal function not found');
                }
            };
        }

        // Mark pathway action buttons as enabled for the CSS hover effect
        document.querySelectorAll('.pathway-action-btn').forEach(btn => {
            const style = btn.getAttribute('style') || '';
            if (style.indexOf('cursor: pointer') !== -1 || style.indexOf('opacity: 1') !== -1) {
                btn.classList.add('is-enabled');
            }
        });
    });
