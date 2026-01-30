/**
 * CustomSelectAdapter
 * A utility class to enhance native <select> elements into custom "premium" dropdowns.
 * Supports single and multi-select (checkboxes).
 */
class CustomSelectAdapter {
    constructor(selectElement) {
        if (!selectElement) return;
        this.select = selectElement;
        this.container = null;
        this.trigger = null;
        this.menu = null;
        this.isOpen = false;
        this.isMultiple = this.select.multiple;
        
        // Hide the native select
        this.select.style.display = 'none';

        this.init();
    }

    init() {
        this.createStructure();
        this.syncOptions();
        this.setupListeners();
        this.setupObserver();
    }

    createStructure() {
        // Create container
        this.container = document.createElement('div');
        this.container.className = 'custom-dropdown relative-pos';
        this.container.id = `${this.select.id}-custom-container`;
        
        // Add focusout listener to close when tabbing away
        this.container.addEventListener('focusout', (e) => {
            if (!this.container.contains(e.relatedTarget)) {
                this.close();
            }
        });
        
        // Create trigger button
        this.trigger = document.createElement('button');
        this.trigger.type = 'button';
        this.trigger.className = 'form-control dropdown-premium-btn';
        this.trigger.id = `${this.select.id}-custom-trigger`;
        this.trigger.style.justifyContent = 'space-between';

        // Trigger text
        const btnText = document.createElement('span');
        btnText.className = 'btn-text';
        this.trigger.appendChild(btnText);

        // Icon
        const icon = document.createElement('i');
        icon.className = 'fas fa-caret-down';
        this.trigger.appendChild(icon);

        // Create menu
        this.menu = document.createElement('div');
        this.menu.className = 'dropdown-premium-menu';
        this.menu.id = `${this.select.id}-custom-menu`;
        
        // Assemble
        this.container.appendChild(this.trigger);
        this.container.appendChild(this.menu);

        // Insert after the select element
        this.select.parentNode.insertBefore(this.container, this.select.nextSibling);

        this.updateTriggerLabel();
    }

    syncOptions() {
        this.menu.innerHTML = ''; // Clear existing items
        const fragment = document.createDocumentFragment();

        if (this.isMultiple) {
            // Add "Select All" header if multiple
            const selectAll = document.createElement('label');
            selectAll.className = 'dropdown-header-premium';
            selectAll.style.cursor = 'pointer';
            selectAll.style.display = 'flex';
            selectAll.style.alignItems = 'center';
            selectAll.style.gap = '8px';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'dropdown-checkbox';
            
            const total = Array.from(this.select.options).filter(o => o.value !== '').length;
            const selected = Array.from(this.select.selectedOptions).filter(o => o.value !== '').length;
            
            checkbox.checked = total > 0 && selected === total;
            checkbox.indeterminate = selected > 0 && selected < total;
            
            checkbox.addEventListener('change', (e) => {
                e.stopPropagation();
                Array.from(this.select.options).forEach(opt => {
                    if (opt.value !== '') opt.selected = checkbox.checked;
                });
                this.select.dispatchEvent(new Event('change', { bubbles: true }));
                this.updateUI();
            });

            selectAll.appendChild(checkbox);
            selectAll.appendChild(document.createTextNode('Select / Deselect All'));
            fragment.appendChild(selectAll);
        }

        Array.from(this.select.children).forEach(child => {
            if (child.tagName === 'OPTGROUP') {
                const header = document.createElement('div');
                header.className = 'dropdown-header-premium';
                header.textContent = child.label;
                fragment.appendChild(header);

                Array.from(child.children).forEach(option => {
                    fragment.appendChild(this.createOptionItem(option));
                });
            } else if (child.tagName === 'OPTION') {
                fragment.appendChild(this.createOptionItem(child));
            }
        });

        this.menu.appendChild(fragment);
        this.updateTriggerLabel();
    }

    createOptionItem(option) {
        const item = document.createElement('label');
        item.className = 'dropdown-item-label';
        item.style.cursor = 'pointer';
        item.dataset.value = option.value;
        
        const flex = document.createElement('div');
        flex.className = 'flex-center-gap';
        flex.style.gap = '8px';
        flex.style.alignItems = 'center';

        if (this.isMultiple) {
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'dropdown-checkbox';
            checkbox.checked = option.selected;
            checkbox.addEventListener('change', (e) => {
                e.stopPropagation();
                option.selected = checkbox.checked;
                this.select.dispatchEvent(new Event('change', { bubbles: true }));
                this.updateUI();
            });
            flex.appendChild(checkbox);
        } else {
            const check = document.createElement('i');
            check.className = 'fas fa-check';
            check.style.width = '12px';
            check.style.visibility = option.selected ? 'visible' : 'hidden';
            flex.appendChild(check);
        }
        
        const text = document.createElement('span');
        text.textContent = option.text;
        flex.appendChild(text);
        
        item.appendChild(flex);

        if (!this.isMultiple) {
            item.addEventListener('click', (e) => {
                this.selectValue(option.value);
                this.close();
            });
        }

        return item;
    }

