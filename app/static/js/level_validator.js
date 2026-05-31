/**
 * Level Validator — async blockchain verification with localStorage persistence.
 * Submits verification, polls for result, survives page navigation.
 */
(function () {
	const STORAGE_KEY = 'levelValidatorTask';
	const POLL_INTERVAL = 2000; // ms
	const IS_SYSADMIN = window.__isSysAdmin || false;

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
		const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
		const html = `
      <div class="result-card result-pending">
        <div class="result-spinner"><i class="fas fa-circle-notch fa-spin"></i></div>
        <div class="result-text">
          <strong>${isChinese ? '正在区块链上验证…' : 'Verifying on blockchain…'}</strong>
          <span class="result-meta">${params.member_id} · ${params.path_name} · ${isChinese ? '级别' : 'Level'} ${params.level}</span>
          <span class="result-hint"><i class="fas fa-clock"></i> ${isChinese ? '已用时间' : 'Elapsed'}: <span id="elapsedTime">0:00</span> — ${isChinese ? '您可以离开此页面，稍后再回来查看。' : 'You can leave this page and come back later.'}</span>
        </div>
      </div>`;
		showResult(html);
	}

	function buildHistoryHtml(history) {
		if (!history || history.length === 0) return '';

		const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
		let rows = '';
		history.forEach(item => {
			const actionText = item.action === 'Recorded' ? (isChinese ? '已记录' : 'Recorded') : (item.action === 'Revoked' ? (isChinese ? '已撤销' : 'Revoked') : item.action);
			const icon = item.action === 'Recorded' ? '<i class="fas fa-check-circle" style="color: #28a745;"></i>' : '<i class="fas fa-ban" style="color: #dc3545;"></i>';

			rows += `
				<div class="history-item" style="padding: 12px 0; border-bottom: 1px solid var(--border-color, #eee);">
					<div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
						<strong style="font-size: 1rem;">${icon} ${actionText}</strong>
						<span style="color: #666; font-size: 0.88rem;">${item.time}</span>
					</div>
					<div class="detail-row" style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: none;">
						<span class="detail-label" style="color: #666; font-weight: normal;">${isChinese ? '操作人:' : 'By:'}</span>
						<span class="detail-value">${IS_SYSADMIN ? item.user : '****'}</span>
					</div>
					<div class="detail-row" style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: none;">
						<span class="detail-label" style="color: #666; font-weight: normal;">${isChinese ? '交易哈希:' : 'Tx Hash:'}</span>
						<span class="detail-value hash-value">${item.tx_hash}</span>
					</div>
					<div class="detail-row" style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: none;">
						<span class="detail-label" style="color: #666; font-weight: normal;">${isChinese ? '区块:' : 'Block:'}</span>
						<span class="detail-value">${item.block_number}</span>
					</div>
				</div>
			`;
		});

		return `
		<div class="result-details" style="margin-top: 20px;">
			<h4 style="margin-top: 0; margin-bottom: 10px; font-size: 1.1em; border-bottom: 2px solid var(--border-color, #eee); padding-bottom: 8px;"><i class="fas fa-history"></i> ${isChinese ? '交易历史记录' : 'Transaction History'}</h4>
			<div class="history-list">
				${rows}
			</div>
		</div>`;
	}

	function showVerified(result, params, elapsedMs) {
		const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
		const elapsed = elapsedMs ? `<span class="result-elapsed"><i class="fas fa-clock"></i> ${formatElapsed(elapsedMs)}</span>` : '';
		const html = `
      <div class="result-card result-verified">
        <div class="result-icon"><i class="fas fa-check-circle"></i></div>
        <div class="result-text">
          <strong>${isChinese ? '区块链验证成功' : 'Verified on Blockchain'}</strong>
          <span class="result-meta">${params.member_id} · ${params.path_name} · ${isChinese ? '级别' : 'Level'} ${params.level}</span>
          ${elapsed}
        </div>
      </div>
      <div class="result-details">
        <div class="detail-row"><span class="detail-label">${isChinese ? '颁发日期' : 'Issue Date'}</span><span class="detail-value">${result.issue_date}</span></div>
        <div class="detail-row"><span class="detail-label">${isChinese ? '记录人' : 'Recorded By'}</span><span class="detail-value">${IS_SYSADMIN ? result.recorded_user : '****'}</span></div>
        <div class="detail-row"><span class="detail-label">${isChinese ? '记录时间' : 'Recorded Time'}</span><span class="detail-value">${result.recorded_time}</span></div>
        <div class="detail-row"><span class="detail-label">${isChinese ? '交易哈希' : 'Transaction Hash'}</span><span class="detail-value hash-value">${result.tx_hash}</span></div>
        <div class="detail-row"><span class="detail-label">${isChinese ? '区块高度' : 'Block Number'}</span><span class="detail-value">${result.block_number}</span></div>
        <div class="detail-row"><span class="detail-label">${isChinese ? '完成哈希' : 'Completion Hash'}</span><span class="detail-value hash-value">${result.expected_hash}</span></div>
      </div>
      ${buildHistoryHtml(result.history)}`;
		showResult(html);
	}

	function showRevoked(result, params, elapsedMs) {
		const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
		const elapsed = elapsedMs ? `<span class="result-elapsed"><i class="fas fa-clock"></i> ${formatElapsed(elapsedMs)}</span>` : '';
		const html = `
      <div class="result-card result-error">
        <div class="result-icon"><i class="fas fa-ban"></i></div>
        <div class="result-text">
          <strong>${isChinese ? '已在区块链上撤销' : 'Revoked on Blockchain'}</strong>
          <span class="result-meta">${params.member_id} · ${params.path_name} · ${isChinese ? '级别' : 'Level'} ${params.level}</span>
          ${elapsed}
        </div>
      </div>
      <div class="result-details">
        <div class="detail-row"><span class="detail-label">${isChinese ? '颁发日期' : 'Issue Date'}</span><span class="detail-value">${result.issue_date}</span></div>
        <div class="detail-row"><span class="detail-label">${isChinese ? '撤销人' : 'Revoked By'}</span><span class="detail-value">${IS_SYSADMIN ? result.revoked_user : '****'}</span></div>
        <div class="detail-row"><span class="detail-label">${isChinese ? '撤销时间' : 'Revoked Time'}</span><span class="detail-value">${result.revoked_time}</span></div>
        <div class="detail-row"><span class="detail-label">${isChinese ? '交易哈希' : 'Transaction Hash'}</span><span class="detail-value hash-value">${result.tx_hash}</span></div>
        <div class="detail-row"><span class="detail-label">${isChinese ? '区块高度' : 'Block Number'}</span><span class="detail-value">${result.block_number}</span></div>
        <div class="detail-row"><span class="detail-label">${isChinese ? '完成哈希' : 'Completion Hash'}</span><span class="detail-value hash-value">${result.expected_hash}</span></div>
      </div>
      ${buildHistoryHtml(result.history)}`;
		showResult(html);
	}

	function showNotFound(result, params, elapsedMs) {
		const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
		const elapsed = elapsedMs ? `<span class="result-elapsed"><i class="fas fa-clock"></i> ${formatElapsed(elapsedMs)}</span>` : '';
		const html = `
      <div class="result-card result-not-found">
        <div class="result-icon"><i class="fas fa-times-circle"></i></div>
        <div class="result-text">
          <strong>${isChinese ? '未在区块链上找到记录' : 'Not Found on Blockchain'}</strong>
          <span class="result-meta">${params.member_id} · ${params.path_name} · ${isChinese ? '级别' : 'Level'} ${params.level}</span>
          ${elapsed}
        </div>
      </div>
      <div class="result-details">
        <div class="detail-row"><span class="detail-label">${isChinese ? '预期哈希' : 'Expected Hash'}</span><span class="detail-value hash-value">${result.expected_hash || 'N/A'}</span></div>
      </div>`;
		showResult(html);
	}

	function showError(msg) {
		const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
		const html = `
      <div class="result-card result-error">
        <div class="result-icon"><i class="fas fa-exclamation-triangle"></i></div>
        <div class="result-text">
          <strong>${isChinese ? '错误' : 'Error'}</strong>
          <span class="result-meta">${msg}</span>
        </div>
      </div>`;
		showResult(html);
	}

	function setButtonLoading(loading) {
		const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
		if (loading) {
			verifyBtn.disabled = true;
			verifyBtn.innerHTML = `<i class="fas fa-circle-notch fa-spin"></i> ${isChinese ? '正在验证…' : 'Verifying…'}`;
		} else {
			verifyBtn.disabled = false;
			verifyBtn.innerHTML = `<i class="fas fa-search"></i> ${isChinese ? '在区块链上验证' : 'Verify on Blockchain'}`;
		}
	}

	function getCookie(name) {
		let cookieValue = null;
		if (document.cookie && document.cookie !== '') {
			const cookies = document.cookie.split(';');
			for (let i = 0; i < cookies.length; i++) {
				const cookie = cookies[i].trim();
				if (cookie.substring(0, name.length + 1) === (name + '=')) {
					cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
					break;
				}
			}
		}
		return cookieValue;
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
		const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
		fetch(`/tools/validator/status/${taskId}`)
			.then(r => r.json())
			.then(data => {
				if (!data.success) {
					stopPolling();
					stopElapsedTimer();
					localStorage.removeItem(STORAGE_KEY);
					showError(data.error || (isChinese ? `错误 ${r.status}: 任务已过期或未找到。` : `Error ${r.status}: Task expired or not found.`));
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
					} else if (data.result.revoked) {
						showRevoked(data.result, params, elapsedMs);
					} else if (data.result.verified) {
						showVerified(data.result, params, elapsedMs);
					} else {
						showNotFound(data.result, params, elapsedMs);
					}
				}
				// status === 'pending' → keep polling
			})
			.catch((err) => {
				const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
				stopPolling();
				stopElapsedTimer();
				localStorage.removeItem(STORAGE_KEY);
				showError(isChinese ? `检查状态时发生网络错误: ${err.message || '未知错误'}` : `Network error while checking status: ${err.message || 'Unknown error'}`);
				setButtonLoading(false);
			});
	}

	// ── Submit ──────────────────────────────────────────────
	function submitVerification() {
		const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
		const memberId = memberIdInput.value.trim();
		const pathName = pathSelect.value;
		const level = levelSelect.value;

		if (!memberId || !/^PN-\d+$/.test(memberId)) {
			showError(isChinese ? '会员 ID 格式必须为 PN-12345678。' : 'Member ID must be in PN-12345678 format.');
			return;
		}
		if (!pathName) { showError(isChinese ? '请选择一个教育路径。' : 'Please select an education path.'); return; }
		if (!level) { showError(isChinese ? '请选择一个级别。' : 'Please select a level.'); return; }

		const params = { member_id: memberId, path_name: pathName, level: parseInt(level) };
		const startedAt = Date.now();

		setButtonLoading(true);
		showLoading(params);
		startElapsedTimer(startedAt);

		fetch('/tools/validator', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				'X-CSRFToken': getCookie('csrf_token') || ''
			},
			body: JSON.stringify(params)
		})
			.then(r => {
				const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
				if (!r.ok) {
					return r.text().then(text => {
						throw new Error(isChinese ? `服务器返回 ${r.status}: ${text.substring(0, 100)}` : `Server returned ${r.status}: ${text.substring(0, 100)}`);
					});
				}
				return r.json();
			})
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
			.catch((err) => {
				const isChinese = typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN';
				showError(isChinese ? `请求失败: ${err.message || '检查服务器日志'}` : `Request failed: ${err.message || 'Check server logs'}`);
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
				// Sync CustomSelect wrappers
				pathSelect.dispatchEvent(new Event('change'));
				levelSelect.dispatchEvent(new Event('change'));

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
