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
