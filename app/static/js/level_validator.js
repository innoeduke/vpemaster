/**
 * Level Validator — async blockchain verification with localStorage persistence.
 * Submits verification, polls for result, survives page navigation.
 */
(function () {
	const STORAGE_KEY = 'levelValidatorTask';
	const POLL_INTERVAL = 2000; // ms

	const verifyBtn = document.getElementById('verifyBtn');
	const resultArea = document.getElementById('resultArea');
	const resultContent = document.getElementById('resultContent');

	const memberIdInput = document.getElementById('memberId');
	const pathSelect = document.getElementById('educationPath');
	const levelSelect = document.getElementById('levelNumber');

	let pollTimer = null;
	let elapsedTimer = null;

	// ── Helpers ──────────────────────────────────────────────
	function showResult(html) {
		resultArea.style.display = 'block';
		resultContent.innerHTML = html;
	}

	function formatElapsed(ms) {
		const totalSec = Math.floor(ms / 1000);
		const m = Math.floor(totalSec / 60);
		const s = totalSec % 60;
		return `${m}:${s.toString().padStart(2, '0')}`;
	}

	function startElapsedTimer(startTime) {
		stopElapsedTimer();
		const update = () => {
			const el = document.getElementById('elapsedTime');
			if (el) el.textContent = formatElapsed(Date.now() - startTime);
		};
		update();
		elapsedTimer = setInterval(update, 1000);
	}

	function stopElapsedTimer() {
		if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; }
	}

	function showLoading(params) {
		const html = `
      <div class="result-card result-pending">
        <div class="result-spinner"><i class="fas fa-circle-notch fa-spin"></i></div>
        <div class="result-text">
          <strong>Verifying on blockchain…</strong>
          <span class="result-meta">${params.member_id} · ${params.path_name} · Level ${params.level}</span>
          <span class="result-hint"><i class="fas fa-clock"></i> Elapsed: <span id="elapsedTime">0:00</span> — You can leave this page and come back later.</span>
        </div>
      </div>`;
		showResult(html);
	}

	function showVerified(result, params, elapsedMs) {
		const elapsed = elapsedMs ? `<span class="result-elapsed"><i class="fas fa-clock"></i> ${formatElapsed(elapsedMs)}</span>` : '';
		const html = `
      <div class="result-card result-verified">
        <div class="result-icon"><i class="fas fa-check-circle"></i></div>
        <div class="result-text">
          <strong>Verified on Blockchain</strong>
          <span class="result-meta">${params.member_id} · ${params.path_name} · Level ${params.level}</span>
          ${elapsed}
        </div>
      </div>
      <div class="result-details">
        <div class="detail-row"><span class="detail-label">Transaction Hash</span><span class="detail-value hash-value">${result.tx_hash}</span></div>
        <div class="detail-row"><span class="detail-label">Block Number</span><span class="detail-value">${result.block_number}</span></div>
        <div class="detail-row"><span class="detail-label">Recorded Time</span><span class="detail-value">${result.recorded_time}</span></div>
        <div class="detail-row"><span class="detail-label">Completion Hash</span><span class="detail-value hash-value">${result.expected_hash}</span></div>
      </div>`;
		showResult(html);
	}

	function showNotFound(result, params, elapsedMs) {
		const elapsed = elapsedMs ? `<span class="result-elapsed"><i class="fas fa-clock"></i> ${formatElapsed(elapsedMs)}</span>` : '';
		const html = `
      <div class="result-card result-not-found">
        <div class="result-icon"><i class="fas fa-times-circle"></i></div>
        <div class="result-text">
          <strong>Not Found on Blockchain</strong>
          <span class="result-meta">${params.member_id} · ${params.path_name} · Level ${params.level}</span>
          ${elapsed}
        </div>
      </div>
      <div class="result-details">
        <div class="detail-row"><span class="detail-label">Expected Hash</span><span class="detail-value hash-value">${result.expected_hash || 'N/A'}</span></div>
      </div>`;
		showResult(html);
	}

	function showError(msg) {
		const html = `
      <div class="result-card result-error">
        <div class="result-icon"><i class="fas fa-exclamation-triangle"></i></div>
        <div class="result-text">
          <strong>Error</strong>
          <span class="result-meta">${msg}</span>
        </div>
      </div>`;
		showResult(html);
	}

	function setButtonLoading(loading) {
		if (loading) {
			verifyBtn.disabled = true;
			verifyBtn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Verifying…';
		} else {
			verifyBtn.disabled = false;
			verifyBtn.innerHTML = '<i class="fas fa-search"></i> Verify on Blockchain';
		}
	}

	// ── Polling ─────────────────────────────────────────────
	function startPolling(taskId, params) {
		stopPolling();
		pollTimer = setInterval(() => pollStatus(taskId, params), POLL_INTERVAL);
	}

	function stopPolling() {
		if (pollTimer) {
			clearInterval(pollTimer);
			pollTimer = null;
		}
	}

	function pollStatus(taskId, params) {
		fetch(`/tools/validator/status/${taskId}`)
			.then(r => r.json())
			.then(data => {
				if (!data.success) {
					stopPolling();
					stopElapsedTimer();
					const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
					localStorage.removeItem(STORAGE_KEY);
					showError(data.error || 'Task expired or not found.');
					setButtonLoading(false);
					return;
				}
				if (data.status === 'done') {
					stopPolling();
					stopElapsedTimer();
					const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
					const elapsedMs = saved.started_at ? Date.now() - saved.started_at : null;
					localStorage.removeItem(STORAGE_KEY);
					setButtonLoading(false);
					if (data.result.error) {
						showError(data.result.error);
					} else if (data.result.verified) {
						showVerified(data.result, params, elapsedMs);
					} else {
						showNotFound(data.result, params, elapsedMs);
					}
				}
				// status === 'pending' → keep polling
			})
			.catch(() => {
				stopPolling();
				stopElapsedTimer();
				localStorage.removeItem(STORAGE_KEY);
				showError('Network error while checking status.');
				setButtonLoading(false);
			});
	}

	// ── Submit ──────────────────────────────────────────────
	function submitVerification() {
		const memberId = memberIdInput.value.trim();
		const pathName = pathSelect.value;
		const level = levelSelect.value;

		if (!memberId || !/^PN-\d+$/.test(memberId)) {
			showError('Member ID must be in PN-12345678 format.');
			return;
		}
		if (!pathName) { showError('Please select an education path.'); return; }
		if (!level) { showError('Please select a level.'); return; }

		const params = { member_id: memberId, path_name: pathName, level: parseInt(level) };
		const startedAt = Date.now();

		setButtonLoading(true);
		showLoading(params);
		startElapsedTimer(startedAt);

		fetch('/tools/validator', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(params)
		})
			.then(r => r.json())
			.then(data => {
				if (!data.success) {
					stopElapsedTimer();
					showError(data.error);
					setButtonLoading(false);
					return;
				}
				// Persist task + start time to localStorage
				const task = { task_id: data.task_id, params, started_at: startedAt };
				localStorage.setItem(STORAGE_KEY, JSON.stringify(task));
				startPolling(data.task_id, params);
			})
			.catch(() => {
				showError('Network error. Please try again.');
				setButtonLoading(false);
			});
	}

	// ── Init ────────────────────────────────────────────────
	verifyBtn.addEventListener('click', submitVerification);

	// On page load, check for pending task
	const saved = localStorage.getItem(STORAGE_KEY);
	if (saved) {
		try {
			const task = JSON.parse(saved);
			if (task.task_id && task.params) {
				// Restore form values
				memberIdInput.value = task.params.member_id || '';
				pathSelect.value = task.params.path_name || '';
				levelSelect.value = task.params.level || '';

				setButtonLoading(true);
				showLoading(task.params);
				if (task.started_at) startElapsedTimer(task.started_at);
				startPolling(task.task_id, task.params);
			}
		} catch (e) {
			localStorage.removeItem(STORAGE_KEY);
		}
	}
})();
