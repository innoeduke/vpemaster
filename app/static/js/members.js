class TablePaginator {
  constructor(config) {
    this.tableId = config.tableId;
    this.containerId = config.containerId;
    this.pageSize = config.pageSize || 10;
    this.currentPage = 1;
    this.storageKey = config.storageKey;

    this.table = document.getElementById(this.tableId);
    this.container = document.getElementById(this.containerId);

    if (!this.table || !this.container) return;

    this.tbody = this.table.querySelector('tbody');
    this.infoDisplay = this.container.querySelector('.pagination-info');
    this.currentPageDisplay = this.container.querySelector('.current-page-display');
    this.totalPagesDisplay = this.container.querySelector('.total-pages-display');
    this.pageSizeSelect = this.container.querySelector('.page-size-select');

    this.firstBtn = this.container.querySelector('.first-page-btn');
    this.prevBtn = this.container.querySelector('.prev-page-btn');
    this.nextBtn = this.container.querySelector('.next-page-btn');
    this.lastBtn = this.container.querySelector('.last-page-btn');

    this.init();
  }

  init() {
    // Load saved page size
    if (this.storageKey) {
      const savedSize = localStorage.getItem(`${this.storageKey}_page_size`);
      if (savedSize) {
        this.pageSize = parseInt(savedSize);
        if (this.pageSizeSelect) this.pageSizeSelect.value = this.pageSize;
      }
    }

    // Event listeners
    if (this.pageSizeSelect) {
      this.pageSizeSelect.addEventListener('change', (e) => {
        this.pageSize = parseInt(e.target.value);
        this.currentPage = 1;
        if (this.storageKey) {
          localStorage.setItem(`${this.storageKey}_page_size`, this.pageSize);
        }
        this.update();
      });
    }

    if (this.firstBtn) this.firstBtn.addEventListener('click', () => { this.currentPage = 1; this.update(); });
    if (this.prevBtn) this.prevBtn.addEventListener('click', () => { this.currentPage = Math.max(1, this.currentPage - 1); this.update(); });
    if (this.nextBtn) this.nextBtn.addEventListener('click', () => { this.currentPage++; this.update(); });
    if (this.lastBtn) this.lastBtn.addEventListener('click', () => { this.currentPage = this.getTotalPages(); this.update(); });

    this.update();
  }

  getFilteredRows() {
    return Array.from(this.tbody.rows).filter(row => {
      const isHiddenBySearch = row.getAttribute('data-search-hidden') === 'true';
      const isSubRow = row.hasAttribute('data-parent-id');
      return !isHiddenBySearch && !isSubRow;
    });
  }

  getTotalPages() {
    const rows = this.getFilteredRows();
    return Math.ceil(rows.length / this.pageSize) || 1;
  }

  update() {
    const rows = Array.from(this.tbody.rows);
    const filteredRows = this.getFilteredRows();
    const totalPages = this.getTotalPages();

    if (this.currentPage > totalPages) this.currentPage = totalPages;
    if (this.currentPage < 1) this.currentPage = 1;

    const startIndex = (this.currentPage - 1) * this.pageSize;
    const endIndex = startIndex + this.pageSize;

    const visibleRows = new Set(filteredRows.slice(startIndex, endIndex));

    rows.forEach((row) => {
      const parentId = row.getAttribute('data-parent-id');
      if (parentId) {
        const parentRow = this.tbody.querySelector(`tr[data-id="${parentId}"]`);
        if (visibleRows.has(parentRow) && parentRow.classList.contains('expanded')) {
          row.style.display = "";
        } else {
          row.style.display = "none";
        }
      } else {
        if (visibleRows.has(row)) {
          row.style.display = "";
        } else {
          row.style.display = "none";
        }
      }
    });

    const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
    if (this.infoDisplay) {
      if (rows.length === 0) {
        this.infoDisplay.textContent = isChinese ? '没有找到记录' : 'No records found';
      } else {
        this.infoDisplay.textContent = isChinese
          ? `显示第 ${startIndex + 1} - ${Math.min(endIndex, filteredRows.length)} 条记录，共 ${filteredRows.length} 条`
          : `Showing ${startIndex + 1} - ${Math.min(endIndex, filteredRows.length)} of ${filteredRows.length}`;
      }
    }

    if (this.currentPageDisplay) this.currentPageDisplay.textContent = this.currentPage;
    if (this.totalPagesDisplay) this.totalPagesDisplay.textContent = totalPages;

    if (this.firstBtn) this.firstBtn.disabled = this.currentPage === 1;
    if (this.prevBtn) this.prevBtn.disabled = this.currentPage === 1;
    if (this.nextBtn) this.nextBtn.disabled = this.currentPage >= totalPages;
    if (this.lastBtn) this.lastBtn.disabled = this.currentPage >= totalPages;
  }
}

