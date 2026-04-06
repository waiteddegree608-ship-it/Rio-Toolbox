(function () {
    const settingsForm = document.getElementById("ai-settings-form");
    const presetForm = document.getElementById("ai-preset-form");
    const presetList = document.getElementById("ai-preset-list");
    const presetSelect = document.getElementById("ai-preset-select");
    const chatForm = document.getElementById("ai-chat-form");
    const chatBox = document.getElementById("ai-conversation");
    const messageInput = document.getElementById("ai-chat-message");
    const characterVisual = document.getElementById("ai-character-visual");
    const characterMeta = document.getElementById("ai-character-meta");
    const characterHeading = document.querySelector(".ai-character-panel .panel-header h2");
    const sidebarToggle = document.getElementById("ai-sidebar-toggle");
    const historyList = document.getElementById("ai-history-list");
    const historyRefresh = document.getElementById("ai-history-refresh");
    const historyClear = document.getElementById("ai-history-clear");
    const settingsSectionToggle = document.getElementById("ai-settings-section-toggle");
    const settingsSectionBody = document.getElementById("ai-settings-section-body");
    const historySectionToggle = document.getElementById("ai-history-section-toggle");
    const historySectionBody = document.getElementById("ai-history-section-body");
    const layout = document.querySelector(".ai-grid");

    if (!settingsForm || !presetForm || !presetList || !presetSelect || !chatForm || !chatBox || !messageInput) {
        return;
    }

    const DEFAULT_PARTNER_NAME = "调月莉音";

    const state = {
        messages: [],
        presets: [],
        settings: {},
        history: [],
        basePartnerName: DEFAULT_PARTNER_NAME,
        partnerName: DEFAULT_PARTNER_NAME,
        assistantAvatar: "",
        activeHistoryId: null
    };

    const SIDEBAR_COLLAPSE_KEY = "rio-ai-sidebar-collapsed";
    const HISTORY_COLLAPSE_KEY = "rio-ai-history-collapsed";
    const SETTINGS_COLLAPSE_KEY = "rio-ai-settings-collapsed";

    function extractFileName(path) {
        if (!path) return "";
        const segments = path.split(/[\\/]/);
        return segments[segments.length - 1] || "";
    }

    function setLabelText(label, text) {
        if (!label) return;
        if (!label.dataset.defaultText) {
            label.dataset.defaultText = label.textContent || "";
        }
        label.textContent = text || label.dataset.defaultText;
    }

    function syncLabelWithValue(labelId, value) {
        const label = document.getElementById(labelId);
        if (!label) return;
        const fileName = extractFileName(value);
        setLabelText(label, fileName);
    }

    settingsForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const payload = Object.fromEntries(new FormData(settingsForm).entries());
        Object.keys(payload).forEach((key) => {
            if (payload[key] === "") {
                payload[key] = null;
            }
        });
        try {
            const response = await fetch("/api/ai/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (!response.ok) {
                throw new Error("配置保存失败");
            }
            const saved = await response.json();
            state.settings = saved;
            renderCharacter(saved.character_image);
            syncLabelWithValue("ai-character-image-label", saved.character_image);
            alert("配置已保存");
        } catch (error) {
            console.error(error);
            alert("保存配置失败，请稍后再试");
        }
    });

    presetForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const payload = Object.fromEntries(new FormData(presetForm).entries());
        try {
            const response = await fetch("/api/ai/presets", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (!response.ok) {
                throw new Error("预设保存失败");
            }
            presetForm.reset();
            await loadPresets();
        } catch (error) {
            console.error(error);
            alert("保存预设失败，请稍后再试");
        }
    });

    presetList.addEventListener("click", async (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        const item = target.closest("li[data-id]");
        if (!item) return;
        const id = item.dataset.id;
        if (!id) return;
        if (target.dataset.action === "delete") {
            if (!confirm("确定删除该预设吗？")) return;
            await deletePreset(id);
            return;
        }
        selectPreset(id);
    });

    presetSelect.addEventListener("change", () => {
        const id = presetSelect.value;
        selectPreset(id || null);
    });

    chatForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const content = messageInput.value.trim();
        if (!content) return;
        appendMessage("user", content);
        messageInput.value = "";
        await sendToServer();
    });

    messageInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            chatForm.requestSubmit();
        }
    });

    sidebarToggle && sidebarToggle.addEventListener("click", () => {
        if (!layout) return;
        const nextState = !layout.classList.contains("sidebar-collapsed");
        applySidebarCollapse(nextState);
        localStorage.setItem(SIDEBAR_COLLAPSE_KEY, String(nextState));
    });

    historyRefresh && historyRefresh.addEventListener("click", () => {
        loadHistory();
    });

    historyClear && historyClear.addEventListener("click", async () => {
        if (!confirm("确定清空所有历史聊天记录吗？该操作不可撤销。")) return;
        try {
            const response = await fetch("/api/ai/history", { method: "DELETE" });
            if (!response.ok) throw new Error();
            state.history = [];
            state.activeHistoryId = null;
            renderHistory();
            resetConversation();
        } catch (error) {
            console.error(error);
            alert("清空历史记录失败，请稍后再试");
        }
    });

    settingsSectionToggle && settingsSectionBody && settingsSectionToggle.addEventListener("click", () => {
        toggleSection(settingsSectionToggle, settingsSectionBody, SETTINGS_COLLAPSE_KEY);
    });

    historySectionToggle && historySectionBody && historySectionToggle.addEventListener("click", () => {
        toggleSection(historySectionToggle, historySectionBody, HISTORY_COLLAPSE_KEY);
    });

    historyList && historyList.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        const item = target.closest(".history-item[data-id]");
        if (!item) return;
        const id = item.dataset.id;
        if (!id) return;
        loadHistoryEntry(id);
    });

    async function loadSettings() {
        try {
            const response = await fetch("/api/ai/settings");
            if (!response.ok) throw new Error();
            const payload = await response.json();
            state.settings = payload || {};
            if (state.settings.character_name) {
                state.basePartnerName = state.settings.character_name;
            }
            state.partnerName = state.basePartnerName;
            for (const [key, value] of Object.entries(state.settings)) {
                const field = settingsForm.elements.namedItem(key);
                if (field instanceof HTMLInputElement) {
                    field.value = value ?? "";
                }
            }
            renderCharacter(state.settings.character_image);
            syncLabelWithValue("ai-character-image-label", state.settings.character_image);
            updateChatTitle(false);
            updateCharacterHeading();
        } catch (error) {
            console.error(error);
        }
    }

    async function loadPresets() {
        try {
            const response = await fetch("/api/ai/presets");
            if (!response.ok) throw new Error();
            const payload = await response.json();
            state.presets = payload || [];
            renderPresets();
            updateChatTitle(false);
            updateCharacterHeading();
        } catch (error) {
            console.error(error);
        }
    }

    async function deletePreset(id) {
        try {
            const response = await fetch(`/api/ai/presets/${id}`, { method: "DELETE" });
            if (!response.ok) throw new Error();
            await loadPresets();
        } catch (error) {
            console.error(error);
            alert("删除预设失败");
        }
    }

    function renderPresets() {
        const currentSelection = presetSelect.value;
        if (!state.presets.length) {
            presetList.innerHTML = '<li class="muted">暂无预设，请在下方创建。</li>';
        } else {
            presetList.innerHTML = state.presets.map((preset) => `
                <li data-id="${preset.id}" class="preset-item">
                    <div class="preset-info">
                        <strong>${preset.name}</strong>
                        ${preset.description ? `<span class="muted">${preset.description}</span>` : ""}
                    </div>
                    <button class="ghost-button" data-action="delete">删除</button>
                </li>
            `).join("");
        }
        presetSelect.innerHTML = '<option value="">无预设</option>' + state.presets.map((preset) => `
            <option value="${preset.id}">${preset.name}</option>
        `).join("");
        if (currentSelection) {
            const exists = state.presets.some((item) => item.id === currentSelection);
            if (exists) {
                presetSelect.value = currentSelection;
                highlightPreset(currentSelection);
            } else {
                selectPreset(null);
            }
        } else {
            selectPreset(null);
        }
    }

    function selectPreset(id) {
        if (!id) {
            presetSelect.value = "";
            highlightPreset(null);
            state.partnerName = state.basePartnerName || DEFAULT_PARTNER_NAME;
            updateChatTitle(false);
            characterMeta && (characterMeta.innerHTML = '<p class="muted">右侧展示最新的角色设定素材，方便对话时保持沉浸感。</p>');
            updateCharacterHeading();
            return;
        }
        const preset = state.presets.find((item) => item.id === id);
        if (!preset) return;
        presetSelect.value = id;
        highlightPreset(id);
        state.partnerName = preset.name || DEFAULT_PARTNER_NAME;
        updateChatTitle(false);
        characterMeta && (characterMeta.innerHTML = `
            <p><strong>预设：</strong>${preset.name}</p>
            ${preset.description ? `<p class="muted">${preset.description}</p>` : ""}
            ${preset.character_card ? `<p class="muted">角色卡：${preset.character_card}</p>` : ""}
            ${preset.world_book ? `<p class="muted">世界书：${preset.world_book}</p>` : ""}
        `);
        updateCharacterHeading();
    }

    function highlightPreset(id) {
        const items = presetList.querySelectorAll("li[data-id]");
        items.forEach((item) => {
            item.classList.toggle("active", item.dataset.id === id);
        });
    }

    function getDisplayName(role) {
        return role === "assistant" ? (state.partnerName || DEFAULT_PARTNER_NAME) : "我";
    }

    function getAvatarMarkup(role) {
        if (role === "assistant") {
            const avatar = state.assistantAvatar;
            if (avatar) {
                return `<img src="${avatar}" alt="${escapeAttribute(getDisplayName(role))}" />`;
            }
            return `<span class="avatar-initial">${(state.partnerName || DEFAULT_PARTNER_NAME).charAt(0)}</span>`;
        }
        return '<span class="avatar-initial">我</span>';
    }

    function appendMessage(role, content) {
        state.messages.push({ role, content });
        ensureChatInitialized();
        const wrapper = document.createElement("div");
        wrapper.className = `chat-message ${role === "user" ? "from-user" : "from-assistant"}`;
        wrapper.innerHTML = `
            <div class="chat-avatar">${getAvatarMarkup(role)}</div>
            <div class="chat-body">
                <div class="chat-name">${escapeHTML(getDisplayName(role))}</div>
                <div class="chat-bubble">${escapeHTML(content)}</div>
            </div>
        `;
        chatBox.appendChild(wrapper);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    async function sendToServer() {
        const payload = {
            messages: state.messages,
            preset_id: presetSelect.value || null
        };
        const placeholder = appendPending();
        try {
            const response = await fetch("/api/ai/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(errorText || "接口请求失败");
            }
            const result = await response.json();
            removePending(placeholder);
            appendMessage("assistant", result.reply || "(暂无回复)");
            state.activeHistoryId = null;
            await loadHistory(true);
        } catch (error) {
            console.error(error);
            removePending(placeholder);
            appendMessage("assistant", "对话暂时无法进行，请检查配置后重试。");
            state.activeHistoryId = null;
            await loadHistory(true);
        }
    }

    function appendPending() {
        ensureChatInitialized();
        const wrapper = document.createElement("div");
        wrapper.className = "chat-message from-assistant pending";
        wrapper.innerHTML = `
            <div class="chat-avatar">${getAvatarMarkup("assistant")}</div>
            <div class="chat-body">
                <div class="chat-name">${escapeHTML(state.partnerName || DEFAULT_PARTNER_NAME)}</div>
                <div class="chat-bubble muted">正在思考…</div>
            </div>
        `;
        chatBox.appendChild(wrapper);
        chatBox.scrollTop = chatBox.scrollHeight;
        updateChatTitle(true);
        return wrapper;
    }

    function removePending(node) {
        if (node && node.parentElement) {
            node.parentElement.removeChild(node);
        }
        updateChatTitle(false);
        updateCharacterHeading();
    }

    function renderCharacter(src) {
        if (!characterVisual) return;
        state.assistantAvatar = src || "";
        if (!src) {
            characterVisual.innerHTML = '<div class="fortune-image-placeholder"><span class="muted">可在设置中指定角色图片</span></div>';
            updateChatTitle(false);
            updateCharacterHeading();
            return;
        }
        const displayName = state.partnerName || DEFAULT_PARTNER_NAME;
        characterVisual.innerHTML = `<img src="${src}" alt="${escapeAttribute(displayName)}" class="fortune-photo">`;
        updateChatTitle(false);
        updateCharacterHeading();
    }

    function escapeAttribute(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function escapeHTML(text) {
        return escapeAttribute(text).replace(/\n/g, "<br>");
    }

    function ensureChatInitialized() {
        if (!chatBox.dataset.initialized) {
            chatBox.innerHTML = "";
            chatBox.dataset.initialized = "true";
        }
    }


    function resetConversation() {
        state.messages = [];
        state.activeHistoryId = null;
        delete chatBox.dataset.initialized;
        chatBox.innerHTML = '<p class="muted">开始新的对话，左侧选择预设或直接输入问题。</p>';
        updateChatTitle(false);
    }

    function applySidebarCollapse(collapsed) {
        if (!layout || !sidebarToggle) return;
        layout.classList.toggle("sidebar-collapsed", collapsed);
        sidebarToggle.textContent = collapsed ? "展开" : "收起";
        sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
        sidebarToggle.title = collapsed ? "展开侧边栏" : "收起侧边栏";
    }

    function applySectionState(button, body, expanded) {
        if (!button || !body) return;
        button.setAttribute("aria-expanded", String(expanded));
        body.classList.toggle("collapsed", !expanded);
    }

    function toggleSection(button, body, storageKey) {
        if (!button || !body) return;
        const expanded = button.getAttribute("aria-expanded") === "true";
        const nextExpanded = !expanded;
        applySectionState(button, body, nextExpanded);
        if (storageKey) {
            try {
                localStorage.setItem(storageKey, String(!nextExpanded));
            } catch (error) {
                console.warn("无法保存展开偏好", error);
            }
        }
    }

    function ensureSectionExpanded(button, body, storageKey) {
        if (!button || !body) return;
        if (button.getAttribute("aria-expanded") === "true") return;
        applySectionState(button, body, true);
        if (storageKey) {
            try {
                localStorage.setItem(storageKey, "false");
            } catch (error) {
                console.warn("无法保存展开偏好", error);
            }
        }
    }

    function updateChatTitle(isTyping) {
        const heading = document.getElementById("ai-chat-title");
        if (!heading) return;
        const name = state.partnerName || DEFAULT_PARTNER_NAME;
        heading.textContent = isTyping ? `${name} 正在输入…` : name;
    }

    function updateCharacterHeading() {
        if (!characterHeading) return;
        characterHeading.textContent = state.partnerName || DEFAULT_PARTNER_NAME;
    }

    function formatTimestamp(value) {
        if (!value) return "";
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleString("zh-CN", { hour12: false });
    }

    function renderHistory() {
        if (!historyList) return;
        if (!state.history.length) {
            historyList.innerHTML = '<li class="muted">暂无聊天记录。</li>';
            return;
        }
        const items = state.history.slice().reverse().map((entry) => {
            if (!entry || !entry.id) return "";
            const latestUser = Array.isArray(entry.messages)
                ? [...entry.messages].reverse().find((msg) => msg.role === "user")
                : null;
            const summaryRaw = latestUser ? latestUser.content || "" : entry.reply || "";
            const summary = summaryRaw.length > 80 ? summaryRaw.slice(0, 80) + "…" : summaryRaw;
            const presetLabel = entry.preset_name || (entry.preset_id ? `预设 ${entry.preset_id.slice(0, 6)}` : "无预设");
            const timestamp = formatTimestamp(entry.timestamp);
            const metaParts = [];
            if (presetLabel) metaParts.push(presetLabel);
            if (timestamp) metaParts.push(timestamp);
            const metaText = metaParts.join(" · ");
            const isActive = state.activeHistoryId === entry.id;
            return `
                <li class="history-item${isActive ? " active" : ""}" data-id="${escapeAttribute(entry.id)}">
                    <button type="button" class="history-item-button">
                        <span class="history-item-title">${escapeHTML(summary || "(无摘要)")}</span>
                        <span class="history-item-meta">${escapeHTML(metaText)}</span>
                    </button>
                </li>
            `;
        }).filter(Boolean).join("");
        historyList.innerHTML = items || '<li class="muted">暂无聊天记录。</li>';
    }

    async function loadHistory(silent = false) {
        if (!historyList) return;
        try {
            const response = await fetch("/api/ai/history");
            if (!response.ok) throw new Error();
            const payload = await response.json();
            state.history = Array.isArray(payload.items) ? payload.items : [];
            if (state.activeHistoryId) {
                const exists = state.history.some((item) => item && item.id === state.activeHistoryId);
                if (!exists) {
                    state.activeHistoryId = null;
                }
            }
            renderHistory();
        } catch (error) {
            if (!silent) {
                console.error(error);
                alert("历史记录获取失败");
            }
        }
    }

    function loadHistoryEntry(historyId) {
        if (!historyId) return;
        const entry = state.history.find((item) => item && item.id === historyId);
        if (!entry) return;
        ensureSectionExpanded(historySectionToggle, historySectionBody, HISTORY_COLLAPSE_KEY);
        const presetExists = entry.preset_id && state.presets.some((item) => item.id === entry.preset_id);
        if (presetExists) {
            selectPreset(entry.preset_id);
        } else {
            selectPreset(null);
            if (entry.preset_name) {
                state.partnerName = entry.preset_name;
                updateChatTitle(false);
                updateCharacterHeading();
                if (characterMeta) {
                    characterMeta.innerHTML = `<p class="muted">历史预设：${escapeHTML(entry.preset_name)}</p>`;
                }
            }
        }
        state.messages = [];
        delete chatBox.dataset.initialized;
        chatBox.innerHTML = "";
        const conversation = Array.isArray(entry.messages) ? entry.messages : [];
        let lastRole = null;
        for (const message of conversation) {
            if (!message || typeof message.content !== "string") continue;
            if (message.role !== "assistant" && message.role !== "user") continue;
            const role = message.role === "assistant" ? "assistant" : "user";
            appendMessage(role, message.content);
            lastRole = role;
        }
        if (entry.reply && lastRole !== "assistant") {
            appendMessage("assistant", entry.reply);
            lastRole = "assistant";
        }
        chatBox.scrollTop = chatBox.scrollHeight;
        state.activeHistoryId = entry.id;
        renderHistory();
        updateChatTitle(false);
        messageInput.focus();
    }


    // 文件上传逻辑
    function setupFileUpload({
        buttonId,
        fileInputId,
        labelId,
        hiddenInputId = null,
        uploadCategory = null,
        isText = false,
        onTextLoaded,
        onUploadSuccess
    }) {
        const button = document.getElementById(buttonId);
        const fileInput = document.getElementById(fileInputId);
        const label = document.getElementById(labelId);
        const hiddenInput = hiddenInputId ? document.getElementById(hiddenInputId) : null;
        if (!button || !fileInput || !label) return;
        if (!isText && !uploadCategory) return;
        button.addEventListener("click", () => fileInput.click());
        fileInput.addEventListener("change", async () => {
            const file = fileInput.files[0];
            if (!file) return;
            setLabelText(label, file.name);
            if (isText) {
                // 读取文本内容
                const reader = new FileReader();
                reader.onload = function (e) {
                    if (typeof onTextLoaded === "function") {
                        onTextLoaded(e.target.result);
                    }
                };
                reader.readAsText(file);
                return;
            }
            if (!uploadCategory) return;
            // 上传文件到后端
            const formData = new FormData();
            formData.append("file", file);
            try {
                const resp = await fetch(`/api/uploads/${uploadCategory}`, {
                    method: "POST",
                    body: formData
                });
                if (!resp.ok) throw new Error("上传失败");
                const data = await resp.json();
                if (data.url && hiddenInput) {
                    hiddenInput.value = data.url;
                }
                if (typeof onUploadSuccess === "function") {
                    onUploadSuccess(data);
                }
            } catch (err) {
                alert("文件上传失败，请重试");
                setLabelText(label, label.dataset.defaultText || "");
                if (hiddenInput) {
                    hiddenInput.value = "";
                }
                console.error(err);
            }
        });
    }

    // 角色图片上传
    setupFileUpload({
        buttonId: "ai-character-image-upload",
        fileInputId: "ai-character-image-file",
        labelId: "ai-character-image-label",
        hiddenInputId: "ai-character-image",
        uploadCategory: "ai-images",
        onUploadSuccess: (data) => {
            renderCharacter(data.url);
            syncLabelWithValue("ai-character-image-label", data.url);
        }
    });

    // 角色卡上传
    setupFileUpload({
        buttonId: "preset-card-upload",
        fileInputId: "preset-card-file",
        labelId: "preset-card-label",
        hiddenInputId: "preset-card",
        uploadCategory: "ai-cards"
    });

    // 世界书上传
    setupFileUpload({
        buttonId: "preset-world-upload",
        fileInputId: "preset-world-file",
        labelId: "preset-world-label",
        hiddenInputId: "preset-world",
        uploadCategory: "ai-worlds"
    });

    // 提示词/破甲导入（文本内容直接填充到 textarea）
    setupFileUpload({
        buttonId: "preset-prompt-import",
        fileInputId: "preset-prompt-file",
        labelId: "preset-prompt-label",
        hiddenInputId: null,
        uploadCategory: null,
        isText: true,
        onTextLoaded: (text) => {
            const textarea = document.getElementById("preset-prompt");
            if (textarea) textarea.value = text;
        },
        onUploadSuccess: () => {
            // no-op for text import
        }
    });

    if (settingsSectionToggle && settingsSectionBody) {
        try {
            const stored = localStorage.getItem(SETTINGS_COLLAPSE_KEY);
            if (stored !== null) {
                applySectionState(settingsSectionToggle, settingsSectionBody, stored !== "true");
            }
        } catch (error) {
            console.warn("无法读取面板偏好", error);
        }
    }

    if (historySectionToggle && historySectionBody) {
        try {
            const stored = localStorage.getItem(HISTORY_COLLAPSE_KEY);
            if (stored !== null) {
                applySectionState(historySectionToggle, historySectionBody, stored !== "true");
            }
        } catch (error) {
            console.warn("无法读取面板偏好", error);
        }
    }

    loadSettings();
    loadPresets();
    if (layout) {
        const stored = localStorage.getItem(SIDEBAR_COLLAPSE_KEY);
        applySidebarCollapse(stored === "true");
    }
    loadHistory(true);
    updateChatTitle(false);
    updateCharacterHeading();
})();
