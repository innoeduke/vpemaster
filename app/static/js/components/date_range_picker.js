(function () {
    const MONTH_LABELS = {
        '01': 'January', '02': 'February', '03': 'March', '04': 'April',
        '05': 'May', '06': 'June', '07': 'July', '08': 'August',
        '09': 'September', '10': 'October', '11': 'November', '12': 'December',
    };
    const pad = (n) => String(n).padStart(2, '0');
    const parseValue = (v) => {
        if (!v || typeof v !== 'string' || v.length < 7) return null;
        const y = parseInt(v.slice(0, 4), 10);
        const m = parseInt(v.slice(5, 7), 10);
        if (!y || !m) return null;
        return { year: y, month: m, key: `${y}-${pad(m)}` };
    };
    const formatValue = (year, month) => `${year}-${pad(month)}`;
    const formatDisplay = (year, month) => `${MONTH_LABELS[pad(month)]} ${year}`;

    function buildMonthPicker(pickerEl) {
        const role = pickerEl.getAttribute('data-month-role');
        const input = pickerEl.querySelector('[data-month-picker-input]');
        const trigger = pickerEl.querySelector('[data-month-picker-trigger]');
        const popover = pickerEl.querySelector('[data-month-picker-popover]');
        const yearEl = pickerEl.querySelector('[data-month-picker-year]');
        const prevBtn = pickerEl.querySelector('[data-month-picker-prev]');
        const nextBtn = pickerEl.querySelector('[data-month-picker-next]');
        const grid = pickerEl.querySelector('[data-month-picker-grid]');
        const valueEl = pickerEl.querySelector('[data-month-picker-value]');
        if (!input || !trigger || !popover || !yearEl || !valueEl) return null;

        const cells = Array.from(grid.querySelectorAll('[data-month]'));
        const getValue = () => parseValue(input.value);

        const setViewYear = (year) => {
            yearEl.textContent = year;
            yearEl.dataset.year = year;
        };
        const getViewYear = () => parseInt(yearEl.textContent, 10);

        const render = (boundary) => {
            const current = getValue();
            const year = getViewYear();
            cells.forEach((cell) => {
                const m = parseInt(cell.getAttribute('data-month'), 10);
                cell.removeAttribute('aria-selected');
                cell.removeAttribute('disabled');
                if (current && current.year === year && current.month === m) {
                    cell.setAttribute('aria-selected', 'true');
                }
                if (boundary && boundary(year, m)) {
                    cell.setAttribute('disabled', '');
                }
            });
        };

        const renderDisplay = () => {
            const v = getValue();
            valueEl.textContent = v ? formatDisplay(v.year, v.month) : '—';
        };

        const open = () => {
            const v = getValue();
            setViewYear(v ? v.year : new Date().getFullYear());
            popover.hidden = false;
            trigger.setAttribute('aria-expanded', 'true');
            render();
        };
        const close = () => {
            popover.hidden = true;
            trigger.setAttribute('aria-expanded', 'false');
        };

        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            const wasOpen = !popover.hidden;
            if (wasOpen) {
                close();
            } else {
                popover.hidden = false;
                trigger.setAttribute('aria-expanded', 'true');
                open();
            }
        });
        popover.addEventListener('click', (e) => e.stopPropagation());

        prevBtn.addEventListener('click', () => {
            setViewYear(getViewYear() - 1);
            render();
        });
        nextBtn.addEventListener('click', () => {
            setViewYear(getViewYear() + 1);
            render();
        });

        grid.addEventListener('click', (e) => {
            const cell = e.target.closest('[data-month]');
            if (!cell || cell.hasAttribute('disabled')) return;
            const year = getViewYear();
            const month = parseInt(cell.getAttribute('data-month'), 10);
            input.value = formatValue(year, month);
            renderDisplay();
            close();
        });

        return {
            role,
            pickerEl,
            input,
            trigger,
            popover,
            get value() { return getValue(); },
            isOpen: () => !popover.hidden,
            open,
            close,
            setValue: (year, month) => {
                input.value = formatValue(year, month);
                renderDisplay();
            },
            refresh: render,
            refreshDisplay: renderDisplay,
        };
    }

    function wireInstance(root) {
        const btn = root.querySelector('.date-range-btn');
        const modal = root.querySelector('.date-range-modal');
        if (!btn || !modal) return;

        const pickers = Array.from(root.querySelectorAll('[data-month-picker]'))
            .map(buildMonthPicker)
            .filter(Boolean);
        const start = pickers.find((p) => p.role === 'start');
        const end = pickers.find((p) => p.role === 'end');

        pickers.forEach((p) => p.refreshDisplay());

        const boundaryFor = (target) => {
            if (target === end && start.value) {
                return (y, m) => formatValue(y, m) < formatValue(start.value.year, start.value.month);
            }
            if (target === start && end.value) {
                return (y, m) => formatValue(y, m) > formatValue(end.value.year, end.value.month);
            }
            return null;
        };

        const coordChange = (changed) => {
            if (!start || !end) return;
            const sv = start.value, ev = end.value;
            if (changed === start && sv && (!ev || ev.key < sv.key)) {
                end.setValue(sv.year, sv.month);
            } else if (changed === end && ev && (!sv || sv.key > ev.key)) {
                start.setValue(ev.year, ev.month);
            }
            start.refresh(boundaryFor(start));
            end.refresh(boundaryFor(end));
        };

        // Open/close coordination: when one picker opens, close the other.
        pickers.forEach((picker) => {
            const originalOpen = picker.open;
            picker.open = () => {
                pickers.forEach((p) => { if (p !== picker) p.close(); });
                originalOpen();
            };
        });

        // Re-coordinate after a month is chosen (grid click is inside buildMonthPicker;
        // we observe input value changes here).
        pickers.forEach((picker) => {
            picker.input.addEventListener('change', () => coordChange(picker));
        });

        document.addEventListener('click', (e) => {
            pickers.forEach((p) => {
                if (p.isOpen() && !p.popover.contains(e.target) && !p.trigger.contains(e.target)) {
                    p.close();
                }
            });
        });

        const openModal = () => {
            modal.hidden = false;
            modal.removeAttribute('inert');
            btn.setAttribute('aria-expanded', 'true');
            document.body.classList.add('modal-open');
        };
        const closeModal = () => {
            pickers.forEach((p) => p.close());
            if (document.activeElement && modal.contains(document.activeElement)) {
                document.activeElement.blur();
            }
            modal.hidden = true;
            modal.setAttribute('inert', '');
            btn.setAttribute('aria-expanded', 'false');
            document.body.classList.remove('modal-open');
        };

        btn.addEventListener('click', openModal);
        modal.querySelectorAll('[data-close-modal]').forEach((el) => {
            el.addEventListener('click', closeModal);
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const openPicker = pickers.find((p) => p.isOpen());
                if (openPicker) { openPicker.close(); return; }
                if (!modal.hidden) closeModal();
            }
        });
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
