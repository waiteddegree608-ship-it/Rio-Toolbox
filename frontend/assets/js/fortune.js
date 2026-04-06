(function () {
    const button = document.getElementById("fortune-button");
    const content = document.getElementById("fortune-content");
    const imageWrap = document.getElementById("fortune-image");
    let currentEntry = null;
    const DEFAULT_BUTTON_LABEL = "抽取今日运势";

    if (!button || !content || !imageWrap) {
        return;
    }

    initializeFortune();

    button.addEventListener("click", async () => {
        if (button.disabled) {
            return;
        }
        const previousLabel = button.textContent;
        button.disabled = true;
        button.textContent = "抽签中...";
        content.innerHTML = '<p class="muted">正在为你寻觅今日的签运...</p>';
        try {
            const response = await fetch("/api/fortune", { method: "POST" });
            if (!response.ok) {
                throw new Error("抽签失败");
            }
            const payload = await response.json();
            if (!payload.entry) {
                throw new Error("返回数据缺失");
            }
            currentEntry = payload.entry;
            renderFortuneEntry(currentEntry);
            if (payload.locked) {
                disableButton("今日已抽签");
            }
            if (payload.already_drawn) {
                content.insertAdjacentHTML("beforeend", '<p class="muted">今日签已记录，明天再来抽新的吧。</p>');
            }
        } catch (error) {
            console.error(error);
            content.innerHTML = '<p class="muted">暂时无法获取运势，请稍后再试。</p>';
            if (!currentEntry) {
                button.disabled = false;
                button.textContent = previousLabel || DEFAULT_BUTTON_LABEL;
            } else {
                disableButton("今日已抽签");
            }
        } finally {
            if (!button.disabled) {
                button.textContent = DEFAULT_BUTTON_LABEL;
            }
        }
    });

    async function initializeFortune() {
        try {
            const response = await fetch("/api/fortune");
            if (!response.ok) {
                throw new Error("状态加载失败");
            }
            const payload = await response.json();
            if (payload.entry) {
                currentEntry = payload.entry;
                renderFortuneEntry(currentEntry);
                disableButton("今日已抽签");
            }
        } catch (error) {
            console.warn("获取今日运势失败", error);
        }
    }

    function renderFortuneEntry(entry) {
        const fortune = entry.fortune || {};
        const quote = typeof entry.quote === "string" ? entry.quote : "";
        content.innerHTML = `
            <div class="fortune-result">
                <div class="fortune-type">${fortune.type || "未知签"}</div>
                <p class="fortune-message">${fortune.message || ""}</p>
                <p class="fortune-time">抽签时间：${formatTime(entry.timestamp || entry.date)}</p>
            </div>
            ${quote ? renderCompanion(quote, entry.image) : ""}
        `;
        renderImage(entry.image);
    }

    function renderImage(src) {
        if (!src) {
            imageWrap.innerHTML = '<span class="muted">尚未找到莉音的照片，请在 assets/images/liyin/ 放入图片。</span>';
            return;
        }
        imageWrap.innerHTML = `
            <img src="${src}" alt="调月莉音" class="fortune-photo">
        `;
    }

    function disableButton(label) {
        button.disabled = true;
        button.textContent = label || "今日已抽签";
    }

    function renderCompanion(text, avatarSrc) {
        const avatar = avatarSrc
            ? `<img src="${avatarSrc}" alt="调月莉音" />`
            : '<span class="fortune-avatar-initial">莉</span>';
        return `
            <div class="fortune-companion">
                <div class="fortune-avatar">${avatar}</div>
                <div class="fortune-bubble">
                    <div class="fortune-speaker">调月莉音</div>
                    <p>${escapeHTML(text)}</p>
                </div>
            </div>
        `;
    }

    function formatTime(timeStr) {
        if (!timeStr) return "";
        try {
            const date = new Date(timeStr);
            return date.toLocaleString();
        } catch (error) {
            return timeStr;
        }
    }

    function escapeHTML(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML.replace(/\n/g, "<br>");
    }
})();