function openUserModal(userId = null, source = null) {
  const modal = document.getElementById('userModal');
  const title = document.getElementById('user-modal-title');
  const form = document.getElementById('user-form');

  if (!modal || !form) return;

  form.reset();
  document.getElementById('user_id').value = '';
  document.getElementById('user_contact_id').value = '';

  const roleSelect = document.getElementById('role_id_select');
  if (roleSelect) {
    Array.from(roleSelect.options).forEach(opt => {
      if (opt.dataset.name === 'Member' || opt.text.trim() === 'Member') {
        opt.selected = true;
      } else {
        opt.selected = false;
      }
    });
  }

  // Resolve the row from `source`. It can be a <tr> directly (row click)
  // or a button inside the row (existing edit-button behavior).
  let tr = null;
  if (source) {
    if (source.tagName === 'TR') {
      tr = source;
    } else if (typeof source.closest === 'function') {
      tr = source.closest('tr');
    }
  }

  if (userId && tr) {
    const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
    title.textContent = isChinese ? '编辑用户' : 'Edit User';
    document.getElementById('user_id').value = userId;
    document.getElementById('user_contact_id').value = tr.dataset.contactId || '';
    document.getElementById('username').value = tr.dataset.username || '';
    document.getElementById('first_name').value = tr.dataset.firstName || '';
    document.getElementById('last_name').value = tr.dataset.lastName || '';
    document.getElementById('email').value = tr.dataset.email || '';
    document.getElementById('phone').value = tr.dataset.phone || '';

    try {
      const userRoles = JSON.parse(tr.dataset.roles || '[]');
      if (userRoles.length > 0 && roleSelect) {
        Array.from(roleSelect.options).forEach(opt => {
          if (userRoles.includes(parseInt(opt.value))) {
            opt.selected = true;
          } else {
            opt.selected = false;
          }
        });
      }
    } catch (e) {
      console.error('Error parsing user roles:', e);
    }

    document.getElementById('password').placeholder = isChinese ? '留空以保持当前密码' : 'Leave blank to keep current';
  } else {
    const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
    title.textContent = isChinese ? '添加新用户' : 'Add New User';
    document.getElementById('password').placeholder = isChinese ? '输入密码...' : 'Enter password...';
  }

  modal.style.display = 'flex';
}

function closeUserModal() {
  const modal = document.getElementById('userModal');
  if (modal) modal.style.display = 'none';
}

async function handleUserSubmit(e) {
  e.preventDefault();

  const duplicateModal = document.getElementById('duplicateModal');
  if (duplicateModal && duplicateModal.style.display === 'flex') {
    return;
  }

  const form = e.target;
  const userId = document.getElementById('user_id').value;
  const url = userId ? `/user/form/${userId}` : '/user/form';

  const formData = new FormData(form);

  try {
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    });

    if (response.redirected) {
      window.location.href = response.url;
      return;
    }

    window.location.reload();
  } catch (error) {
    console.error('Error saving user:', error);
    window.location.reload();
  }
}

function openRemoveUserModal(actionUrl, userName) {
  const deleteModal = document.getElementById("deleteModal");
  const deleteForm = document.getElementById("deleteForm");
  const deleteModalText = document.getElementById("deleteModalText");
  
  if (deleteForm && deleteModal && deleteModalText) {
    deleteForm.action = actionUrl;
    deleteModalText.innerHTML = `
      <strong>Remove "${userName}" from this club?</strong><br><br>
      <span style="font-size: 0.9em; color: #666;">
        Their contact record will be converted from <em>Member</em> to <em>Guest</em>.<br>
        If the user has no other club memberships, their account will also be removed.
      </span>
    `;
    deleteModal.style.display = "flex";
  }
}

let lastCheckedUserValues = { username: '', first_name: '', last_name: '', email: '', phone: '' };

