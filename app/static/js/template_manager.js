// Template Manager client-side logic.
// Two entry points: initListPage() and initEditorPage().

(function () {
  'use strict';

  function readJson(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    var hidden = document.querySelector('input[name="csrf_token"]');
    return hidden ? hidden.value : '';
  }

  // ---------- List page ----------

  function initListPage() {
    var buttons = document.querySelectorAll('.tm-delete-btn');
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var name = btn.getAttribute('data-name');
        var display = btn.getAttribute('data-display') || name;
        if (!window.confirm('Delete template "' + display + '"? This cannot be undone.')) {
          return;
        }
        var fd = new FormData();
        fd.append('name', name);
        fetch('/meetings/templates/delete', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCsrfToken() },
          body: fd,
          credentials: 'same-origin',
        })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
        .then(function (res) {
          if (res.ok && res.body.success) {
            var row = btn.closest('tr');
            if (row) row.parentNode.removeChild(row);
          } else {
            window.alert('Delete failed: ' + ((res.body && res.body.message) || 'unknown error'));
          }
        })
        .catch(function (err) { window.alert('Delete failed: ' + err); });
      });
    });

    // New-template modal
    var newBtn = document.getElementById('tm-new-btn');
    var modal = document.getElementById('tm-new-modal');
    var closeBtn = document.getElementById('tm-new-modal-close');
    var cancelBtn = document.getElementById('tm-new-modal-cancel');
    if (newBtn && modal) {
      newBtn.addEventListener('click', function () {
        modal.style.display = 'block';
        var input = modal.querySelector('input[name="name"]');
        if (input) { input.value = ''; setTimeout(function () { input.focus(); }, 50); }
      });
      var close = function () { modal.style.display = 'none'; };
      if (closeBtn) closeBtn.addEventListener('click', close);
      if (cancelBtn) cancelBtn.addEventListener('click', close);
      modal.addEventListener('click', function (e) {
        if (e.target === modal) close();
      });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modal.style.display === 'block') close();
      });
    }
  }

  // ---------- Editor page ----------

  var editor = {
    rows: [],
    typeChoices: [],
    saveUrl: '',
    listUrl: '',
  };

  function blankRow() {
    var defaultType = (editor.typeChoices && editor.typeChoices.length) ? editor.typeChoices[0] : '';
    return { type: defaultType, title: '', role: '', owner: '', duration_min: '', duration_max: '', hidden: false };
  }

  function typeOptions(selected) {
    var html = '';
    editor.typeChoices.forEach(function (t) {
      var sel = t === selected ? ' selected' : '';
      html += '<option value="' + escapeHtml(t) + '"' + sel + '>' + escapeHtml(t) + '</option>';
    });
    return html;
  }

  function roleOptions(selected) {
    var html = '<option value=""></option>';
    var hasMatch = false;
    editor.roleChoices.forEach(function (r) {
      var sel = r === selected ? ' selected' : '';
      if (sel) hasMatch = true;
      html += '<option value="' + escapeHtml(r) + '"' + sel + '>' + escapeHtml(r) + '</option>';
    });
    // Preserve legacy / custom role text that's not in the current list
    if (selected && !hasMatch) {
      html += '<option value="' + escapeHtml(selected) + '" selected>' + escapeHtml(selected) + ' (legacy)</option>';
    }
    return html;
  }

  function renderRows() {
    var tbody = document.getElementById('tm-rows-body');
    if (!tbody) return;
    if (!editor.rows.length) {
      tbody.innerHTML = '<tr class="tm-empty-row"><td colspan="8" style="text-align:center; padding:1rem; color:#888;">No rows yet. Click "Add row" to start.</td></tr>';
      return;
    }
    var html = '';
    editor.rows.forEach(function (row, idx) {
      var isSection = row.type === 'Section';
      var rowClass = isSection ? ' class="tm-row-section"' : '';
      var dis = isSection ? ' disabled' : '';
      html += ''
        + '<tr data-idx="' + idx + '"' + rowClass + '>'
        +   '<td class="tm-num-col tm-drag-handle" title="Drag to reorder"><span class="tm-grip"><i class="fas fa-grip-vertical"></i></span> ' + (idx + 1) + '</td>'
        +   '<td class="tm-type-col"><select class="tm-type">' + typeOptions(row.type) + '</select></td>'
        +   '<td class="tm-title-col"><input type="text" class="tm-title" value="' + escapeHtml(row.title) + '"></td>'
        +   '<td class="tm-role-col"><select class="tm-role"' + dis + '>' + roleOptions(row.role) + '</select></td>'
        +   '<td class="tm-minmax-col"><input type="number" min="0" class="tm-min" value="' + escapeHtml(row.duration_min) + '"' + dis + '></td>'
        +   '<td class="tm-minmax-col"><input type="number" min="0" class="tm-max" value="' + escapeHtml(row.duration_max) + '"' + dis + '></td>'
        +   '<td class="tm-check-col"><input type="checkbox" class="tm-hidden"' + (row.hidden ? ' checked' : '') + '></td>'
        +   '<td class="tm-actions-col">'
        +     '<button type="button" class="tm-action-btn tm-move-up" title="Move up" aria-label="Move up"><i class="fas fa-arrow-up"></i></button>'
        +     '<button type="button" class="tm-action-btn tm-move-down" title="Move down" aria-label="Move down"><i class="fas fa-arrow-down"></i></button>'
        +     '<button type="button" class="tm-action-btn tm-action-btn--danger tm-delete-row" title="Delete row" aria-label="Delete row"><i class="fas fa-trash"></i></button>'
        +   '</td>'
        + '</tr>';
    });
    tbody.innerHTML = html;
  }

  function collectRows() {
    return editor.rows.map(function (row) {
      return {
        type: row.type || '',
        title: row.title || '',
        role: row.role || '',
        owner: row.owner || '',
        duration_min: row.duration_min === '' || row.duration_min == null ? '' : String(row.duration_min),
        duration_max: row.duration_max === '' || row.duration_max == null ? '' : String(row.duration_max),
        hidden: !!row.hidden,
      };
    });
  }

  // Validate before save. Returns an array of error messages (empty = ok).
  function validateRows() {
    var errors = [];
    var firstBadIdx = -1;
    editor.rows.forEach(function (row, idx) {
      var isSection = row.type === 'Section';
      var badRequired = [];
      var badRange = [];

      if (!row.type || !row.type.trim()) badRequired.push('Type');
      if (!row.title || !row.title.trim()) badRequired.push('Title');

      if (!isSection) {
        var minVal = parseInt(row.duration_min, 10);
        var maxVal = parseInt(row.duration_max, 10);
        var hasMin = !isNaN(minVal) && row.duration_min !== '' && row.duration_min != null;
        var hasMax = !isNaN(maxVal) && row.duration_max !== '' && row.duration_max != null;

        if (!hasMin) badRequired.push('Min');
        if (!hasMax) badRequired.push('Max');

        if (hasMin && hasMax && minVal > maxVal) {
          badRange.push('Min cannot be greater than Max');
        }
      }

      var rowErrors = [];
      if (badRequired.length) {
        var verb = badRequired.length > 1 ? ' are required' : ' is required';
        rowErrors.push(badRequired.join(', ') + verb);
      }
      if (badRange.length) {
        rowErrors.push(badRange.join(', '));
      }

      if (rowErrors.length) {
        if (firstBadIdx < 0) firstBadIdx = idx;
        errors.push('Row ' + (idx + 1) + ': ' + rowErrors.join('; '));
      }
    });
    return { errors: errors, firstBadIdx: firstBadIdx };
  }

  function clearInvalidMarkers() {
    var tbody = document.getElementById('tm-rows-body');
    if (!tbody) return;
    tbody.querySelectorAll('.tm-invalid').forEach(function (el) {
      el.classList.remove('tm-invalid');
    });
  }

  function markInvalidRow(idx) {
    var tbody = document.getElementById('tm-rows-body');
    if (!tbody) return;
    var tr = tbody.querySelector('tr[data-idx="' + idx + '"]');
    if (!tr) return;
    var row = editor.rows[idx];
    var isSection = row.type === 'Section';
    if (!row.type || !row.type.trim()) {
      var sel = tr.querySelector('.tm-type');
      if (sel) sel.classList.add('tm-invalid');
    }
    if (!row.title || !row.title.trim()) {
      var ti = tr.querySelector('.tm-title');
      if (ti) ti.classList.add('tm-invalid');
    }
    if (!isSection) {
      var minVal = parseInt(row.duration_min, 10);
      var maxVal = parseInt(row.duration_max, 10);
      var hasMin = !isNaN(minVal) && row.duration_min !== '' && row.duration_min != null;
      var hasMax = !isNaN(maxVal) && row.duration_max !== '' && row.duration_max != null;

      if (!hasMin || (hasMin && hasMax && minVal > maxVal)) {
        var mn = tr.querySelector('.tm-min');
        if (mn) mn.classList.add('tm-invalid');
      }
      if (!hasMax || (hasMin && hasMax && minVal > maxVal)) {
        var mx = tr.querySelector('.tm-max');
        if (mx) mx.classList.add('tm-invalid');
      }
    }
  }

  function wireEditorEvents() {
    var tbody = document.getElementById('tm-rows-body');
    if (!tbody) return;

    tbody.addEventListener('input', function (e) {
      var tr = e.target.closest('tr');
      if (!tr) return;
      var idx = parseInt(tr.getAttribute('data-idx'), 10);
      if (isNaN(idx) || !editor.rows[idx]) return;
      var row = editor.rows[idx];
      if (e.target.classList.contains('tm-title')) {
        row.title = e.target.value;
        if (row.title && row.title.trim()) e.target.classList.remove('tm-invalid');
      }
      else if (e.target.classList.contains('tm-min')) {
        row.duration_min = e.target.value;
        if (row.duration_min !== '' && row.duration_min != null) e.target.classList.remove('tm-invalid');
      }
      else if (e.target.classList.contains('tm-max')) {
        row.duration_max = e.target.value;
        if (row.duration_max !== '' && row.duration_max != null) e.target.classList.remove('tm-invalid');
      }
    });

    tbody.addEventListener('change', function (e) {
      var tr = e.target.closest('tr');
      if (!tr) return;
      var idx = parseInt(tr.getAttribute('data-idx'), 10);
      if (isNaN(idx) || !editor.rows[idx]) return;
      var row = editor.rows[idx];
      if (e.target.classList.contains('tm-type')) {
        row.type = e.target.value;
        if (row.type === 'Section') {
          tr.classList.add('tm-row-section');
        } else {
          tr.classList.remove('tm-row-section');
        }
        // Toggle the disabled state of role/min/max when type changes
        var disable = row.type === 'Section';
        var roleEl = tr.querySelector('.tm-role');
        var minEl = tr.querySelector('.tm-min');
        var maxEl = tr.querySelector('.tm-max');
        if (roleEl) roleEl.disabled = disable;
        if (minEl) minEl.disabled = disable;
        if (maxEl) maxEl.disabled = disable;
        if (row.type) e.target.classList.remove('tm-invalid');
      }
      else if (e.target.classList.contains('tm-role')) row.role = e.target.value;
      else if (e.target.classList.contains('tm-hidden')) row.hidden = e.target.checked;
    });

    // `input` fires on <select> in modern browsers too; some setups
    // (custom dropdowns, assistive tech) only fire `input`. Handle both.
    tbody.addEventListener('input', function (e) {
      if (!e.target.classList.contains('tm-type')) return;
      var tr = e.target.closest('tr');
      if (!tr) return;
      var idx = parseInt(tr.getAttribute('data-idx'), 10);
      if (isNaN(idx) || !editor.rows[idx]) return;
      var row = editor.rows[idx];
      console.log('[TemplateManager] type input row', idx, ':', row.type, '->', e.target.value);
      if (row.type !== e.target.value) {
        row.type = e.target.value;
        if (row.type === 'Section') {
          tr.classList.add('tm-row-section');
        } else {
          tr.classList.remove('tm-row-section');
        }
        var disable = row.type === 'Section';
        var roleEl = tr.querySelector('.tm-role');
        var minEl = tr.querySelector('.tm-min');
        var maxEl = tr.querySelector('.tm-max');
        if (roleEl) roleEl.disabled = disable;
        if (minEl) minEl.disabled = disable;
        if (maxEl) maxEl.disabled = disable;
        if (row.type) e.target.classList.remove('tm-invalid');
      }
    });

    tbody.addEventListener('click', function (e) {
      var btn = e.target.closest('button');
      if (!btn) return;
      var tr = btn.closest('tr');
      if (!tr) return;
      var idx = parseInt(tr.getAttribute('data-idx'), 10);
      if (isNaN(idx)) return;
      if (btn.classList.contains('tm-move-up') && idx > 0) {
        var tmp = editor.rows[idx - 1];
        editor.rows[idx - 1] = editor.rows[idx];
        editor.rows[idx] = tmp;
        renderRows();
      } else if (btn.classList.contains('tm-move-down') && idx < editor.rows.length - 1) {
        var tmp2 = editor.rows[idx + 1];
        editor.rows[idx + 1] = editor.rows[idx];
        editor.rows[idx] = tmp2;
        renderRows();
      } else if (btn.classList.contains('tm-delete-row')) {
        if (window.confirm('Delete this row?')) {
          editor.rows.splice(idx, 1);
          renderRows();
        }
      }
    });

    var addBtn = document.getElementById('tm-add-row');
    if (addBtn) {
      addBtn.addEventListener('click', function () {
        editor.rows.push(blankRow());
        renderRows();
      });
    }

    var saveBtn = document.getElementById('tm-save');
    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        clearInvalidMarkers();
        var validation = validateRows();
        if (validation.errors.length) {
          var status = document.getElementById('tm-save-status');
          if (status) {
            status.hidden = false;
            status.textContent = 'Cannot save: ' + validation.errors[0] + (validation.errors.length > 1 ? ' (+' + (validation.errors.length - 1) + ' more)' : '');
            status.className = 'tm-status tm-status-error';
          }
          markInvalidRow(validation.firstBadIdx);
          var tbody = document.getElementById('tm-rows-body');
          var tr = tbody && tbody.querySelector('tr[data-idx="' + validation.firstBadIdx + '"]');
          if (tr) tr.scrollIntoView({ behavior: 'smooth', block: 'center' });
          return;
        }

        saveBtn.disabled = true;
        var status = document.getElementById('tm-save-status');
        var rowsToSave = collectRows();
        console.log('[TemplateManager] saving', rowsToSave.length, 'rows:', rowsToSave);
        if (status) { status.hidden = false; status.textContent = 'Saving…'; status.className = 'tm-status tm-status-info'; }
        fetch(editor.saveUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({ rows: rowsToSave }),
          credentials: 'same-origin',
        })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
        .then(function (res) {
          saveBtn.disabled = false;
          if (res.ok && res.body.success) {
            if (status) { status.textContent = 'Saved.'; status.className = 'tm-status tm-status-success'; }
            var url = new URL(editor.listUrl, window.location.origin);
            url.searchParams.set('_', Date.now().toString());
            window.setTimeout(function () { window.location.replace(url.toString()); }, 400);
          } else {
            if (status) { status.textContent = 'Save failed: ' + ((res.body && res.body.message) || 'unknown error'); status.className = 'tm-status tm-status-error'; }
          }
        })
        .catch(function (err) {
          saveBtn.disabled = false;
          if (status) { status.textContent = 'Save failed: ' + err; status.className = 'tm-status tm-status-error'; }
        });
      });
    }
  }

  function initEditorPage() {
    var rows = readJson('tm-rows-data');
    console.log('[TemplateManager] initEditorPage, rows from server:', rows ? rows.length : 0);
    editor.rows = Array.isArray(rows) ? rows.map(function (r) {
      return {
        type: r.type || '',
        title: r.title || '',
        role: r.role || '',
        owner: r.owner || '',
        duration_min: r.duration_min == null ? '' : String(r.duration_min),
        duration_max: r.duration_max == null ? '' : String(r.duration_max),
        hidden: !!r.hidden,
      };
    }) : [];
    editor.typeChoices = readJson('tm-type-choices') || ['Section', 'Generic'];
    editor.roleChoices = readJson('tm-role-choices') || [];
    editor.saveUrl = readJson('tm-save-url') || '';
    editor.listUrl = readJson('tm-list-url') || '/meetings/templates';

    renderRows();
    wireEditorEvents();

    // Sortable.js is loaded with `defer` in base.html, so it may not be
    // available the moment this script runs. Poll briefly until it is, then
    // attach the drag handler.
    var sortableAttempts = 0;
    function tryWireDrag() {
      if (typeof window.Sortable !== 'undefined') {
        wireDragReorder();
      } else if (sortableAttempts < 20) {
        sortableAttempts += 1;
        window.setTimeout(tryWireDrag, 50);
      } else {
        console.warn('Sortable.js not available; drag-to-reorder disabled.');
      }
    }
    tryWireDrag();
  }

  function wireDragReorder() {
    var tbody = document.getElementById('tm-rows-body');
    if (!tbody || typeof window.Sortable === 'undefined') return;
    // Avoid double-init if initEditorPage is called more than once
    if (tbody._sortable) {
      tbody._sortable.destroy();
    }
    tbody._sortable = window.Sortable.create(tbody, {
      handle: '.tm-drag-handle',
      animation: 150,
      ghostClass: 'tm-row-ghost',
      chosenClass: 'tm-row-chosen',
      dragClass: 'tm-row-drag',
      onEnd: function () {
        // Re-sync editor.rows to match the new DOM order
        var newOrder = [];
        var trs = tbody.querySelectorAll('tr[data-idx]');
        trs.forEach(function (tr) {
          var oldIdx = parseInt(tr.getAttribute('data-idx'), 10);
          if (!isNaN(oldIdx) && editor.rows[oldIdx] !== undefined) {
            newOrder.push(editor.rows[oldIdx]);
          }
        });
        if (newOrder.length === editor.rows.length) {
          editor.rows = newOrder;
        }
        renderRows();
      },
    });
  }

  window.TemplateManager = {
    initListPage: initListPage,
    initEditorPage: initEditorPage,
  };
})();
