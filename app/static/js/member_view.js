
    var selectedRegisterPathwayId = null;
    function openRegisterPathwayModal() {
        selectedRegisterPathwayId = null;
        document.getElementById('pathway-dropdown-menu').style.display = 'none';
        const trigger = document.querySelector('.pathway-select-trigger');
        if (trigger) trigger.classList.remove('active');
        
        openActionModal('registerPathwayModal');
        
        var btn = document.getElementById('btn-confirm-register-pathway');
        if (btn) { btn.disabled = true; btn.style.opacity = '0.5'; }
        document.querySelectorAll('.register-pathway-option').forEach(function(el) {
            el.classList.remove('selected');
            var icon = el.querySelector('.select-indicator');
            if (icon) { icon.className = 'far fa-circle select-indicator'; }
        });
    }
    function selectRegisterPathway(el, pathwayId, pathwayName) {
        document.querySelectorAll('.register-pathway-option').forEach(function(item) {
            item.classList.remove('selected');
            var icon = item.querySelector('.select-indicator');
            if (icon) { icon.className = 'far fa-circle select-indicator'; }
        });
        el.classList.add('selected');
        var icon = el.querySelector('.select-indicator');
        if (icon) { icon.className = 'fas fa-check-circle select-indicator'; }
        selectedRegisterPathwayId = pathwayId;
        var btn = document.getElementById('btn-confirm-register-pathway');
        if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
    }
    function confirmRegisterPathway() {
        if (!selectedRegisterPathwayId) return;
        registerFromFilter(selectedRegisterPathwayId, '');
        closeRegisterPathwayModal();
    }
    function closeRegisterPathwayModal() {
        closeActionModal('registerPathwayModal');
    }

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
