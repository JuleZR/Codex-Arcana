import { getCsrfToken } from "./utils.js";

function isCarryLoadEnabled() {
  const button = document.querySelector("[data-carry-load-toggle]");
  if (button instanceof HTMLElement && button.dataset.carryEnabled !== undefined) {
    return button.dataset.carryEnabled === "1";
  }
  return false;
}

function setCarryLoadEnabled(enabled) {
  document.querySelectorAll("[data-carry-load-toggle]").forEach((button) => {
    button.dataset.carryEnabled = enabled ? "1" : "0";
  });
}

function readDecimal(value, fallback = 0) {
  const normalized = String(value ?? "")
    .trim()
    .replace(/\s+/g, "")
    .replace(",", ".");
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function readInteger(value, fallback = 0) {
  const parsed = Number.parseInt(String(value ?? "").trim(), 10);
  return Number.isInteger(parsed) ? parsed : fallback;
}

function formatModifier(value) {
  const numericValue = readInteger(value, 0);
  if (numericValue > 0) {
    return `+${numericValue}`;
  }
  return String(numericValue);
}

function getCarryWeight() {
  const button = document.querySelector("[data-carry-load-toggle]");
  if (!(button instanceof HTMLElement)) {
    return 0;
  }
  return readDecimal(button.dataset.carryWeight, 0);
}

function getStrengthValue() {
  const row = document.querySelector('[data-attribute-short-name="ST"]');
  if (!(row instanceof HTMLElement)) {
    return 0;
  }
  const valueCell = row.querySelector("[data-attribute-value]");
  if (!(valueCell instanceof HTMLElement)) {
    return 0;
  }
  return readInteger(valueCell.textContent, 0);
}

function calculateCarryPenalty(weight, strength) {
  if (strength <= 0) {
    return weight > 0 ? -8 : 0;
  }
  if (weight >= strength * 8) {
    return -8;
  }
  if (weight >= strength * 6) {
    return -4;
  }
  if (weight >= strength * 3) {
    return -2;
  }
  if (weight >= strength * 2) {
    return -1;
  }
  return 0;
}

function applyValueAndTooltip(element, enabled, carryPenalty) {
  if (!(element instanceof HTMLElement)) {
    return;
  }
  const baseValue = readInteger(element.dataset.baseValue, 0);
  const resolvedValue = enabled ? baseValue + carryPenalty : baseValue;
  const tooltipOff = String(element.dataset.tooltipOff || element.dataset.carryTooltipOff || element.dataset.tooltip || "");
  const tooltipOn = String(element.dataset.tooltipOn || element.dataset.carryTooltipOn || tooltipOff);
  const format = String(element.dataset.format || "").trim().toLowerCase();
  element.textContent = format === "modifier" ? formatModifier(resolvedValue) : String(resolvedValue);
  element.dataset.tooltip = enabled ? tooltipOn : tooltipOff;
}

function applyToggleButton(button, enabled) {
  if (!(button instanceof HTMLButtonElement)) {
    return;
  }
  button.setAttribute("aria-pressed", enabled ? "true" : "false");
  button.classList.toggle("is-active", enabled);
}

function applyPenaltyBadge(button, enabled, carryPenalty) {
  if (!(button instanceof HTMLButtonElement)) {
    return;
  }
  const badge = button.querySelector("[data-carry-load-penalty]");
  const separator = button.querySelector("[data-carry-load-separator]");
  if (!(badge instanceof HTMLElement)) {
    return;
  }
  if (!enabled || carryPenalty === 0) {
    badge.hidden = true;
    badge.textContent = "";
    if (separator instanceof HTMLElement) {
      separator.hidden = true;
    }
    return;
  }
  badge.hidden = false;
  badge.textContent = formatModifier(carryPenalty);
  if (separator instanceof HTMLElement) {
    separator.hidden = false;
  }
}

function applyCarrySeverity(button, enabled, carryPenalty) {
  if (!(button instanceof HTMLButtonElement)) {
    return;
  }
  button.classList.remove(
    "is-carry-light",
    "is-carry-medium",
    "is-carry-heavy",
    "is-carry-overloaded",
  );
  if (!enabled) {
    return;
  }
  if (carryPenalty <= -8) {
    button.classList.add("is-carry-overloaded");
    return;
  }
  if (carryPenalty <= -4) {
    button.classList.add("is-carry-heavy");
    return;
  }
  if (carryPenalty <= -2) {
    button.classList.add("is-carry-medium");
    return;
  }
  if (carryPenalty <= -1) {
    button.classList.add("is-carry-light");
  }
}

function applyCarryLoadState(enabled) {
  const carryPenalty = calculateCarryPenalty(getCarryWeight(), getStrengthValue());
  document.querySelectorAll("[data-carry-load-toggle]").forEach((button) => {
    applyToggleButton(button, enabled);
    applyPenaltyBadge(button, enabled, carryPenalty);
    applyCarrySeverity(button, enabled, carryPenalty);
  });
  document.querySelectorAll("[data-carry-load-display]").forEach((element) => {
    applyValueAndTooltip(element, enabled, carryPenalty);
  });
  document.querySelectorAll("[data-carry-initiative-display]").forEach((element) => {
    applyValueAndTooltip(element, enabled, carryPenalty);
  });
  document.querySelectorAll("[data-carry-skill-loaded-total]").forEach((element) => {
    applyValueAndTooltip(element, enabled, carryPenalty);
  });
  document.querySelectorAll("[data-carry-weapon-loaded-total]").forEach((element) => {
    applyValueAndTooltip(element, enabled, carryPenalty);
  });
}

export function initCarryLoadToggle() {
  if (document.body.dataset.carryLoadToggleBound !== "1") {
    document.body.dataset.carryLoadToggleBound = "1";
    document.addEventListener("click", async (event) => {
      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }
      const button = target.closest("[data-carry-load-toggle]");
      if (!(button instanceof HTMLButtonElement)) {
        return;
      }
      event.preventDefault();
      const nextEnabled = !isCarryLoadEnabled();
      setCarryLoadEnabled(nextEnabled);
      applyCarryLoadState(nextEnabled);
      const updateUrl = button.dataset.carryUpdateUrl;
      if (updateUrl) {
        try {
          const response = await fetch(updateUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: {
              Accept: "application/json",
              "Content-Type": "application/json",
              "X-CSRFToken": getCsrfToken(),
            },
            body: JSON.stringify({ enabled: nextEnabled }),
          });
          if (!response.ok) throw new Error("carry load update failed");
        } catch (_error) {
          setCarryLoadEnabled(!nextEnabled);
          applyCarryLoadState(!nextEnabled);
        }
      }
    });
  }

  applyCarryLoadState(isCarryLoadEnabled());
}