    selectValue(value) {
        if (this.select.value !== value) {
            this.select.value = value;
            this.select.dispatchEvent(new Event('change', { bubbles: true }));
        }
        this.updateUI();
    }

    updateUI() {
        this.updateTriggerLabel();
        this.syncOptions(); // Re-render to keep checkboxes and headers in sync
    }

    updateTriggerLabel() {
        const btnText = this.trigger.querySelector('.btn-text');
        const options = Array.from(this.select.options).filter(o => o.value !== '');
        const selectedOptions = Array.from(this.select.selectedOptions).filter(o => o.value !== '');
        
        if (this.isMultiple) {
            if (selectedOptions.length === 0) {
                btnText.textContent = '0 selected';
            } else if (selectedOptions.length === options.length && options.length > 0) {
                btnText.textContent = 'All Selected';
            } else {
                btnText.textContent = this._formatDateRanges(selectedOptions);
            }
        } else {
            const selectedOption = this.select.options[this.select.selectedIndex];
            if (selectedOption) {
                btnText.textContent = selectedOption.text;
            } else {
                const placeholder = this.select.querySelector('option[value=""]');
                btnText.textContent = placeholder ? placeholder.text : 'Select...';
            }
        }
    }

    /**
     * Helper to combine adjacent date ranges like "2024 Jan-Jun" and "2024 Jul-Dec"
     * into "2024 Jan-Dec", or across years like "2024 Jul-2025 Jun".
     */
    _formatDateRanges(selectedOptions) {
        const pattern = /^(\d{4}) (Jan-Jun|Jul-Dec)$/;
        const ranges = [];
        const others = [];

        selectedOptions.forEach(opt => {
            const text = opt.text.trim();
            const match = text.match(pattern);
            if (match) {
                const year = parseInt(match[1]);
                const half = match[2] === 'Jul-Dec' ? 1 : 0;
                ranges.push({ val: year * 2 + half, text: text });
            } else {
                others.push(text);
            }
        });

        // If no ranges found or mixed with many others, fall back to "X selected"
        if (ranges.length === 0) {
            if (others.length > 2) return `${others.length} selected`;
            return others.join(', ');
        }

        // Sort ranges numerically
        ranges.sort((a, b) => a.val - b.val);

        // Group into contiguous blocks
        const groups = [];
        if (ranges.length > 0) {
            let currentGroup = [ranges[0]];
            for (let i = 1; i < ranges.length; i++) {
                if (ranges[i].val === ranges[i - 1].val + 1) {
                    currentGroup.push(ranges[i]);
                } else {
                    groups.push(currentGroup);
                    currentGroup = [ranges[i]];
                }
            }
            groups.push(currentGroup);
        }

        // Format each group
        const formattedGroups = groups.map(group => {
            const start = group[0];
            const end = group[group.length - 1];

            if (start === end) return start.text;

            const startMatch = start.text.match(pattern);
            const endMatch = end.text.match(pattern);
            
            const sYear = startMatch[1];
            const sMonth = startMatch[2].split('-')[0]; // Jan or Jul
            const eYear = endMatch[1];
            const eMonth = endMatch[2].split('-')[1]; // Jun or Dec

            if (sYear === eYear) {
                return `${sYear} ${sMonth}-${eMonth}`;
            } else {
                return `${sYear} ${sMonth} - ${eYear} ${eMonth}`;
            }
        });

        const allLabels = [...formattedGroups, ...others];
        
        // Final length check: if too many labels, show count
        if (allLabels.length > 2) {
            return `${selectedOptions.length} selected`;
        }
        
        return allLabels.join(', ');
    }

    toggle() {
        if (this.isOpen) this.close();
        else this.open();
    }

    open() {
        this.menu.style.display = 'block';
        this.isOpen = true;
        setTimeout(() => document.addEventListener('click', this.handleOutsideClick), 0);
    }

    close() {
        this.menu.style.display = 'none';
        this.isOpen = false;
        document.removeEventListener('click', this.handleOutsideClick);
    }

    handleOutsideClick = (e) => {
        if (!this.container.contains(e.target)) {
            this.close();
        }
    }

    setupListeners() {
        this.trigger.addEventListener('click', (e) => {
            this.toggle();
        });

        this.select.addEventListener('change', () => {
             this.updateUI();
        });
    }

    setupObserver() {
        this.observer = new MutationObserver(() => {
            this.syncOptions();
        });
        this.observer.observe(this.select, { childList: true, subtree: true });
    }
}
