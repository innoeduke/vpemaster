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

/**
 * Fetches all contacts from the API and caches them
 */
async function fetchAndCacheContacts() {
  try {
    const response = await fetch('/api/contacts/all');
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
    case 3: return (contact.Club || '').toLowerCase();
    case 4: return (contact.Completed_Paths || '').toLowerCase();
    case 5: return (contact.credentials || '').toLowerCase();
    case 6: return (contact.Next_Project || '').toLowerCase();
    case 7: return (contact.Mentor || '').toLowerCase();
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

  // Build participation sort value
  const sortValue = `${String(contact.role_count).padStart(3, '0')}_${contact.is_qualified ? '1' : '0'}_${String(contact.tt_count).padStart(3, '0')}_${String(contact.attendance_count).padStart(3, '0')}_${String(contact.award_count).padStart(3, '0')}`;

  row.innerHTML = `
    <td>
      <div class="contact-name-cell">
        ${contact.Avatar_URL 
          ? `<img src="/static/${contact.Avatar_URL}" alt="Avatar" class="contact-avatar-small">`
          : `<div class="contact-avatar-placeholder-small"><i class="fas fa-user"></i></div>`
        }
        <div class="contact-name-info ${canViewAllLogs ? 'clickable-name' : ''}" 
             ${canViewAllLogs ? `onclick="window.location.href='/speech_logs?speaker_id=${contact.id}&view_mode=member'" title="View ${contact.Name}'s speech logs"` : ''}>
          ${contact.Name}
          ${contact.DTM ? '<sup class="dtm-superscript">DTM</sup>' : ''}
          ${contact.Member_ID ? `<span class="badge-member-id" style="margin-left: 5px; font-size: 0.8em; vertical-align: text-top; background-color: rgb(231, 231, 228); border-radius: 5px; padding: 2px 5px;">${contact.Member_ID}</span>` : ''}
        </div>
      </div>
    </td>
    <td data-sort="${sortValue}">
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
    <td>${contact.Phone_Number}</td>
    <td>${contact.Club}</td>
    <td>
      ${contact.Completed_Paths && contact.Completed_Paths !== '-' 
        ? contact.Completed_Paths.split('/').map(path => {
            const p = path.trim();
            const abbr = p.substring(0, 2).toLowerCase();
            return `<span class="badge-path path-${abbr}">${p}</span>`;
          }).join(' ')
        : '-'}
    </td>
    <td>${contact.credentials}</td>
    <td>${contact.Next_Project}</td>
    <td>${contact.Mentor}</td>
    ${hasEditPermission ? `
    <td>
      <div class="action-links">
        <button class="icon-btn" onclick="openContactModal(${contact.id})" title="Edit">
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

  return row;
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
          alert(data.message || "An error occurred while saving the contact.");
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
 * Handles delete form submission and refreshes cache
 */
function handleDeleteFormSubmit(event) {
  event.preventDefault();
  const form = event.target;
  
  fetch(form.action, {
    method: "POST",
    headers: {
      "X-Requested-With": "XMLHttpRequest",
    },
  })
    .then((response) => {
      // Some routes might redirect, some might return JSON
      if (response.redirected) {
        // If it redirected, we should probably refresh anyway
        if (typeof closeDeleteModal === 'function') closeDeleteModal();
        refreshContactCache();
        return;
      }
      return response.json();
    })
    .then((data) => {
      if (data && data.success === false) {
        alert(data.message || "An error occurred while deleting the contact.");
      } else {
        // Assume success if no error reported or if it redirected
        if (typeof closeDeleteModal === 'function') closeDeleteModal();
        refreshContactCache();
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      // Even on error, we refresh cache to be safe
      if (typeof closeDeleteModal === 'function') closeDeleteModal();
      refreshContactCache();
    });
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

  // Set up delete form for AJAX submission
  const deleteForm = document.getElementById('deleteForm');
  if (deleteForm) {
    deleteForm.addEventListener('submit', handleDeleteFormSubmit);
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

// Make refreshContactCache available globally for modal callbacks
window.refreshContactCache = refreshContactCache;
