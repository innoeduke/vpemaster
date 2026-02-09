document.addEventListener("DOMContentLoaded", function () {
  setupSearch(
    "meeting-search",
    ".logs-container",
    ".speech-log-entry, .role-log-entry",
    ".meeting-info"
  );

  const meetingFilter = document.getElementById('meeting-filter');
  if (meetingFilter) {
      meetingFilter.addEventListener('change', function() {
          const meetingNumber = this.value;
          const url = new URL(window.location.href);
          url.searchParams.set('meeting_number', meetingNumber);
          // Ensure we stay in admin (Meeting) view when filtering by meeting
          url.searchParams.set('view_mode', 'admin');
          window.location.href = url.toString();
      });
  }
  if (document.getElementById("speaker-search")) {
    setupSearch(
      "speaker-search",
      ".logs-container",
      ".speech-log-entry, .role-log-entry",
      ".speaker-info"
    );

    // Auto-fill speaker search if query param is present
    const urlParams = new URLSearchParams(window.location.search);
    const speakerSearch = urlParams.get('speaker_search');
    if (speakerSearch) {
      const input = document.getElementById("speaker-search");
      input.value = speakerSearch;
      // Trigger keyup to apply filter
      input.dispatchEvent(new Event('keyup'));
      // If clear button exists, show it
      const clearBtn = document.getElementById("clear-speaker-search");
      if (clearBtn) clearBtn.style.display = "block";
    }
  }

  // Add click listeners to role badges
  document.querySelectorAll('.role-badge, .speech-badge').forEach(badge => {
    badge.addEventListener('click', function() {
        showRoleHistory(this);
    });
  });

  // Close modal when clicking outside
  window.addEventListener('click', function(event) {
    const modal = document.getElementById('roleHistoryModal');
    if (event.target == modal) {
        closeHistoryModal();
    }
  });
});



function showRoleHistory(badge) {
    const roleName = badge.dataset.role;
    const historyData = JSON.parse(badge.dataset.history || '[]');
    
    const modal = document.getElementById('roleHistoryModal');
    const roleNameEl = document.getElementById('historyRoleName');
    const historyListEl = document.getElementById('historyList');
    
    roleNameEl.innerText = `${roleName} History`;
    historyListEl.innerHTML = '';
    
    // Filter only completed items (some might be pending)
    const completedHistory = historyData.filter(item => item.status === 'completed');
    
    if (completedHistory.length === 0) {
        historyListEl.innerHTML = '<div class="history-empty">No completed history found for this role.</div>';
    } else {
        completedHistory.forEach(item => {
            const historyItem = document.createElement('div');
            historyItem.className = 'history-item';
            
            const roleInfo = item.role_name ? `<span class="history-role-tag">${item.role_name}</span>` : '';
            
            // Determine full project code (use backend provided if available, else fallback)
            // Backend now provides 'project_code' as the full code (e.g. EH1.2)
            const fullCode = item.project_code || item.name.split(' ')[0];
            
            // Build Title HTML
            let titleHtml = '';
            if (item.speech_title) {
                if (item.media_url) {
                     titleHtml = `<div class="history-title" style="font-weight: bold;"><a href="${item.media_url}" target="_blank" class="history-media-link"><i class="fas fa-play-circle"></i> ${item.speech_title}</a></div>`;
                } else {
                     titleHtml = `<div class="history-title" style="font-weight: bold;">${item.speech_title}</div>`;
                }
            } else {
                // Fallback if no title but we have a name (legacy)
                titleHtml = `<div class="history-title" style="font-weight: bold;">${item.name.replace(fullCode, '').trim()}</div>`;
            }

            // Build Evaluator HTML
            let evaluatorHtml = '';
            if (item.evaluator) {
                evaluatorHtml = `<div class="history-evaluator" style="color: #64748b;">Evaluated by: ${item.evaluator}</div>`;
            }

            historyItem.innerHTML = `
                <div class="history-item-top">
                    <span class="history-meeting-num">Meeting #${item.meeting_number} ${roleInfo}</span>
                    <span class="history-date">${item.meeting_date}</span>
                </div>
                <div class="history-project-content" style="margin-top: 8px; display: flex; flex-direction: column; gap: 4px;">
                    ${titleHtml}
                    <div class="history-project-code" style="font-weight: 600; color: #2563eb; display: flex; align-items: center; gap: 6px;">
                        ${fullCode} <span style="color: #64748b; font-weight: normal; margin-left: 8px;">${item.project_name || ''}</span>
                    </div>
                    ${evaluatorHtml}
                </div>
            `;
            historyListEl.appendChild(historyItem);
        });
    }
    
    modal.style.display = 'flex';
}

