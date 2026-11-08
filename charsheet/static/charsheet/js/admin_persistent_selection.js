"use strict";
(() => {
    const script = document.currentScript;
    const key = `admin-selection:${script.dataset.user}:${window.location.pathname}`;

    document.addEventListener("DOMContentLoaded", () => {
        const form = document.getElementById("changelist-form");
        if (!form) return;

        let selected;
        try {
            const saved = JSON.parse(sessionStorage.getItem(key) || "[]");
            selected = new Set(Array.isArray(saved) ? saved.map(String) : []);
            sessionStorage.setItem(key, JSON.stringify([...selected]));
        } catch {
            return;
        }

        const boxes = [...form.querySelectorAll("input.action-select")];
        const toggle = document.getElementById("action-toggle");
        const status = document.createElement("p");
        const count = document.createElement("span");
        count.setAttribute("aria-live", "polite");
        const clear = document.createElement("button");
        clear.type = "button";
        clear.textContent = "Auswahl leeren";
        status.append(count, " ", clear);
        form.prepend(status);

        function render() {
            count.textContent = `${selected.size} insgesamt ausgewählt (über Suche, Filter und Seiten hinweg).`;
            clear.disabled = selected.size === 0;
        }

        function save() {
            try {
                sessionStorage.setItem(key, JSON.stringify([...selected]));
            } catch {
                // Keep the current selection usable if storage becomes unavailable.
            }
            render();
        }

        function rememberVisible() {
            boxes.forEach((box) => {
                if (box.checked) selected.add(box.value);
                else selected.delete(box.value);
            });
            save();
        }

        function restore() {
            boxes.forEach((box) => {
                box.checked = selected.has(box.value);
                box.closest("tr").classList.toggle("selected", box.checked);
            });
            if (boxes.length) {
                // Let Django update its counter and the select-across controls.
                boxes[0].dispatchEvent(new Event("change", {bubbles: true}));
            }
            render();
        }

        form.addEventListener("change", (event) => {
            if (event.target.matches("input.action-select")) rememberVisible();
        });
        if (toggle) toggle.addEventListener("click", rememberVisible);

        function clearSelection() {
            selected.clear();
            restore();
            save();
        }
        clear.addEventListener("click", clearSelection);
        form.querySelectorAll(".actions .clear a").forEach((link) => {
            link.addEventListener("click", clearSelection);
        });

        form.addEventListener("submit", (event) => {
            if (event.defaultPrevented || event.submitter?.name === "_save") return;
            const actions = form.querySelectorAll("select[name=action]");
            const index = Number(event.submitter?.value || 0);
            if (!actions[index]?.value) return;
            rememberVisible();
            const across = form.querySelector("input[name=select_across]");
            if (across?.value !== "1" && selected.size) {
                const visible = new Set(boxes.map((box) => box.value));
                selected.forEach((id) => {
                    if (visible.has(id)) return;
                    const input = document.createElement("input");
                    input.type = "hidden";
                    input.name = "_selected_action";
                    input.value = id;
                    form.append(input);
                });
                // Django applies actions to the current filtered queryset.
                // Explicit IDs must therefore be posted to the unfiltered list.
                form.action = window.location.pathname;
            }
            selected.clear();
            save();
        });

        window.addEventListener("pageshow", restore);
        restore();
    });
})();