async function checkUserDuplicates() {
  const userId = document.getElementById('user_id').value;
  const contactId = document.getElementById('user_contact_id').value;
  const clubIdElement = document.querySelector('input[name="club_id"]');
  const clubId = clubIdElement ? clubIdElement.value : '';

  if (userId && contactId) return;

  const username = document.getElementById('username').value.trim();
  const firstName = document.getElementById('first_name').value.trim();
  const lastName = document.getElementById('last_name').value.trim();
  const email = document.getElementById('email').value.trim();
  const phone = document.getElementById('phone').value.trim();

  if (!username && !firstName && !lastName && !email && !phone) return;

  if (username === lastCheckedUserValues.username &&
    firstName === lastCheckedUserValues.first_name &&
    lastName === lastCheckedUserValues.last_name &&
    email === lastCheckedUserValues.email &&
    phone === lastCheckedUserValues.phone) {
    return;
  }

  lastCheckedUserValues = { username, first_name: firstName, last_name: lastName, email, phone };

  try {
    const response = await fetch('/user/check_duplicates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username, first_name: firstName, last_name: lastName,
        full_name: `${firstName} ${lastName}`.trim(),
        email, phone, club_id: clubId
      })
    });

    const data = await response.json();
    const duplicateModal = document.getElementById('duplicateModal');
    const duplicateList = document.getElementById('duplicateList');
    const modalTitle = duplicateModal ? duplicateModal.querySelector('h3') : null;
    const proceedWithNewBtn = document.getElementById('proceedWithNew');

    if (data.duplicates && data.duplicates.length > 0) {
      if (!duplicateList || !duplicateModal) return;

      duplicateList.innerHTML = '';
      let hasHardDuplicate = false;

      data.duplicates.forEach(dup => {
        const div = document.createElement('div');
        div.className = 'duplicate-item';

        const info = document.createElement('div');
        info.className = 'duplicate-info';
        const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
        const clubsText = dup.clubs && dup.clubs.length > 0 ? dup.clubs.join(', ') : (isChinese ? '无俱乐部成员身份' : 'No club memberships');

        let membershipNotice = '';
        let buttonText = isChinese ? '邀请用户' : 'Invite User';

        if (dup.in_current_club) {
          if (dup.type === 'User' || dup.has_user) {
            membershipNotice = `<div class="status-text" style="color: #dc3545;">${isChinese ? '已经是该俱乐部的成员。' : 'Already a member of this club.'}</div>`;
            buttonText = isChinese ? '查看成员' : 'View Member';
            hasHardDuplicate = true;
          } else {
            membershipNotice = `<div class="status-text" style="color: #28a745;">${isChinese ? '该俱乐部的现有宾客。' : 'Existing guest in this club.'}</div>`;
            buttonText = isChinese ? '转为用户' : 'Convert to User';
          }
        }

        let nameDisplay = dup.username;
        const first = dup.first_name || '';
        const last = dup.last_name || '';
        if (first || last) nameDisplay = `${first} ${last}`.trim();

        const hasUsername = dup.username && dup.username.toLowerCase() !== 'n/a' && dup.username.trim() !== '';
        const displayNameHtml = (hasUsername && nameDisplay.toLowerCase() !== dup.username.toLowerCase())
          ? `<div class="dup-name">${nameDisplay}</div><div class="dup-username">(${dup.username})</div>`
          : `<div class="dup-name">${nameDisplay}</div>`;

        info.innerHTML = `
          <div class="dup-header">${displayNameHtml}</div>
          <div class="dup-details">
            <div class="dup-club-list"><i class="fas fa-university"></i> ${clubsText}</div>
            ${membershipNotice}
          </div>
        `;

        const actionDiv = document.createElement('div');
        actionDiv.className = 'duplicate-actions';

        const pickBtn = document.createElement('button');
        pickBtn.type = 'button';
        pickBtn.className = 'planner-btn planner-btn-sm planner-btn-info';
        pickBtn.textContent = buttonText;
        pickBtn.addEventListener('click', async () => {
          if (dup.type === 'Contact' && !dup.has_user && dup.in_current_club) {
            document.getElementById('user_contact_id').value = dup.id;
            if (dup.first_name) document.getElementById('first_name').value = dup.first_name;
            if (dup.last_name) document.getElementById('last_name').value = dup.last_name;
            if (dup.email) document.getElementById('email').value = dup.email;
            if (dup.phone) document.getElementById('phone').value = dup.phone;
            duplicateModal.style.display = 'none';
          } else {
            const targetId = dup.type === 'User' ? dup.id : dup.user_id;
            if (!targetId) return;

            if (!dup.in_current_club) {
              try {
                const res = await fetch('/user/request_join', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ target_user_id: targetId, club_id: clubId })
                });
                const joinData = await res.json();
                if (joinData.success) {
                  window.location.reload();
                } else {
                  alert(joinData.error || 'Failed to send request.');
                }
              } catch (err) {
                alert('Error sending request.');
              }
            } else {
              duplicateModal.style.display = 'none';
            }
          }
        });

        actionDiv.appendChild(pickBtn);
        div.appendChild(info);
        div.appendChild(actionDiv);
        duplicateList.appendChild(div);
      });

      if (modalTitle) {
        const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
        modalTitle.textContent = hasHardDuplicate 
          ? (isChinese ? '用户已存在' : 'User Already Exists') 
          : (isChinese ? '发现潜在的重复用户' : 'Potential Duplicate Found');
      }
      if (proceedWithNewBtn) {
        proceedWithNewBtn.style.display = hasHardDuplicate ? 'none' : 'block';
      }

      duplicateModal.style.display = 'flex';
    }
  } catch (err) {
    console.error("Duplication check failed", err);
  }
}

