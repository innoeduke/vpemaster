// --- Modal Variables ---
// These are needed by the openContactModal() function in base.html
const contactModal = document.getElementById("contactModal");
const contactForm = document.getElementById("contactForm");
const contactModalTitle = document.getElementById("contactModalTitle");

// --- Pagination State ---
let allContactsCache = []; // Cache of all contacts from API
let filteredContacts = []; // Contacts after applying tab and search filters
let currentPage = 1;
let pageSize = 25;
let sortColumnIndex = 1; // Participation
let sortDirection = 'desc';
let selectedContactIds = new Set(); // Globally tracked selected IDs

/**
 * Fetches all contacts from the API and caches them
 */
async function fetchAndCacheContacts() {
  // Use server-injected data if available (and not empty), to respect server-side filters
  if (typeof INITIAL_CONTACTS !== 'undefined' && INITIAL_CONTACTS && INITIAL_CONTACTS.length > 0) {
    allContactsCache = INITIAL_CONTACTS;
    INITIAL_CONTACTS = null; // Consume once so subsequent refreshes fetch from API
    return allContactsCache;
  }

  try {
    let url = '/api/contacts/all?t=' + new Date().getTime();

    // Append selected term IDs if available (from global variable injected in template)
    if (typeof selectedTermIds !== 'undefined' && Array.isArray(selectedTermIds) && selectedTermIds.length > 0) {
      selectedTermIds.forEach(id => {
        url += `&term=${encodeURIComponent(id)}`;
      });
    } else {
      // If getting terms from URL params directly (fallback)
      const urlParams = new URLSearchParams(window.location.search);
      const termsInfo = urlParams.getAll('term');
      if (termsInfo.length > 0) {
        termsInfo.forEach(id => {
          url += `&term=${encodeURIComponent(id)}`;
        });
      }
    }

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error('Failed to fetch contacts');
    }
    allContactsCache = await response.json();

    return allContactsCache;
  } catch (error) {
    console.error('Error fetching contacts:', error);
    return [];
  }
}

/**
 * Refreshes the contact cache (call after add/edit/delete)
 */
async function refreshContactCache() {

  await fetchAndCacheContacts();
  applyFiltersAndPaginate();
}

/**
 * Applies tab and search filters to cached contacts
 */
function applyFilters() {
  const activeTabItem = document.querySelector(".nav-item.active");
  if (!activeTabItem) {
    filteredContacts = [...allContactsCache];
    return;
  }

  const activeTab = activeTabItem.dataset.type;
  const searchInput = document.getElementById("searchInput");
  const searchTerm = searchInput ? searchInput.value.toUpperCase().trim() : '';

  // Filter by tab
  filteredContacts = allContactsCache.filter(contact => contact.Type === activeTab);

  // Filter by search term
  if (searchTerm) {
    filteredContacts = filteredContacts.filter(contact => {
      const searchableText = [
        contact.Name,
        contact.Phone_Number,
        contact.Date_Created,
        contact.Club,
        contact.Completed_Paths,
        contact.credentials,
        contact.Next_Project,
        contact.Mentor,
        contact.Member_ID
      ].join(' ').toUpperCase();

      return searchableText.includes(searchTerm);
    });
  }

  // Sort filtered contacts
  filteredContacts.sort((a, b) => {
    const aVal = getContactSortValue(a, sortColumnIndex);
    const bVal = getContactSortValue(b, sortColumnIndex);
    const comparison = aVal.localeCompare(bVal, undefined, { numeric: true, sensitivity: 'base' });
    return sortDirection === 'asc' ? comparison : -comparison;
  });
}

/**
 * Returns a sortable string value for a contact based on column index
 */
