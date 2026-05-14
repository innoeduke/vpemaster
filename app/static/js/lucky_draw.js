// Cache DOM elements
function cacheElements() {
    return {
        drawButton: document.getElementById("drawButton"),
        resetButton: document.getElementById("resetButton"),
        winnersWall: document.getElementById("winnersWall"),
        rosterData: document.getElementById("rosterData"),
        drawTypeSelect: document.getElementById("drawType")
    };
}

// Shared state
let drawnWinners = [];
let allEntries = [];

// Initialize lucky draw functionality
function initializeLuckyDraw(elements) {
    // Load roster data from hidden div
    if (elements.rosterData) {
        const entries = elements.rosterData.querySelectorAll('.roster-entry');

        entries.forEach(entry => {
            const entryData = {
                order: entry.dataset.order,
                name: entry.dataset.name,
                avatar: entry.dataset.avatar,
                type: entry.dataset.type,
                ticket: entry.dataset.ticket,
                hasTopicsRole: entry.dataset.hasTopicsRole
            };
            allEntries.push(entryData);
        });
    }

    // Attach draw button event
    if (elements.drawButton) {
        elements.drawButton.addEventListener('click', () => performLuckyDraw(elements));
    }

    // Attach reset button event
    if (elements.resetButton) {
        elements.resetButton.addEventListener('click', () => resetDraws(elements));
    }
}

// Filter entries based on selected draw type
function getFilteredEntries() {
    const drawTypeSelect = document.getElementById('drawType');
    const selectedType = drawTypeSelect ? drawTypeSelect.value : 'all-audience';

    return allEntries.filter(entry => {
        // Always exclude cancelled tickets
        if (entry.ticket === 'Cancelled') {
            return false;
        }

        // Exclude already drawn winners
        const isAlreadyDrawn = drawnWinners.some(winner =>
            winner.order === entry.order && winner.name === entry.name
        );
        if (isAlreadyDrawn) return false;

        // Filter by type
        switch (selectedType) {
            case 'all-audience':
                // All audience: Members and Guests, but NOT Officers
                return entry.type === 'Member' || entry.type === 'Guest';
            case 'members':
                return entry.type === 'Member' || entry.type === 'Officer';
            case 'guests':
                return entry.type === 'Guest';
            case 'table-topics':
                return entry.hasTopicsRole === 'true';
            case 'full-house':
                // Full House: Everyone including Officers
                return true;
            default:
                return entry.type === 'Member' || entry.type === 'Guest';
        }
    });
}

// Perform lucky draw
function performLuckyDraw(elements) {
    const validEntries = getFilteredEntries();

    if (validEntries.length === 0) {
        showNotification('No eligible entries for drawing with current filter', 'warning');
        return;
    }

    // Random selection
    const randomIndex = Math.floor(Math.random() * validEntries.length);
    const selectedEntry = validEntries[randomIndex];

    // Add to drawn winners
    drawnWinners.push(selectedEntry);

    // Add winner tile to wall
    addWinnerTile(selectedEntry, elements);
}

// Reset all draws
function resetDraws(elements) {
    // Clear drawn winners array
    drawnWinners = [];

    // Clear winners wall
    elements.winnersWall.innerHTML = '';

    // Restore placeholder
    const placeholder = document.createElement('div');
    placeholder.className = 'wall-placeholder';
    placeholder.innerHTML = `
    <i class="fas fa-trophy"></i>
    <p>Winners will appear here</p>
  `;
    elements.winnersWall.appendChild(placeholder);

    // Show notification
    showNotification('All winners cleared', 'info');
}

// Add winner tile to the wall
function addWinnerTile(entry, elements) {
    // Remove placeholder if it exists
    const placeholder = elements.winnersWall.querySelector('.wall-placeholder');
    if (placeholder) {
        placeholder.remove();
    }

    // Create winner tile
    const tile = document.createElement('div');
    tile.className = 'winner-tile';

    // Create avatar
    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'winner-avatar';

    if (entry.avatar && entry.avatar.trim() !== '') {
        const img = document.createElement('img');
        img.src = entry.avatar;
        img.alt = entry.name;

        img.onerror = function () {
            // Fallback to initials if image fails to load
            this.style.display = 'none';
            const initials = getInitials(entry.name);
            const initialsDiv = document.createElement('div');
            initialsDiv.className = 'avatar-initials';
            initialsDiv.textContent = initials;
            avatarDiv.appendChild(initialsDiv);
        };

        avatarDiv.appendChild(img);
    } else {
        // Use initials if no avatar
        const initials = getInitials(entry.name);
        const initialsDiv = document.createElement('div');
        initialsDiv.className = 'avatar-initials';
        initialsDiv.textContent = initials;
        avatarDiv.appendChild(initialsDiv);
    }

    // Create order number badge
    const orderBadge = document.createElement('div');
    orderBadge.className = 'winner-order-badge';
    orderBadge.innerHTML = `<i class="fas fa-tag"></i> ${entry.order}`;

    // Create name
    const nameDiv = document.createElement('div');
    nameDiv.className = 'winner-name';
    nameDiv.textContent = entry.name;

    // Assemble tile
    tile.appendChild(orderBadge);
    tile.appendChild(avatarDiv);
    tile.appendChild(nameDiv);

    // Add animation
    tile.style.opacity = '0';
    tile.style.transform = 'scale(0.8)';
    elements.winnersWall.appendChild(tile);

    // Trigger animation
    setTimeout(() => {
        tile.style.opacity = '1';
        tile.style.transform = 'scale(1)';
    }, 10);
}

// Get initials from name
function getInitials(name) {
    if (!name || name === 'N/A') return '?';
    const parts = name.trim().split(' ');
    if (parts.length === 1) {
        return parts[0].substring(0, 2).toUpperCase();
    }
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}


// Main initialization
document.addEventListener("DOMContentLoaded", function () {
    const elements = cacheElements();
    initializeLuckyDraw(elements);
});

// Expose for testing
window._luckyDrawHooks = {
    getFilteredEntries,
    allEntries,
    drawnWinners
};
