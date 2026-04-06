(function () {
    const singleForm = document.getElementById("calendar-single-form");
    const recurringForm = document.getElementById("calendar-recurring-form");
    const configWrap = document.getElementById("calendar-config");
    const timelineWrap = document.getElementById("calendar-timeline");
    const rangeInput = document.getElementById("calendar-range");

    if (!singleForm || !recurringForm || !configWrap || !timelineWrap) {
        return;
    }

    const state = {
        single: [],
        recurring: [],
        timeline: [],
        range: Number(rangeInput?.value || 30)
    };

    setDefaultDates();

    rangeInput?.addEventListener("change", () => {
        const parsed = Number(rangeInput.value);
        if (!Number.isInteger(parsed) || parsed < 7 || parsed > 120) {
            rangeInput.value = String(state.range);
            return;
        }
        state.range = parsed;
        loadCalendar();
    });

    singleForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(singleForm);
        const payload = {
            title: formData.get("title")?.toString().trim(),
            date: formData.get("date")
        };
        if (!payload.title || !payload.date) {
            alert("请填写完整的事项信息。");
            return;
        }
        await mutate("/api/calendar/events", payload, singleForm);
    });

    recurringForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(recurringForm);
        const payload = {
            title: formData.get("title")?.toString().trim(),
            weekday: Number(formData.get("weekday")),
            start_date: formData.get("start_date"),
            end_date: formData.get("end_date")
        };
        if (!payload.title || !payload.start_date || !payload.end_date || !payload.weekday) {
            alert("请完善周期事项信息。");
            return;
        }
        await mutate("/api/calendar/recurring", payload, recurringForm);
    });

    async function mutate(url, payload, form) {
        try {
            const response = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (!response.ok) {
                const reason = await response.json().catch(() => ({}));
                throw new Error(reason.detail || "保存失败");
            }
            form.reset();
            setDefaultDates();
            loadCalendar();
        } catch (error) {
            console.error(error);
            alert(error.message || "操作失败，请稍后再试。");
        }
    }

    async function removeEvent(url) {
        try {
            const response = await fetch(url, { method: "DELETE" });
            if (!response.ok) {
                const reason = await response.json().catch(() => ({}));
                throw new Error(reason.detail || "删除失败");
            }
            loadCalendar();
        } catch (error) {
            console.error(error);
            alert(error.message || "删除失败，请稍后再试。");
        }
    }

    function renderConfig() {
        if (state.single.length === 0 && state.recurring.length === 0) {
            configWrap.innerHTML = '<p class="muted">尚未添加任何事项。</p>';
            return;
        }
        const singleHTML = state.single.map((item) => `
            <div class="config-card">
                <div>
                    <strong>${item.title}</strong>
                    <div class="muted">日期：${item.date}</div>
                </div>
                <button class="ghost-button" data-action="delete-single" data-id="${item.id}">删除</button>
            </div>
        `).join("");
        const recurringHTML = state.recurring.map((item) => `
            <div class="config-card">
                <div>
                    <strong>${item.title}</strong>
                    <div class="muted">${formatWeekday(item.weekday)} · ${item.start_date} - ${item.end_date}</div>
                </div>
                <button class="ghost-button" data-action="delete-recurring" data-id="${item.id}">删除</button>
            </div>
        `).join("");
        configWrap.innerHTML = `
            ${singleHTML ? `<div class="config-group"><h3>单日事项</h3>${singleHTML}</div>` : ""}
            ${recurringHTML ? `<div class="config-group"><h3>周期事项</h3>${recurringHTML}</div>` : ""}
        `;
    }

    configWrap.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        const action = target.dataset.action;
        const id = target.dataset.id;
        if (!action || !id) return;
        if (action === "delete-single") {
            removeEvent(`/api/calendar/events/${id}`);
        } else if (action === "delete-recurring") {
            removeEvent(`/api/calendar/recurring/${id}`);
        }
    });

    function renderTimeline() {
        if (!state.timeline.length) {
            timelineWrap.innerHTML = '<p class="muted">未来区间内暂无日程安排。</p>';
            return;
        }
        timelineWrap.innerHTML = state.timeline.map((item) => {
            const badge = item.type === "recurring" ? "周期" : "单日";
            const distance = item.days_from_today;
            const distanceLabel = distance === 0 ? "就在今天" : (distance > 0 ? `${distance} 天后` : `已过去 ${Math.abs(distance)} 天`);
            return `
                <article class="timeline-item">
                    <div class="timeline-meta">
                        <span class="timeline-date">${item.date}</span>
                        <span class="timeline-badge">${badge}</span>
                    </div>
                    <div class="timeline-title">${item.title}</div>
                    <div class="timeline-distance">${distanceLabel}</div>
                </article>
            `;
        }).join("");
    }

    async function loadCalendar() {
        const today = new Date();
        const end = new Date();
        end.setDate(end.getDate() + state.range);
        const params = new URLSearchParams({
            start: formatDate(today),
            end: formatDate(end)
        });
        try {
            const response = await fetch(`/api/calendar/overview?${params.toString()}`);
            if (!response.ok) {
                throw new Error("无法加载日程信息");
            }
            const payload = await response.json();
            state.single = payload.single_events || [];
            state.recurring = payload.recurring_events || [];
            state.timeline = payload.timeline || [];
            renderConfig();
            renderTimeline();
        } catch (error) {
            console.error(error);
            timelineWrap.innerHTML = '<p class="muted">日程加载失败，请稍后再试。</p>';
        }
    }

    function formatWeekday(weekday) {
        const mapping = { 1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日" };
        return mapping[weekday] || "未知";
    }

    function formatDate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    function setDefaultDates() {
        const today = formatDate(new Date());
        const singleDate = document.getElementById("single-date");
        const recurringStart = document.getElementById("recurring-start");
        const recurringEnd = document.getElementById("recurring-end");
        if (singleDate instanceof HTMLInputElement && !singleDate.value) {
            singleDate.value = today;
        }
        if (recurringStart instanceof HTMLInputElement && !recurringStart.value) {
            recurringStart.value = today;
        }
        if (recurringEnd instanceof HTMLInputElement && !recurringEnd.value) {
            const end = new Date();
            end.setDate(end.getDate() + 30);
            recurringEnd.value = formatDate(end);
        }
    }

    loadCalendar();
})();
