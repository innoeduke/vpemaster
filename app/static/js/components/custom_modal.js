/**
 * Shared Custom Modal Component
 *
 * Provides showCustomConfirm (returns Promise<boolean>) and showCustomAlert
 * (returns Promise<void>) backed by the #custom-modal markup partial in
 * app/templates/components/custom_modal.html. Relies on .custom-modal*
 * styles from agenda-base.css, which are bundled globally via css_all.
 */

window.showCustomConfirm = function (title, message, iconClass = "confirm") {
    return new Promise((resolve) => {
        const modal = document.getElementById("custom-modal");
        const titleEl = document.getElementById("custom-modal-title");
        const messageEl = document.getElementById("custom-modal-message");
        const iconEl = document.getElementById("custom-modal-icon");
        const okBtn = document.getElementById("custom-modal-ok");
        const cancelBtn = document.getElementById("custom-modal-cancel");

        titleEl.textContent = title;
        messageEl.innerHTML = message;
        iconEl.className = "custom-modal-icon " + iconClass;
        iconEl.innerHTML = iconClass === "confirm" ? '<i class="fas fa-question-circle"></i>' : '<i class="fas fa-exclamation-circle"></i>';

        cancelBtn.style.display = "inline-block";
        modal.style.display = "flex";

        const handleOk = () => {
            modal.style.display = "none";
            cleanup();
            resolve(true);
        };

        const handleCancel = () => {
            modal.style.display = "none";
            cleanup();
            resolve(false);
        };

        const cleanup = () => {
            okBtn.removeEventListener("click", handleOk);
            cancelBtn.removeEventListener("click", handleCancel);
        };

        okBtn.addEventListener("click", handleOk);
        cancelBtn.addEventListener("click", handleCancel);
    });
};

window.showCustomAlert = function (title, message, iconClass = "alert") {
    return new Promise((resolve) => {
        const modal = document.getElementById("custom-modal");
        const titleEl = document.getElementById("custom-modal-title");
        const messageEl = document.getElementById("custom-modal-message");
        const iconEl = document.getElementById("custom-modal-icon");
        const okBtn = document.getElementById("custom-modal-ok");
        const cancelBtn = document.getElementById("custom-modal-cancel");

        titleEl.textContent = title;
        messageEl.innerHTML = message;
        iconEl.className = "custom-modal-icon " + iconClass;
        iconEl.innerHTML = '<i class="fas fa-info-circle"></i>';

        cancelBtn.style.display = "none";
        modal.style.display = "flex";

        const handleOk = () => {
            modal.style.display = "none";
            okBtn.removeEventListener("click", handleOk);
            resolve();
        };

        okBtn.addEventListener("click", handleOk);
    });
};