async function loadUsersAsync() {
  const tableBody = document.getElementById('users-table-body');
  if (!tableBody) return;

  try {
    const response = await fetch('/api/settings/users');
    const data = await response.json();

    if (data.success) {
      tableBody.innerHTML = '';

      data.users.forEach((user, index) => {
        const tr = document.createElement('tr');
        tr.className = user.status === 'inactive' ? 'inactive-user' : '';
        tr.dataset.id = user.id;
        tr.dataset.username = user.username;
        tr.dataset.firstName = user.first_name;
        tr.dataset.lastName = user.last_name;
        tr.dataset.email = user.email;
        tr.dataset.phone = user.phone;
        tr.dataset.contactId = user.contact_id;
        tr.dataset.roles = user.roles_json;

        const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
        let rolesHtml = '';
        if (user.best_role) {
          const roleName = user.best_role.name;
          const roleNameLower = roleName.toLowerCase();
          const knownRoles = ['sysadmin', 'clubadmin', 'operator', 'staff', 'member'];
          const badgeClass = knownRoles.includes(roleNameLower) ? `role-${roleNameLower}` : 'role-other';
          let roleDisplay = roleName;
          if (isChinese) {
            if (roleNameLower === 'sysadmin') roleDisplay = '系统管理员';
            else if (roleNameLower === 'clubadmin') roleDisplay = '俱乐部管理员';
            else if (roleNameLower === 'operator') roleDisplay = '操作员';
            else if (roleNameLower === 'staff') roleDisplay = '工作人员';
            else if (roleNameLower === 'member') roleDisplay = '成员';
          }
          rolesHtml = `<span class="roster-role-tag ${badgeClass}">${roleDisplay}</span>`;
        } else {
          rolesHtml = `<em class="text-muted">${isChinese ? '无角色' : 'No Role'}</em>`;
        }

        let pathHtml = '';
        if (user.current_path) {
          pathHtml = `<span class="badge-path path-${user.path_abbr}">${user.current_path}</span>`;
        }

        const contactDisplay = user.contact_name ? `${user.contact_name} (${user.username})` : `<em class="user-not-linked">${isChinese ? '未关联' : 'Not Linked'}</em>`;

        const escapedName = (user.contact_name || user.username).replace(/'/g, "\\'").replace(/"/g, '&quot;');
        let actionsHtml = `
          <div class="action-links">
            <button type="button" class="icon-btn edit-user-btn" onclick="openUserModal('${user.id}', this)" title="${isChinese ? '编辑' : 'Edit'}">
              <i class="fas fa-edit"></i>
            </button>
            <button class="delete-btn icon-btn" onclick="openRemoveUserModal('/user/delete/${user.id}', '${escapedName}')" title="${isChinese ? '移出俱乐部' : 'Remove from Club'}">
              <i class="fas fa-user-minus"></i>
            </button>
          </div>
        `;

        tr.innerHTML = `
          <td class="col-no">${index + 1}</td>
          <td class="col-name"><div class="member-name-cell ${typeof CAN_EDIT_USERS !== 'undefined' && CAN_EDIT_USERS ? 'clickable-cell' : ''}" ${typeof CAN_EDIT_USERS !== 'undefined' && CAN_EDIT_USERS ? `onclick="openUserModal('${user.id}', this.closest('tr'))"` : ''}>${contactDisplay}</div></td>
          <td class="col-roles">${rolesHtml}</td>
          <td class="col-email">${user.email}</td>
          <td class="col-phone">${user.phone || ''}</td>
          <td class="col-mentor">${user.mentor_name}</td>
          <td class="col-path">${pathHtml}</td>
          <td class="col-project">${(user.next_project && user.next_project !== 'null') ? user.next_project : '-'}</td>
          <td class="col-actions">${actionsHtml}</td>
        `;

        tableBody.appendChild(tr);
      });

      if (window.activePaginators && window.activePaginators['user-settings']) {
        window.activePaginators['user-settings'].update();
      }

      const searchInput = document.getElementById('global-settings-search');
      if (searchInput && searchInput.value) {
        searchInput.dispatchEvent(new Event('keyup'));
      }

    } else {
      const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
      tableBody.innerHTML = `<tr><td colspan="9" class="text-danger text-center">${isChinese ? '无法加载用户' : 'Failed to load users'}: ${data.message}</td></tr>`;
    }
  } catch (error) {
    console.error("Error loading users:", error);
    const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
    tableBody.innerHTML = `<tr><td colspan="9" class="text-danger text-center">${isChinese ? '加载用户时出错。' : 'Error loading users.'}</td></tr>`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadUsersAsync();

  // Initialize Paginator
  if (document.getElementById("user-settings-table")) {
    window.activePaginators = window.activePaginators || {};
    window.activePaginators["user-settings"] = new TablePaginator({
      tableId: "user-settings-table",
      containerId: "user-settings",
      pageSize: 10,
      storageKey: "users_table"
    });

    if (typeof setupTableSorting === "function") {
      setupTableSorting("user-settings-table");
    }
  }


  // Duplicate Modal Bindings
  const proceedBtn = document.getElementById('proceedWithNew');
  if (proceedBtn) proceedBtn.onclick = () => document.getElementById('duplicateModal').style.display = 'none';

  const cancelBtn = document.getElementById('cancelSave');
  if (cancelBtn) cancelBtn.onclick = () => {
    document.getElementById('duplicateModal').style.display = 'none';
    closeUserModal();
  };

  const closeDup = document.getElementById('closeDuplicateModal');
  if (closeDup) closeDup.onclick = () => document.getElementById('duplicateModal').style.display = 'none';

  // Duplicate Check Event Listeners
  ['username', 'first_name', 'last_name', 'email', 'phone'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('blur', checkUserDuplicates);
  });

  // Setup Search Filter
  const searchInput = document.getElementById('global-settings-search');
  const searchClear = document.getElementById('clear-global-settings-search');
  
  if (searchInput) {
    searchInput.addEventListener('keyup', () => {
      const filter = searchInput.value.toUpperCase().trim();
      if (searchClear) searchClear.style.display = filter.length > 0 ? "block" : "none";
      
      const tbody = document.getElementById('users-table-body');
      if (tbody) {
        Array.from(tbody.rows).forEach(row => {
          let rowText = "";
          row.querySelectorAll("td").forEach(cell => {
            rowText += cell.textContent.toUpperCase() + " ";
          });
          const isMatch = rowText.includes(filter);
          row.setAttribute('data-search-hidden', isMatch ? 'false' : 'true');
        });
        
        if (window.activePaginators && window.activePaginators['user-settings']) {
          window.activePaginators['user-settings'].currentPage = 1;
          window.activePaginators['user-settings'].update();
        }
      }
    });
  }

  if (searchClear && searchInput) {
    searchClear.addEventListener('click', () => {
      searchInput.value = '';
      searchInput.dispatchEvent(new Event('keyup'));
    });
  }

  // Bulk Import file selector triggers automatic form submit
  const bulkFile = document.getElementById('bulk-import-file');
  const bulkBtn = document.getElementById('bulk-import-btn');
  if (bulkFile && bulkBtn) {
    bulkBtn.addEventListener('click', () => bulkFile.click());
    bulkFile.addEventListener('change', () => {
      if (bulkFile.files.length > 0) {
        document.getElementById('bulk-import-form').submit();
      }
    });
  }
});
