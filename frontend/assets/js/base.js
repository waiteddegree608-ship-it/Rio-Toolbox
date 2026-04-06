(function () {
    const gradients = [
        "gradient-aurora",
        "gradient-dusk",
        "gradient-ocean",
        "gradient-mauve"
    ];

    const body = document.body;
    const select = document.getElementById("gradient-select");
    const STORAGE_KEY = "rio-toolbox-gradient";

    function applyGradient(name) {
        gradients.forEach((gradient) => body.classList.remove(gradient));
        body.classList.add(name);
        localStorage.setItem(STORAGE_KEY, name);
        if (select) {
            select.value = name;
        }
    }

    function initialLoad() {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved && gradients.includes(saved)) {
            applyGradient(saved);
        } else if (select) {
            applyGradient(select.value);
        }
    }

    if (select) {
        select.addEventListener("change", (event) => {
            const value = event.target.value;
            if (gradients.includes(value)) {
                applyGradient(value);
            }
        });
    }

    initialLoad();
})();
