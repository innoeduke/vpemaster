// Self Check-In page — vanilla JS, no framework, no CSRF token (matches the
// voting_routes.py anonymous POST pattern). Handles the search filter, the
// AJAX check-in POST, and a small toast for feedback.
(function () {
  'use strict';

  var token = document.body.getAttribute('data-token');
  var list = document.getElementById('ci-list');
  var search = document.getElementById('ci-search');
  var emptyHint = document.getElementById('ci-empty');
  var toastEl = document.getElementById('ci-toast');
  var toastTimer = null;

  function showToast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.hidden = false;
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.hidden = true; }, 2400);
  }

  function formatTime(iso) {
    // iso comes back as a naive UTC timestamp from datetime.utcnow().isoformat()
    var d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
    if (isNaN(d.getTime())) return '';
    var h = String(d.getHours()).padStart(2, '0');
    var m = String(d.getMinutes()).padStart(2, '0');
    return h + ':' + m;
  }

  function markChecked(row, iso) {
    row.classList.add('is-checked');
    var btn = row.querySelector('[data-action="checkin"]');
    if (!btn) return;
    btn.disabled = true;
    var label = btn.querySelector('.ci-btn-label');
    var time = formatTime(iso || '');
    if (label) label.textContent = (time ? time + ' ' : '') + 'Checked in';
  }

  // -------- Search filter --------
  function applyFilter() {
    if (!search || !list) return;
    var q = (search.value || '').trim().toLowerCase();
    var rows = list.children;
    var visible = 0;
    for (var i = 0; i < rows.length; i++) {
      var name = rows[i].getAttribute('data-name') || '';
      var match = !q || name.indexOf(q) !== -1;
      rows[i].classList.toggle('is-hidden', !match);
      if (match) visible++;
    }
    if (emptyHint) emptyHint.hidden = visible !== 0;
  }
  if (search) search.addEventListener('input', applyFilter);

  // -------- Check in --------
  function onCheckinClick(btn) {
    var row = btn.closest('.ci-row');
    if (!row) return;
    var id = row.getAttribute('data-id');
    if (!id) return;
    if (btn.disabled) return;
    btn.disabled = true;
    var label = btn.querySelector('.ci-btn-label');
    var prev = label ? label.textContent : '';
    if (label) label.textContent = '…';

    fetch('/checkin/' + encodeURIComponent(token) + '/mark/' + encodeURIComponent(id), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        if (!data || !data.success) throw new Error((data && data.message) || 'Failed');
        markChecked(row, data.checked_in_at);
        showToast(data.already ? 'Already checked in' : 'Welcome!');
      })
      .catch(function () {
        btn.disabled = false;
        if (label) label.textContent = prev || 'Check In';
        showToast('Could not check in. Try again.');
      });
  }

  if (list) {
    list.addEventListener('click', function (ev) {
      var btn = ev.target.closest('[data-action="checkin"]');
      if (btn) onCheckinClick(btn);
    });
  }
})();