function getContactSortValue(contact, index) {
  switch (index) {
    case 0: return (contact.Name || '').toLowerCase();
    case 1:
      // Participation: [Role Count]_[Qualified]_[TT Count]_[Attendance]_[Awards]
      return `${String(contact.role_count || 0).padStart(3, '0')}_${contact.is_qualified ? '1' : '0'}_${String(contact.tt_count || 0).padStart(3, '0')}_${String(contact.attendance_count || 0).padStart(3, '0')}_${String(contact.award_count || 0).padStart(3, '0')}`;
    case 2: return (contact.Phone_Number || '').toLowerCase();
    case 3: return (contact.Date_Created || '').toLowerCase();
    case 4: return (contact.Club || '').toLowerCase();
    case 5: return (contact.Completed_Paths || '').toLowerCase();
    case 6: return (contact.credentials || '').toLowerCase();
    case 7: return (contact.Next_Project || '').toLowerCase();
    case 8: return (contact.Mentor || '').toLowerCase();
    default: return '';
  }
}

/**
 * Renders the current page of contacts to the table
 */
function renderContactsPage() {
  const tbody = document.querySelector("#contactsTable tbody");
  if (!tbody) return;

  // Calculate pagination
  const totalPages = Math.ceil(filteredContacts.length / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = Math.min(startIndex + pageSize, filteredContacts.length);
  const pageContacts = filteredContacts.slice(startIndex, endIndex);

  // Clear existing rows
  tbody.innerHTML = '';

  // Render contacts for current page
  pageContacts.forEach(contact => {
    const row = createContactRow(contact);
    tbody.appendChild(row);
  });

  // Update pagination controls
  updatePaginationControls(startIndex, endIndex, filteredContacts.length, totalPages);

  // Hide loading spinner and show table
  const spinner = document.getElementById('contactsLoadingSpinner');
  const table = document.getElementById('contactsTable');
  if (spinner && table) {
    spinner.style.display = 'none';
    table.style.display = 'table';
  }
}

/**
 * Creates a table row element for a contact
 */
function createContactRow(contact) {
  const row = document.createElement('tr');
  row.dataset.type = contact.Type;
  row.dataset.contactId = contact.id;

  // Build participation sort value
  const sortValue = `${String(contact.role_count).padStart(3, '0')}_${contact.is_qualified ? '1' : '0'}_${String(contact.tt_count).padStart(3, '0')}_${String(contact.attendance_count).padStart(3, '0')}_${String(contact.award_count).padStart(3, '0')}`;

  let html = '';
  if (hasEditPermission) {
    const isChecked = selectedContactIds.has(contact.id) ? 'checked' : '';
    html += `<td class="col-checkbox" style="text-align: center;"><input type="checkbox" class="contact-select-checkbox" data-id="${contact.id}" ${isChecked} onchange="handleCheckboxChange(this)"></td>`;
  }

  html += `
    <td class="col-name">
      <div class="contact-name-cell">
        ${(() => {
      if (!contact.Avatar_URL) {
        return `<div class="contact-avatar-placeholder-small"><i class="fas fa-user"></i></div>`;
      }
      let avatarPath = contact.Avatar_URL;
      // If just a filename, prepend root dir
      if (avatarPath.indexOf('/') === -1) {
        const root = (typeof avatarRootDir !== 'undefined') ? avatarRootDir : 'uploads/avatars';
        avatarPath = `${root}/${avatarPath}`;
      }
      return `<img src="/static/${avatarPath}" alt="Avatar" class="contact-avatar-small">`;
    })()}
        <div class="contact-name-info ${canViewAllLogs ? 'clickable-name' : ''}" 
             ${canViewAllLogs ? `onclick="window.location.href='/speech_logs?speaker_id=${contact.id}&view_mode=member'" title="View ${contact.Name}'s speech logs"` : ''}>
          ${contact.Name}
          ${contact.DTM ? '<sup class="dtm-superscript">DTM</sup>' : ''}
          ${contact.Member_ID && contact.Type !== 'Guest' ? `<span class="badge-member-id" style="margin-left: 5px; font-size: 0.8em; vertical-align: text-top; background-color: rgb(231, 231, 228); border-radius: 5px; padding: 2px 5px;">${contact.Member_ID}</span>` : ''}
        </div>
      </div>
    </td>
    <td class="col-part" data-sort="${sortValue}">
      <div class="participation-container">
        ${contact.is_qualified ? '<i class="fas fa-star" title="Qualified Guest" style="color: #ffc107; font-size: 1.1em;"></i>' : ''}
        <a href="/speech_logs?speaker_id=${contact.id}" title="Roles Taken" class="participation-badge badge-roles">
          <i class="fas fa-user-tag"></i> ${contact.role_count}
        </a>
        <a href="/speech_logs?speaker_id=${contact.id}" title="Topic Speeches" class="participation-badge badge-tt">
          <i class="fas fa-comment"></i> ${contact.tt_count}
        </a>
        <a href="/speech_logs?speaker_id=${contact.id}" title="Attendance" class="participation-badge badge-attendance">
          <i class="fas fa-calendar-check"></i> ${contact.attendance_count}
        </a>
        <a href="/speech_logs?speaker_id=${contact.id}" title="Awards Won" class="participation-badge badge-awards">
          <i class="fas fa-trophy"></i> ${contact.award_count}
        </a>
      </div>
    </td>
    <td class="col-phone">${contact.Phone_Number}</td>
    <td class="col-date">${contact.Date_Created}</td>
    <td class="col-club">${contact.Club}</td>
    <td class="col-paths">
      ${contact.Completed_Paths && contact.Completed_Paths !== '-'
      ? contact.Completed_Paths.split('/').map(path => {
        const p = path.trim();
        const abbr = p.substring(0, 2).toLowerCase();
        return `<span class="badge-path path-${abbr}">${p}</span>`;
      }).join(' ')
      : '-'}
    </td>
    <td class="col-creds">${contact.credentials}</td>
    <td class="col-next">${contact.Next_Project}</td>
    <td class="col-mentor">${contact.Mentor}</td>
    ${hasEditPermission ? `
    <td class="col-actions">
      <div class="action-links">
        <button class="icon-btn toggle-connection-btn" onclick="toggleConnection(${contact.id})" title="${contact.is_connected ? 'Connected' : 'Disconnected'}">
          <i class="fas ${contact.is_connected ? 'fa-toggle-on' : 'fa-toggle-off'}" style="color: ${contact.is_connected ? '#28a745' : '#6c757d'}"></i>
        </button>
        <button class="icon-btn edit-contact-btn" onclick="openContactModal(${contact.id})" title="Edit">
          <i class="fas fa-edit"></i>
        </button>
        ${contact.Type === 'Guest' ? `
        <button class="delete-btn icon-btn" onclick="openDeleteModal('/contact/delete/${contact.id}', 'contact')" title="Delete">
          <i class="fas fa-trash-alt"></i>
        </button>
        ` : ''}
      </div>
    </td>
    ` : ''}
  `;

  row.innerHTML = html;
  return row;
}

/**
 * Toggles the connected status of a contact
 */
async function toggleConnection(contactId) {
  try {
    const response = await fetch(`/contact/toggle_connection/${contactId}`, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error('Failed to toggle connection');
    }

    const data = await response.json();
    if (data.success) {
      // Find and update the contact in cache
      const contact = allContactsCache.find(c => c.id === contactId);
      if (contact) {
        contact.is_connected = data.is_connected;
        // Re-render the table without full reload if possible, but simplest is to just re-render current page
        renderContactsPage();
      }
    } else {
      alert(data.message || 'Error toggling connection');
    }
  } catch (error) {
    console.error('Error:', error);
    alert('An error occurred while toggling connection');
  }
}

/**
 * Updates pagination control states and info display
 */
function updatePaginationControls(startIndex, endIndex, totalContacts, totalPages) {
  // Update info text
  const paginationInfo = document.getElementById('paginationInfo');
  if (paginationInfo) {
    if (totalContacts === 0) {
      paginationInfo.textContent = 'No contacts found';
    } else {
      paginationInfo.textContent = `Showing ${startIndex + 1} - ${endIndex} of ${totalContacts} contacts`;
    }
  }

  // Update page indicator
  const currentPageSpan = document.getElementById('currentPage');
  const totalPagesSpan = document.getElementById('totalPages');
  if (currentPageSpan) currentPageSpan.textContent = currentPage;
  if (totalPagesSpan) totalPagesSpan.textContent = totalPages || 1;

  // Update button states
  const firstBtn = document.getElementById('firstPageBtn');
  const prevBtn = document.getElementById('prevPageBtn');
  const nextBtn = document.getElementById('nextPageBtn');
  const lastBtn = document.getElementById('lastPageBtn');

  if (firstBtn) firstBtn.disabled = currentPage === 1;
  if (prevBtn) prevBtn.disabled = currentPage === 1;
  if (nextBtn) nextBtn.disabled = currentPage >= totalPages || totalPages === 0;
  if (lastBtn) lastBtn.disabled = currentPage >= totalPages || totalPages === 0;
}

/**
 * Applies filters and updates pagination
 */
function applyFiltersAndPaginate(resetPage = false) {
  if (resetPage) {
    currentPage = 1;
    localStorage.setItem('contacts_current_page', currentPage);
  }

  applyFilters();

  // Reset to page 1 if current page exceeds total pages
  const totalPages = Math.ceil(filteredContacts.length / pageSize);
  if (currentPage > totalPages && totalPages > 0) {
    currentPage = 1;
  }

  renderContactsPage();

  // Update clear button visibility
  const searchInput = document.getElementById("searchInput");
  const clearBtn = document.getElementById("clear-searchInput");
  if (searchInput && clearBtn) {
    clearBtn.style.display = searchInput.value.trim().length > 0 ? "block" : "none";
  }
}

/**
 * Navigates to a specific page
 */
function goToPage(page) {
  const totalPages = Math.ceil(filteredContacts.length / pageSize);
  currentPage = Math.max(1, Math.min(page, totalPages));
  renderContactsPage();

  // Save state
  localStorage.setItem('contacts_current_page', currentPage);
}

/**
 * Changes the page size
 */
function changePageSize(newSize) {
  pageSize = parseInt(newSize);
  currentPage = 1; // Reset to first page
  renderContactsPage();

  // Save state
  localStorage.setItem('contacts_page_size', pageSize);
}

/**
 * Handles contact form submission and refreshes cache
 */
function handleContactFormSubmit(event) {
  const form = event.target;
  const formData = new FormData(form);

  // Check if this is an AJAX submission (from contacts page)
  if (form.dataset.ajaxSubmit === 'true') {
    event.preventDefault();

    fetch(form.action, {
      method: "POST",
      body: formData,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
    })
      .then((response) => {
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
          return response.json();
        } else {
          throw new Error("Server returned an unexpected response. Please check your permissions and try again.");
        }
      })
      .then((data) => {
        if (data.success) {
          // Close the modal
          if (typeof closeContactModal === 'function') {
            closeContactModal();
          }
          // Refresh the cache
          refreshContactCache();
        } else {
          if (data.duplicate_contact) {
            showDuplicateModal(data.message, data.duplicate_contact);
          } else {
            alert(data.message || "An error occurred while saving the contact.");
          }
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        alert("An error occurred while saving the contact.");
      });
  }
  // Otherwise, let the form submit normally (for other pages like agenda)
}

/**
 * Sets up the search, sort, tab, and pagination functionality
 */
document.addEventListener("DOMContentLoaded", function () {
  const table = document.getElementById("contactsTable");
  const searchInput = document.getElementById("searchInput");
  const clearBtn = document.getElementById("clear-searchInput");
  const tabs = document.querySelectorAll(".nav-item");

  if (!table || !searchInput || !clearBtn) return;

  // Load saved preferences
  const savedPageSize = localStorage.getItem('contacts_page_size');
  if (savedPageSize) {
    pageSize = parseInt(savedPageSize);
    const pageSizeSelect = document.getElementById('pageSizeSelect');
    if (pageSizeSelect) pageSizeSelect.value = pageSize;
  }

  const savedPage = localStorage.getItem('contacts_current_page');
  if (savedPage) {
    currentPage = parseInt(savedPage);
  }

  // Set up contact form for AJAX submission
  const contactForm = document.getElementById('contactForm');
  if (contactForm) {
    contactForm.dataset.ajaxSubmit = 'true';
    contactForm.addEventListener('submit', handleContactFormSubmit);
  }

  // Initialize sorting
  setupContactsTableSorting();

  // Restore saved tab
  const savedTab = localStorage.getItem("contacts_active_tab");
  if (savedTab) {
    const tabToActivate = Array.from(tabs).find(t => t.dataset.type === savedTab);
    if (tabToActivate) {
      tabs.forEach(t => t.classList.remove("active"));
      tabToActivate.classList.add("active");
    }
  }

  // Apply view class based on active tab
  const activeTabItem = document.querySelector(".nav-item.active");
  if (activeTabItem) {
    const activeTab = activeTabItem.dataset.type;
    if (activeTab === "Guest") {
      table.classList.add("guest-view");
      table.classList.remove("member-view");
    } else if (activeTab === "Member") {
      table.classList.remove("guest-view");
      table.classList.add("member-view");
    } else {
      table.classList.remove("guest-view", "member-view");
    }
  }

  // Tab click logic
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");

      // Update view class
      const tabType = tab.dataset.type;
      if (tabType === "Guest") {
        table.classList.add("guest-view");
        table.classList.remove("member-view");
      } else if (tabType === "Member") {
        table.classList.remove("guest-view");
        table.classList.add("member-view");
      } else {
        table.classList.remove("guest-view", "member-view");
      }

      currentPage = 1; // Reset to first page when changing tabs
      applyFiltersAndPaginate();

      // Save state
      localStorage.setItem("contacts_active_tab", tabType);
    });
  });

  // Search input logic
  searchInput.addEventListener("keyup", () => {
    currentPage = 1; // Reset to first page when searching
    applyFiltersAndPaginate();
  });

  clearBtn.addEventListener("click", () => {
    searchInput.value = "";
    currentPage = 1;
    applyFiltersAndPaginate();
  });

  // Pagination button handlers
  const firstPageBtn = document.getElementById('firstPageBtn');
  const prevPageBtn = document.getElementById('prevPageBtn');
  const nextPageBtn = document.getElementById('nextPageBtn');
  const lastPageBtn = document.getElementById('lastPageBtn');
  const pageSizeSelect = document.getElementById('pageSizeSelect');

  if (firstPageBtn) {
    firstPageBtn.addEventListener('click', () => goToPage(1));
  }

  if (prevPageBtn) {
    prevPageBtn.addEventListener('click', () => goToPage(currentPage - 1));
  }

  if (nextPageBtn) {
    nextPageBtn.addEventListener('click', () => goToPage(currentPage + 1));
  }

  if (lastPageBtn) {
    lastPageBtn.addEventListener('click', () => {
      const totalPages = Math.ceil(filteredContacts.length / pageSize);
      goToPage(totalPages);
    });
  }

  if (pageSizeSelect) {
    pageSizeSelect.addEventListener('change', (e) => {
      changePageSize(e.target.value);
    });
  }

  // Fetch and cache all contacts asynchronously (non-blocking)
  fetchAndCacheContacts().then(() => {
    // Initial render after data is loaded
    applyFiltersAndPaginate();

    // Auto-open Contact Modal via ID param
    const urlParams = new URLSearchParams(window.location.search);
    const contactIdToOpen = urlParams.get('id');

    if (contactIdToOpen) {
      // Find the contact in cache
      const targetContact = allContactsCache.find(c => c.id === parseInt(contactIdToOpen));

      if (targetContact) {
        const contactType = targetContact.Type;
        const tabToActivate = Array.from(tabs).find(t => t.dataset.type === contactType);

        if (tabToActivate) {
          tabs.forEach(t => t.classList.remove("active"));
          tabToActivate.classList.add("active");
          applyFiltersAndPaginate();
        }

        // Open the modal
        if (typeof openContactModal === 'function') {
          openContactModal(contactIdToOpen);
        }
      }
    }
  });
});

