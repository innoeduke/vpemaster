document.addEventListener("DOMContentLoaded", function () {
  setupSearch(
    "meeting-search",
    ".logs-container",
    ".speech-log-entry, .role-log-entry",
    ".meeting-info"
  );
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
});



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
