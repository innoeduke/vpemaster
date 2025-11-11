document.addEventListener("DOMContentLoaded", function () {
  setupSearch(
    "meeting-search",
    ".logs-container",
    ".speech-log-entry",
    ".meeting-info"
  );
  if (document.getElementById("speaker-search")) {
    setupSearch(
      "speaker-search",
      ".logs-container",
      ".speech-log-entry",
      ".speaker-info"
    );
  }
});

function get_presentation_by_id(presentationId) {
  if (!Array.isArray(allPresentations) || !presentationId) {
    return null;
  }
  return allPresentations.find((p) => p.id == presentationId);
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
        // Force a page reload to re-render the card with the new status and button logic
        window.location.reload();
      } else {
        alert("Error suspending status: " + data.message);
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      alert("An error occurred while suspending the status.");
    });
}
