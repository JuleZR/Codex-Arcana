import { applySheetPartials } from "./partial_updates.js";
import { getCsrfToken } from "./utils.js";

export function initSpellPanel() {
  const panel = document.getElementById("sheetSpellPanel");
  if (!panel || panel.dataset.spellPanelBound === "1") {
    return;
  }
  panel.dataset.spellPanelBound = "1";

  panel.querySelectorAll("[data-cast-spell-trigger]").forEach((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    button.addEventListener("click", async () => {
      const url = button.getAttribute("data-cast-url") || "";
      if (!url || button.disabled) {
        return;
      }
      button.disabled = true;
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": getCsrfToken(),
            Accept: "application/json",
          },
          credentials: "same-origin",
        });
        const payload = await response.json();
        if (!response.ok || !payload?.ok) {
          window.alert(String(payload?.message || "Zauber konnte nicht gewirkt werden."));
          return;
        }
        if (Array.isArray(payload.partials) && payload.partials.length) {
          applySheetPartials(payload);
        }
      } catch (_error) {
        window.alert("Zauber konnte nicht gewirkt werden.");
      } finally {
        button.disabled = false;
      }
    });
  });
}
