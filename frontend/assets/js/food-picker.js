(function () {
    const button = document.getElementById("food-picker-button");
    const result = document.getElementById("food-picker-result");

    if (!button || !result) {
        return;
    }

    button.addEventListener("click", async () => {
        button.disabled = true;
        button.textContent = "正在思考...";
        result.textContent = "正在挑选...";

        try {
            const response = await fetch("/api/random-food");
            if (!response.ok) {
                throw new Error(`服务异常: ${response.status}`);
            }
            const payload = await response.json();
            result.innerHTML = `<div class="result-value">${payload.name}</div><div class="result-range">类别 ${payload.category}</div>`;
        } catch (error) {
            console.error(error);
            result.textContent = "暂时无法决定，请稍后重试。";
        } finally {
            button.disabled = false;
            button.textContent = "帮我决定";
        }
    });
})();
