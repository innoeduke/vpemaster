/**
 * Shared Custom Select Component
 * 
 * enhanced select dropdown with support for icons, colors, and search/filtering.
 */

class CustomSelect {
	constructor(selectId, options = {}) {
		this.select = document.getElementById(selectId);
		if (!this.select) return;

		this.options = options;

		// Check if already initialized
		if (this.select.nextSibling && this.select.nextSibling.classList && this.select.nextSibling.classList.contains('custom-select-container')) {
			this.container = this.select.nextSibling;
			this.trigger = this.container.querySelector('.custom-select-trigger');
			this.optionsList = this.container.querySelector('.custom-select-options');
		} else {
			this.container = document.createElement('div');
			this.container.className = 'custom-select-container';
			this.trigger = document.createElement('div');
			this.trigger.className = 'custom-select-trigger';
			this.optionsList = document.createElement('div');
			this.optionsList.className = 'custom-select-options';

			this.select.hide = true;
			this.select.style.display = 'none';
			this.select.parentNode.insertBefore(this.container, this.select.nextSibling);
			this.container.appendChild(this.trigger);
			this.container.appendChild(this.optionsList);

			this.trigger.onclick = (e) => {
				if (this.select.disabled) return;
				e.preventDefault();
				e.stopPropagation();
				// Close other open selects
				document.querySelectorAll('.custom-select-container').forEach(c => {
					if (c !== this.container) c.classList.remove('open');
				});
				this.container.classList.toggle('open');
			};

			document.addEventListener('click', () => {
				this.container.classList.remove('open');
			});
		}

		this.updateTrigger();
		this.renderOptions();
	}

	updateTrigger() {
		if (!this.select.options.length) {
			this.trigger.innerHTML = '<span class="custom-select-text">Select...</span>';
			return;
		}
		const selectedOpt = this.select.options[this.select.selectedIndex];
		const text = selectedOpt ? selectedOpt.text : 'Select...';
		let icon = selectedOpt ? selectedOpt.dataset.icon : null;

		let innerHTML = '';
		if (icon) {
			// Ensure it has a style prefix (fas, fab, far)
			if (!icon.startsWith('fa')) {
				icon = 'fas ' + icon;
			} else if (!icon.includes(' ')) {
				// Has 'fa-...' but no 'fas '
				icon = 'fas ' + icon;
			}
			innerHTML += `<i class="${icon} custom-select-icon"></i> `;
		}
		innerHTML += `<span class="custom-select-text">${text}</span>`;
		this.trigger.innerHTML = innerHTML;
	}

	renderOptions() {
		this.optionsList.innerHTML = '';

		const groups = this.select.getElementsByTagName('optgroup');
		if (groups.length > 0) {
			Array.from(groups).forEach(group => {
				const groupDiv = document.createElement('div');
				groupDiv.className = 'custom-option-group';
				groupDiv.innerText = group.label;
				groupDiv.dataset.groupLabel = group.label;
				this.optionsList.appendChild(groupDiv);

				Array.from(group.getElementsByTagName('option')).forEach(opt => {
					this.createOption(opt);
				});
			});
		} else {
			Array.from(this.select.options).forEach(opt => {
				this.createOption(opt);
			});
		}
	}

	createOption(opt) {
		// Skip placeholders if desired, or handle them
		if (opt.value === "" && opt.disabled) return;

		const optDiv = document.createElement('div');
		optDiv.className = 'custom-option';
		if (opt.className) optDiv.className += ' ' + opt.className;
		if (opt.selected) optDiv.className += ' selected';

		// Check for data-code to bold it
		const code = opt.dataset.code;
		let icon = opt.dataset.icon;

		let innerHTML = '';
		if (icon) {
			// Ensure it has a style prefix (fas, fab, far)
			if (!icon.startsWith('fa')) {
				icon = 'fas ' + icon;
			} else if (!icon.includes(' ')) {
				// Has 'fa-...' but no 'fas '
				icon = 'fas ' + icon;
			}
			innerHTML += `<i class="${icon} custom-option-icon"></i> `;
		}

		if (code) {
			const checkmark = opt.text.startsWith('✓ ') ? '✓ ' : '';
			const name = opt.text.replace('✓ ', '');
			innerHTML += `${checkmark}<span class="project-code">${code}</span> ${name}`;
		} else {
			innerHTML += opt.text;
		}

		optDiv.innerHTML = innerHTML;

		optDiv.dataset.value = opt.value;

		optDiv.onclick = (e) => {
			e.stopPropagation();
			this.select.value = opt.value;
			this.select.dispatchEvent(new Event('change'));
			this.updateTrigger();
			this.container.classList.remove('open');
			this.renderOptions(); // Update selected state
		};

		this.optionsList.appendChild(optDiv);
	}

	refresh() {
		this.updateTrigger();
		this.renderOptions();
		this.updateVisibility();
	}

	updateVisibility() {
		const optDivs = this.optionsList.querySelectorAll('.custom-option');
		const groupDivs = this.optionsList.querySelectorAll('.custom-option-group');

		groupDivs.forEach(g => g.style.display = 'none');

		optDivs.forEach(div => {
			const originalOpt = Array.from(this.select.options).find(o => o.value == div.dataset.value);
			if (originalOpt) {
				const isVisible = originalOpt.style.display !== 'none';
				div.style.display = isVisible ? 'block' : 'none';

				if (isVisible && originalOpt.parentElement.tagName === 'OPTGROUP') {
					const groupLabel = originalOpt.parentElement.label;
					const groupDiv = Array.from(groupDivs).find(g => g.dataset.groupLabel === groupLabel);
					if (groupDiv) groupDiv.style.display = 'block';
				}
			}
		});
	}

	setValue(val) {
		this.select.value = val;
		this.select.dispatchEvent(new Event('change'));
		this.refresh();
	}

	disable() {
		this.select.disabled = true;
		this.container.classList.add('disabled');
	}

	enable() {
		this.select.disabled = false;
		this.container.classList.remove('disabled');
	}
}
