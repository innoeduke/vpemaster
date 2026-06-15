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
  }

  // ---------- Editor page ----------

  var editor = {
    rows: [],
    typeChoices: [],
    saveUrl: '',
    listUrl: '',
  };

  function blankRow() {
    return { type: '', title: '', role: '', owner: '', duration_min: '', duration_max: '', hidden: false };
  }

  function typeOptions(selected) {
    var html = '';
    editor.typeChoices.forEach(function (t) {
      var sel = t === selected ? ' selected' : '';
      html += '<option value="' + escapeHtml(t) + '"' + sel + '>' + escapeHtml(t) + '</option>';
    });
    return html;
  }

  function renderRows() {
    var tbody = document.getElementById('tm-rows-body');
    if (!tbody) return;
    if (!editor.rows.length) {
      tbody.innerHTML = '<tr class="tm-empty-row"><td colspan="9" style="text-align:center; padding:1rem; color:#888;">No rows yet. Click "Add row" to start.</td></tr>';
      return;
    }
    var html = '';
    editor.rows.forEach(function (row, idx) {
      html += ''
        + '<tr data-idx="' + idx + '">'
        +   '<td class="tm-num-col tm-drag-handle" title="Drag to reorder"><span class="tm-grip"><i class="fas fa-grip-vertical"></i></span> ' + (idx + 1) + '</td>'
        +   '<td><select class="tm-type">' + typeOptions(row.type) + '</select></td>'
        +   '<td><input type="text" class="tm-title" value="' + escapeHtml(row.title) + '"></td>'
        +   '<td><input type="text" class="tm-role" value="' + escapeHtml(row.role) + '"></td>'
        +   '<td><input type="text" class="tm-owner" value="' + escapeHtml(row.owner) + '"></td>'
        +   '<td class="tm-num-col"><input type="number" min="0" class="tm-min" value="' + escapeHtml(row.duration_min) + '"></td>'
        +   '<td class="tm-num-col"><input type="number" min="0" class="tm-max" value="' + escapeHtml(row.duration_max) + '"></td>'
        +   '<td class="tm-check-col"><input type="checkbox" class="tm-hidden"' + (row.hidden ? ' checked' : '') + '></td>'
        +   '<td class="tm-actions-col">'
        +     '<button type="button" class="btn btn-sm btn-secondary tm-move-up" title="Move up"><i class="fas fa-arrow-up"></i></button> '
        +     '<button type="button" class="btn btn-sm btn-secondary tm-move-down" title="Move down"><i class="fas fa-arrow-down"></i></button> '
        +     '<button type="button" class="btn btn-sm btn-danger tm-delete-row" title="Delete row"><i class="fas fa-trash"></i></button>'
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

  function wireEditorEvents() {
    var tbody = document.getElementById('tm-rows-body');
    if (!tbody) return;

    tbody.addEventListener('input', function (e) {
      var tr = e.target.closest('tr');
      if (!tr) return;
      var idx = parseInt(tr.getAttribute('data-idx'), 10);
      if (isNaN(idx) || !editor.rows[idx]) return;
      var row = editor.rows[idx];
      if (e.target.classList.contains('tm-title')) row.title = e.target.value;
      else if (e.target.classList.contains('tm-role')) row.role = e.target.value;
      else if (e.target.classList.contains('tm-owner')) row.owner = e.target.value;
      else if (e.target.classList.contains('tm-min')) row.duration_min = e.target.value;
      else if (e.target.classList.contains('tm-max')) row.duration_max = e.target.value;
    });

    tbody.addEventListener('change', function (e) {
      var tr = e.target.closest('tr');
      if (!tr) return;
      var idx = parseInt(tr.getAttribute('data-idx'), 10);
      if (isNaN(idx) || !editor.rows[idx]) return;
      var row = editor.rows[idx];
      if (e.target.classList.contains('tm-type')) row.type = e.target.value;
      else if (e.target.classList.contains('tm-hidden')) row.hidden = e.target.checked;
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
        saveBtn.disabled = true;
        var status = document.getElementById('tm-save-status');
        if (status) { status.hidden = false; status.textContent = 'Saving…'; status.className = 'tm-status tm-status-info'; }
        fetch(editor.saveUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({ rows: collectRows() }),
          credentials: 'same-origin',
        })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
        .then(function (res) {
          saveBtn.disabled = false;
          if (res.ok && res.body.success) {
            if (status) { status.textContent = 'Saved.'; status.className = 'tm-status tm-status-success'; }
            window.setTimeout(function () { window.location.assign(editor.listUrl); }, 400);
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
    editor.saveUrl = readJson('tm-save-url') || '';
    editor.listUrl = readJson('tm-list-url') || '/meetings/templates';

    renderRows();
    wireEditorEvents();
    wireDragReorder();
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