/**
 * Custom sort setup for the contacts table that works with client-side pagination
 */
function setupContactsTableSorting() {
  const table = document.getElementById("contactsTable");
  if (!table) return;

  const headers = table.querySelectorAll("th.sortable");
  headers.forEach(header => {
    header.addEventListener("click", (e) => {
      // Prevent any other sort listeners (like from main.js) from firing
      e.stopImmediatePropagation();
      e.preventDefault();

      const index = parseInt(header.dataset.columnIndex);
      if (sortColumnIndex === index) {
        sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
      } else {
        sortColumnIndex = index;
        // Default to descending for Participation, ascending for others
        sortDirection = (index === 1) ? 'desc' : 'asc';
      }

      // Update UI
      headers.forEach(h => delete h.dataset.sortDir);
      header.dataset.sortDir = sortDirection;

      // Sort the whole set and go back to page 1
      applyFiltersAndPaginate(true);
    });
  });

  // Set initial UI state
  const initialHeader = Array.from(headers).find(h => parseInt(h.dataset.columnIndex) === sortColumnIndex);
  if (initialHeader) {
    initialHeader.dataset.sortDir = sortDirection;
  }
}


/**
 * Handles individual checkbox changes
 */
function handleCheckboxChange(checkbox) {
  const id = parseInt(checkbox.dataset.id);
  if (checkbox.checked) {
    selectedContactIds.add(id);
  } else {
    selectedContactIds.delete(id);
  }
  updateMergeButtonState();
}

