
class TablePaginator {
  constructor(config) {
    this.tableId = config.tableId;
    this.containerId = config.containerId;
    this.pageSize = config.pageSize || 10;
    this.currentPage = 1;
    this.storageKey = config.storageKey;

    this.table = document.getElementById(this.tableId);
    this.container = document.getElementById(this.containerId);

    if (!this.table) return;

    this.init();

    // Recalculate page size dynamically on resize
    window.addEventListener('resize', () => {
      const oldSize = this.pageSize;
      this.updatePageSize();
      if (oldSize !== this.pageSize) {
        this.update();
      }
    });
  }

  init() {
    this.updatePageSize();
    this.update();
  }

  updatePageSize() {
    if (!this.table) return;
    const style = window.getComputedStyle(this.table);
    const paddingLeft = parseFloat(style.paddingLeft) || 0;
    const paddingRight = parseFloat(style.paddingRight) || 0;
    const paddingTop = parseFloat(style.paddingTop) || 0;
    const paddingBottom = parseFloat(style.paddingBottom) || 0;
    
    let parent = this.table;
    let contentHeight = 0;
    while (parent) {
      if (parent.clientHeight > 0 && window.getComputedStyle(parent).overflowY !== 'visible') {
        const pStyle = window.getComputedStyle(parent);
        const pTop = parseFloat(pStyle.paddingTop) || 0;
        const pBottom = parseFloat(pStyle.paddingBottom) || 0;
        contentHeight = parent.clientHeight - pTop - pBottom;
        break;
      }
      parent = parent.parentElement;
    }
    if (contentHeight <= 0) {
      contentHeight = window.innerHeight - 300;
    }

    let rowHeight = 45;
    const tbody = this.table.querySelector('tbody');
    const tempRow = tbody ? tbody.querySelector('tr:not(.empty-row)') : this.table.querySelector('tr:not(.empty-row)');
    if (tempRow) {
      const originalDisplay = tempRow.style.display;
      tempRow.style.setProperty('display', '', 'important');
      rowHeight = tempRow.offsetHeight || 45;
      tempRow.style.setProperty('display', originalDisplay);
    }
    const rowsCount = Math.floor(contentHeight / rowHeight);
    this.pageSize = Math.max(1, rowsCount);
  }

  goToPage(page) {
    const totalPages = this.getTotalPages();
    this.currentPage = Math.max(1, Math.min(page, totalPages));
    this.update();
  }

  getFilteredRows() {
    const tbody = this.table.querySelector('tbody') || this.table;
    return Array.from(tbody.querySelectorAll('tr')).filter(row => !row.classList.contains('empty-row'));
  }

  getTotalPages() {
    const rows = this.getFilteredRows();
    return Math.ceil(rows.length / this.pageSize) || 1;
  }

  update() {
    const rows = this.getFilteredRows();
    const totalPages = this.getTotalPages();

    if (this.currentPage > totalPages) this.currentPage = totalPages;
    if (this.currentPage < 1) this.currentPage = 1;

    const startIndex = (this.currentPage - 1) * this.pageSize;
    const endIndex = startIndex + this.pageSize;

    const visibleRows = new Set(rows.slice(startIndex, endIndex));

    rows.forEach((row) => {
      row.style.setProperty('display', visibleRows.has(row) ? '' : 'none', 'important');
    });

    const emptyState = this.table.querySelector('.empty-row');
    if (emptyState) {
      emptyState.style.setProperty('display', rows.length === 0 ? '' : 'none', 'important');
    }

    if (this.container) {
      const displayPages = Math.max(1, totalPages);
      const displayCurrentPage = this.currentPage || 1;
      
      let html = '';
      
      // Previous button
      const prevDisabled = displayCurrentPage === 1 ? 'disabled' : '';
      html += `
          <button class="msg-pagination-btn" ${prevDisabled} data-page="${displayCurrentPage - 1}" title="Previous Page">
              <i class="fas fa-chevron-left"></i> Prev
          </button>
      `;
      
      const maxVisible = 5;
      let startPage = Math.max(1, displayCurrentPage - Math.floor(maxVisible / 2));
      let endPage = Math.min(displayPages, startPage + maxVisible - 1);
      
      if (endPage - startPage + 1 < maxVisible) {
          startPage = Math.max(1, endPage - maxVisible + 1);
      }
      
      if (startPage > 1) {
          html += `<button class="msg-pagination-btn" data-page="1">1</button>`;
          if (startPage > 2) {
              html += `<span class="msg-pagination-info">...</span>`;
          }
      }
      
      for (let p = startPage; p <= endPage; p++) {
          html += `
              <button class="msg-pagination-btn ${p === displayCurrentPage ? 'active' : ''}" data-page="${p}">
                  ${p}
              </button>
          `;
      }
      
      if (endPage < displayPages) {
          if (endPage < displayPages - 1) {
              html += `<span class="msg-pagination-info">...</span>`;
          }
          html += `<button class="msg-pagination-btn" data-page="${displayPages}">${displayPages}</button>`;
      }
      
      // Next button
      const nextDisabled = displayCurrentPage === displayPages ? 'disabled' : '';
      html += `
          <button class="msg-pagination-btn" ${nextDisabled} data-page="${displayCurrentPage + 1}" title="Next Page">
              Next <i class="fas fa-chevron-right"></i>
          </button>
      `;
      
      this.container.innerHTML = html;
      
      // Attach click events
      this.container.querySelectorAll('.msg-pagination-btn:not([disabled])').forEach((btn) => {
        btn.addEventListener('click', () => {
          const page = parseInt(btn.getAttribute('data-page'), 10);
          this.goToPage(page);
        });
      });
    }
  }
}

