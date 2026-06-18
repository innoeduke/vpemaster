
    // --- Create Modal Logic ---
    const createModal = document.getElementById("createLinkModal");
    function openCreateModal() {
        createModal.style.display = "flex";
    }
    function closeCreateModal() {
        createModal.style.display = "none";
    }

    // --- Edit Modal Logic ---
    const editModal = document.getElementById("editLinkModal");
    const editForm = document.getElementById("editLinkForm");
    const editCodeDisplay = document.getElementById("edit_code_display");
    const editMeetingNumber = document.getElementById("edit_meeting_number");
    const editExpiresAt = document.getElementById("edit_expires_at");
    const editMaxFiles = document.getElementById("edit_max_files");
    const editMaxFileSize = document.getElementById("edit_max_file_size");
    const editDescription = document.getElementById("edit_description");

    function openEditModal(linkData) {
        editForm.action = `/uploads/edit/${linkData.id}`;
        editCodeDisplay.value = linkData.code;
        editMeetingNumber.value = linkData.meeting_number;
        editExpiresAt.value = linkData.expires_at;
        editMaxFiles.value = linkData.max_files;
        editMaxFileSize.value = linkData.max_file_size;
        editDescription.value = linkData.description;
        editModal.style.display = "flex";
    }

    function closeEditModal() {
        editModal.style.display = "none";
    }

    // --- Toggle Active Switch AJAX Logic ---
    function toggleLinkStatus(linkId, checkbox) {
        const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
        fetch(`/uploads/toggle/${linkId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update switch text
                const container = checkbox.closest('.switch-container');
                if (container) {
                    const switchText = container.querySelector('.switch-text');
                    if (switchText) {
                        switchText.textContent = data.is_active 
                            ? (isChinese ? '激活' : 'Active') 
                            : (isChinese ? '禁用' : 'Disabled');
                    }
                }
            } else {
                checkbox.checked = !checkbox.checked; // Revert switch if failure
                alert((isChinese ? "无法更新状态: " : "Failed to update status: ") + data.message);
            }
        })
        .catch(error => {
            checkbox.checked = !checkbox.checked; // Revert
            console.error("Error:", error);
            alert(isChinese ? "发生错误，请重试。" : "An error occurred. Please try again.");
        });
    }

    // --- Click-to-copy utility ---
    function copyLink(text, button) {
        safeCopyText(text).then(() => {
            const container = button.closest('.copy-btn-container');
            const tooltip = container.querySelector('.copy-tooltip');
            if (tooltip) {
                tooltip.classList.add('show');
                setTimeout(() => {
                    tooltip.classList.remove('show');
                }, 1500);
            }
        }).catch(err => {
            console.error('Could not copy text: ', err);
        });
    }

    // Close modals on clicking outside of container
    window.addEventListener("click", (event) => {
        if (event.target === createModal) {
            closeCreateModal();
        }
        if (event.target === editModal) {
            closeEditModal();
        }
    });
