
    var selectedRegisterPathwayId = null;
    function openRegisterPathwayModal() {
        selectedRegisterPathwayId = null;
        document.getElementById('pathway-dropdown-menu').style.display = 'none';
        const trigger = document.querySelector('.pathway-select-trigger');
        if (trigger) trigger.classList.remove('active');
        var modal = document.getElementById('registerPathwayModal');
        if (modal) modal.style.display = 'flex';
        var btn = document.getElementById('btn-confirm-register-pathway');
        if (btn) { btn.disabled = true; btn.style.opacity = '0.5'; }
        document.querySelectorAll('.register-pathway-option').forEach(function(el) {
            el.classList.remove('selected');
            el.style.background = 'white';
            el.style.borderColor = '#eee';
            var icon = el.querySelector('.select-indicator');
            if (icon) { icon.className = 'far fa-circle select-indicator'; icon.style.color = '#ccc'; }
        });
    }
    function selectRegisterPathway(el, pathwayId, pathwayName) {
        document.querySelectorAll('.register-pathway-option').forEach(function(item) {
            item.classList.remove('selected');
            item.style.background = 'white';
            item.style.borderColor = '#eee';
            var icon = item.querySelector('.select-indicator');
            if (icon) { icon.className = 'far fa-circle select-indicator'; icon.style.color = '#ccc'; }
        });
        el.classList.add('selected');
        el.style.background = '#e6f9ee';
        el.style.borderColor = '#28a745';
        var icon = el.querySelector('.select-indicator');
        if (icon) { icon.className = 'fas fa-check-circle select-indicator'; icon.style.color = '#28a745'; }
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
        var modal = document.getElementById('registerPathwayModal');
        if (modal) modal.style.display = 'none';
    }
    document.addEventListener('click', function(e) {
        var modal = document.getElementById('registerPathwayModal');
        if (modal && e.target === modal) {
            modal.style.display = 'none';
        }
    });

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