/**
 * Toggles selection of all contacts on the current page
 */
function toggleSelectAll(source) {
  const checkboxes = document.querySelectorAll('.contact-select-checkbox');
  checkboxes.forEach(cb => {
    cb.checked = source.checked;
    const id = parseInt(cb.dataset.id);
    if (source.checked) {
      selectedContactIds.add(id);
    } else {
      selectedContactIds.delete(id);
    }
  });
  updateMergeButtonState();
}

/**
 * Updates the visibility/state of the Merge button based on selection
 */
function updateMergeButtonState() {
  const mergeBtn = document.getElementById('mergeContactsBtn');

  if (mergeBtn) {
    if (selectedContactIds.size >= 2) {
      mergeBtn.style.display = 'inline-block';
    } else {
      mergeBtn.style.display = 'none';
    }
  }

  // Update "Select All" state for current page
  const selectAll = document.getElementById('selectAllContacts');
  const pageCheckboxes = document.querySelectorAll('.contact-select-checkbox');
  if (selectAll && pageCheckboxes.length > 0) {
    // Check if all currently visible checkboxes are in the selected set
    const allSelected = Array.from(pageCheckboxes).every(cb => selectedContactIds.has(parseInt(cb.dataset.id)));
    selectAll.checked = allSelected;
  }
}

