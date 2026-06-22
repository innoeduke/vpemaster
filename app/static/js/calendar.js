
    (function () {
        // Auto-color unknown meeting-type KPI tiles. The calendar.css file
        // hard-codes a background color for each known type. When a new meeting
        // type appears (e.g., "Regular Meeting") without a matching CSS rule,
        // its tile inherits the page background and the white text inside
        // becomes unreadable. Hash the type name into a dark, saturated
        // palette so every new type gets a distinct, readable color and the
        // same type always renders the same color.
        const KPI_COLOR_PALETTE = [
            '#0d9488', // teal
            '#65a30d', // lime
            '#4338ca', // indigo
            '#dc2626', // red
            '#0891b2', // cyan
            '#e11d48', // rose
            '#1e40af', // dark blue
            '#9333ea', // purple
            '#0f766e', // dark teal
            '#854d0e', // dark amber
            '#7c2d12', // dark orange
            '#831843', // dark pink
        ];

        function hashString(str) {
            let hash = 5381;
            for (let i = 0; i < str.length; i++) {
                hash = ((hash << 5) + hash) + str.charCodeAt(i);
                hash = hash | 0;
            }
            return Math.abs(hash);
        }

        function isBackgroundUnset(bg) {
            if (!bg || bg === 'transparent' || bg === 'rgba(0, 0, 0, 0)') return true;
            const match = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
            if (!match) return true;
            const r = Number(match[1]);
            const g = Number(match[2]);
            const b = Number(match[3]);
            return r > 240 && g > 240 && b > 240;
        }

        function colorUnknownTypeTiles() {
            const tiles = document.querySelectorAll('.calendar-kpis .kpi-tile');
            tiles.forEach((tile) => {
                const typeClass = Array.from(tile.classList).find(cls => /^type-.+/.test(cls));
                if (!typeClass) return;
                if (!isBackgroundUnset(window.getComputedStyle(tile).backgroundColor)) return;
                const labelEl = tile.querySelector('.kpi-label');
                const typeName = labelEl ? labelEl.textContent.trim() : typeClass;
                tile.style.backgroundColor = KPI_COLOR_PALETTE[hashString(typeName) % KPI_COLOR_PALETTE.length];
            });
        }

        colorUnknownTypeTiles();

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
