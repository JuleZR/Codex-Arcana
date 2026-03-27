import { applySheetPartials } from "./partial_updates.js";

export function initSheetActions() {
  if (document.body.dataset.sheetActionsBound === "1") {
    return;
  }
  document.body.dataset.sheetActionsBound = "1";

  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.hasAttribute("data-sheet-action")) {
      return;
    }

    event.preventDefault();

    try {
      const response = await fetch(form.action, {
        method: form.method || "POST",
        body: new FormData(form),
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        credentials: "same-origin",
      });
      if (!response.ok) {
        throw new Error("sheet action failed");
      }
      const payload = await response.json();
      if (!payload?.ok) {
        throw new Error("sheet action invalid");
      }
      applySheetPartials(payload);
      if (form.hasAttribute("data-reset-after-success")) {
        form.reset();
      }
    } catch (_error) {
      form.submit();
    }
  });
}

