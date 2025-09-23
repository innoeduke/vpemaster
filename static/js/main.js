// static/js/main.js

/**
 * Initializes a search input with autocomplete functionality.
 * @param {string} inputId The ID of the search input element.
 * @param {Array<Object>} data The array of objects to search through (e.g., contacts).
 * @param {string} searchKey The key in the data objects to search against (e.g., 'Name').
 * @param {function(Object)} onSelect A callback function to execute when an item is selected.
 */
function initializeAutocomplete(inputId, data, searchKey, onSelect) {
    const searchInput = document.getElementById(inputId);
    if (!searchInput) return;

    let currentFocus;
    searchInput.addEventListener('input', function() {
        const val = this.value;
        closeAllLists();
        if (!val) {
            onSelect(null); // Clear selection if input is empty
            return false;
        }
        currentFocus = -1;

        const suggestions = document.createElement('div');
        suggestions.id = this.id + 'autocomplete-list';
        suggestions.classList.add('autocomplete-items');
        this.parentNode.appendChild(suggestions);

        const filteredData = data.filter(item => item[searchKey].toUpperCase().includes(val.toUpperCase()));

        filteredData.forEach(item => {
            const itemDiv = document.createElement('div');
            itemDiv.innerHTML = "<strong>" + item[searchKey].substr(0, val.length) + "</strong>";
            itemDiv.innerHTML += item[searchKey].substr(val.length);
            itemDiv.innerHTML += `<input type='hidden' value='${JSON.stringify(item)}'>`;
            itemDiv.addEventListener('click', function() {
                const selectedItem = JSON.parse(this.getElementsByTagName('input')[0].value);
                searchInput.value = selectedItem[searchKey];
                onSelect(selectedItem);
                closeAllLists();
            });
            suggestions.appendChild(itemDiv);
        });
    });

    function closeAllLists(elmnt) {
        const items = document.getElementsByClassName('autocomplete-items');
        for (let i = 0; i < items.length; i++) {
            if (elmnt != items[i] && elmnt != searchInput) {
                items[i].parentNode.removeChild(items[i]);
            }
        }
    }

    document.addEventListener('click', function(e) {
        closeAllLists(e.target);
    });
}


/**
 * Initializes a standard table or list filter search box.
 * @param {string} inputId The ID of the search input element.
 * @param {string} clearBtnId The ID of the clear button for the search input.
 * @param {string} targetSelector The CSS selector for the items to be filtered (e.g., '.speech-log-entry' or '#contactsTable tbody tr').
 * @param {string} textSelector The CSS selector within the target item where the text to be searched is located.
 */
function initializeSearchFilter(inputId, clearBtnId, targetSelector, textSelector) {
    const searchInput = document.getElementById(inputId);
    const clearBtn = document.getElementById(clearBtnId);

    if (!searchInput || !clearBtn) return;

    const filterItems = () => {
        const filter = searchInput.value.toUpperCase();
        const items = document.querySelectorAll(targetSelector);

        clearBtn.style.display = searchInput.value.length > 0 ? 'block' : 'none';

        items.forEach(item => {
            const textElement = item.querySelector(textSelector);
            if (textElement) {
                const txtValue = textElement.textContent || textElement.innerText;
                if (txtValue.toUpperCase().indexOf(filter) > -1) {
                    item.style.display = "";
                } else {
                    item.style.display = "none";
                }
            }
        });
    };

    const clearSearch = () => {
        searchInput.value = '';
        filterItems();
    };

    searchInput.addEventListener('keyup', filterItems);
    clearBtn.addEventListener('click', clearSearch);

    // Initial call to set button visibility
    filterItems();
}