/**
 * Handles the click on Merge button - shows custom premium modal
 */
function handleMergeClick() {
  const contactIds = Array.from(selectedContactIds);

  if (contactIds.length < 2) return;

  // Find contact names for confirmation (might be in cache even if not on page)
  // Logic: We might need to fetch if not in cache, but simplified: assume cache has needed
  // In a real paginated API scenario without full cache, we'd fetch details.
  // Here allContactsCache has everything.
  const selectedContacts = allContactsCache.filter(c => selectedContactIds.has(c.id));

  // Logic to identify primary (Oldest Member > Oldest Guest)
  function getSortKey(c) {
    const typePriority = (c.Type !== 'Guest') ? 0 : 1;
    const createdDate = (c.Date_Created && c.Date_Created !== '-') ? c.Date_Created : '9999-99-99';
    return `${typePriority}_${createdDate}_${String(c.id).padStart(10, '0')}`;
  }

  const sortedSelected = [...selectedContacts].sort((a, b) => getSortKey(a).localeCompare(getSortKey(b)));
  const primary = sortedSelected[0];
  const others = sortedSelected.slice(1);

  // Populate Custom Modal
  const modal = document.getElementById('mergeContactModal');
  const countSpan = document.getElementById('mergeCount');
  const primaryDetails = document.getElementById('primaryContactDetails');
  const primaryMeta = document.getElementById('primaryContactMeta');
  const secondaryList = document.getElementById('secondaryContactsList');
  const confirmBtn = document.getElementById('confirmMergeBtn');

  if (countSpan) countSpan.textContent = selectedContacts.length;
  if (primaryDetails) primaryDetails.textContent = primary.Name;
  if (primaryMeta) primaryMeta.textContent = `${primary.Type} • Created: ${primary.Date_Created}`;

  if (secondaryList) {
    secondaryList.innerHTML = others.map(c => `<li><strong>${c.Name}</strong> (${c.Type})</li>`).join('');
  }

  // Setup Confirm Button with once listener
  confirmBtn.onclick = async () => {
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Merging...';

    try {
      const response = await fetch('/contacts/merge', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ contact_ids: contactIds })
      });

      const data = await response.json();
      if (data.success) {
        closeMergeModal();
        // Reset "Select All" and global selection
        const selectAll = document.getElementById('selectAllContacts');
        if (selectAll) selectAll.checked = false;
        selectedContactIds.clear();

        await refreshContactCache();
      } else {
        alert('Error merging contacts: ' + (data.message || 'Unknown error'));
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = '<i class="fas fa-check-circle"></i> Confirm Merge';
      }
    } catch (error) {
      console.error('Error:', error);
      alert('An error occurred during communication with the server.');
      confirmBtn.disabled = false;
      confirmBtn.innerHTML = '<i class="fas fa-check-circle"></i> Confirm Merge';
    }
  };

  modal.style.display = 'block';
}

