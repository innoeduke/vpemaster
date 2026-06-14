// --- Modal Variables ---
// These are needed by the openContactModal() function in base.html
const contactModal = document.getElementById("contactModal");
const contactForm = document.getElementById("contactForm");
const contactModalTitle = document.getElementById("contactModalTitle");

// --- Pagination State ---
let allContactsCache = []; // Cache of all contacts from API
let filteredContacts = []; // Contacts after applying search filter
let currentPage = 1;
let pageSize = 10;
let sortColumnIndex = null; // null = use backend order (default sort done in DB)
let sortDirection = 'asc';
let selectedContactIds = new Set(); // Globally tracked selected IDs
// Set true when the cache currently holds only the server-rendered first
// page. The background load fills in the rest; the page-size dropdown
// may need to re-fetch a different-sized first page.
let initialFirstPageOnly = false;

/**
 * Fetches all contacts from the API and caches them
 */
async function fetchAndCacheContacts() {
  // Use server-injected data if available (and not empty), to respect server-side filters
  if (typeof INITIAL_CONTACTS !== 'undefined' && INITIAL_CONTACTS && INITIAL_CONTACTS.length > 0) {
    allContactsCache = INITIAL_CONTACTS;
    initialFirstPageOnly = true;
    INITIAL_CONTACTS = null; // Consume once so subsequent refreshes fetch from API
    // Kick off the background load for the rest of the rows (page 2+)
    // so pagination works without waiting for the user to navigate.
    fetchRemainingContacts().then(() => {
      applyFiltersAndPaginate();
    });
    return allContactsCache;
  }

  try {
    let url = '/api/contacts/all?t=' + new Date().getTime();

    const startDateInput = document.getElementById('start_date');
    const endDateInput = document.getElementById('end_date');
    let startDate = startDateInput ? startDateInput.value : null;
    let endDate = endDateInput ? endDateInput.value : null;

    if (!startDate || !endDate) {
      const urlParams = new URLSearchParams(window.location.search);
      if (!startDate) startDate = urlParams.get('start_date');
      if (!endDate) endDate = urlParams.get('end_date');
    }

    if (startDate && endDate) {
      url += `&start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`;
    }

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error('Failed to fetch contacts');
    }
    allContactsCache = await response.json();
    initialFirstPageOnly = false;

    return allContactsCache;
  } catch (error) {
    console.error('Error fetching contacts:', error);
    return [];
  }
}

/**
 * Fetches contacts starting from page 2 and appends them to the cache.
 * Used to fill in the rest of the rows after the server has rendered the
 * first page directly in HTML.
 */