class GridPaginator {
  constructor(config) {
    this.tableId = config.tableId;
    this.containerId = config.containerId;
    this.pageSize = config.pageSize || 10;
    this.currentPage = 1;
    this.storageKey = config.storageKey;

    this.table = document.getElementById(this.tableId);
    this.container = document.getElementById(this.containerId);

    if (!this.table) return;

    this.init();

    // Recalculate page size dynamically on resize
    window.addEventListener('resize', () => {
      const oldSize = this.pageSize;
      this.updatePageSize();
      if (oldSize !== this.pageSize) {
        this.update();
      }
    });
  }

  init() {
    this.updatePageSize();
    this.update();
  }

  updatePageSize() {
    if (!this.table) return;
    const style = window.getComputedStyle(this.table);
    const paddingLeft = parseFloat(style.paddingLeft) || 0;
    const paddingRight = parseFloat(style.paddingRight) || 0;
    const paddingTop = parseFloat(style.paddingTop) || 0;
    const paddingBottom = parseFloat(style.paddingBottom) || 0;
    
    let parent = this.table;
    let contentHeight = 0;
    while (parent) {
      if (parent.clientHeight > 0 && window.getComputedStyle(parent).overflowY !== 'visible') {
        const pStyle = window.getComputedStyle(parent);
        const pTop = parseFloat(pStyle.paddingTop) || 0;
        const pBottom = parseFloat(pStyle.paddingBottom) || 0;
        contentHeight = parent.clientHeight - pTop - pBottom;
        break;
      }
      parent = parent.parentElement;
    }
    if (contentHeight <= 0) {
      contentHeight = window.innerHeight - 300;
    }

    const contentWidth = (parent || this.table).clientWidth - paddingLeft - paddingRight;
    const gap = parseFloat(style.rowGap || style.gap) || 20;

    const isMobile = window.innerWidth <= 768;
    if (isMobile) {
      // On mobile, grid is 1 column. Card has aspect-ratio: auto.
      // Measure a card height if visible, or default to 150px.
      let cardHeight = 150;
      const tempCard = this.table.querySelector('.msg-item');
      if (tempCard) {
        const originalDisplay = tempCard.style.display;
        tempCard.style.setProperty('display', 'flex', 'important');
        cardHeight = tempCard.offsetHeight || 150;
        tempCard.style.setProperty('display', originalDisplay);
      }
      const rowsCount = Math.floor((contentHeight + gap) / (cardHeight + gap));
      this.pageSize = Math.max(1, rowsCount);
    } else {
      // On desktop, 2 columns, 3:1 aspect ratio
      const colWidth = (contentWidth - gap) / 2;
      const cardHeight = colWidth / 3;
      const rowsCount = Math.floor((contentHeight + gap) / (cardHeight + gap));
      this.pageSize = Math.max(1, rowsCount) * 2;
    }
  }

  goToPage(page) {
    const totalPages = this.getTotalPages();
    this.currentPage = Math.max(1, Math.min(page, totalPages));
    this.update();
  }

