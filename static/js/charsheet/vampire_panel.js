import { applySheetPartials } from "./partial_updates.js";
import { getCsrfToken } from "./utils.js";

function readInt(value, fallback = 0) {
  const parsed = Number.parseInt(String(value ?? "").trim(), 10);
  return Number.isNaN(parsed) ? fallback : parsed;
}

function setFeedback(panel, message, isError = false) {
  const feedback = panel.querySelector("[data-vampire-power-feedback]");
  if (!(feedback instanceof HTMLElement)) {
    return;
  }
  feedback.textContent = String(message || "");
  feedback.classList.toggle("is-error", isError);
}

async function activateVampirePower(panel, button) {
  const url = String(button.getAttribute("data-activate-url") || "");
  const powerId = readInt(button.getAttribute("data-vampire-power-id"), 0);
  const bloodCost = readInt(button.getAttribute("data-vampire-blood-cost"), 0);
  if (!url || powerId <= 0 || button.dataset.vampirePowerPending === "1") {
    return;
  }

  button.dataset.vampirePowerPending = "1";
  button.disabled = true;
  setFeedback(panel, "Vampirkraft wird angewendet …");
  try {
    const body = new URLSearchParams({
      power_id: String(powerId),
      blood_amount: String(bloodCost),
      ajax: "1",
    });
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCsrfToken(),
        "X-Requested-With": "XMLHttpRequest",
        Accept: "application/json",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      },
      credentials: "same-origin",
      body,
    });
    const payload = await response.json();
    if (!response.ok || !payload?.ok) {
      throw new Error(String(payload?.message || payload?.error || "Vampirkraft konnte nicht angewendet werden."));
    }
    applySheetPartials(payload);
    setFeedback(
      panel,
      `${String(payload.power_name || "Vampirkraft")} angewendet (${readInt(payload.spent_blood, bloodCost)} BP).`,
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Vampirkraft konnte nicht angewendet werden.";
    setFeedback(panel, message, true);
    window.alert(message);
  } finally {
    button.dataset.vampirePowerPending = "0";
    button.disabled = false;
  }
}

export function initVampirePanel() {
  document.querySelectorAll("[data-vampire-power-panel]").forEach((panel) => {
    if (!(panel instanceof HTMLElement) || panel.dataset.vampirePowerBound === "1") {
      return;
    }
    panel.dataset.vampirePowerBound = "1";

    panel.querySelectorAll(".vampire_power_entry").forEach((entry) => {
      entry.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") {
          return;
        }
        const nestedInteractive = event.target instanceof Element
          ? event.target.closest("button, a, input, select, textarea")
          : null;
        if (nestedInteractive) {
          return;
        }
        event.preventDefault();
        entry.click();
      });
    });

    panel.querySelectorAll("[data-activate-vampire-power]").forEach((button) => {
      if (!(button instanceof HTMLButtonElement)) {
        return;
      }
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        activateVampirePower(panel, button);
      });
    });
  });
}
