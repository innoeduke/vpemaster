
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
        // KPI Filter and Mobile Label Toggle Logic
        const parent = document.querySelector('.filter-row-premium');
        const kpiTiles = document.querySelectorAll('.calendar-kpis .kpi-tile');
        const totalTile = document.querySelector('.kpi-tile-total');
        const cards = document.querySelectorAll('.meeting-card');
        const rows = document.querySelectorAll('.calendar-body .calendar-row');

        const updateMonthVisibility = () => {
            rows.forEach(row => {
                const totalCards = row.querySelectorAll('.meeting-card').length;
                const visibleCards = Array.from(row.querySelectorAll('.meeting-card')).filter(card => card.style.display !== 'none');
                
                // Toggle cell-empty class on each calendar-cell
                row.querySelectorAll('.calendar-cell').forEach(cell => {
                    const cellVisibleCards = Array.from(cell.querySelectorAll('.meeting-card')).filter(card => card.style.display !== 'none');
                    if (cellVisibleCards.length === 0) {
                        cell.classList.add('cell-empty');
                    } else {
                        cell.classList.remove('cell-empty');
                    }
                });

                if (totalCards > 0 && visibleCards.length === 0) {
                    row.classList.add('month-empty');
                } else {
                    row.classList.remove('month-empty');
                }
            });
        };

        if (parent) {
            kpiTiles.forEach((tile) => {
                const typeClass = Array.from(tile.classList).find(cls => cls.startsWith('type-'));
                if (!typeClass) return;

                tile.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();

                    const isActive = tile.classList.contains('active-filter');

                    // Reset other tiles' active state and mobile show-label class
                    kpiTiles.forEach(t => {
                        t.classList.remove('active-filter');
                        t.classList.remove('show-label');
                    });
                    if (totalTile) totalTile.classList.remove('active-filter');

                    if (isActive) {
                        // Disable filter
                        parent.classList.remove('has-active-filter');
                        cards.forEach(card => card.style.display = 'flex');
                        updateMonthVisibility();
                    } else {
                        // Enable filter and show label (for mobile view)
                        tile.classList.add('active-filter');
                        tile.classList.add('show-label');
                        parent.classList.add('has-active-filter');
                        
                        cards.forEach(card => {
                            if (card.classList.contains(typeClass)) {
                                card.style.display = 'flex';
                            } else {
                                card.style.display = 'none';
                            }
                        });
                        updateMonthVisibility();
                    }
                });
            });

            if (totalTile) {
                totalTile.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    kpiTiles.forEach(t => {
                        t.classList.remove('active-filter');
                        t.classList.remove('show-label');
                    });
                    totalTile.classList.remove('active-filter');
                    parent.classList.remove('has-active-filter');
                    cards.forEach(card => card.style.display = 'flex');
                    updateMonthVisibility();
                });
            }
        }
    })();
