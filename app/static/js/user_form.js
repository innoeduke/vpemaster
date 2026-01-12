/**
 * Logic for the User Form contact search and automatic contact creation.
 */
document.addEventListener('DOMContentLoaded', function () {
    const contactSearch = document.getElementById('contact_search');
    const contactIdHidden = document.getElementById('contact_id_hidden');
    const createNewCheckbox = document.getElementById('create_new_contact');
    const contactDropdown = document.getElementById('contact_dropdown');
    const contactDataScript = document.getElementById('contact_data');

    if (!contactSearch || !createNewCheckbox || !contactDropdown || !contactDataScript) return;

    let contacts = [];
    try {
        contacts = JSON.parse(contactDataScript.textContent);
    } catch (e) {
        console.error("Failed to parse contact data", e);
    }

    // Handle checkbox toggling
    createNewCheckbox.addEventListener('change', function () {
        if (this.checked) {
            contactSearch.disabled = true;
            contactSearch.style.backgroundColor = '#f0f0f0';
            contactSearch.value = '';
            contactIdHidden.value = '0';
            contactDropdown.style.display = 'none';
        } else {
            contactSearch.disabled = false;
            contactSearch.style.backgroundColor = '';
        }
    });

    // Handle custom autocomplete selection
    contactSearch.addEventListener('input', function () {
        const val = this.value.toLowerCase();
        contactDropdown.innerHTML = '';

        if (!val) {
            contactDropdown.style.display = 'none';
            contactIdHidden.value = '0';
            return;
        }

        const filtered = contacts
            .filter(c => c.name.toLowerCase().includes(val))
            .slice(0, 5); // Limit to top 5

        if (filtered.length > 0) {
            filtered.forEach(c => {
                const div = document.createElement('div');
                div.className = 'autocomplete-suggestion';
                div.textContent = c.name;
                div.addEventListener('click', function () {
                    contactSearch.value = c.name;
                    contactIdHidden.value = c.id;
                    contactDropdown.style.display = 'none';
                });
                contactDropdown.appendChild(div);
            });
            contactDropdown.style.display = 'block';
        } else {
            contactDropdown.style.display = 'none';
            contactIdHidden.value = '0';
        }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function (e) {
        if (e.target !== contactSearch && e.target !== contactDropdown) {
            contactDropdown.style.display = 'none';
        }
    });

    // Ensure hidden field is updated if user clears the search box manually
    contactSearch.addEventListener('blur', function () {
        // We use a timeout to let the click event on the suggestion execute first
        setTimeout(() => {
            const currentVal = contactSearch.value.toLowerCase();
            const match = contacts.find(c => c.name.toLowerCase() === currentVal);
            if (match) {
                contactIdHidden.value = match.id;
            } else if (contactSearch.value === '') {
                contactIdHidden.value = '0';
            }
        }, 200);
    });
});
