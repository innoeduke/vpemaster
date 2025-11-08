function setupSearch(inputId, containerSelector, itemSelector, textSelector) {
    const searchInput = document.getElementById(inputId);
    const clearButton = document.getElementById(`clear-${inputId}`);
    const containers = document.querySelectorAll(containerSelector);

    function filterItems() {
        const filter = searchInput.value.toUpperCase();

        if (searchInput.value.length > 0) {
            clearButton.style.display = 'block';
        } else {
            clearButton.style.display = 'none';
        }

        containers.forEach(container => {
            const items = container.querySelectorAll(itemSelector);
            let hasVisibleItems = false;

            items.forEach(item => {
                const textElement = item.querySelector(textSelector);
                if (textElement) {
                    const textValue = textElement.textContent || textElement.innerText;
                    if (textValue.toUpperCase().indexOf(filter) > -1) {
                        item.style.display = '';
                        hasVisibleItems = true;
                    } else {
                        item.style.display = 'none';
                    }
                }
            });

            // For speech logs: hide level heading if no items are visible
            const levelHeading = container.previousElementSibling;
            if (levelHeading && levelHeading.classList.contains('level-heading')) {
                levelHeading.style.display = hasVisibleItems ? '' : 'none';
            }
        });
    }

    function clearSearch() {
        searchInput.value = '';
        filterItems();
    }

    searchInput.addEventListener('keyup', filterItems);
    clearButton.addEventListener('click', clearSearch);

    // Initial setup to show/hide clear button
    filterItems();
}