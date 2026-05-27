// static/js/main.js

/**
 * Initializes a search input with autocomplete functionality.
 * @param {string} inputId The ID of the search input element.
 * @param {Array<Object>} data The array of objects to search through (e.g., contacts).
 * @param {string} searchKey The key in the data objects to search against (e.g., 'Name').
 * @param {function(Object)} onSelect A callback function to execute when an item is selected.
 */
function initializeAutocomplete(inputId, data, searchKey, onSelect) {
  const searchInput = document.getElementById(inputId);
  if (!searchInput) return;

  let currentFocus;
  searchInput.addEventListener("input", function () {
    const val = this.value;
    closeAllLists();
    if (!val) {
      onSelect(null); // Clear selection if input is empty
      return false;
    }
    currentFocus = -1;

    const suggestions = document.createElement("div");
    suggestions.id = this.id + "autocomplete-list";
    suggestions.classList.add("autocomplete-items");
    this.parentNode.appendChild(suggestions);

    const filteredData = data.filter((item) =>
      item[searchKey].toUpperCase().includes(val.toUpperCase())
    );

    filteredData.forEach((item) => {
      const itemDiv = document.createElement("div");
      itemDiv.innerHTML =
        "<strong>" + item[searchKey].substr(0, val.length) + "</strong>";
      itemDiv.innerHTML += item[searchKey].substr(val.length);
      itemDiv.innerHTML += `<input type='hidden' value='${JSON.stringify(
        item
      )}'>`;
      itemDiv.addEventListener("click", function () {
        const selectedItem = JSON.parse(
          this.getElementsByTagName("input")[0].value
        );
        searchInput.value = selectedItem[searchKey];
        onSelect(selectedItem);
        closeAllLists();
      });
      suggestions.appendChild(itemDiv);
    });
  });

  function closeAllLists(elmnt) {
    const items = document.getElementsByClassName("autocomplete-items");
    for (let i = 0; i < items.length; i++) {
      if (elmnt != items[i] && elmnt != searchInput) {
        items[i].parentNode.removeChild(items[i]);
      }
    }
  }

  document.addEventListener("click", function (e) {
    closeAllLists(e.target);
  });
}

/**
 * Initializes a standard table or list filter search box.
 * @param {string} inputId The ID of the search input element.
 * @param {string} clearBtnId The ID of the clear button for the search input.
 * @param {string} targetSelector The CSS selector for the items to be filtered (e.g., '.speech-log-entry' or '#contactsTable tbody tr').
 * @param {string} textSelector The CSS selector within the target item where the text to be searched is located.
 */
function initializeSearchFilter(
  inputId,
  clearBtnId,
  targetSelector,
  textSelector
) {
  const searchInput = document.getElementById(inputId);
  const clearBtn = document.getElementById(clearBtnId);

  if (!searchInput || !clearBtn) return;

  const filterItems = () => {
    const filter = searchInput.value.toUpperCase();
    const items = document.querySelectorAll(targetSelector);

    clearBtn.style.display = searchInput.value.length > 0 ? "block" : "none";

    items.forEach((item) => {
      const textElement = item.querySelector(textSelector);
      if (textElement) {
        const txtValue = textElement.textContent || textElement.innerText;
        if (txtValue.toUpperCase().indexOf(filter) > -1) {
          item.style.display = "";
        } else {
          item.style.display = "none";
        }
      }
    });
  };

  const clearSearch = () => {
    searchInput.value = "";
    filterItems();
  };

  searchInput.addEventListener("keyup", filterItems);
  clearBtn.addEventListener("click", clearSearch);

  // Initial call to set button visibility
  filterItems();
}

function switchContactTab(tabName) {
  const tabBasic = document.getElementById("tab-basic-info");
  const tabEdu = document.getElementById("tab-education");
  const panelBasic = document.getElementById("panel-basic-info");
  const panelEdu = document.getElementById("panel-education");

  if (tabName === 'basic-info') {
    if (tabBasic) tabBasic.classList.add("active");
    if (tabEdu) tabEdu.classList.remove("active");
    if (panelBasic) panelBasic.style.display = "block";
    if (panelEdu) panelEdu.style.display = "none";
  } else if (tabName === 'education') {
    if (tabBasic) tabBasic.classList.remove("active");
    if (tabEdu) tabEdu.classList.add("active");
    if (panelBasic) panelBasic.style.display = "none";
    if (panelEdu) panelEdu.style.display = "block";
  }
}
window.switchContactTab = switchContactTab;

