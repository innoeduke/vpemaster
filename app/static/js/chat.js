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
        
        // Split lines to format paragraphs & lists
        let lines = html.split('\n');
        let formatted = [];
        let inList = false;

        for (let line of lines) {
            let trimmed = line.trim();
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
        
        let readableName = toolName.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
        let details = '';
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
                        let welcome = data.mode === 'ai' 
                            ? "Hello! I am your VPE Master AI Assistant. I can help you book roles, check in contacts, create meetings, complete levels, and look up records. Ask me anything!"
                            : "Hello! Command Terminal is active. Type `/help` to see list of available commands.";
                        appendMessage('assistant', welcome);
                    }
                    historyLoaded = true;
                    scrollToBottom();
                } else {
                    appendMessage('system', 'Error loading history: ' + data.message);
                }
            })
            .catch(err => {
                showTyping(false);
                appendMessage('system', 'Failed to connect to history server.');
                console.error(err);
            });
    }

    // Clear Chat History
    clearBtn.addEventListener('click', function() {
        if (confirm("Are you sure you want to clear your chat history?")) {
            fetch('/chat/clear', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        messagesPane.innerHTML = '';
                        let welcome = document.getElementById('chatModeBadge').textContent.trim() === 'AI'
                            ? "History cleared. Ask me anything!"
                            : "History cleared. Type `/help` for commands.";
                        appendMessage('assistant', welcome);
                    } else {
                        alert("Failed to clear chat: " + data.message);
                    }
                })
                .catch(err => console.error(err));
        }
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
                appendMessage('system', data.message || 'Error occurred.');
            }
        })
        .catch(err => {
            showTyping(false);
            isSending = false;
            sendBtn.disabled = false;
            appendMessage('system', 'Network error. Could not send message.');
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
