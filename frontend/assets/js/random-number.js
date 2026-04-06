(function () {
    const form = document.getElementById("random-form");
    const result = document.getElementById("random-result");

    if (!form || !result) {
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const formData = new FormData(form);
        const min = formData.get("min");
        const max = formData.get("max");

        if (min === null || max === null) {
            result.textContent = "请输入合法的数值范围。";
            return;
        }

        const minValue = Number(min);
        const maxValue = Number(max);

        if (Number.isNaN(minValue) || Number.isNaN(maxValue)) {
            result.textContent = "请输入数字。";
            return;
        }

        if (minValue > maxValue) {
            result.textContent = "最小值不能大于最大值。";
            return;
        }

        result.textContent = "正在生成...";

        try {
            const response = await fetch(`/api/random-number?min=${encodeURIComponent(minValue)}&max=${encodeURIComponent(maxValue)}`);
            if (!response.ok) {
                throw new Error(`服务异常: ${response.status}`);
            }
            const payload = await response.json();
            result.innerHTML = `<div class="result-value">${payload.value}</div><div class="result-range">范围 ${payload.range.min} - ${payload.range.max}</div>`;
        } catch (error) {
            console.error(error);
            result.textContent = "生成失败，请稍后再试。";
        }
    });
})();