function openContactModal(contactId) {
  const contactModal = document.getElementById("contactModal");
  const contactForm = document.getElementById("contactForm");
  const contactModalTitle = document.getElementById("contactModalTitle");

  contactForm.reset();
  if (contactId) {
    contactModalTitle.textContent = "Edit Contact";
    const actionUrl = new URL(`/contact/form/${contactId}`, window.location.origin);
    actionUrl.searchParams.set("referer", window.location.href);
    contactForm.action = actionUrl.pathname + actionUrl.search;
    fetch(`/contact/form/${contactId}`, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then((response) => response.json())
      .then((data) => {
        // Populate first_name and last_name instead of name
        document.getElementById("first_name").value = data.contact.first_name || "";
        document.getElementById("last_name").value = data.contact.last_name || "";
        document.getElementById("name").value = data.contact.Name || ""; // Hidden field
        document.getElementById("type").value = data.contact.Type || "Guest"; // Hidden field

        document.getElementById("member_id").value = data.contact.Member_ID || "";
        document.getElementById("email").value = data.contact.Email || "";
        document.getElementById("phone_number").value =
          data.contact.Phone_Number || "";

         let bioText = data.contact.Bio || "";
         bioText = bioText.replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n');
         document.getElementById("bio").value = bioText;
         
         const registeredPathsEl = document.getElementById("registered_paths");
         if (registeredPathsEl) {
           registeredPathsEl.innerHTML = '';
            if (data.contact.registered_paths && data.contact.registered_paths.length > 0) {
              data.contact.registered_paths.forEach(p => {
                const opt = document.createElement("option");
                const statusIcon = p.status && p.status.toLowerCase() === 'completed' ? '✅' : '⏳';
                opt.text = `${statusIcon} ${p.name}`;
                opt.value = p.name;
                if (data.contact.current_path && p.name === data.contact.current_path) {
                  opt.selected = true;
                }
                registeredPathsEl.appendChild(opt);
              });
           } else {
             const opt = document.createElement("option");
             opt.text = "No Paths Registered";
             opt.value = "";
             registeredPathsEl.appendChild(opt);
           }
         }
         document.getElementById("dtm").checked = data.contact.DTM;
        const officerCheckbox = document.getElementById("is_officer");
        if (officerCheckbox) {
          officerCheckbox.checked = data.contact.is_officer;
          officerCheckbox.disabled = !(data.is_clubadmin || data.is_sysadmin);
          if (officerCheckbox.disabled) {
            officerCheckbox.classList.add("disabled-checkbox");
          } else {
            officerCheckbox.classList.remove("disabled-checkbox");
          }
        }

        // Show/hide mentor_id rows based on type
        const memberIdRow = document.getElementById("member_id_container");
        const mentorIdRow = document.getElementById("mentor_id_container");
        const isGuest = data.contact.Type === 'Guest';

        if (memberIdRow) memberIdRow.style.display = 'flex'; // Always show for edit
        if (mentorIdRow) mentorIdRow.style.display = isGuest ? 'none' : 'flex';

        // Handle Avatar Preview
        const avatarImg = document.getElementById("modal-avatar-img");
        const placeholder = document.getElementById("modal-avatar-placeholder");
        const avatarContainer = document.querySelector(".profile-avatar-container");
        const type = data.contact.Type;
        
        if (avatarContainer) {
          avatarContainer.dataset.contactId = data.contact.id;
          avatarContainer.dataset.contactType = type;
          if (type === 'Member' || type === 'Officer') {
            avatarContainer.style.cursor = 'pointer';
            avatarContainer.title = "View Speech Logs";
          } else {
            avatarContainer.style.cursor = 'default';
            avatarContainer.removeAttribute('title');
          }
        }

        if (data.contact.Avatar_URL) {
          let avatarPath = data.contact.Avatar_URL;
          // If just a filename, prepend root dir
          if (avatarPath.indexOf('/') === -1) {
            const root = (typeof avatarRootDir !== 'undefined') ? avatarRootDir : 'uploads/avatars';
            avatarPath = `${root}/${avatarPath}`;
          }
          avatarImg.src = `/static/${avatarPath}`;
          avatarImg.style.display = 'block';
          placeholder.style.display = 'none';
        } else {
          avatarImg.style.display = 'none';
          placeholder.style.display = 'flex';
        }

        // Populate Home Club Selector
        const homeClubSelect = document.getElementById("home_club_id");
        const homeClubRow = document.getElementById("home_club_container");
        if (homeClubSelect && homeClubRow) {
          // Show clubs the user is a member of
          let clubsToShow = data.user_clubs || [];
          const isSysAdmin = data.is_sysadmin;
          const currentClubId = data.current_club_id;

          homeClubSelect.innerHTML = '';
          // If no home club, show None
          if (!data.home_club_id) {
            const noneOption = document.createElement("option");
            noneOption.value = "";
            noneOption.textContent = "None";
            homeClubSelect.appendChild(noneOption);
          }

          if (clubsToShow.length > 0) {
            clubsToShow.forEach(club => {
              const option = document.createElement("option");
              option.value = club.id;
              
              // Handle labels: Exactly as in DB
              option.textContent = club.name;

              // Handle disabling particular options for Club Admins
              if (!isSysAdmin && club.id !== currentClubId) {
                  option.disabled = true;
              }
              
              homeClubSelect.appendChild(option);
            });
            if (data.home_club_id) {
              homeClubSelect.value = data.home_club_id;
            }
          }

          // Visibility and Disabling logic
          homeClubRow.style.display = 'flex'; // Always show now
          
          if (data.user_clubs && data.user_clubs.length <= 1) {
             // If user only in one club, don't allow changing it
             homeClubSelect.disabled = true;
          } else {
             homeClubSelect.disabled = false;
          }
        }

        // Populate Mentor Dropdown
        const mentorSelect = document.getElementById("mentor_id");
        if (mentorSelect) {
          const candidates = data.mentor_candidates || (typeof MENTOR_CANDIDATES !== 'undefined' ? MENTOR_CANDIDATES : []);
          mentorSelect.innerHTML = '<option value="0">None</option>';
          candidates.forEach(m => {
            // Don't list self as mentor
            if (m.id !== data.contact.id) {
              const option = document.createElement("option");
              option.value = m.id;
              option.textContent = m.name;
              mentorSelect.appendChild(option);
            }
          });
          mentorSelect.value = data.contact.mentor_id || 0;
        }

        // Handle Education Accordion Visibility
        const educationWrapper = document.getElementById("educationFieldsWrapper");
        const basicInfoAccordion = document.getElementById("basicInfoAccordion");
        const contactTabs = document.querySelector(".contact-modal-tabs");
        const tabEducation = document.getElementById("tab-education");
        if (type === 'Member' || type === 'Officer') {
          if (educationWrapper) educationWrapper.style.display = "block";
          if (tabEducation) tabEducation.style.display = "inline-block";
          if (contactTabs) contactTabs.style.display = "flex";
          document.getElementById("current_path").value = data.contact.current_path || "";
          document.getElementById("next_project").value = data.contact.next_project || "";
          document.getElementById("credentials").value = data.contact.credentials || "";
        } else {
          if (educationWrapper) educationWrapper.style.display = "none";
          if (tabEducation) tabEducation.style.display = "none";
          if (contactTabs) contactTabs.style.display = "none";
        }

        switchContactTab('basic-info');
      });
  } else {
    contactModalTitle.textContent = "Add Guest";
    const actionUrl = new URL("/contact/form", window.location.origin);
    actionUrl.searchParams.set("referer", window.location.href);
    contactForm.action = actionUrl.pathname + actionUrl.search;
    
    const contactTabs = document.querySelector(".contact-modal-tabs");
    if (contactTabs) contactTabs.style.display = "none";
    const educationWrapper = document.getElementById("educationFieldsWrapper");
    if (educationWrapper) educationWrapper.style.display = "none";

    // Hide mentor_id row for new contacts (default is Guest)
    const memberIdRow = document.getElementById("member_id_container");
    const mentorIdRow = document.getElementById("mentor_id_container");
    const homeClubRow = document.getElementById("home_club_container");

    if (memberIdRow) memberIdRow.style.display = 'flex'; // Keep visible to allow entry
    if (mentorIdRow) mentorIdRow.style.display = 'none';
    if (homeClubRow) homeClubRow.style.display = 'none'; // Only show if we have clubs to pick from

    // Reset Avatar for New Entry
    const avatarContainer = document.querySelector(".profile-avatar-container");
    if (avatarContainer) {
      delete avatarContainer.dataset.contactId;
      delete avatarContainer.dataset.contactType;
      avatarContainer.style.cursor = 'default';
      avatarContainer.removeAttribute('title');
    }
    document.getElementById("modal-avatar-img").style.display = 'none';
    document.getElementById("modal-avatar-placeholder").style.display = 'flex';

    const officerCheckbox = document.getElementById("is_officer");
    if (officerCheckbox) {
      officerCheckbox.checked = false;
    }

    switchContactTab('basic-info');
  }
  contactModal.style.display = "flex";
}

function closeContactModal() {
  const contactModal = document.getElementById("contactModal");
  if (contactModal) contactModal.style.display = "none";
}

function showDuplicateModal(message, duplicateData) {
  if (typeof closeContactModal === 'function') closeContactModal();
  const modal = document.getElementById('duplicateContactModal');
  if (!modal) {
    if (typeof showCustomAlert === 'function') {
      showCustomAlert("Duplicate Contact", message);
    } else {
      alert(message);
    }
    return;
  }

  const msgEl = document.getElementById('duplicateMessage');
  const nameEl = document.getElementById('dupName');
  const emailEl = document.getElementById('dupEmail');
  const phoneEl = document.getElementById('dupPhone');

  if (msgEl) msgEl.textContent = message;
  if (nameEl) nameEl.textContent = duplicateData.name || '-';
  if (emailEl) emailEl.textContent = duplicateData.email || '-';
  if (phoneEl) phoneEl.textContent = duplicateData.phone || '-';

  // Configure "View Existing" button
  const viewBtn = document.getElementById('viewDupBtn');
  if (viewBtn) {
    viewBtn.onclick = function () {
      closeDuplicateModal();
      if (typeof closeContactModal === 'function') closeContactModal();
      if (typeof openContactModal === 'function') openContactModal(duplicateData.id);
    };
  }

  modal.style.display = 'flex';
}

function closeDuplicateModal() {
  const modal = document.getElementById('duplicateContactModal');
  if (modal) modal.style.display = 'none';
}

window.closeDuplicateModal = closeDuplicateModal;
window.showDuplicateModal = showDuplicateModal;

function previewAvatar(input) {
  if (input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = function (e) {
      const avatarImg = document.getElementById("modal-avatar-img");
      const placeholder = document.getElementById("modal-avatar-placeholder");
      avatarImg.src = e.target.result;
      avatarImg.style.display = 'block';
      placeholder.style.display = 'none';
    }
    reader.readAsDataURL(input.files[0]);
  }
}

function navigateToSpeechLogs() {
  const avatarContainer = document.querySelector(".profile-avatar-container");
  if (avatarContainer) {
    const contactId = avatarContainer.dataset.contactId;
    const type = avatarContainer.dataset.contactType;
    if (contactId && (type === 'Member' || type === 'Officer')) {
      window.location.href = `/speech_logs?view_mode=member&speaker_id=${contactId}`;
    }
  }
}
window.navigateToSpeechLogs = navigateToSpeechLogs;

document.addEventListener("DOMContentLoaded", function () {
  const navPane = document.getElementById("nav-pane");
  const navOverlay = document.getElementById("nav-overlay");

  // Function to close the nav
  function closeNav() {
    if (navPane.classList.contains("expanded")) {
      navPane.classList.remove("expanded");
    }
  }

  if (navOverlay) {
    navOverlay.addEventListener("click", closeNav);
  }

  // Contact Modal Type Change Listener
  const typeSelect = document.getElementById("type");
  const educationWrapper = document.getElementById("educationFieldsWrapper");
  if (typeSelect && educationWrapper) {
    typeSelect.addEventListener("change", function () {
      if (this.value === 'Member' || this.value === 'Officer') {
        educationWrapper.style.display = 'block';
      } else {
        educationWrapper.style.display = 'none';
      }
    });
  }
});

/**
 * Sorts an HTML table.
 * @param {HTMLTableElement} table The table to sort
 * @param {number} columnIndex The index of the column to sort
 * @param {boolean} asc Whether to sort in ascending order
 * @param {string|null} sortType Optional explicit sort type ('numeric', 'text', 'checkbox')
 */
function sortTableByColumn(table, columnIndex, asc = true, sortType = null) {
  const tbody = table.querySelector("tbody");
  const rows = Array.from(tbody.querySelectorAll("tr"));
  const direction = asc ? 1 : -1;

  // Check column type based on the first data cell
  const firstCell =
    rows[0] && rows[0].querySelector(`td:nth-child(${columnIndex + 1})`);
  let colType = sortType || "text"; // Use provided type or default to text

  if (!sortType && firstCell) {
    const firstCellCheckbox = firstCell.querySelector('input[type="checkbox"]');
    const firstCellText = firstCell.textContent.trim();

    if (firstCellCheckbox) {
      colType = "checkbox";
    } else if (firstCellText.length > 0 && !isNaN(parseFloat(firstCellText))) {
      colType = "numeric";
    }
  }

  const sortedRows = rows.sort((a, b) => {
    const aCell = a.querySelector(`td:nth-child(${columnIndex + 1})`);
    const bCell = b.querySelector(`td:nth-child(${columnIndex + 1})`);
    if (!aCell || !bCell) return 0;

    // Check for custom sort value
    if (aCell.dataset.sort !== undefined && bCell.dataset.sort !== undefined) {
      return aCell.dataset.sort.localeCompare(bCell.dataset.sort) * direction;
    }

    switch (colType) {
      case "checkbox":
        const aChecked = aCell.querySelector('input[type="checkbox"]').checked;
        const bChecked = bCell.querySelector('input[type="checkbox"]').checked;
        return (aChecked - bChecked) * direction;

      case "numeric":
        const aNum = parseFloat(aCell.textContent.trim()) || 0;
        const bNum = parseFloat(bCell.textContent.trim()) || 0;
        return (aNum - bNum) * direction;

      default: // "text"
        const aVal = aCell.textContent.trim();
        const bVal = bCell.textContent.trim();
        return aVal.localeCompare(bVal) * direction;
    }
  });

  // Remove all existing rows from tbody
  while (tbody.firstChild) {
    tbody.removeChild(tbody.firstChild);
  }

  // Re-add the sorted rows
  tbody.append(...sortedRows);
}

/**
 * REUSABLE HELPER: Attaches click listeners to a table's sortable headers.
 */
function setupTableSorting(tableId) {
  const table = document.getElementById(tableId);
  if (!table) return;

  table.querySelectorAll("th.sortable").forEach((headerCell) => {
    headerCell.addEventListener("click", () => {
      // Adjust column index to be 0-based for the sort function
      // HTML data-column-index is 1-based, but sort function expects 0-based
      const columnIndex = parseInt(headerCell.dataset.columnIndex, 10);
      const currentDir = headerCell.dataset.sortDir;
      const newDir = currentDir === "asc" ? "desc" : "asc";
      const sortType = headerCell.dataset.sortType || null;

      if (typeof sortTableByColumn === "function") {
        sortTableByColumn(table, columnIndex, newDir === "asc", sortType);
      } else {
        console.error(
          "sortTableByColumn function not found. Was main.js loaded?"
        );
        return;
      }

      table
        .querySelectorAll("th.sortable")
        .forEach((th) => delete th.dataset.sortDir);

      headerCell.dataset.sortDir = newDir;
    });
  });
}

/**
 * REUSABLE HELPER: Attaches keyup/click listeners to a search box for filtering a table.
 */
function setupTableFilter(tableId, inputId, clearId) {
  const table = document.getElementById(tableId);
  const searchInput = document.getElementById(inputId);
  const clearButton = document.getElementById(clearId);

  if (!table || !searchInput || !clearButton) return;

  const tbody = table.querySelector("tbody");
  if (!tbody) return;

  const filterTable = () => {
    const filter = searchInput.value.toUpperCase().trim();
    const rows = tbody.querySelectorAll("tr");
    clearButton.style.display = filter.length > 0 ? "block" : "none";

    rows.forEach((row) => {
      let rowText = "";
      // Get text from all cells except the last one (Actions)
      row.querySelectorAll("td:not(:last-child)").forEach((cell) => {
        rowText += cell.textContent.toUpperCase() + " ";
      });

      if (rowText.includes(filter)) {
        row.style.display = "";
      } else {
        row.style.display = "none";
      }
    });
  };

  const clearSearch = () => {
    searchInput.value = "";
    filterTable();
  };

  searchInput.addEventListener("keyup", filterTable);
  clearButton.addEventListener("click", clearSearch);

  // Initial setup
  filterTable();
}

/**
 * REUSABLE HELPER: Sets up accordion functionality
 */
function setupAccordions(container = document) {
  // Clone and replace to remove old listeners (simple way to avoid duplicates)
  // Or just check class? No, straightforward approach:

  // Actually, calling this on page load is fine.
  // If called again (e.g. after dynamic content), we want to make sure we don't double bind.
  // The contacts modal is static HTML included in the page, so once is enough.

  const acc = container.querySelectorAll(".accordion");
  acc.forEach(btn => {
    // Remove old listener if any? Hard to do anon function.
    // Use a property flag.
    if (btn.dataset.accInit) return;
    btn.dataset.accInit = "true";

    btn.addEventListener("click", function () {
      // Mutual exclusion logic for contact modal accordions
      const isContactModalAccordion = this.closest("#contactForm");

      if (isContactModalAccordion) {
        const allAccs = isContactModalAccordion.querySelectorAll(".accordion");
        allAccs.forEach(otherBtn => {
          if (otherBtn !== this) {
            otherBtn.classList.remove("active");
            const otherPanel = otherBtn.nextElementSibling;
            otherPanel.style.maxHeight = null;
          }
        });
      }

      this.classList.toggle("active");
      var panel = this.nextElementSibling;
      if (panel.style.maxHeight && panel.style.maxHeight !== "0px") {
        panel.style.maxHeight = null;

        // "Opposite action" logic: if we just collapsed one, expand the other
        if (isContactModalAccordion) {
          const otherBtn = Array.from(isContactModalAccordion.querySelectorAll(".accordion")).find(b => b !== this);
          if (otherBtn) {
            otherBtn.classList.add("active");
            const otherPanel = otherBtn.nextElementSibling;
            otherPanel.style.maxHeight = otherPanel.scrollHeight + "px";
          }
        }
      } else {
        panel.style.maxHeight = panel.scrollHeight + "px";
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", function () {
  setupAccordions();

  // --- Global Delete Modal AJAX Handler ---
  const deleteForm = document.getElementById('deleteForm');
  if (deleteForm) {
    deleteForm.addEventListener('submit', function (e) {
      // If another handler already prevented default (e.g. specialized logic), skip
      if (e.defaultPrevented) return;

      e.preventDefault();
      const form = e.target;

      fetch(form.action, {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
      })
        .then((response) => {
          // Handle redirects if any (though usually we expect JSON)
          if (response.redirected) {
            if (typeof closeDeleteModal === 'function') closeDeleteModal();
            location.reload();
            return;
          }
          if (!response.ok) {
            return response.text().then(text => {
              throw new Error(`Server returned ${response.status}: ${text.substring(0, 100)}...`);
            });
          }
          return response.json().catch(() => {
            throw new Error("Invalid JSON response from server");
          });
        })
        .then((data) => {
          if (data) {
            if (data.success) {
              if (typeof closeDeleteModal === 'function') closeDeleteModal();

              // Handle specialized refresh if available, otherwise reload
              if (typeof refreshContactCache === 'function') {
                refreshContactCache();
              } else {
                location.reload();
              }
            } else {
              if (data.logs && typeof showUsageWarningModal === 'function') {
                if (typeof closeDeleteModal === 'function') closeDeleteModal();
                const usageId = data.id || data.session_type_id;
                const usageType = data.type || 'session';
                showUsageWarningModal(data.message, data.logs, usageId, usageType);
              } else {
                alert(data.message || "An error occurred while deleting the item.");
              }
            }
          }
        })
        .catch((error) => {
          console.error("Delete Error:", error);
          alert("An error occurred while deleting the item.");
        });
    });
  }
});

/**
 * Show a premium-style notification
 * @param {string} message The message to display
 * @param {string} type The type of notification ('info', 'warning', 'success', 'error')
 */
function showNotification(message, type = 'info') {
  const notification = document.createElement('div');
  notification.className = `notification notification-${type}`;
  notification.textContent = message;

  document.body.appendChild(notification);

  setTimeout(() => {
    notification.classList.add('show');
  }, 10);

  setTimeout(() => {
    notification.classList.remove('show');
    setTimeout(() => notification.remove(), 300);
  }, 3000);
}

/**
 * Safely copies text to the clipboard, with fallback for insecure/non-supported contexts.
 * Returns a Promise that resolves when the text is copied.
 * @param {string} text The text to copy
 * @returns {Promise<void>}
 */
function safeCopyText(text) {
  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    return navigator.clipboard.writeText(text);
  }
  
  // Fallback using older document.execCommand API
  return new Promise((resolve, reject) => {
    try {
      const textArea = document.createElement('textarea');
      textArea.value = text;
      // Prevent scrolling on mobile/focused views
      textArea.style.top = '0';
      textArea.style.left = '0';
      textArea.style.position = 'fixed';
      textArea.style.opacity = '0';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      
      const successful = document.execCommand('copy');
      document.body.removeChild(textArea);
      
      if (successful) {
        resolve();
      } else {
        reject(new Error('execCommand copy returned false'));
      }
    } catch (err) {
      reject(err);
    }
  });
}
window.safeCopyText = safeCopyText;

