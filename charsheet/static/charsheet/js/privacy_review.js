"use strict";

(() => {
    function redactSelection(value, start, end) {
        return value.slice(0, start) + "[Geschwärzt]" + value.slice(end);
    }
    if (typeof module !== "undefined") module.exports = { redactSelection };
    if (typeof document === "undefined") return;

    const editor = document.querySelector("[data-field-editor]");
    function updateEditor() {
        if (!editor) return;
        const action = editor.querySelector('[name="field-action"]').value;
        editor.querySelectorAll("[data-partial]").forEach(element => {
            element.hidden = action !== "partial";
        });
        const preview = editor.querySelector("[data-field-preview]");
        if (preview) {
            const original = editor.querySelector(".privacy-original")?.textContent || preview.dataset.original;
            const text = editor.querySelector('[name="field-text"]').value;
            const structured = editor.querySelector('[name="field-as_text"]');
            const partial = structured && !structured.checked ? "Geprüfte Struktur – die einzelnen Werte stehen unten." : text;
            preview.textContent = action === "partial" ? partial :
                ["redact", "withhold", "not_personal"].includes(action) ? "[Geschwärzt]" : original;
        }
    }
    editor?.addEventListener("input", updateEditor);
    editor?.addEventListener("change", updateEditor);
    updateEditor();

    document.querySelectorAll("[data-live-preview]").forEach(input => {
        input.addEventListener("input", () => {
            document.getElementById(input.dataset.livePreview).textContent = input.value;
        });
    });
    document.querySelectorAll("[data-redact]").forEach(button => {
        button.addEventListener("click", () => {
            const input = document.getElementById(button.dataset.redact);
            if (input.selectionStart === input.selectionEnd) {
                input.focus();
                return;
            }
            const start = input.selectionStart;
            input.value = redactSelection(input.value, start, input.selectionEnd);
            input.setSelectionRange(start, start + "[Geschwärzt]".length);
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.focus();
        });
    });
    document.querySelectorAll("[data-jump-button]").forEach(button => {
        button.addEventListener("click", () => {
            const target = new URL(document.getElementById(button.dataset.jumpButton).value, location.href);
            if (target.origin === location.origin) location.assign(target.href);
        });
    });
    document.querySelectorAll("[data-service]").forEach(section => {
        const status = section.querySelector('select[name$="-status"]');
        const transfer = section.querySelector('select[name$="-transfer_applies"]');
        function update() {
            section.querySelectorAll(".privacy-control").forEach(control => {
                const name = control.querySelector("input, select, textarea")?.name || "";
                const key = name.split("-").pop();
                control.hidden = key !== "status" && (
                    status.value === "" || (status.value === "not_used" ? key !== "reason" :
                        key === "reason" || (["safeguards", "copy_source"].includes(key) && transfer.value !== "yes"))
                );
            });
        }
        status.addEventListener("change", update);
        transfer.addEventListener("change", update);
        update();
    });
    document.querySelector("[data-add-value]")?.addEventListener("click", event => {
        const form = event.target.closest("form");
        const total = form.querySelector('[name="values-TOTAL_FORMS"]');
        if (Number(total.value) >= 40) return;
        const template = form.querySelector("[data-empty-row]");
        const html = template.innerHTML.replaceAll("__prefix__", total.value);
        form.querySelector("[data-value-rows]").insertAdjacentHTML("beforeend", html);
        total.value = String(Number(total.value) + 1);
    });
    document.querySelectorAll("[data-confirm]").forEach(button => {
        button.addEventListener("click", event => {
            if (!window.confirm(button.dataset.confirm)) event.preventDefault();
        });
    });
    const approval = document.querySelector("[data-approval-form]");
    const dialog = document.getElementById("privacy-approval-dialog");
    if (approval && dialog) {
        let submitter;
        approval.addEventListener("submit", event => {
            if (approval.dataset.confirmed === "yes") return;
            event.preventDefault();
            submitter = event.submitter;
            if (typeof dialog.showModal === "function") dialog.showModal();
            else if (window.confirm("Genau diesen geprüften Stand endgültig freigeben?")) {
                approval.dataset.confirmed = "yes";
                approval.requestSubmit(submitter);
            }
        });
        dialog.querySelector("[data-dialog-cancel]").addEventListener("click", () => dialog.close());
        dialog.querySelector("[data-dialog-approve]").addEventListener("click", () => {
            approval.dataset.confirmed = "yes";
            dialog.close();
            approval.requestSubmit(submitter);
        });
        dialog.addEventListener("close", () => submitter?.focus());
    }
    const firstError = document.querySelector('[aria-invalid="true"], .privacy-invalid input, .privacy-invalid textarea, .privacy-invalid select, .privacy-alert[tabindex]');
    for (let ancestor = firstError?.parentElement; ancestor; ancestor = ancestor.parentElement) {
        if (ancestor.tagName === "DETAILS") ancestor.open = true;
    }
    firstError?.focus();
})();
