document.addEventListener("DOMContentLoaded", function () {
  // 添加与agenda.html相同的会议过滤器事件监听器
  const meetingFilter = document.getElementById("meeting-filter");
  if (meetingFilter) {
    meetingFilter.addEventListener("change", () => {
      window.location.href = `/roster?meeting_number=${meetingFilter.value}`;
    });
  }

  // 当联系人选择改变时，自动填充类别字段
  const contactSelect = document.getElementById("contact_id");
  const contactTypeSelect = document.getElementById("contact_type");

  if (contactSelect && contactTypeSelect) {
    contactSelect.addEventListener("change", function () {
      const selectedOption = this.options[this.selectedIndex];
      const contactType = selectedOption.getAttribute("data-type");

      // 在类别选择框中选择匹配的选项
      for (let i = 0; i < contactTypeSelect.options.length; i++) {
        if (contactTypeSelect.options[i].value === contactType) {
          contactTypeSelect.selectedIndex = i;
          break;
        }
      }
    });
  }

  // 设置表单中的order_number为第一个未分配条目的序号，如果没有则默认为1
  const firstUnallocatedOrder =
    "{{ first_unallocated_entry.order_number if first_unallocated_entry else '' }}";
  if (firstUnallocatedOrder) {
    document.getElementById("order_number").value = firstUnallocatedOrder;
  } else {
    // 如果没有未分配的条目，则默认设置为1
    document.getElementById("order_number").value = 1;
  }

  // 表单提交处理
  document
    .getElementById("roster-form")
    .addEventListener("submit", function (e) {
      e.preventDefault();

      const entryId = document.getElementById("entry-id").value;
      const url = entryId
        ? `/roster/api/roster/${entryId}`
        : "/roster/api/roster";
      const method = entryId ? "PUT" : "POST";

      const formData = {
        meeting_number: document.getElementById("meeting-filter").value,
        order_number: document.getElementById("order_number").value,
        contact_id: document.getElementById("contact_id").value,
        ticket: document.getElementById("ticket").value,
      };

      fetch(url, {
        method: method,
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formData),
      })
        .then((response) => {
          // 检查响应是否成功
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          return response.json();
        })
        .then((data) => {
          if (data.error) {
            alert("Error: " + data.error);
          } else {
            // 保存成功后重定向到当前会议页面，确保显示所有条目
            const meetingNumber =
              document.getElementById("meeting-filter").value;
            window.location.href = `/roster?meeting_number=${meetingNumber}`;
          }
        })
        .catch((error) => {
          console.error("Error:", error);
          alert("An error occurred while saving the entry: " + error.message);
        });
    });

  // 编辑按钮处理
  document.querySelectorAll(".edit-entry").forEach((button) => {
    button.addEventListener("click", function () {
      const entryId = this.getAttribute("data-id");
      const row = document.querySelector(`tr[data-entry-id="${entryId}"]`);

      // 填充表单
      document.getElementById("entry-id").value = entryId;
      document.getElementById("order_number").value = row.cells[0].textContent;
      document.getElementById("ticket").value = row.cells[2].textContent;

      // 设置联系人，处理N/A情况
      const contactName = row.cells[1].textContent;
      const contactSelect = document.getElementById("contact_id");
      for (let i = 0; i < contactSelect.options.length; i++) {
        if (contactSelect.options[i].text === contactName) {
          contactSelect.selectedIndex = i;
          // 触发change事件以自动填充类别
          contactSelect.dispatchEvent(new Event("change"));
          break;
        }
      }

      // 更新表单标题
      document.getElementById("form-title").textContent = "Edit Entry";

      // 滚动到表单
      document
        .querySelector(".roster-form-container")
        .scrollIntoView({ behavior: "smooth" });
    });
  });

  // 取消按钮处理
  document.querySelectorAll(".cancel-entry").forEach((button) => {
    button.addEventListener("click", function () {
      const entryId = this.getAttribute("data-id");

      if (confirm("Are you sure you want to cancel this entry?")) {
        fetch(`/roster/api/roster/${entryId}`, {
          method: "DELETE",
        })
          .then((response) => {
            // 检查响应是否成功
            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
          })
          .then((data) => {
            if (data.error) {
              alert("Error: " + data.error);
            } else {
              // 取消成功后重定向到当前会议页面，确保显示所有条目
              const meetingNumber =
                document.getElementById("meeting-filter").value;
              window.location.href = `/roster?meeting_number=${meetingNumber}`;
            }
          })
          .catch((error) => {
            console.error("Error:", error);
            alert(
              "An error occurred while cancelling the entry: " + error.message
            );
          });
      }
    });
  });

  // 取消编辑按钮处理
  const cancelEditButton = document.getElementById("cancel-edit");
  if (cancelEditButton) {
    cancelEditButton.addEventListener("click", function () {
      const rosterForm = document.getElementById("roster-form");
      if (rosterForm) {
        rosterForm.reset();
      }
      document.getElementById("entry-id").value = "";
      document.getElementById("form-title").textContent = "Add Entry";
    });
  }
});