async function fetchRemainingContacts() {
  try {
    const url = '/api/contacts/all?t=' + new Date().getTime();
    const response = await fetch(url);
    if (!response.ok) return;
    const rows = await response.json();
    if (!Array.isArray(rows)) return;
    // Skip the rows already in the cache (the server-rendered first page).
    const seen = new Set(allContactsCache.map(c => c.id));
    const extra = rows.filter(c => !seen.has(c.id));
    allContactsCache = allContactsCache.concat(extra);
    initialFirstPageOnly = false;
  } catch (error) {
    console.error('Error fetching remaining contacts:', error);
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
 * Applies search filter to cached contacts (no tab filter — Members & Guests are merged).
 */
function applyFilters() {
  const searchInput = document.getElementById("searchInput");
  const searchTerm = searchInput ? searchInput.value.toUpperCase().trim() : '';

  // Start with the full cache; no tab filtering.
  filteredContacts = allContactsCache.slice();

  // Filter by search term
  if (searchTerm) {
    filteredContacts = filteredContacts.filter(contact => {
      const typeLabel = getContactTypeLabel(contact);
      const searchableText = [
        contact.Name,
        contact.Phone_Number,
        contact.Email,
        contact.Member_ID,
        contact.display_club_name,
        typeLabel
      ].join(' ').toUpperCase();

      return searchableText.includes(searchTerm);
    });
  }

  // Sort filtered contacts (skip when no column chosen — preserve backend order)
  if (sortColumnIndex !== null) {
    filteredContacts.sort((a, b) => {
      const aVal = getContactSortValue(a, sortColumnIndex);
      const bVal = getContactSortValue(b, sortColumnIndex);
      const comparison = aVal.localeCompare(bVal, undefined, { numeric: true, sensitivity: 'base' });
      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }
}

/**
 * Returns the displayed type label for a contact (e.g. Officer title, Member, or Guest)
 */
function getContactTypeLabel(contact) {
  if (contact.is_officer && contact.officer_title) {
    return contact.officer_title;
  }
  const isMember = contact.Type === 'Member' || contact.Type === 'Past Member';
  return isMember ? 'Member' : 'Guest';
}

/**
 * Returns a sortable string value for a contact based on column index
 */
function getContactSortValue(contact, index) {
  switch (index) {
    case 0: return (contact.Name || '').toLowerCase();
    case 1: return getContactTypeLabel(contact).toLowerCase();
    case 2: return (contact.display_club_name || '').toLowerCase();
    case 3:
      // Participation: [Attendance]_[Role Count]_[Qualified]_[TT Count]_[Awards]
      return `${String(contact.attendance_count || 0).padStart(3, '0')}_${String(contact.role_count || 0).padStart(3, '0')}_${contact.is_qualified ? '1' : '0'}_${String(contact.tt_count || 0).padStart(3, '0')}_${String(contact.award_count || 0).padStart(3, '0')}`;
    case 4: return (contact.Phone_Number || '').toLowerCase();
    case 5: return (contact.Email || '').toLowerCase();
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
  const sortValue = `${String(contact.attendance_count).padStart(3, '0')}_${String(contact.role_count).padStart(3, '0')}_${contact.is_qualified ? '1' : '0'}_${String(contact.tt_count).padStart(3, '0')}_${String(contact.award_count).padStart(3, '0')}`;

  let html = '';
  if (hasEditPermission) {
    const isChecked = selectedContactIds.has(contact.id) ? 'checked' : '';
    html += `<td class="col-checkbox" style="text-align: center;"><input type="checkbox" class="contact-select-checkbox" data-id="${contact.id}" ${isChecked} onchange="handleCheckboxChange(this)"></td>`;
  }

  html += `
    <td class="col-name">
      <div class="contact-name-cell ${canViewMembers && contact.Member_ID && contact.Type !== 'Guest' ? 'clickable-cell' : ''}"
           ${canViewMembers && contact.Member_ID && contact.Type !== 'Guest' ? `onclick="window.location.href='/speech_logs?speaker_id=${contact.id}&view_mode=member'" title="View ${contact.Name}'s member page"` : ''}>
        ${(() => {
      if (!contact.Avatar_URL) {
        return `<div class="contact-avatar-placeholder-small">
                  <i class="fas fa-user"></i>
                </div>`;
      }
      let avatarPath = contact.Avatar_URL;
      // If just a filename, prepend root dir
      if (avatarPath.indexOf('/') === -1) {
        const root = (typeof avatarRootDir !== 'undefined') ? avatarRootDir : 'avatars';
        avatarPath = `${root}/${avatarPath}`;
      }
      return `<img src="/static/${avatarPath}" alt="Avatar" class="contact-avatar-small">`;
    })()}
        <div class="contact-name-text">
          <span class="contact-name-info">
            ${contact.Name}
            ${contact.DTM ? '<sup class="dtm-superscript">DTM</sup>' : ''}
          </span>
          ${contact.Member_ID && contact.Type !== 'Guest' ? `
            <span class="badge-member-id">
              ${contact.Member_ID}
            </span>` : ''}
        </div>
      </div>
    </td>
    <td class="col-type">
      ${(() => {
        if (contact.is_officer && contact.officer_title) {
          return `<span class="contact-type-badge type-officer">${contact.officer_title}</span>`;
        }
        const isMember = contact.Type === 'Member' || contact.Type === 'Past Member';
        const label = isMember ? 'Member' : 'Guest';
        const typeClass = isMember ? 'member' : 'guest';
        return `<span class="contact-type-badge type-${typeClass}">${label}</span>`;
      })()}
    </td>
    <td class="col-home-club">${contact.display_club_name || '-'}</td>
    <td class="col-part" data-sort="${sortValue}">
      <div class="participation-container">
        ${contact.is_qualified ? '<i class="fas fa-star" title="Qualified Guest" style="color: #ffc107; font-size: 1.1em;"></i>' : ''}
        ${canViewMembers ? `
          <a href="/speech_logs?speaker_id=${contact.id}" title="Attendance" class="participation-badge badge-attendance">
            <i class="fas fa-calendar-check"></i> ${contact.attendance_count}
          </a>
          <a href="/speech_logs?speaker_id=${contact.id}" title="Roles Taken" class="participation-badge badge-roles">
            <i class="fas fa-user-tag"></i> ${contact.role_count}
          </a>
          <a href="/speech_logs?speaker_id=${contact.id}" title="Topic Speeches" class="participation-badge badge-tt">
            <i class="fas fa-comment"></i> ${contact.tt_count}
          </a>
          <a href="/speech_logs?speaker_id=${contact.id}" title="Awards Won" class="participation-badge badge-awards">
            <i class="fas fa-trophy"></i> ${contact.award_count}
          </a>
        ` : `
          <span title="Attendance" class="participation-badge badge-attendance">
            <i class="fas fa-calendar-check"></i> ${contact.attendance_count}
          </span>
          <span title="Roles Taken" class="participation-badge badge-roles">
            <i class="fas fa-user-tag"></i> ${contact.role_count}
          </span>
          <span title="Topic Speeches" class="participation-badge badge-tt">
            <i class="fas fa-comment"></i> ${contact.tt_count}
          </span>
          <span title="Awards Won" class="participation-badge badge-awards">
            <i class="fas fa-trophy"></i> ${contact.award_count}
          </span>
        `}
      </div>
    </td>
    <td class="col-phone">${contact.Phone_Number}</td>
    <td class="col-email"><a href="mailto:${contact.Email}" class="contact-email-link">${contact.Email}</a></td>
    ${hasEditPermission ? `
    <td class="col-actions">
      <div class="action-links">
        <button class="icon-btn toggle-connection-btn" onclick="toggleConnection(${contact.id})" title="${contact.is_connected ? 'Connected' : 'Disconnected'}">
          <i class="fas ${contact.is_connected ? 'fa-toggle-on' : 'fa-toggle-off'}" style="color: ${contact.is_connected ? '#28a745' : '#6c757d'}"></i>
        </button>
        <button class="icon-btn edit-contact-btn" onclick="openContactModal(${contact.id})" title="Edit">
          <i class="fas fa-edit"></i>
        </button>
        <button class="delete-btn icon-btn" ${contact.Type !== 'Guest' ? 'disabled title="Only Guest contacts can be deleted. Manage Members via their user account."' : `onclick="openDeleteModal('/contact/delete/${contact.id}', 'contact')" title="Delete"`}>
          <i class="fas fa-trash-alt"></i>
        </button>
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
 * Updates pagination control states and info display using dynamic numbered buttons
 */
function updatePaginationControls(startIndex, endIndex, totalContacts, totalPages) {
  // Update info text
  const paginationInfo = document.getElementById('paginationInfo');
  if (paginationInfo) {
    if (totalContacts === 0) {
      paginationInfo.textContent = (typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN') ? '没有找到联系人' : 'No contacts found';
    } else {
      if (typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN') {
        paginationInfo.textContent = `显示第 ${startIndex + 1} - ${endIndex} 项，共 ${totalContacts} 个联系人`;
      } else {
        paginationInfo.textContent = `Showing ${startIndex + 1} - ${endIndex} of ${totalContacts} contacts`;
      }
    }
  }

  const controlsContainer = document.querySelector('#paginationContainer .pagination-controls');
  if (controlsContainer && typeof window.renderNumberedPagination === 'function') {
    window.renderNumberedPagination(controlsContainer, currentPage, totalPages, goToPage);
  }
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
  const newSizeInt = parseInt(newSize);
  const oldSize = pageSize;
  pageSize = newSizeInt;
  currentPage = 1; // Reset to first page
  localStorage.setItem('contacts_page_size', pageSize);

  // If the cache only holds the server-rendered first page and the new
  // size differs, fetch a correctly-sized first page from the server.
  if (initialFirstPageOnly && newSizeInt !== oldSize) {
    fetch(`/api/contacts/all?page=1&per_page=${newSizeInt}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data && Array.isArray(data.rows)) {
          allContactsCache = data.rows;
          initialFirstPageOnly = true;
          applyFiltersAndPaginate();
          fetchRemainingContacts().then(() => applyFiltersAndPaginate());
          return;
        }
        renderContactsPage();
      })
      .catch(() => renderContactsPage());
    return;
  }

  renderContactsPage();
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
 * Sets up the search, sort, and pagination functionality
 * (tab logic removed — Members & Guests are merged into a single view)
 */
document.addEventListener("DOMContentLoaded", function () {
  const table = document.getElementById("contactsTable");
  const searchInput = document.getElementById("searchInput");
  const clearBtn = document.getElementById("clear-searchInput");

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
  // Pagination size selector handler
  const pageSizeSelect = document.getElementById('pageSizeSelect');
  if (pageSizeSelect) {
    pageSizeSelect.addEventListener('change', (e) => {
      changePageSize(e.target.value);
    });
  }

  // Action Dropdown Logic
  const actionBtn = document.getElementById("action-btn");
  const actionMenu = document.getElementById("action-menu");
  const actionBar = document.querySelector(".contact-action-bar");

  if (actionBtn && actionMenu && actionBar) {
    actionBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      actionMenu.classList.toggle("show");
    });

    document.addEventListener("click", (e) => {
      if (!actionBtn.contains(e.target) && !actionMenu.contains(e.target)) {
        actionMenu.classList.remove("show");
      }
    });

    // Dynamic 'compact-actions' mode for desktop only
    let isChecking = false;
    const resizeObserver = new ResizeObserver(entries => {
      if (isChecking) return;

      const isMobile = window.innerWidth <= 768;

      for (let entry of entries) {
        const bar = entry.target;

        if (isMobile) {
          bar.classList.remove("compact-actions");
          continue;
        }

        const stats = bar.querySelector(".stats-container");
        const filters = bar.querySelector(".contacts-filter-container");

        if (!stats || !filters) continue;

        isChecking = true;
        // Reset to measure natural position
        bar.classList.remove("compact-actions");

        // Detection: vertical stacking OR horizontal overflow
        const isStacked = filters.offsetTop > stats.offsetTop + 15;
        const isOverflowing = bar.scrollWidth > bar.clientWidth + 5;

        if (isStacked || isOverflowing) {
          bar.classList.add("compact-actions");
        }

        // Release lock after measurement
        setTimeout(() => { isChecking = false; }, 50);
      }
    });
    resizeObserver.observe(actionBar);
  }

  // If the server-rendered first page used a different size than the
  // user's saved page size, fetch the correct-sized first page now
  // (rows are already on screen, so this swap is invisible).
  const serverRenderedSize = (typeof INITIAL_CONTACTS !== 'undefined' && INITIAL_CONTACTS)
    ? INITIAL_CONTACTS.length
    : 0;
  if (serverRenderedSize > 0 && serverRenderedSize !== pageSize) {
    const correctSize = pageSize;
    fetch(`/api/contacts/all?page=1&per_page=${correctSize}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data && Array.isArray(data.rows)) {
          // Replace the server-rendered rows with the correctly-sized first page.
          allContactsCache = data.rows;
          initialFirstPageOnly = true;
          applyFiltersAndPaginate();
          // Continue loading the rest in the background.
          fetchRemainingContacts().then(() => applyFiltersAndPaginate());
        }
      })
      .catch(() => { /* fall back to whatever was server-rendered */ });
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
        sortDirection = (index === 3) ? 'desc' : 'asc';
      }

      // Update UI
      headers.forEach(h => delete h.dataset.sortDir);
      header.dataset.sortDir = sortDirection;

      // Sort the whole set and go back to page 1
      applyFiltersAndPaginate(true);
    });
  });

  // Set initial UI state (only if a default sort column was chosen)
  if (sortColumnIndex !== null) {
    const initialHeader = Array.from(headers).find(h => parseInt(h.dataset.columnIndex) === sortColumnIndex);
    if (initialHeader) {
      initialHeader.dataset.sortDir = sortDirection;
    }
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

  const selectedContacts = allContactsCache.filter(c => selectedContactIds.has(c.id));

  // Logic to identify primary (Oldest Member > Oldest Guest)
  function getSortKey(c) {
    const typePriority = (c.Type !== 'Guest') ? 0 : 1;
    const createdDate = (c.Date_Created && c.Date_Created !== '-') ? c.Date_Created : '9999-99-99';
    return `${typePriority}_${createdDate}_${String(c.id).padStart(10, '0')}`;
  }

  const sortedSelected = [...selectedContacts].sort((a, b) => getSortKey(a).localeCompare(getSortKey(b)));

  // Mutable state for primary/secondary
  let currentPrimary = sortedSelected[0];
  let currentOthers = sortedSelected.slice(1);

  const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
  const translateType = (type) => {
    if (isChinese) {
      const mapping = {
        'Guest': '宾客',
        'Member': '会员',
        'Officer': '官员'
      };
      return mapping[type] || type;
    }
    return type;
  };

  // Helper to render modal contents with current primary/secondary state
  function renderMergeModal() {
    const primaryDetails = document.getElementById('primaryContactDetails');
    const primaryMeta = document.getElementById('primaryContactMeta');
    const secondaryList = document.getElementById('secondaryContactsList');

    if (primaryDetails) primaryDetails.textContent = currentPrimary.Name;

    if (primaryMeta) {
      const translatedType = translateType(currentPrimary.Type);
      const createdLabel = isChinese ? '创建日期' : 'Created';
      primaryMeta.textContent = `${translatedType} • ${createdLabel}: ${currentPrimary.Date_Created}`;
    }

    if (secondaryList) {
      secondaryList.innerHTML = currentOthers.map(c =>
        `<li data-contact-id="${c.id}" title="${isChinese ? '点击设为主要联系人' : 'Click to promote to primary'}"><i class="fas fa-arrow-up" style="font-size: 0.7rem; color: #94a3b8;"></i> <strong>${c.Name}</strong> (${translateType(c.Type)})</li>`
      ).join('');

      // Attach click handlers for promotion
      secondaryList.querySelectorAll('li[data-contact-id]').forEach(li => {
        li.addEventListener('click', () => {
          const clickedId = parseInt(li.dataset.contactId, 10);
          const clickedContact = currentOthers.find(c => c.id === clickedId);
          if (!clickedContact) return;

          // Swap: clicked becomes primary, old primary goes to others
          currentOthers = [currentPrimary, ...currentOthers.filter(c => c.id !== clickedId)];
          currentPrimary = clickedContact;
          renderMergeModal();
        });
      });
    }
  }

  // Populate Custom Modal
  const modal = document.getElementById('mergeContactModal');
  const countSpan = document.getElementById('mergeCount');
  const confirmBtn = document.getElementById('confirmMergeBtn');

  if (countSpan) countSpan.textContent = selectedContacts.length;
  renderMergeModal();

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
        body: JSON.stringify({ contact_ids: contactIds, primary_id: currentPrimary.id })
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

/**
 * Redirects to the messages page and opens the compose modal for a specific user
 */
function openMessageModal(userId, contactName) {
  if (!userId) {
    console.error('No user ID found for this contact');
    return;
  }
  // The messages page handles the auto-open logic via 'recipient_id' and 'recipient_name'
  window.location.href = `/messages?recipient_id=${userId}&recipient_name=${encodeURIComponent(contactName)}`;
}

// Make functions available globally 
window.toggleSelectAll = toggleSelectAll;
window.handleCheckboxChange = handleCheckboxChange;
window.updateMergeButtonState = updateMergeButtonState;
window.handleMergeClick = handleMergeClick;
window.closeMergeModal = closeMergeModal;
window.refreshContactCache = refreshContactCache;

// --- Date Filter Logic ---

/**
 * Submits the form when date changes
 */
function updateDateSelection() {
  const form = document.getElementById('contacts-term-filter-form');
  if (form) form.submit();
}

window.updateDateSelection = updateDateSelection;

