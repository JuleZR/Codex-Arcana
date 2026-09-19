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

function isCarryLoadToggle(element) {
  return element instanceof HTMLElement && element.matches("[data-carry-load-toggle]");
}

function calculateCarryPenalty() {
  const button = document.querySelector("[data-carry-load-toggle]");
  const weight = Number.parseFloat(String(button?.dataset.carryWeight || "0").replace(",", "."));
  const strength = readInteger(document.querySelector('[data-attribute-short-name="ST"] [data-attribute-value]')?.textContent);
  if (strength <= 0) return weight > 0 ? -8 : 0;
  if (weight >= strength * 8) return -8;
  if (weight >= strength * 6) return -4;
  if (weight >= strength * 3) return -2;
  if (weight >= strength * 2) return -1;
  return 0;
}

function applyValueAndTooltip(element, penalty) {
  const base = readInteger(element.dataset.carryBase);
  const applied = element.dataset.carryAffected === "0" ? 0 : penalty;
  const total = base + applied;
  if (!element.hasAttribute("data-carry-tooltip-only")) {
    element.textContent = element.dataset.format === "modifier" ? formatModifier(total) : String(total);
  }
  element.dataset.carryOriginalTooltip ??= element.dataset.tooltip || "";
  const lines = element.dataset.carryOriginalTooltip.split("\n")
    .filter((line) => !/^\| Traglast(?: |\[)/.test(line));
  const totalIndex = lines.findIndex((line) => line.startsWith("| **= Gesamt** |"));
  if (totalIndex !== -1) {
    lines[totalIndex] = `| **= Gesamt** | \`**${formatModifier(total)}**\` |`;
    if (applied) lines.splice(totalIndex, 0, `| Traglast | \`${formatModifier(applied)}\` |`);
  }
  element.dataset.tooltip = lines.join("\n");
}

function applyToggleButton(button, enabled) {
  if (!isCarryLoadToggle(button)) {
    return;
  }
  button.setAttribute("aria-pressed", enabled ? "true" : "false");
  button.classList.toggle("is-active", enabled);
}

function applyPenaltyBadge(button, enabled, carryPenalty) {
  if (!isCarryLoadToggle(button)) {
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
  if (!isCarryLoadToggle(button)) {
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
  const carryPenalty = calculateCarryPenalty();
  document.querySelectorAll("[data-carry-load-toggle]").forEach((button) => {
    applyToggleButton(button, enabled);
    applyPenaltyBadge(button, enabled, carryPenalty);
    applyCarrySeverity(button, enabled, carryPenalty);
  });
  const penalty = enabled ? carryPenalty : 0;
  document.querySelectorAll("[data-carry-value]").forEach((element) => {
    applyValueAndTooltip(element, penalty);
  });
  document.querySelectorAll("[data-carry-flight]").forEach((element) => {
    const armor = readInteger(element.dataset.armorPenalty);
    const blocked = enabled && element.dataset.naturalFlight === "1" && armor + penalty <= -4;
    element.textContent = blocked ? "-" : element.dataset.baseFlight;
    element.dataset.tooltip = blocked
      ? `Natürlicher Flug nicht verfügbar: Rüstung/Schild ${formatModifier(armor)}, Traglast ${formatModifier(penalty)} (Gesamtbelastung mindestens -4).`
      : "";
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
      if (!isCarryLoadToggle(button)) {
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
