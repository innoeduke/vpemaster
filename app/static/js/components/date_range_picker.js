(function () {
    function wireInstance(root) {
        const btn = root.querySelector('.date-range-btn');
        const modal = root.querySelector('.date-range-modal');
        if (!btn || !modal) return;

        const startEl = root.querySelector('input[type="month"][name="start_month"]');
        const endEl = root.querySelector('input[type="month"][name="end_month"]');

        const open = () => {
            modal.hidden = false;
            modal.removeAttribute('inert');
            btn.setAttribute('aria-expanded', 'true');
            document.body.classList.add('modal-open');
        };
        const close = () => {
            if (document.activeElement && modal.contains(document.activeElement)) {
                document.activeElement.blur();
            }
            modal.hidden = true;
            modal.setAttribute('inert', '');
            btn.setAttribute('aria-expanded', 'false');
            document.body.classList.remove('modal-open');
        };

        btn.addEventListener('click', open);
        modal.querySelectorAll('[data-close-modal]').forEach((el) => {
            el.addEventListener('click', close);
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !modal.hidden) close();
        });

        if (startEl && endEl) {
            startEl.addEventListener('change', () => {
                if (startEl.value && (!endEl.value || endEl.value < startEl.value)) {
                    endEl.value = startEl.value;
                }
                endEl.min = startEl.value || '';
            });
            endEl.addEventListener('change', () => {
                if (endEl.value && (!startEl.value || startEl.value > endEl.value)) {
                    startEl.value = endEl.value;
                }
                startEl.max = endEl.value || '';
            });
        }
    }

    function init(root) {
        (root || document).querySelectorAll('[data-date-range-picker]').forEach(wireInstance);
    }

    window.initDateRangePickers = init;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => init(document));
    } else {
        init(document);
    }
})();
