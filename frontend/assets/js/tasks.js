(function () {
    // 配置 marked.js
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,  // 支持换行
            gfm: true,     // GitHub Flavored Markdown
        });
    }

    const dailyForm = document.getElementById("daily-task-form");
    const temporaryForm = document.getElementById("temporary-task-form");
    const dailyList = document.getElementById("daily-task-list");
    const temporaryList = document.getElementById("temporary-task-list");
    const assistantBox = document.getElementById("assistant-conversation");
    const assistantForm = document.getElementById("assistant-chat-form");
    const assistantInput = document.getElementById("assistant-message");
    const assistantRefresh = document.getElementById("assistant-refresh");

    if (!dailyForm || !temporaryForm || !dailyList || !temporaryList || !assistantBox || !assistantForm || !assistantInput) {
        return;
    }

    const state = {
        daily: [],
        temporary: [],
        messages: []  // 改为messages,与ai-chat保持一致
    };

    dailyForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(dailyForm);
        const title = formData.get("title");
        if (!title) return;
        await createTask(title.toString(), "daily", dailyForm);
    });

    temporaryForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(temporaryForm);
        const title = formData.get("title");
        if (!title) return;
        await createTask(title.toString(), "temporary", temporaryForm);
    });

    assistantForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const content = assistantInput.value.trim();
        if (!content) return;
        appendMessage("user", content);  // 简化:直接添加消息
        assistantInput.value = "";
        await sendToAssistant();  // 发送到服务器
    });

    assistantInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            assistantForm.requestSubmit();
        }
    });

    if (assistantRefresh) {
        assistantRefresh.addEventListener("click", async () => {
            clearMessages();  // 清空对话
            await autoAnalyzeTasks();  // 重新分析
        });
    }

    async function createTask(title, type, form) {
        try {
            const response = await fetch("/api/tasks", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title, task_type: type })
            });
            if (!response.ok) {
                const reason = await response.json().catch(() => ({}));
                throw new Error(reason.detail || "任务添加失败");
            }
            form.reset();
            await loadTasks();
            // 任务变更后自动分析
            await autoAnalyzeTasks();
        } catch (error) {
            console.error(error);
            alert(error.message || "任务添加失败，请稍后再试");
        }
    }

    async function toggleTask(id) {
        try {
            const response = await fetch(`/api/tasks/${id}/toggle`, { method: "POST" });
            if (!response.ok) {
                throw new Error("更新失败");
            }
            await loadTasks();
            // 任务状态变更后自动分析
            await autoAnalyzeTasks();
        } catch (error) {
            console.error(error);
            alert("无法更新任务状态，请稍后再试");
        }
    }

    async function deleteTask(id) {
        try {
            const response = await fetch(`/api/tasks/${id}`, { method: "DELETE" });
            if (!response.ok) {
                throw new Error("删除失败");
            }
            await loadTasks();
            // 删除任务后自动分析
            await autoAnalyzeTasks();
        } catch (error) {
            console.error(error);
            alert("删除任务失败，请稍后再试");
        }
    }

    function renderList(container, tasks) {
        if (!tasks.length) {
            container.innerHTML = '<li class="muted">尚未添加任务。</li>';
            return;
        }
        container.innerHTML = tasks.map((task) => `
            <li class="task-item" data-id="${task.id}">
                <label class="task-check">
                    <input type="checkbox" ${task.completed ? "checked" : ""}>
                    <span>${task.title}</span>
                </label>
                <button class="ghost-button" data-action="delete">删除</button>
            </li>
        `).join("");
    }

    function wireList(container, handler) {
        container.addEventListener("click", (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) return;
            const parent = target.closest(".task-item");
            if (!parent) return;
            const id = parent.dataset.id;
            if (!id) return;
            if (target.dataset.action === "delete") {
                handler("delete", id);
            }
        });
        container.addEventListener("change", (event) => {
            const target = event.target;
            if (!(target instanceof HTMLInputElement)) return;
            if (target.type !== "checkbox") return;
            const parent = target.closest(".task-item");
            if (!parent) return;
            const id = parent.dataset.id;
            if (id) handler("toggle", id);
        });
    }

    wireList(dailyList, async (action, id) => {
        if (action === "toggle") {
            await toggleTask(id);
        } else if (action === "delete") {
            await deleteTask(id);
        }
    });

    wireList(temporaryList, async (action, id) => {
        if (action === "toggle") {
            await toggleTask(id);
        } else if (action === "delete") {
            await deleteTask(id);
        }
    });

    async function loadTasks() {
        try {
            const response = await fetch("/api/tasks");
            if (!response.ok) {
                throw new Error("加载失败");
            }
            const payload = await response.json();
            state.daily = payload.daily || [];
            state.temporary = payload.temporary || [];
            renderList(dailyList, state.daily);
            renderList(temporaryList, state.temporary);
        } catch (error) {
            console.error(error);
            dailyList.innerHTML = '<li class="muted">任务加载失败。</li>';
            temporaryList.innerHTML = '<li class="muted">任务加载失败。</li>';
        }
    }

    function escapeHTML(text) {
        const div = document.createElement("div");
        div.textContent = text ?? "";
        return div.innerHTML;
    }

    // 参考 ai-chat.js 的消息添加逻辑
    function appendMessage(role, content) {
        state.messages.push({ role, content });
        const wrapper = document.createElement("div");
        wrapper.className = `chat-message ${role === "user" ? "from-user" : "from-assistant"}`;
        const displayName = role === "user" ? "我" : "AI 助手";

        // AI助手的回复使用 Markdown 渲染，用户消息使用纯文本
        const bubbleContent = role === "assistant" && typeof marked !== 'undefined'
            ? marked.parse(content)
            : escapeHTML(content);

        wrapper.innerHTML = `
            <div class="chat-avatar">
                <span class="avatar-initial">${displayName.charAt(0)}</span>
            </div>
            <div class="chat-body">
                <div class="chat-name">${escapeHTML(displayName)}</div>
                <div class="chat-bubble">${bubbleContent}</div>
            </div>
        `;
        assistantBox.appendChild(wrapper);
        assistantBox.scrollTop = assistantBox.scrollHeight;
    }

    // 参考 ai-chat.js 的加载占位符
    function appendPending() {
        const wrapper = document.createElement("div");
        wrapper.className = "chat-message from-assistant pending";
        wrapper.innerHTML = `
            <div class="chat-avatar">
                <span class="avatar-initial">AI</span>
            </div>
            <div class="chat-body">
                <div class="chat-name">AI 助手</div>
                <div class="chat-bubble muted">正在思考…</div>
            </div>
        `;
        assistantBox.appendChild(wrapper);
        assistantBox.scrollTop = assistantBox.scrollHeight;
        return wrapper;
    }

    // 参考 ai-chat.js 的移除占位符
    function removePending(node) {
        if (node && node.parentElement) {
            node.parentElement.removeChild(node);
        }
    }

    function clearMessages() {
        state.messages = [];
        assistantBox.innerHTML = "";
    }

    // 自动分析任务 - 页面加载或任务变更时调用
    async function autoAnalyzeTasks() {
        clearMessages();  // 清空之前的对话
        const placeholder = appendPending();
        try {
            const response = await fetch("/api/tasks/assistant/analyze", { method: "POST" });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || "分析失败");
            }
            const result = await response.json();
            removePending(placeholder);
            // 将AI的分析结果作为第一条消息添加
            appendMessage("assistant", result.reply || "暂无建议");
        } catch (error) {
            console.error(error);
            removePending(placeholder);
            appendMessage("assistant", error.message || "任务分析暂时无法进行，请检查配置后重试。");
        }
    }

    // 发送对话到服务器 - 参考 ai-chat.js 的 sendToServer
    async function sendToAssistant() {
        const payload = {
            messages: state.messages.map(msg => ({ role: msg.role, content: msg.content }))
        };
        const placeholder = appendPending();
        try {
            const response = await fetch("/api/tasks/assistant/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || "对话失败");
            }
            const result = await response.json();
            removePending(placeholder);
            appendMessage("assistant", result.reply || "(暂无回复)");
        } catch (error) {
            console.error(error);
            removePending(placeholder);
            appendMessage("assistant", "对话暂时无法进行,请稍后再试。");
        }
    }

    async function init() {
        await loadTasks();
        await autoAnalyzeTasks();  // 页面加载时自动分析
    }

    init();
})();