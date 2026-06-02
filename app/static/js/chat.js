// Chat Assistant Frontend Logic

document.addEventListener('DOMContentLoaded', function() {
    const toggleBtn = document.getElementById('chatWidgetToggle');
    const panel = document.getElementById('chatWidgetPanel');
    const minimizeBtn = document.getElementById('chatMinimizeBtn');
    const maximizeBtn = document.getElementById('chatMaximizeBtn');
    const clearBtn = document.getElementById('chatClearBtn');
    const sendBtn = document.getElementById('chatSendBtn');
    const inputText = document.getElementById('chatInputText');
    const messagesPane = document.getElementById('chatPanelMessages');
    const typingIndicator = document.getElementById('chatTypingIndicator');
    const unreadDot = document.getElementById('chatUnreadDot');

    let historyLoaded = false;
    let isSending = false;

    // Helper to render table rows into HTML table
    function renderHtmlTable(rows, hasHeader) {
        let html = '<div class="chat-table-wrapper"><table class="chat-table">';
        
        for (let rowIndex = 0; rowIndex < rows.length; rowIndex++) {
            let cells = rows[rowIndex];
            let isHeader = (rowIndex === 0 && hasHeader);
            
            html += '<tr>';
            for (let cell of cells) {
                let tag = isHeader ? 'th' : 'td';
                html += `<${tag}>${cell}</${tag}>`;
            }
            html += '</tr>';
        }
        
        html += '</table></div>';
        return html;
    }

    // Helper: Escape HTML & format Markdown-like syntax
    function renderMarkdown(text) {
        if (!text) return '';
        
        // Escape HTML to prevent XSS
        let html = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
        
        // Bold: **text**
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // Inline code: `code`
        html = html.replace(/`(.*?)`/g, '<code>$1</code>');
        
        // Links: [label](url)
        // Keep file:// or http/https links active
        html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank">$1</a>');
        
        // Split lines to format paragraphs, lists & tables
        let lines = html.split('\n');
        let formatted = [];
        let inList = false;
        let inTable = false;
        let tableRows = [];

        for (let i = 0; i < lines.length; i++) {
            let line = lines[i];
            let trimmed = line.trim();

            // Detect table rows
            if (trimmed.startsWith('|') && trimmed.endsWith('|') && trimmed.length > 2) {
                // If we are in a list, close it first
                if (inList) {
                    formatted.push('</ul>');
                    inList = false;
                }
                
                // Parse cells: split by '|', skip the first and last empty elements
                let cells = trimmed.split('|').map(c => c.trim());
                cells = cells.slice(1, -1);

                // Check if this is the divider line (e.g. |---|---|)
                let isDivider = cells.every(c => /^[:\s-]+$/.test(c));
                
                if (isDivider) {
                    // Skip the divider line, but mark that we found a table divider
                    if (!inTable && tableRows.length > 0) {
                        inTable = true;
                    }
                    continue;
                }

                tableRows.push(cells);
                continue;
            } else {
                // If we were parsing a table and this line is not a table row, flush the table
                if (tableRows.length > 0) {
                    let tableHtml = renderHtmlTable(tableRows, inTable);
                    formatted.push(tableHtml);
                    tableRows = [];
                    inTable = false;
                }
            }

            // Normal list and paragraph parsing
            if (trimmed.startsWith('* ') || trimmed.startsWith('- ')) {
                if (!inList) {
                    formatted.push('<ul>');
                    inList = true;
                }
                formatted.push('<li>' + trimmed.substring(2) + '</li>');
            } else {
                if (inList) {
                    formatted.push('</ul>');
                    inList = false;
                }
                if (trimmed !== '') {
                    formatted.push('<p>' + trimmed + '</p>');
                }
            }
        }

        // Flush any remaining list or table at the end of loop
        if (tableRows.length > 0) {
            let tableHtml = renderHtmlTable(tableRows, inTable);
            formatted.push(tableHtml);
        }
        if (inList) {
            formatted.push('</ul>');
        }

        return formatted.join('');
    }

    // Scroll to bottom
    function scrollToBottom() {
        messagesPane.scrollTop = messagesPane.scrollHeight;
    }

    // Append Message Bubble
    function appendMessage(role, content) {
        const bubble = document.createElement('div');
        bubble.className = `chat-msg-bubble ${role}`;
        bubble.innerHTML = renderMarkdown(content);
        messagesPane.appendChild(bubble);
        scrollToBottom();
    }

    // Append Tool Summary Card
    function appendToolCard(toolName, args) {
        const card = document.createElement('div');
        card.className = 'chat-tool-card';
        
        const isZh = (typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN');
        let readableName = toolName.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
        
        if (isZh) {
            const nameMap = {
                'assign_role': '分配角色',
                'cancel_role': '取消角色指派',
                'create_meeting': '创建会议',
                'add_contact': '添加联系人',
                'check_in': '签到',
                'complete_level': '记录级别成就',
                'get_pathway_status': '查询路径进度',
                'search_contacts': '搜索联系人',
                'get_meeting_info': '获取会议详情',
                'list_meetings': '列出会议',
                'get_role_assignments': '获取角色指派列表',
                'get_available_roles': '查询空缺角色',
                'update_meeting_status': '更新会议状态',
                'get_voting_results': '获取投票结果',
                'get_meeting_agenda': '获取会议日程',
                'manage_excomm_officers': '执委会管理',
                'query_pathways_library': '查询 Pathways 库'
            };
            if (nameMap[toolName]) {
                readableName = nameMap[toolName];
            }
        }

        let details = '';
        if (isZh) {
            if (toolName === 'assign_role') {
                details = `已指派 ${args.contact_name} 担任会议 ${args.meeting_identifier} 的 ${args.role_name}。`;
            } else if (toolName === 'create_meeting') {
                details = `已在 ${args.date} 创建会议。`;
            } else if (toolName === 'check_in') {
                details = `已签到 ${args.contact_name}。`;
            } else if (toolName === 'complete_level') {
                details = `已为 ${args.contact_name} 记录 ${args.pathway_name} 级别 ${args.level} 的完成成就。`;
            } else {
                details = `已成功执行 ${readableName} 操作。`;
            }
        } else {
            if (toolName === 'assign_role') {
                details = `Assigned ${args.contact_name} as ${args.role_name} for meeting ${args.meeting_identifier}.`;
            } else if (toolName === 'create_meeting') {
                details = `Created meeting on ${args.date}.`;
            } else if (toolName === 'check_in') {
                details = `Checked in ${args.contact_name}.`;
            } else if (toolName === 'complete_level') {
                details = `Completed level ${args.level} of ${args.pathway_name} for ${args.contact_name}.`;
            } else {
                details = `Executed ${readableName} operation.`;
            }
        }

        card.innerHTML = `
            <div class="chat-tool-card-header">
                <i class="fa fa-cogs"></i>
                <span>${readableName}</span>
            </div>
            <div class="chat-tool-card-body">${details}</div>
        `;
        messagesPane.appendChild(card);
        scrollToBottom();
    }

    // Toggle panel
    toggleBtn.addEventListener('click', function() {
        const isOpen = panel.classList.contains('open');
        if (isOpen) {
            panel.classList.remove('open');
            panel.classList.remove('maximized');
            if (maximizeBtn) {
                maximizeBtn.title = "Maximize";
                maximizeBtn.innerHTML = '<i class="fa fa-expand"></i>';
            }
            toggleBtn.classList.remove('active');
        } else {
            panel.classList.add('open');
            toggleBtn.classList.add('active');
            unreadDot.style.display = 'none'; // Clear unread dot
            inputText.focus();
            
            if (!historyLoaded) {
                loadHistory();
            }
        }
    });

    minimizeBtn.addEventListener('click', function() {
        panel.classList.remove('open');
        panel.classList.remove('maximized');
        if (maximizeBtn) {
            maximizeBtn.title = "Maximize";
            maximizeBtn.innerHTML = '<i class="fa fa-expand"></i>';
        }
        toggleBtn.classList.remove('active');
    });

    if (maximizeBtn) {
        maximizeBtn.addEventListener('click', function() {
            const isMaximized = panel.classList.contains('maximized');
            if (isMaximized) {
                panel.classList.remove('maximized');
                maximizeBtn.title = "Maximize";
                maximizeBtn.innerHTML = '<i class="fa fa-expand"></i>';
            } else {
                panel.classList.add('maximized');
                maximizeBtn.title = "Restore";
                maximizeBtn.innerHTML = '<i class="fa fa-compress"></i>';
            }
            scrollToBottom();
        });
    }

    // Load Chat History
    function loadHistory() {
        messagesPane.innerHTML = '';
        showTyping(true);

        fetch('/chat/history')
            .then(res => res.json())
            .then(data => {
                showTyping(false);
                if (data.success) {
                    if (data.messages && data.messages.length > 0) {
                        data.messages.forEach(msg => {
                            appendMessage(msg.role, msg.content);
                        });
                    } else {
                        // Welcome message
                        const isZh = (typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN');
                        let welcome = '';
                        if (isZh) {
                            welcome = data.mode === 'ai'
                                ? "你好！我是您的 Memory Maker AI 助手。我可以帮助您预订角色、签到联系人、创建会议、记录级别成就并查询记录。问我任何问题吧！"
                                : "你好！命令终端已激活。输入 `/help` 查看可用命令列表。";
                        } else {
                            welcome = data.mode === 'ai' 
                                ? "Hello! I am your Memory Maker AI Assistant. I can help you book roles, check in contacts, create meetings, complete levels, and look up records. Ask me anything!"
                                : "Hello! Command Terminal is active. Type `/help` to see list of available commands.";
                        }
                        appendMessage('assistant', welcome);
                    }
                    historyLoaded = true;
                    scrollToBottom();
                } else {
                    const isZh = (typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN');
                    const errMsg = isZh ? '加载历史记录出错：' : 'Error loading history: ';
                    appendMessage('system', errMsg + data.message);
                }
            })
            .catch(err => {
                showTyping(false);
                const isZh = (typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN');
                const errMsg = isZh ? '连接历史记录服务器失败。' : 'Failed to connect to history server.';
                appendMessage('system', errMsg);
                console.error(err);
            });
    }

    // Clear Chat History
    clearBtn.addEventListener('click', function() {
        fetch('/chat/clear', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    messagesPane.innerHTML = '';
                    const isZh = (typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN');
                    const isAi = document.getElementById('chatModeBadge').textContent.trim() === 'AI';
                    let welcome = '';
                    if (isZh) {
                        welcome = isAi
                            ? "历史记录已清除。问我任何问题吧！"
                            : "历史记录已清除。输入 `/help` 查看命令。";
                    } else {
                        welcome = isAi
                            ? "History cleared. Ask me anything!"
                            : "History cleared. Type `/help` for commands.";
                    }
                    appendMessage('assistant', welcome);
                } else {
                    const isZh = (typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN');
                    const errMsg = isZh ? "清除聊天失败：" : "Failed to clear chat: ";
                    alert(errMsg + data.message);
                }
            })
            .catch(err => console.error(err));
    });

    // Show/Hide Typing Indicator
    function showTyping(show) {
        if (show) {
            typingIndicator.style.display = 'flex';
            scrollToBottom();
        } else {
            typingIndicator.style.display = 'none';
        }
    }

    // Send Message
    function sendMessage() {
        const text = inputText.value.trim();
        if (!text || isSending) return;

        isSending = true;
        inputText.value = '';
        inputText.style.height = '36px'; // Reset height
        sendBtn.disabled = true;
        
        appendMessage('user', text);
        showTyping(true);

        fetch('/chat/send', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: text })
        })
        .then(res => res.json())
        .then(data => {
            showTyping(false);
            isSending = false;
            sendBtn.disabled = false;
            
            if (data.success) {
                // If tools were run, show compact tool execution summaries
                if (data.executed_tools && data.executed_tools.length > 0) {
                    data.executed_tools.forEach(tool => {
                        appendToolCard(tool.name, tool.arguments);
                    });
                }
                appendMessage('assistant', data.content);
                
                // If user closed panel while loading, show notification dot
                if (!panel.classList.contains('open')) {
                    unreadDot.style.display = 'block';
                }
            } else {
                const isZh = (typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN');
                const errMsg = isZh ? '发生错误。' : 'Error occurred.';
                appendMessage('system', data.message || errMsg);
            }
        })
        .catch(err => {
            showTyping(false);
            isSending = false;
            sendBtn.disabled = false;
            const isZh = (typeof CURRENT_LOCALE !== 'undefined' && CURRENT_LOCALE === 'zh_CN');
            const errMsg = isZh ? '网络错误。无法发送消息。' : 'Network error. Could not send message.';
            appendMessage('system', errMsg);
            console.error(err);
        });
    }

    sendBtn.addEventListener('click', sendMessage);

    // Keyboard handlers & Textarea Auto-growth
    inputText.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    inputText.addEventListener('input', function() {
        this.style.height = '36px';
        this.style.height = (this.scrollHeight - 4) + 'px';
    });

    // Auto-pulse button once to draw user attention
    setTimeout(() => {
        if (!panel.classList.contains('open')) {
            unreadDot.style.display = 'block';
        }
    }, 2000);
});
