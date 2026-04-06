(function () {
    const dropZone = document.getElementById("ocr-drop-zone");
    const fileInput = document.getElementById("ocr-file-input");
    const selectButton = document.getElementById("ocr-select-file");
    const statusText = document.getElementById("ocr-status");
    const processPendingButton = document.getElementById("ocr-process-pending");
    const resultBody = document.getElementById("ocr-result-body");
    const resultFooter = document.getElementById("ocr-result-footer");

    if (!dropZone || !fileInput || !statusText || !resultBody || !resultFooter) {
        return;
    }

    function setStatus(message, isError = false) {
        statusText.textContent = message;
        statusText.classList.toggle("error", isError);
    }

    function resetResult() {
        resultBody.innerHTML = '<p class="muted">正在处理，请稍候…</p>';
        resultFooter.innerHTML = "";
    }

    function showIdle() {
        resultBody.innerHTML = '<p class="muted">上传图片或 PDF 后，这里会展示 AI 翻译的标题、正文与下载链接。</p>';
        resultFooter.innerHTML = "";
    }

    function renderResult(data) {
        const { title, translated_text: translatedText, original_text: originalText, output_url: outputUrl, output_filename: outputFilename } = data;
        const safeTitle = title || "翻译结果";
        const wrapper = document.createElement("div");
        wrapper.className = "ocr-result-wrapper";
        wrapper.innerHTML = `
            <h3 class="ocr-title">${escapeHTML(safeTitle)}</h3>
            <section>
                <h4 class="ocr-subtitle">翻译正文</h4>
                <pre class="ocr-text-block">${escapeHTML(translatedText || "(无内容)")}</pre>
            </section>
            <section>
                <h4 class="ocr-subtitle">识别原文</h4>
                <pre class="ocr-text-block muted">${escapeHTML(originalText || "(无原文)")}</pre>
            </section>
        `;
        resultBody.innerHTML = "";
        resultBody.appendChild(wrapper);

        const actions = document.createElement("div");
        actions.className = "ocr-actions";
        const downloadLink = document.createElement("a");
        downloadLink.href = outputUrl;
        downloadLink.download = outputFilename;
        downloadLink.className = "ghost-button";
        downloadLink.textContent = "下载翻译文件";

        const copyButton = document.createElement("button");
        copyButton.type = "button";
        copyButton.className = "ghost-button";
        copyButton.textContent = "复制译文";
        copyButton.addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(translatedText || "");
                copyButton.textContent = "已复制";
                setTimeout(() => (copyButton.textContent = "复制译文"), 1600);
            } catch (error) {
                console.error(error);
                copyButton.textContent = "复制失败";
                setTimeout(() => (copyButton.textContent = "复制译文"), 1600);
            }
        });

        actions.append(downloadLink, copyButton);
        resultFooter.innerHTML = "";
        resultFooter.appendChild(actions);
    }

    function escapeHTML(text) {
        const div = document.createElement("div");
        div.textContent = text ?? "";
        return div.innerHTML;
    }

    async function handleFile(file) {
        if (!file) {
            return;
        }
        resetResult();
        setStatus(`正在上传并识别：${file.name}`);
        const formData = new FormData();
        formData.append("file", file);
        try {
            const response = await fetch("/api/ocr/translate", {
                method: "POST",
                body: formData
            });
            if (!response.ok) {
                let message = "上传失败";
                try {
                    const data = await response.json();
                    if (data && typeof data.detail === "string" && data.detail.trim()) {
                        message = data.detail.trim();
                    } else {
                        message = JSON.stringify(data);
                    }
                } catch {
                    const text = await response.text();
                    if (text) {
                        message = text;
                    }
                }
                throw new Error(message);
            }
            const payload = await response.json();
            renderResult(payload);
            setStatus("翻译完成，可在右侧查看结果。");
        } catch (error) {
            console.error(error);
            showIdle();
            const message = error instanceof Error && error.message ? error.message : "文件上传或翻译失败，请稍后再试。";
            setStatus(message, true);
        } finally {
            fileInput.value = "";
        }
    }

    dropZone.addEventListener("click", () => fileInput.click());
    if (selectButton) {
        selectButton.addEventListener("click", () => fileInput.click());
    }

    dropZone.addEventListener("dragover", (event) => {
        event.preventDefault();
        dropZone.classList.add("active");
    });

    dropZone.addEventListener("dragleave", (event) => {
        event.preventDefault();
        dropZone.classList.remove("active");
    });

    dropZone.addEventListener("drop", (event) => {
        event.preventDefault();
        dropZone.classList.remove("active");
        const files = event.dataTransfer?.files;
        if (files && files.length > 0) {
            handleFile(files[0]);
        }
    });

    fileInput.addEventListener("change", () => {
        const files = fileInput.files;
        if (files && files.length > 0) {
            handleFile(files[0]);
        }
    });

    if (processPendingButton) {
        processPendingButton.addEventListener("click", async () => {
            setStatus("正在处理输入文件夹…");
            resetResult();
            try {
                const response = await fetch("/api/ocr/process-pending", {
                    method: "POST"
                });
                if (!response.ok) {
                    const errorMessage = await response.text();
                    throw new Error(errorMessage || "批量处理失败");
                }
                const payload = await response.json();
                const { processed = [], errors = [], skipped = [] } = payload;
                const summary = document.createElement("div");
                summary.className = "ocr-result-wrapper";
                const processedHtml = processed.length
                    ? `<ul>${processed.map(item => `<li>${escapeHTML(item.input)} → ${escapeHTML(item.output)} (${escapeHTML(item.title)})</li>`).join("")}</ul>`
                    : '<p class="muted">未检测到可处理的文件。</p>';
                const errorHtml = errors.length
                    ? `<ul>${errors.map(item => `<li>${escapeHTML(item.input)}：${escapeHTML(String(item.status))} ${escapeHTML(String(item.detail))}</li>`).join("")}</ul>`
                    : "";
                const skippedHtml = skipped.length
                    ? `<ul>${skipped.map(name => `<li>${escapeHTML(name)}</li>`).join("")}</ul>`
                    : "";
                summary.innerHTML = `
                    <h3 class="ocr-title">批量处理结果</h3>
                    <section>
                        <h4 class="ocr-subtitle">成功</h4>
                        ${processedHtml}
                    </section>
                    ${skipped.length ? `<section><h4 class="ocr-subtitle">跳过</h4>${skippedHtml}</section>` : ""}
                    ${errors.length ? `<section><h4 class="ocr-subtitle">发生错误</h4>${errorHtml}</section>` : ""}
                `;
                resultBody.innerHTML = "";
                resultBody.appendChild(summary);
                resultFooter.innerHTML = "";
                if (errors.length) {
                    setStatus("部分文件处理完成，请查看结果。", true);
                } else if (skipped.length && !processed.length) {
                    setStatus("未找到新的待处理文件。", true);
                } else {
                    setStatus("批量处理完成。");
                }
            } catch (error) {
                console.error(error);
                showIdle();
                setStatus("批量处理失败，请稍后重试。", true);
            }
        });
    }

    showIdle();
})();