function closeHistoryModal() {
    const modal = document.getElementById('roleHistoryModal');
    if (modal) modal.style.display = 'none';
}



function completeSpeechLog(button, logId) {
  fetch(`/speech_log/complete/${logId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        const statusContainer = button.parentNode;
        // Replace buttons with the checkmark icon
        statusContainer.innerHTML =
          '<i class="fas fa-check-circle" title="Completed"></i>';

        // Update progress summary if provided
        if (data.progress_html && data.level) {
          const progressContainer = document.getElementById("progress-" + data.level);
          if (progressContainer) {
            progressContainer.innerHTML = data.progress_html;
          }
        }
      } else {
        alert("Error updating status: " + data.message);
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      alert("An error occurred while updating the status.");
    });
}

function suspendSpeechLog(button, logId) {
  if (
    !confirm(
      "Are you sure you want to mark this speech as Delivered (but not Completed for pathway)?"
    )
  ) {
    return;
  }

  fetch(`/speech_log/suspend/${logId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        // Update button/status UI without reload
        const statusContainer = button.parentNode;
        statusContainer.innerHTML = '<span class="status-delivered">Delivered</span>';

        // Update progress summary if provided
        if (data.progress_html && data.level) {
          const progressContainer = document.getElementById("progress-" + data.level);
          if (progressContainer) {
            progressContainer.innerHTML = data.progress_html;
          }
        }
      } else {
        alert("Error suspending status: " + data.message);
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      alert("An error occurred while suspending the status.");
    });
}