  getFilteredRows() {
    return Array.from(this.table.querySelectorAll('.msg-item'));
  }

  getTotalPages() {
    const rows = this.getFilteredRows();
    return Math.ceil(rows.length / this.pageSize) || 1;
  }

  update() {
    const rows = this.getFilteredRows();
    const totalPages = this.getTotalPages();

    if (this.currentPage > totalPages) this.currentPage = totalPages;
    if (this.currentPage < 1) this.currentPage = 1;

    const startIndex = (this.currentPage - 1) * this.pageSize;
    const endIndex = startIndex + this.pageSize;

    const visibleRows = new Set(rows.slice(startIndex, endIndex));

    rows.forEach((row) => {
      row.style.setProperty('display', visibleRows.has(row) ? 'flex' : 'none', 'important');
    });

    const emptyState = this.table.querySelector('.empty-state');
    if (emptyState) {
      emptyState.style.setProperty('display', rows.length === 0 ? 'flex' : 'none', 'important');
    }

    if (this.container) {
      const displayPages = Math.max(1, totalPages);
      const displayCurrentPage = this.currentPage || 1;
      
      let html = '';
      
      // Previous button
      const prevDisabled = displayCurrentPage === 1 ? 'disabled' : '';
      html += `
          <button class="msg-pagination-btn" ${prevDisabled} data-page="${displayCurrentPage - 1}" title="Previous Page">
              <i class="fas fa-chevron-left"></i> Prev
          </button>
      `;
      
      const maxVisible = 5;
      let startPage = Math.max(1, displayCurrentPage - Math.floor(maxVisible / 2));
      let endPage = Math.min(displayPages, startPage + maxVisible - 1);
      
      if (endPage - startPage + 1 < maxVisible) {
          startPage = Math.max(1, endPage - maxVisible + 1);
      }
      
      if (startPage > 1) {
          html += `<button class="msg-pagination-btn" data-page="1">1</button>`;
          if (startPage > 2) {
              html += `<span class="msg-pagination-info">...</span>`;
          }
      }
      
      for (let p = startPage; p <= endPage; p++) {
          html += `
              <button class="msg-pagination-btn ${p === displayCurrentPage ? 'active' : ''}" data-page="${p}">
                  ${p}
              </button>
          `;
      }
      
      if (endPage < displayPages) {
          if (endPage < displayPages - 1) {
              html += `<span class="msg-pagination-info">...</span>`;
          }
          html += `<button class="msg-pagination-btn" data-page="${displayPages}">${displayPages}</button>`;
      }
      
      // Next button
      const nextDisabled = displayCurrentPage === displayPages ? 'disabled' : '';
      html += `
          <button class="msg-pagination-btn" ${nextDisabled} data-page="${displayCurrentPage + 1}" title="Next Page">
              Next <i class="fas fa-chevron-right"></i>
          </button>
      `;
      
      this.container.innerHTML = html;
      
      // Attach click events
      this.container.querySelectorAll('.msg-pagination-btn:not([disabled])').forEach((btn) => {
        btn.addEventListener('click', () => {
          const page = parseInt(btn.getAttribute('data-page'), 10);
          this.goToPage(page);
        });
      });
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // Initialize pagination targeting the list container
  window.activePaginators = window.activePaginators || {};
  window.activePaginators["issues-list"] = new GridPaginator({
    tableId: "issues-list-container",
    containerId: "issue-pagination",
    storageKey: "issues_page"
  });

  // Auto-submit form when any select changes, and show spinner on reset button
  const filterForm = document.querySelector('.issue-filters');
  if (filterForm) {
    filterForm.querySelectorAll('select').forEach(select => {
      select.addEventListener('change', () => {
        const resetBtn = document.getElementById('reset-btn');
        if (resetBtn) {
          const icon = resetBtn.querySelector('i');
          if (icon) {
            icon.className = 'fas fa-spinner fa-spin';
          }
        }
        filterForm.submit();
      });
    });
  }

  // Handle click on reset button (show loading spinner)
  const resetBtn = document.getElementById('reset-btn');
  if (resetBtn) {
    resetBtn.addEventListener('click', (e) => {
      const icon = resetBtn.querySelector('i');
      if (icon) {
        icon.className = 'fas fa-spinner fa-spin';
      }
    });
  }
});