/**
 * Closes the merge confirmation modal
 */
function closeMergeModal() {
  const modal = document.getElementById('mergeContactModal');
  if (modal) modal.style.display = 'none';

  const confirmBtn = document.getElementById('confirmMergeBtn');
  if (confirmBtn) {
    confirmBtn.disabled = false;
    confirmBtn.innerHTML = '<i class="fas fa-check-circle"></i> Confirm Merge';
  }
}

// Make functions available globally 
window.toggleSelectAll = toggleSelectAll;
window.handleCheckboxChange = handleCheckboxChange;
window.updateMergeButtonState = updateMergeButtonState;
window.handleMergeClick = handleMergeClick;
window.closeMergeModal = closeMergeModal;
window.refreshContactCache = refreshContactCache;

// --- Term Filter Logic ---

/**
 * Toggles the term dropdown visibility
 */
function toggleTermDropdown(event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }
  const menu = document.getElementById('term-dropdown-menu');
  if (menu) {
    if (menu.style.display === 'none' || menu.style.display === '') {
      menu.style.display = 'block';
    } else {
      closeDropdownAndSubmit();
    }
  }
}

/**
 * Toggles all term checkboxes based on the "Select All" checkbox state
 */
function toggleAllTerms(source) {
  const checkboxes = document.querySelectorAll('.term-checkbox');
  checkboxes.forEach(cb => cb.checked = source.checked);
  updateTermSelection();
}