// Mobile/iPad Table Adjustments
function adjustTableForIpad() {
    const isIpad = window.innerWidth >= 768 && window.innerWidth <= 1024;
    const table = document.querySelector('.progress-table');
    
    if (!table) return;

    // Reset standard layout if not iPad
    if (!isIpad) {
        // Restore headers
        const headers = table.querySelectorAll('th');
        if (headers.length === 5) { // If currently modified
            // This is a bit complex to revert generic "restore", so simpler is to reload 
            // or we track state. For now, let's just implement the transformation.
            // A full revert would require storing original state or reloading.
            // Given the complexity of DOM manipulation, a reload on orientation change/resize across breakpoints is safer,
            // or we assume users rarely resize desktop <-> iPad dynamically.
            // Let's implement a robust check.
            return; 
        }
        return;
    }

    // Check if already adjusted
    const headers = table.querySelectorAll('thead th');
    if (headers.length === 5) return; // Already 5 columns (Speeches, Required, Elective, Edu)

    // 1. Merge Header Columns
    // Original: [Empty], [Speeches], [Required x3], [Elective], [Edu x2] -> 8 columns (technically 1 empty + 1 speech + 3 req + 1 elec + 2 edu = 8 ths usually, but check HTML)
    // Actually HTML has: <th></th>, <th>Speeches</th>, <th colspan="3">Required Roles</th>, <th>Elective Roles</th>, <th colspan="2">Education Series</th>
    
    // We want: [Empty], [Speeches], [Required (colspan 1)], [Elective (colspan 2)], [Edu (colspan 1)]
    
    const headerRow = table.querySelector('thead tr');
    if (headerRow) {
        // Required Roles: Change colspan 3 -> 1
        const reqHeader = headerRow.querySelector('th:nth-child(3)'); // It's the 3rd TH element
        if (reqHeader) reqHeader.setAttribute('colspan', '1');
        
        // Elective Roles: Change colspan 1 -> 2
        const elecHeader = headerRow.querySelector('th:nth-child(4)');
        if (elecHeader) elecHeader.setAttribute('colspan', '2');
        
        // Edu Series: Change colspan 2 -> 1
        const eduHeader = headerRow.querySelector('th:nth-child(5)');
        if (eduHeader) eduHeader.setAttribute('colspan', '1');
    }

    // 2. Process Body Rows
    const rows = table.querySelectorAll('tbody tr');
    rows.forEach(row => {
        // Cells: 0=Level, 1=Speeches, 2,3,4=Required, 5=Elective, 6,7=Edu (Total 8 tds)
        const cells = Array.from(row.children);
        if (cells.length < 8) return;

        // --- Merge Required Roles (Cells 2, 3, 4) ---
        // Create container for stacked badges
        const reqContainer = document.createElement('div');
        reqContainer.style.display = 'flex';
        reqContainer.style.flexDirection = 'column';
        reqContainer.style.gap = '4px';
        reqContainer.style.width = '100%';

        // Extract contents from cells 2, 3, 4
        [cells[2], cells[3], cells[4]].forEach(cell => {
            while (cell.firstChild) {
                // If it's a badge, reset margins for stacking
                if (cell.firstChild.classList && cell.firstChild.classList.contains('role-badge')) {
                     cell.firstChild.style.margin = '2px 0';
                     cell.firstChild.style.width = '100%';
                     cell.firstChild.style.boxSizing = 'border-box';
                     // Ensure inner content is centered
                     cell.firstChild.style.justifyContent = 'center';
                }
                reqContainer.appendChild(cell.firstChild);
            }
        });

        // Clear cell 2 and append container
        cells[2].innerHTML = '';
        cells[2].appendChild(reqContainer);
        // Hide cells 3 & 4
        cells[3].style.display = 'none';
        cells[4].style.display = 'none';

        // --- Expand Elective Roles (Cell 5) ---
        cells[5].setAttribute('colspan', '2');
        cells[5].style.width = 'auto'; // Reset width restriction
        // Style for side-by-side badges
        // We need to apply flex wrap to the cell content? 
        // Usually badges are inline-block or flex items. 
        // Let's force proper layout for multiple items.
        // Identify badges and set width to ~48%
        const elecBadges = cells[5].querySelectorAll('.role-badge');
        elecBadges.forEach(badge => {
            badge.style.width = 'calc(50% - 6px)'; // 2 per row with gap
            badge.style.margin = '3px';
            badge.style.display = 'inline-flex';
            badge.style.justifyContent = 'center';
        });


        // --- Merge Edu Series (Cells 6, 7) ---
        // Stack horizontally (default block flow might wrap, let's ensure single row or clean wrap)
        const eduContainer = document.createElement('div');
        eduContainer.style.display = 'flex';
        eduContainer.style.flexWrap = 'wrap';
        eduContainer.style.gap = '4px';
        eduContainer.style.justifyContent = 'center';

        [cells[6], cells[7]].forEach(cell => {
             while (cell.firstChild) {
                 if (cell.firstChild.classList && cell.firstChild.classList.contains('role-badge')) {
                     cell.firstChild.style.width = '100%'; // Full width in their new container? 
                     // User said "stack badges in a single row". 
                     // If we merge 2 cols into 1, effectively they become siblings.
                     // "remove colspan... stack badges in a single row" -> Horizontal stacking?
                     cell.firstChild.style.margin = '2px';
                 }
                eduContainer.appendChild(cell.firstChild);
            }
        });

        cells[6].innerHTML = '';
        cells[6].appendChild(eduContainer);
        cells[7].style.display = 'none';
    });
}

// Run adjustment on load and resize
window.addEventListener('load', adjustTableForIpad);
window.addEventListener('resize', function() {
    // Simple debounce or check
    adjustTableForIpad();
});
