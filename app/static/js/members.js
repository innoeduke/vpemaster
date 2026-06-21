class TablePaginator {
  constructor(config) {
    this.tableId = config.tableId;
    this.containerId = config.containerId;
    this.pageSize = config.pageSize || 10;
    this.currentPage = 1;
    this.storageKey = config.storageKey;
    // Optional total count, used when the table only holds the first
    // page of rows (so the info text and total-pages reflect the real
    // total, not the row count in the DOM).
    this.totalCount = typeof config.totalCount === 'number' ? config.totalCount : null;

    this.table = document.getElementById(this.tableId);
    this.container = document.getElementById(this.containerId);

    if (!this.table || !this.container) return;

    this.tbody = this.table.querySelector('tbody');
    this.infoDisplay = this.container.querySelector('.pagination-info');
    this.pageSizeSelect = this.container.querySelector('.page-size-select');

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
        const newSize = parseInt(e.target.value);
        const oldSize = this.pageSize;
        this.pageSize = newSize;
        this.currentPage = 1;
        if (this.storageKey) {
          localStorage.setItem(`${this.storageKey}_page_size`, this.pageSize);
        }
        // If the table currently holds only the first page and the
        // size changed, refetch the first page at the new size.
        if (initialFirstPageOnly && newSize !== oldSize && this.storageKey === 'users_table') {
          const correctSize = newSize;
          fetch(`/api/settings/users?page=1&per_page=${correctSize}`)
            .then(r => r.ok ? r.json() : null)
            .then(data => {
              if (!data || !data.success || !Array.isArray(data.users)) {
                this.update();
                return;
              }
              const tableBody = document.getElementById('users-table-body');
              if (!tableBody) {
                this.update();
                return;
              }
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
                tr.innerHTML = `<td class="col-no">${index + 1}</td><td class="col-name">${user.username}</td><td class="col-roles"></td><td class="col-email"></td><td class="col-phone"></td><td class="col-mentor"></td><td class="col-path"></td><td class="col-project"></td><td class="col-actions"></td>`;
                tableBody.appendChild(tr);
              });
              this.update();
              fetchRemainingUsers().then(() => this.update());
            })
            .catch(() => this.update());
          return;
        }
        this.update();
      });
    }

    this.update();
  }

  goToPage(page) {
    const totalPages = this.getTotalPages();
    this.currentPage = Math.max(1, Math.min(page, totalPages));
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
    if (this.totalCount !== null) {
      return Math.ceil(this.totalCount / this.pageSize) || 1;
    }
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
    const totalForInfo = this.totalCount !== null ? this.totalCount : filteredRows.length;
    if (this.infoDisplay) {
      if (totalForInfo === 0) {
        this.infoDisplay.textContent = isChinese ? '没有找到记录' : 'No records found';
      } else {
        this.infoDisplay.textContent = isChinese
          ? `显示第 ${startIndex + 1} - ${Math.min(endIndex, totalForInfo)} 条记录，共 ${totalForInfo} 条`
          : `Showing ${startIndex + 1} - ${Math.min(endIndex, totalForInfo)} of ${totalForInfo}`;
      }
    }

    const controlsContainer = this.container.querySelector('.pagination-controls');
    if (controlsContainer && typeof window.renderNumberedPagination === 'function') {
      window.renderNumberedPagination(controlsContainer, this.currentPage, totalPages, (page) => this.goToPage(page));
    }
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

    // Username is locked unless the current viewer is a sysadmin in the
    // super club. The flag is injected by users.html as a JS global.
    const usernameInput = document.getElementById('username');
    if (usernameInput) {
      const isSuperClubSysadmin = (typeof IS_SUPER_CLUB_SYSADMIN !== 'undefined') && IS_SUPER_CLUB_SYSADMIN;
      if (!isSuperClubSysadmin) {
        usernameInput.setAttribute('readonly', 'readonly');
        usernameInput.classList.add('readonly-field');
        usernameInput.title = isChinese ? '只有超级俱乐部的系统管理员可以修改用户名' : 'Only a sysadmin in the super club can change the username';
      } else {
        usernameInput.removeAttribute('readonly');
        usernameInput.classList.remove('readonly-field');
        usernameInput.title = '';
      }
    }

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
    // New users always need to provide a username.
    const usernameInput = document.getElementById('username');
    if (usernameInput) {
      usernameInput.removeAttribute('readonly');
      usernameInput.classList.remove('readonly-field');
      usernameInput.title = '';
    }
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

function openRemoveUserModal(actionUrl, userName, targetUserId) {
  const deleteModal = document.getElementById("deleteModal");
  const deleteForm = document.getElementById("deleteForm");
  const deleteModalIconContainer = document.getElementById("deleteModalIconContainer");
  const deleteModalIcon = document.getElementById("deleteModalIcon");
  const deleteModalTitle = document.getElementById("deleteModalTitle");
  const deleteModalDescription = document.getElementById("deleteModalDescription");
  const deleteModalOkBtn = document.getElementById("deleteModalOkBtn");
  
  if (userName) {
    userName = userName.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
  }
  
  if (deleteModal && deleteModalTitle && deleteModalDescription) {
    if (targetUserId && typeof CURRENT_USER_ID !== 'undefined' && targetUserId === CURRENT_USER_ID) {
      // Self-removal warning mode
      let titleCannotRemove = deleteModal.getAttribute('data-title-cannot-remove') || 'Cannot Remove Yourself';
      let msgCannotRemove = deleteModal.getAttribute('data-msg-cannot-remove') || 'You cannot remove yourself from the club. Please contact another administrator or the system administrator for assistance.';
      let btnOkText = deleteModal.getAttribute('data-btn-ok') || 'OK';

      titleCannotRemove = titleCannotRemove.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
      msgCannotRemove = msgCannotRemove.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
      btnOkText = btnOkText.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');

      if (deleteModalIcon) {
        deleteModalIcon.className = "fas fa-exclamation-triangle";
        deleteModalIconContainer.style.color = "#dd6b20"; // warning orange
      }
      deleteModalTitle.textContent = titleCannotRemove;
      deleteModalDescription.textContent = msgCannotRemove;
      
      if (deleteForm) deleteForm.style.display = "none";
      if (deleteModalOkBtn) {
        deleteModalOkBtn.textContent = btnOkText;
        deleteModalOkBtn.style.display = "block";
      }
    } else {
      // Normal member deletion mode
      let titleTemplate = deleteModal.getAttribute('data-title-remove-template') || 'Remove "{userName}" from this club?';
      let msgDescription = deleteModal.getAttribute('data-msg-remove-description') || 'Their contact record will be converted from Member to Guest.';

      titleTemplate = titleTemplate.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
      msgDescription = msgDescription.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');

      if (deleteModalIcon) {
        deleteModalIcon.className = "fas fa-user-minus";
        deleteModalIconContainer.style.color = "#dc3545"; // danger red
      }
      deleteModalTitle.textContent = titleTemplate.replace('{userName}', userName);
      deleteModalDescription.textContent = msgDescription;
      
      if (deleteForm) {
        deleteForm.style.display = "block";
        deleteForm.action = actionUrl;
      }
      if (deleteModalOkBtn) deleteModalOkBtn.style.display = "none";
    }
    
    deleteModal.style.display = "flex";
  }
}

let lastCheckedUserValues = { username: '', first_name: '', last_name: '', email: '', phone: '' };

async function checkUserDuplicates() {
  const userId = document.getElementById('user_id').value;
  const contactId = document.getElementById('user_contact_id').value;
  const clubIdElement = document.querySelector('input[name="club_id"]');
  const clubId = clubIdElement ? clubIdElement.value : '';

  // Once a contact has been picked from the duplicate dialog (Convert to
  // User), stop re-checking. The dialog has done its job; further checks
  // are noise and re-fire the modal as the user tabs through fields.
  if (contactId) return;
  if (userId) return;

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

/**
 * Flag for whether the table currently holds only the server-rendered
 * first page. When true and the user changes the page size, the JS
 * fetches a correctly-sized first page from the paginated endpoint.
 */
let initialFirstPageOnly = false;

async function loadUsersAsync() {
  const tableBody = document.getElementById('users-table-body');
  if (!tableBody) return;

  // If the server already rendered the first page, skip the full-list
  // fetch and treat the existing rows as the first page. We still need
  // to load the rest in the background for client-side pagination.
  if (typeof INITIAL_USERS !== 'undefined' && INITIAL_USERS && INITIAL_USERS.length > 0) {
    initialFirstPageOnly = true;
    if (window.activePaginators && window.activePaginators['user-settings']) {
      window.activePaginators['user-settings'].update();
    }
    // Background-load the remaining rows (page 2+) for full pagination.
    fetchRemainingUsers().then(() => {
      if (window.activePaginators && window.activePaginators['user-settings']) {
        window.activePaginators['user-settings'].update();
      }
    });
    return;
  }

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

        const nameHtml = user.contact_name
          ? `<span class="contact-name-info">${user.contact_name}</span><span class="member-username">(${user.username})</span>`
          : `<span class="contact-name-info"><em class="user-not-linked">${isChinese ? '未关联' : 'Not Linked'}</em></span>`;

        let avatarHtml;
        if (user.avatar_url) {
          let avatarPath = user.avatar_url;
          if (avatarPath.indexOf('/') === -1) {
            const root = (typeof avatarRootDir !== 'undefined') ? avatarRootDir : 'avatars';
            avatarPath = `${root}/${avatarPath}`;
          }
          avatarHtml = `<img src="/static/${avatarPath}" alt="Avatar" class="contact-avatar-small">`;
        } else {
          avatarHtml = `<div class="contact-avatar-placeholder-small"><i class="fas fa-user"></i></div>`;
        }

        const nameClickable = user.contact_id ? 'clickable-cell' : '';
        const nameOnclick = user.contact_id
          ? `onclick="window.location.href='/speech_logs?speaker_id=${user.contact_id}&view_mode=member'" title="${isChinese ? '查看成员页面' : 'View member page'}"`
          : '';

        const escapedName = (user.contact_name || user.username).replace(/'/g, "\\'").replace(/"/g, '&quot;');
        const toggleBtnHtml = user.contact_id ? `
          <button class="tm-action-btn toggle-connection-btn" onclick="toggleConnection(${user.contact_id})" title="${user.is_connected ? (isChinese ? '已连接' : 'Connected') : (isChinese ? '已断开' : 'Disconnected')}">
            <i class="fas ${user.is_connected ? 'fa-toggle-on' : 'fa-toggle-off'}" style="color: ${user.is_connected ? '#28a745' : '#6c757d'}"></i>
          </button>
        ` : '';
        let actionsHtml = `
          <div class="tm-action-buttons">
            ${toggleBtnHtml}
            <button type="button" class="tm-action-btn edit-user-btn" onclick="openUserModal('${user.id}', this)" title="${isChinese ? '编辑' : 'Edit'}">
              <i class="fas fa-edit"></i>
            </button>
            <button class="tm-action-btn tm-action-btn--danger delete-btn" onclick="openRemoveUserModal('/user/delete/${user.id}', '${escapedName}', ${user.id})" title="${isChinese ? '移出俱乐部' : 'Remove from Club'}">
              <i class="fas fa-user-minus"></i>
            </button>
          </div>
        `;

        tr.innerHTML = `
          <td class="col-no">${index + 1}</td>
          <td class="col-name"><div class="member-name-cell ${nameClickable}" ${nameOnclick}>${avatarHtml}<div class="contact-name-text">${nameHtml}</div></div></td>
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

      initialFirstPageOnly = false;
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

/**
 * Loads the full user list in the background and replaces the
 * server-rendered rows in the tbody with the JS-rendered ones (so
 * paginator + search work over the full set). No visible spinner
 * because the user already sees rows.
 */
async function fetchRemainingUsers() {
  const tableBody = document.getElementById('users-table-body');
  if (!tableBody) return;
  try {
    const response = await fetch('/api/settings/users');
    if (!response.ok) return;
    const data = await response.json();
    if (!data.success || !Array.isArray(data.users)) return;

    // Replace server-rendered rows with the full set so the paginator
    // can navigate across the whole list. Index 1-based for display.
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

      const nameHtml = user.contact_name
        ? `<span class="contact-name-info">${user.contact_name}</span><span class="member-username">(${user.username})</span>`
        : `<span class="contact-name-info"><em class="user-not-linked">${isChinese ? '未关联' : 'Not Linked'}</em></span>`;

      let avatarHtml;
      if (user.avatar_url) {
        let avatarPath = user.avatar_url;
        if (avatarPath.indexOf('/') === -1) {
          const root = (typeof avatarRootDir !== 'undefined') ? avatarRootDir : 'avatars';
          avatarPath = `${root}/${avatarPath}`;
        }
        avatarHtml = `<img src="/static/${avatarPath}" alt="Avatar" class="contact-avatar-small">`;
      } else {
        avatarHtml = `<div class="contact-avatar-placeholder-small"><i class="fas fa-user"></i></div>`;
      }

      const nameClickable = user.contact_id ? 'clickable-cell' : '';
      const nameOnclick = user.contact_id
        ? `onclick="window.location.href='/speech_logs?speaker_id=${user.contact_id}&view_mode=member'" title="${isChinese ? '查看成员页面' : 'View member page'}"`
        : '';
      const escapedName = (user.contact_name || user.username).replace(/'/g, "\\'").replace(/"/g, '&quot;');
      const toggleBtnHtml = user.contact_id ? `
        <button class="tm-action-btn toggle-connection-btn" onclick="toggleConnection(${user.contact_id})" title="${user.is_connected ? (isChinese ? '已连接' : 'Connected') : (isChinese ? '已断开' : 'Disconnected')}">
          <i class="fas ${user.is_connected ? 'fa-toggle-on' : 'fa-toggle-off'}" style="color: ${user.is_connected ? '#28a745' : '#6c757d'}"></i>
        </button>
      ` : '';
      const actionsHtml = `
        <div class="tm-action-buttons">
          ${toggleBtnHtml}
          <button type="button" class="tm-action-btn edit-user-btn" onclick="openUserModal('${user.id}', this)" title="${isChinese ? '编辑' : 'Edit'}">
            <i class="fas fa-edit"></i>
          </button>
          <button class="tm-action-btn tm-action-btn--danger delete-btn" onclick="openRemoveUserModal('/user/delete/${user.id}', '${escapedName}', ${user.id})" title="${isChinese ? '移出俱乐部' : 'Remove from Club'}">
            <i class="fas fa-user-minus"></i>
          </button>
        </div>
      `;

      tr.innerHTML = `
        <td class="col-no">${index + 1}</td>
        <td class="col-name"><div class="member-name-cell ${nameClickable}" ${nameOnclick}>${avatarHtml}<div class="contact-name-text">${nameHtml}</div></div></td>
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
    initialFirstPageOnly = false;
  } catch (error) {
    console.error('Error loading remaining users:', error);
  }
}



// Export functions to global window scope so inline onclick handlers can access them
window.openUserModal = openUserModal;
window.closeUserModal = closeUserModal;
window.openRemoveUserModal = openRemoveUserModal;
window.toggleConnection = toggleConnection;

/**
 * Toggles the connected status of a contact linked to this user.
 * Updates the button icon/title in place without reloading the table.
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
      const isConnected = data.is_connected;
      const buttons = document.querySelectorAll(
        `.toggle-connection-btn[onclick="toggleConnection(${contactId})"]`
      );
      const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
      const titleText = isConnected
        ? (isChinese ? '已连接' : 'Connected')
        : (isChinese ? '已断开' : 'Disconnected');
      const iconClass = isConnected ? 'fa-toggle-on' : 'fa-toggle-off';
      const iconColor = isConnected ? '#28a745' : '#6c757d';
      buttons.forEach(btn => {
        btn.title = titleText;
        const icon = btn.querySelector('i');
        if (icon) {
          icon.className = `fas ${iconClass}`;
          icon.style.color = iconColor;
        }
      });
    } else {
      alert(data.message || 'Error toggling connection');
    }
  } catch (error) {
    console.error('Error:', error);
    alert('An error occurred while toggling connection');
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
      storageKey: "users_table",
      totalCount: (typeof USERS_TOTAL !== 'undefined') ? USERS_TOTAL : null
    });

    if (typeof setupTableSorting === "function") {
      setupTableSorting("user-settings-table");
    }

    // If the server rendered a different number of rows than the
    // user's saved page size, fetch a correctly-sized first page so
    // pagination matches the user's preference. Rows are already on
    // screen, so the swap is invisible.
    const paginator = window.activePaginators["user-settings"];
    if (paginator && initialFirstPageOnly
        && typeof INITIAL_USERS !== 'undefined' && INITIAL_USERS
        && INITIAL_USERS.length !== paginator.pageSize
        && typeof USERS_TOTAL !== 'undefined' && USERS_TOTAL > paginator.pageSize) {
      const correctSize = paginator.pageSize;
      fetch(`/api/settings/users?page=1&per_page=${correctSize}`)
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (!data || !data.success || !Array.isArray(data.users)) return;
          const tableBody = document.getElementById('users-table-body');
          if (!tableBody) return;
          // Replace the server-rendered rows with the correctly-sized
          // first page using the same row format. The rest of the data
          // will be filled in by the background load.
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
            tr.innerHTML = `
              <td class="col-no">${index + 1}</td>
              <td class="col-name">${user.username}</td>
              <td class="col-roles"></td>
              <td class="col-email"></td>
              <td class="col-phone"></td>
              <td class="col-mentor"></td>
              <td class="col-path"></td>
              <td class="col-project"></td>
              <td class="col-actions"></td>
            `;
            tableBody.appendChild(tr);
          });
          paginator.update();
          // Continue loading the rest in the background.
          fetchRemainingUsers().then(() => paginator.update());
        })
        .catch(() => { /* keep server-rendered rows */ });
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

});