/**
 * Updates the term selection display text and logic
 */
function updateTermSelection() {
  const checkboxes = document.querySelectorAll('.term-checkbox');
  const selectedCheckboxes = Array.from(checkboxes).filter(cb => cb.checked);
  const selectedCount = selectedCheckboxes.length;
  const totalCount = checkboxes.length;

  // Update Count/Range Text
  const btnText = document.getElementById('term-btn-text');
  if (!btnText) return;

  if (selectedCount === totalCount && totalCount > 0) {
    btnText.textContent = "All Terms";
  } else if (selectedCount === 0) {
    btnText.textContent = "0 selected";
  } else {
    const ranges = [];
    // Logic to combine adjacent terms
    // 1. Sort by start date
    selectedCheckboxes.sort((a, b) => {
      const dateA = a.dataset.start || '';
      const dateB = b.dataset.start || '';
      return dateA.localeCompare(dateB);
    });

    if (selectedCheckboxes.length > 0) {
      let currentRange = {
        startLabel: (selectedCheckboxes[0].dataset.label || '').split(' ')[1], // e.g. "Jan-Jun"
        startYear: (selectedCheckboxes[0].dataset.label || '').split(' ')[0],
        endLabel: (selectedCheckboxes[0].dataset.label || '').split(' ')[1],
        endYear: (selectedCheckboxes[0].dataset.label || '').split(' ')[0],
        fullStart: selectedCheckboxes[0].dataset.start,
        fullEnd: selectedCheckboxes[0].dataset.end,
        count: 1
      };

      for (let i = 1; i < selectedCheckboxes.length; i++) {
        const next = selectedCheckboxes[i];
        const prevEnd = new Date(currentRange.fullEnd);
        const nextStart = new Date(next.dataset.start);

        // Check if adjacent: next start is within 1 day of prev end
        const diffTime = Math.abs(nextStart - prevEnd);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

        if (diffDays <= 2) { // 1 day gap (e.g. Jun 30 to Jul 01)
          currentRange.endLabel = (next.dataset.label || '').split(' ')[1];
          currentRange.endYear = (next.dataset.label || '').split(' ')[0];
          currentRange.fullEnd = next.dataset.end;
          currentRange.count++;
        } else {
          ranges.push(formatRange(currentRange));
          currentRange = {
            startLabel: (next.dataset.label || '').split(' ')[1],
            startYear: (next.dataset.label || '').split(' ')[0],
            endLabel: (next.dataset.label || '').split(' ')[1],
            endYear: (next.dataset.label || '').split(' ')[0],
            fullStart: next.dataset.start,
            fullEnd: next.dataset.end,
            count: 1
          };
        }
      }
      ranges.push(formatRange(currentRange));
    }

    btnText.textContent = ranges.join(', ');
  }

  // Helper to format a single range
  function formatRange(range) {
    if (range.count === 1) {
      return `${range.startYear} ${range.startLabel}`;
    }
    const s = (range.startLabel || '').split('-')[0]; // "Jan"
    const e = (range.endLabel || '').split('-')[1];   // "Jun" or "Dec"
    return `${range.startYear} ${s} - ${range.endYear} ${e}`;
  }

  // Update Select All Checkbox State
  const selectAll = document.getElementById('term-select-all');
  if (selectAll) {
    if (selectedCount === totalCount && totalCount > 0) {
      selectAll.checked = true;
      selectAll.indeterminate = false;
    } else if (selectedCount === 0) {
      selectAll.checked = false;
      selectAll.indeterminate = false;
    } else {
      selectAll.checked = false; // Or indeterminate logic if desired, but unchecked is safer default
      // selectAll.indeterminate = true; // Optional based on preference
    }
  }
}

/**
 * Closes the term dropdown and submits the form
 */
function closeDropdownAndSubmit() {
  const menu = document.getElementById('term-dropdown-menu');
  if (menu) {
    menu.style.display = 'none';
  }
  const form = document.getElementById('contacts-term-filter-form');
  if (form) form.submit();
}

// Make term functions globally available
window.toggleTermDropdown = toggleTermDropdown;
window.toggleAllTerms = toggleAllTerms;
window.updateTermSelection = updateTermSelection;
window.closeDropdownAndSubmit = closeDropdownAndSubmit;

// Add event listeners specific to term logic
document.addEventListener('DOMContentLoaded', function () {
  // Initial term updates
  updateTermSelection();

  // Close on click outside
  document.addEventListener('click', function (event) {
    const container = document.getElementById('term-dropdown-container');
    const menu = document.getElementById('term-dropdown-menu');

    if (menu && menu.style.display === 'block' && container && !container.contains(event.target)) {
      closeDropdownAndSubmit();
    }
  });

  // Prevent clicks inside menu from closing it via the document listener
  const termMenu = document.getElementById('term-dropdown-menu');
  if (termMenu) {
    termMenu.addEventListener('click', function (event) {
      event.stopPropagation();
    });
  }
});
