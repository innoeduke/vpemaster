document.addEventListener("DOMContentLoaded", function () {
  // 添加与agenda.html相同的会议过滤器事件监听器
  const meetingFilter = document.getElementById("meeting-filter");
  if (meetingFilter) {
    meetingFilter.addEventListener("change", () => {
      window.location.href = `/roster?meeting_number=${meetingFilter.value}`;
    });
  }

  // 使用事件委托处理联系人选择变化
  document.addEventListener('change', function(event) {
    if (event.target.id === 'contact_id') {
      const contactSelect = event.target;
      const contactTypeSelect = document.getElementById("contact_type");
      
      if (contactTypeSelect) {
        const selectedOption = contactSelect.options[contactSelect.selectedIndex];
        const contactType = selectedOption.getAttribute("data-type");

        // 在类别选择框中选择匹配的选项
        let matchedIndex = -1;
        for (let i = 0; i < contactTypeSelect.options.length; i++) {
          if (contactTypeSelect.options[i].value === contactType) {
            matchedIndex = i;
            break;
          }
        }

        // 如果找到匹配项，则选择它；否则选择默认的空选项
        if (matchedIndex !== -1) {
          contactTypeSelect.selectedIndex = matchedIndex;
        } else {
          contactTypeSelect.selectedIndex = 0; // 选择空选项
        }
      }
    }
  });

  // 设置表单中的order_number为下一个可用序号（最后序号+1），如果没有条目则默认为1
  const nextOrderNumber = document.getElementById('next-order-number')?.value || '';
  if (nextOrderNumber) {
    document.getElementById("order_number").value = nextOrderNumber;
  } else {
    // 如果没有条目，则默认设置为1
    document.getElementById("order_number").value = 1;
  }

  // 打开联系人模态框并添加来源参数
  window.openContactModalWithReferer = function() {
    // 调用原始的 openContactModal 函数
    openContactModal();
    
    // 修改表单的 action，添加来源参数
    const contactForm = document.getElementById("contactForm");
    if (contactForm) {
      contactForm.action = contactForm.action + "?referer=" + encodeURIComponent(window.location.href);
    }
  }

  // 检查URL中是否有新添加的联系人ID参数
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.has('new_contact_id') && urlParams.has('new_contact_name') && urlParams.has('new_contact_type')) {
    // 获取新联系人的信息
    const contactId = urlParams.get('new_contact_id');
    const contactName = decodeURIComponent(urlParams.get('new_contact_name'));
    const contactType = decodeURIComponent(urlParams.get('new_contact_type'));
    
    // 将新联系人添加到联系人选择框中
    const contactSelect = document.getElementById("contact_id");
    let optionExists = false;
    
    // 检查选项是否已存在
    for (let i = 0; i < contactSelect.options.length; i++) {
      if (contactSelect.options[i].value === contactId) {
        optionExists = true;
        break;
      }
    }
    
    // 如果选项不存在，则添加
    if (!optionExists) {
      const newOption = document.createElement("option");
      newOption.value = contactId;
      newOption.textContent = contactName;
      newOption.setAttribute("data-type", contactType);
      contactSelect.appendChild(newOption);
    }
    
    // 选中新添加的联系人
    contactSelect.value = contactId;
    
    // 触发联系人选择框的change事件，以自动填充联系人类别
    contactSelect.dispatchEvent(new Event('change'));
    
    // 从URL中移除参数
    const url = new URL(window.location);
    url.searchParams.delete('new_contact_id');
    url.searchParams.delete('new_contact_name');
    url.searchParams.delete('new_contact_type');
    window.history.replaceState({}, document.title, url);
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
            // 保存成功后刷新表单，准备下一次输入
            const rosterForm = document.getElementById("roster-form");
            if (rosterForm) {
              rosterForm.reset();
              
              // 清空隐藏的entry-id字段
              document.getElementById("entry-id").value = "";
              
              // 重置表单标题
              document.getElementById("form-title").textContent = "Add Entry";
              
              // 重新设置order_number为下一个可用序号
              const nextOrderNumber = document.getElementById('next-order-number')?.value || '';
              if (nextOrderNumber) {
                document.getElementById("order_number").value = nextOrderNumber;
              } else {
                // 如果没有条目，则默认设置为1
                document.getElementById("order_number").value = 1;
              }
            }
            
            // 显示成功消息
            alert("Entry saved successfully!");
          }
        })
        .catch((error) => {
          console.error("Error:", error);
          alert("An error occurred while saving the entry.");
        });
    });
});