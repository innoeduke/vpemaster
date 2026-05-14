/**
 * Generic Autocomplete component.
 * @param {HTMLInputElement} inputElement - The text input for searching.
 * @param {HTMLInputElement} hiddenElement - The hidden input to store the selected ID.
 * @param {Array} dataSource - Array of objects to search through.
 * @param {Object} options - Configuration options.
 */
function initAutocomplete(inputElement, hiddenElement, dataSource, options = {}) {
    const {
        displayKey = 'Name',
        idKey = 'id',
        onSelect = null,
        maxResults = 10,
        resultRenderer = null
    } = options;

    let currentFocus = -1;

    inputElement.addEventListener("input", function(e) {
        let container, item, val = this.value;
        closeAllLists();
        
        if (!val || val.length < 1) {
            hiddenElement.value = "";
            return;
        }

        currentFocus = -1;
        container = document.createElement("div");
        container.setAttribute("id", this.id + "autocomplete-list");
        container.setAttribute("class", "autocomplete-suggestions");
        
        this.parentNode.appendChild(container);

        const filtered = dataSource.filter(data => 
            data[displayKey].toUpperCase().includes(val.toUpperCase())
        ).slice(0, maxResults);

        filtered.forEach(data => {
            item = document.createElement("div");
            item.setAttribute("class", "autocomplete-suggestion");
            
            if (resultRenderer) {
                item.innerHTML = resultRenderer(data, val);
            } else {
                // Highlight matching part
                const matchStart = data[displayKey].toUpperCase().indexOf(val.toUpperCase());
                const matchEnd = matchStart + val.length;
                const beforeMatch = data[displayKey].slice(0, matchStart);
                const match = data[displayKey].slice(matchStart, matchEnd);
                const afterMatch = data[displayKey].slice(matchEnd);
                
                item.innerHTML = `${beforeMatch}<strong>${match}</strong>${afterMatch}`;
            }

            item.addEventListener("click", function(e) {
                inputElement.value = data[displayKey];
                hiddenElement.value = data[idKey];
                closeAllLists();
                if (onSelect) onSelect(data);
            });
            container.appendChild(item);
        });
    });

    inputElement.addEventListener("keydown", function(e) {
        let x = document.getElementById(this.id + "autocomplete-list");
        if (x) x = x.getElementsByTagName("div");
        if (e.keyCode == 40) { // DOWN
            currentFocus++;
            addActive(x);
        } else if (e.keyCode == 38) { // UP
            currentFocus--;
            addActive(x);
        } else if (e.keyCode == 13) { // ENTER
            e.preventDefault();
            if (currentFocus > -1) {
                if (x) x[currentFocus].click();
            }
        }
    });

    function addActive(x) {
        if (!x) return false;
        removeActive(x);
        if (currentFocus >= x.length) currentFocus = 0;
        if (currentFocus < 0) currentFocus = (x.length - 1);
        x[currentFocus].classList.add("autocomplete-active");
    }

    function removeActive(x) {
        for (let i = 0; i < x.length; i++) {
            x[i].classList.remove("autocomplete-active");
        }
    }

    function closeAllLists(elmnt) {
        const x = document.getElementsByClassName("autocomplete-suggestions");
        for (let i = 0; i < x.length; i++) {
            if (elmnt != x[i] && elmnt != inputElement) {
                x[i].parentNode.removeChild(x[i]);
            }
        }
    }

    document.addEventListener("click", function (e) {
        closeAllLists(e.target);
    });
}
