export function initCreatureCards() {
  if (document.documentElement.dataset.creatureCardsBound === "1") {
    return;
  }
  document.documentElement.dataset.creatureCardsBound = "1";

  document.addEventListener("pointerdown", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target?.closest(".creature-card__damage-cluster")) {
      return;
    }
    event.stopPropagation();
  }, true);

  const submitCreatureDamageForm = (form, button = null) => {
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    if (button instanceof HTMLButtonElement && typeof form.requestSubmit === "function") {
      form.requestSubmit(button);
      return;
    }
    if (typeof form.requestSubmit === "function") {
      form.requestSubmit();
      return;
    }
    form.submit();
  };

  const readInt = (value, fallback = 0) => {
    const parsed = Number.parseInt(String(value ?? "").trim(), 10);
    return Number.isNaN(parsed) ? fallback : parsed;
  };

  const woundPenaltyForLabel = (label) => {
    if (label === "-2" || label === "-4" || label === "-6") {
      return readInt(label, 0);
    }
    return 0;
  };

  const formatPenalty = (penalty) => (
    penalty ? `; Malus ${penalty > 0 ? `+${penalty}` : penalty}` : ""
  );

  const woundZoneForDamage = (cluster, damage) => {
    const rows = Array.from(cluster.querySelectorAll("[data-creature-wound-row]"))
      .map((row) => ({
        label: String(row.getAttribute("data-label") || "-"),
        threshold: readInt(row.getAttribute("data-threshold"), 0),
      }))
      .sort((a, b) => a.threshold - b.threshold);
    let current = { label: "-", threshold: 0, penalty: 0 };
    for (const row of rows) {
      if (damage >= row.threshold) {
        current = {
          label: row.label,
          threshold: row.threshold,
          penalty: woundPenaltyForLabel(row.label),
        };
      } else {
        break;
      }
    }
    return current;
  };

  const renderPreviewDamage = (cluster, nextDamage) => {
    const card = cluster.closest(".creature-card");
    const currentEl = cluster.querySelector("[data-creature-damage-current]");
    const maxEl = cluster.querySelector("[data-creature-damage-max]");
    const maxDamage = readInt(cluster.getAttribute("data-creature-wound-max") || maxEl?.textContent, 0);
    const damage = Math.max(0, Math.min(nextDamage, Math.max(0, maxDamage)));
    cluster.dataset.creatureCurrentDamage = String(damage);
    if (currentEl instanceof HTMLElement) {
      currentEl.textContent = String(damage);
    }
    if (maxEl instanceof HTMLElement) {
      maxEl.textContent = String(maxDamage);
    }

    const zone = woundZoneForDamage(cluster, damage);
    const status = card?.querySelector("[data-creature-wound-status]");
    if (!(status instanceof HTMLElement)) {
      return;
    }
    status.hidden = zone.label === "-";
    const labelEl = status.querySelector("[data-creature-wound-label]");
    const thresholdEl = status.querySelector("[data-creature-wound-threshold]");
    const penaltyEl = status.querySelector("[data-creature-wound-penalty]");
    if (labelEl instanceof HTMLElement) {
      labelEl.textContent = zone.label;
    }
    if (thresholdEl instanceof HTMLElement) {
      thresholdEl.textContent = String(zone.threshold);
    }
    if (penaltyEl instanceof HTMLElement) {
      penaltyEl.textContent = formatPenalty(zone.penalty);
    }
  };

  const applyPreviewDamageAction = (cluster, action) => {
    if (action !== "heal" && action !== "damage") {
      return;
    }
    const current = readInt(cluster.getAttribute("data-creature-current-damage"), 0);
    const nextDamage = action === "damage" ? current + 1 : current - 1;
    renderPreviewDamage(cluster, nextDamage);
  };

  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const button = target?.closest(".creature-card__damage-cluster button");
    if (button instanceof HTMLButtonElement && !button.disabled && button.form instanceof HTMLFormElement) {
      const form = button.form;
      event.preventDefault();
      event.stopPropagation();
      submitCreatureDamageForm(form, button);
      return;
    }

    const cluster = target?.closest(".creature-card__damage-cluster");
    if (!(cluster instanceof HTMLElement)) {
      return;
    }
    const rect = cluster.getBoundingClientRect();
    const edgeWidth = Math.min(24, Math.max(14, rect.width * 0.32));
    const forms = Array.from(cluster.querySelectorAll("form"));
    if (!forms.length) {
      const action = button instanceof HTMLButtonElement
        ? button.getAttribute("data-creature-damage-action")
        : event.clientX <= rect.left + edgeWidth
          ? "heal"
          : event.clientX >= rect.right - edgeWidth
            ? "damage"
            : "";
      if (!action) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      applyPreviewDamageAction(cluster, action);
      return;
    }

    const form = event.clientX <= rect.left + edgeWidth
      ? forms[0]
      : event.clientX >= rect.right - edgeWidth
        ? forms[forms.length - 1]
        : null;
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    const submitter = form.querySelector("button[type='submit']");
    if (submitter instanceof HTMLButtonElement && submitter.disabled) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    submitCreatureDamageForm(form, submitter instanceof HTMLButtonElement ? submitter : null);
  }, true);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initCreatureCards, { once: true });
} else {
  initCreatureCards();
}
