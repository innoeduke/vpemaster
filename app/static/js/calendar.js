
    (function () {
        const modal = document.getElementById('date-range-modal');
        const btn = document.getElementById('date-range-btn');
        if (!modal || !btn) return;

        const open = () => {
            modal.hidden = false;
            modal.removeAttribute('inert');
            document.body.classList.add('modal-open');
        };
        const close = () => {
            if (document.activeElement && modal.contains(document.activeElement)) {
                document.activeElement.blur();
            }
            modal.hidden = true;
            modal.setAttribute('inert', '');
            document.body.classList.remove('modal-open');
        };

        btn.addEventListener('click', open);
        modal.querySelectorAll('[data-close-modal]').forEach((el) => {
            el.addEventListener('click', close);
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !modal.hidden) close();
        });

        // Keep start <= end and end >= start as the user changes values
        const startEl = document.getElementById('modal-start-month');
        const endEl = document.getElementById('modal-end-month');
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
    })();
