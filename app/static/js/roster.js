document.addEventListener("DOMContentLoaded", function () {
  const meetingFilter = document.getElementById("meeting-filter");
  const rosterForm = document.getElementById("roster-form");
  const tableBody = document.querySelector(".table tbody");
  const cancelEditBtn = document.getElementById("cancel-edit");
  const formTitle = document.getElementById("form-title");
  const entryIdInput = document.getElementById("entry-id");
  const orderNumberInput = document.getElementById("order_number");
  const contactIdSelect = document.getElementById("contact_id");
  const contactTypeSelect = document.getElementById("contact_type");
  const ticketSelect = document.getElementById("ticket");

  // Handle meeting selection change
  if (meetingFilter) {
    meetingFilter.addEventListener("change", () => {
      window.location.href = `/roster?meeting_number=${meetingFilter.value}`;
    });
  }

  // Auto-fill contact type when a contact is selected.
  if (contactIdSelect) {
    contactIdSelect.addEventListener("change", function () {
      const selectedOption = this.options[this.selectedIndex];
      const contactType = selectedOption.getAttribute("data-type");
      if (contactTypeSelect && contactType) {
        contactTypeSelect.value = contactType;
        // Manually trigger change event to cascade updates (e.g., ticket class).
        contactTypeSelect.dispatchEvent(new Event("change"));
      } else if (contactTypeSelect) {
        contactTypeSelect.value = "";
      }
    });
  }

  // If contact type is changed to 'Officer', also set ticket class to 'Officer'.
  if (contactTypeSelect) {
    contactTypeSelect.addEventListener("change", function () {
      if (this.value === "Officer") {
        ticketSelect.value = "Officer";
      } else {
        ticketSelect.value = "Early-bird";
      }
    });
  }

  // Function to reset the form to its initial state for adding a new entry
  function resetRosterForm() {
    if (!rosterForm) return;
    rosterForm.reset();
    entryIdInput.value = "";
    formTitle.textContent = "Add Entry";
    contactTypeSelect.value = "";


    // Calculate next order number from the table, based on actual entries
    const rows = tableBody.querySelectorAll("tr[data-entry-id]");
    let maxOrder = 0;
    rows.forEach((row) => {
      const orderCell = row.querySelector("td:first-child");
      if (orderCell && orderCell.textContent) {
        const order = parseInt(orderCell.textContent.trim(), 10);
        if (!isNaN(order) && order > maxOrder) {
          maxOrder = order;
        }
      }
    });
    const nextOrder = maxOrder > 0 ? maxOrder + 1 : 1;
    orderNumberInput.value = nextOrder;
  }
  
  function populateRosterEditForm(rosterId) {
    fetch(`/roster/api/roster/${rosterId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch entry details.');
            }
            return response.json();
        })
        .then(entry => {
            entryIdInput.value = entry.id;
            orderNumberInput.value = entry.order_number;
            contactIdSelect.value = entry.contact_id;
            ticketSelect.value = entry.ticket;

            // Trigger change to update contact type
            contactIdSelect.dispatchEvent(new Event('change'));

            formTitle.textContent = 'Edit Entry';
            rosterForm.scrollIntoView({ behavior: 'smooth' });
        })
        .catch(error => {
            console.error('Error fetching entry for edit:', error);
            alert('Error fetching entry for edit: ' + error.message);
        });
  }

  if (tableBody) {
    // Set initial order number
    resetRosterForm();

    // Handle clicks on the table for edit and cancel actions
    // Handle clicks on the table for edit and cancel actions
    tableBody.addEventListener("click", function (e) {
      const editButton = e.target.closest(".edit-entry");
      const cancelButton = e.target.closest(".cancel-entry");

      if (editButton) {
        e.preventDefault();
        const entryId = editButton.dataset.id;
        populateRosterEditForm(entryId);
      }

      if (cancelButton) {
        e.preventDefault();
        const entryId = cancelButton.dataset.id;
        if (confirm("Are you sure you want to cancel this roster entry?")) {
          fetch(`/roster/api/roster/${entryId}`, { method: "DELETE" })
            .then((response) =>
              response.json().then((data) => ({ ok: response.ok, data }))
            )
            .then(({ ok, data }) => {
              if (!ok) throw new Error(data.error || "Failed to cancel entry.");
              window.location.reload();
            })
            .catch((error) => {
              console.error("Error cancelling entry:", error);
              alert(`Error: ${error.message}`);
            });
        }
      }
    });
  }

  // Handle cancel edit button click
  if (cancelEditBtn) {
    cancelEditBtn.addEventListener("click", resetRosterForm);
  }

  // Handle form submission for adding/updating entries
  if (rosterForm) {
    rosterForm.addEventListener("submit", function (e) {
      e.preventDefault();

      const entryId = entryIdInput.value;
      const url = entryId
        ? `/roster/api/roster/${entryId}`
        : "/roster/api/roster";
      const method = entryId ? "PUT" : "POST";

      const formData = {
        meeting_number: meetingFilter.value,
        order_number: orderNumberInput.value,
        contact_id: contactIdSelect.value,
        ticket: ticketSelect.value,
      };

      fetch(url, {
        method: method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      })
        .then((response) =>
          response.json().then((data) => ({ ok: response.ok, data }))
        )
        .then(({ ok, data }) => {
          if (!ok) throw new Error(data.error || "Failed to save the entry.");
          window.location.reload();
        })
        .catch((error) => {
          console.error("Error:", error);
          alert(`An error occurred while saving the entry: ${error.message}`);
        });
    });
  }

  // Handle adding a new contact and returning to the roster
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.has("new_contact_id") && urlParams.has("new_contact_name")) {
    const contactId = urlParams.get("new_contact_id");
    const contactName = decodeURIComponent(urlParams.get("new_contact_name"));
    const contactType = decodeURIComponent(
      urlParams.get("new_contact_type") || ""
    );

    if (
      contactIdSelect &&
      !Array.from(contactIdSelect.options).some(
        (opt) => opt.value === contactId
      )
    ) {
      const newOption = new Option(contactName, contactId);
      newOption.setAttribute("data-type", contactType);
      contactIdSelect.add(newOption);
    }

    if (contactIdSelect) {
      contactIdSelect.value = contactId;
      contactIdSelect.dispatchEvent(new Event("change"));
    }

    const url = new URL(window.location);
    url.searchParams.delete("new_contact_id");
    url.searchParams.delete("new_contact_name");
    url.searchParams.delete("new_contact_type");
    window.history.replaceState({}, document.title, url.toString());
  }
  
  // Initialize sorting if the function exists
  if (typeof setupTableSorting === "function") {
    setupTableSorting("rosterTable");
  }
  
  // Initialize lucky draw functionality
  initializeLuckyDraw();
});

// Opens the contact modal and sets the referrer for redirection
function openContactModalWithReferer() {
  if (typeof openContactModal === "function") {
    openContactModal();
  }
  const contactForm = document.getElementById("contactForm");
  if (contactForm) {
    const actionUrl = new URL(contactForm.action);
    actionUrl.searchParams.set("referer", window.location.href);
    contactForm.action = actionUrl.toString();
  }
}

// 抽奖功能
function initializeLuckyDraw() {
  const drawButton = document.getElementById('drawButton');
  if (drawButton) {
    drawButton.addEventListener('click', performLuckyDraw);
  }
}

// 存储已抽中的获奖者
let drawnWinners = [];

// 抽奖功能实现
function performLuckyDraw() {
  // 获取所有有效的名册条目（排除已取消的条目和已抽中的获奖者）
  const validEntries = [];
  const rows = document.querySelectorAll("#rosterTable tbody tr");
  
  rows.forEach(row => {
    // 检查行是否为空行（没有数据）
    const orderCell = row.querySelector('td:first-child');
    if (orderCell && orderCell.textContent.trim() !== '' && orderCell.textContent.trim() !== 'N/A') {
      const ticketCell = row.querySelector('td:nth-child(4)');
      if (ticketCell && ticketCell.textContent.trim() !== 'Cancelled') {
        const order = orderCell.textContent.trim();
        const name = row.querySelector('td:nth-child(2)').textContent.trim();
        
        // 检查是否已经被抽中
        const isAlreadyDrawn = drawnWinners.some(winner => 
          winner.order === order && winner.name === name
        );
        
        if (!isAlreadyDrawn) {
          validEntries.push({
            order: order,
            name: name
          });
        }
      }
    }
  });
  
  // 如果没有有效条目，显示提示信息
  if (validEntries.length === 0) {
    document.getElementById('luckyDrawResult').innerHTML = 
      '<div class="no-entries">No valid entries for drawing</div>';
    return;
  }
  
  // 随机选择一个条目
  const randomIndex = Math.floor(Math.random() * validEntries.length);
  const selectedEntry = validEntries[randomIndex];
  
  // 添加到已抽中的获奖者列表
  drawnWinners.push(selectedEntry);
  
  // 显示结果
  document.getElementById('luckyDrawResult').innerHTML = 
    '<div class="winner-order">' + selectedEntry.order + '</div>' +
    '<div class="winner-name">' + selectedEntry.name + '</div>';
  
  // 添加到获奖者列表
  const winnersList = document.getElementById('winnersList');
  if (winnersList) {
    const winnerElement = document.createElement('div');
    winnerElement.textContent = selectedEntry.order + '# ' + selectedEntry.name;
    winnersList.appendChild(winnerElement);
  }
}
