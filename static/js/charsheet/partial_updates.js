const BODY_ARMOR_ZONES = [
  "shield",
  "head",
  "face",
  "eyes",
  "neck",
  "torso",
  "organs",
  "soft_tissue",
  "arm_left",
  "hand_left",
  "leg_left",
  "foot_left",
  "arm_right",
  "hand_right",
  "leg_right",
  "foot_right",
];

function applyBodyArmorUpdate(payload) {
  const bodyArmor = payload?.bodyArmor;
  if (!bodyArmor || typeof bodyArmor !== "object") {
    return [];
  }

  const bodyPanel = document.getElementById("lowerPanelBody");
  if (!(bodyPanel instanceof HTMLElement)) {
    return [];
  }

  BODY_ARMOR_ZONES.forEach((zone) => {
    const value = Number(bodyArmor[zone] || 0);
    const protectedZone = value > 0;

    bodyPanel.querySelectorAll(`.armor_callout_row[data-body-zone="${zone}"]`).forEach((row) => {
      row.querySelectorAll(".armor_callout_value").forEach((entry) => {
        entry.textContent = protectedZone ? String(value) : "";
      });
      row.querySelectorAll(".armor_callout_pill").forEach((entry) => {
        entry.classList.toggle("is-empty", !protectedZone);
      });
    });

    bodyPanel.querySelectorAll(`.armor_map_zone[data-body-zone="${zone}"]`).forEach((entry) => {
      entry.classList.toggle("is-protected", protectedZone);
    });

    bodyPanel.querySelectorAll(`.armor_callout_lines [data-body-zone="${zone}"]`).forEach((entry) => {
      entry.toggleAttribute("hidden", !protectedZone);
    });
  });

  return ["lowerPanelBody"];
}

export function applySheetPartials(payload) {
  const partials = Array.isArray(payload?.partials) ? payload.partials : [];
  const updatedTargets = applyBodyArmorUpdate(payload);

  partials.forEach((partial) => {
    const targetId = String(partial?.target || "").trim();
    const html = String(partial?.html || "");
    if (!targetId || !html) {
      return;
    }

    const current = document.getElementById(targetId);
    if (!current) {
      return;
    }
    if (typeof current.__floatingWindowController?.destroy === "function") {
      current.__floatingWindowController.destroy();
    }

    // Card-hand floatings are moved out of #sheetCardHand into the global app
    // layer for dragging. Replacing the host alone would otherwise leave stale
    // open cards visible until the next full page load.
    if (targetId === "sheetCardHand") {
      document.querySelectorAll("[data-card-hand-floating]").forEach((floating) => {
        if (!current.contains(floating)) {
          floating.remove();
        }
      });
    }

    const preservedOpenState = new Map();
    const preservedValueState = new Map();
    const preservedScrollState = new Map();
    current.querySelectorAll("[data-preserve-open-id]").forEach((element) => {
      if (!(element instanceof HTMLDetailsElement)) {
        return;
      }
      const preserveId = String(element.dataset.preserveOpenId || "").trim();
      if (!preserveId) {
        return;
      }
      preservedOpenState.set(preserveId, element.open);
    });
    current.querySelectorAll("[data-preserve-value-id]").forEach((element) => {
      const preserveId = String(element.dataset.preserveValueId || "").trim();
      if (!preserveId) {
        return;
      }
      if (
        element instanceof HTMLInputElement
        || element instanceof HTMLTextAreaElement
        || element instanceof HTMLSelectElement
      ) {
        preservedValueState.set(preserveId, element.value);
      }
    });
    current.querySelectorAll("[data-preserve-scroll-id]").forEach((element) => {
      if (!(element instanceof HTMLElement)) {
        return;
      }
      const preserveId = String(element.dataset.preserveScrollId || "").trim();
      if (!preserveId) {
        return;
      }
      preservedScrollState.set(preserveId, element.scrollTop);
    });

    const template = document.createElement("template");
    template.innerHTML = html.trim();
    const next = template.content.firstElementChild;
    if (!(next instanceof HTMLElement)) {
      return;
    }

    next.querySelectorAll("[data-preserve-open-id]").forEach((element) => {
      if (!(element instanceof HTMLDetailsElement)) {
        return;
      }
      const preserveId = String(element.dataset.preserveOpenId || "").trim();
      if (!preserveId || !preservedOpenState.has(preserveId)) {
        return;
      }
      element.open = Boolean(preservedOpenState.get(preserveId));
    });
    next.querySelectorAll("[data-preserve-value-id]").forEach((element) => {
      const preserveId = String(element.dataset.preserveValueId || "").trim();
      if (!preserveId || !preservedValueState.has(preserveId)) {
        return;
      }
      if (
        element instanceof HTMLInputElement
        || element instanceof HTMLTextAreaElement
        || element instanceof HTMLSelectElement
      ) {
        element.value = String(preservedValueState.get(preserveId) || "");
        element.dispatchEvent(new Event("input", { bubbles: true }));
      }
    });
    next.querySelectorAll("[data-preserve-scroll-id]").forEach((element) => {
      if (!(element instanceof HTMLElement)) {
        return;
      }
      const preserveId = String(element.dataset.preserveScrollId || "").trim();
      if (!preserveId || !preservedScrollState.has(preserveId)) {
        return;
      }
      element.scrollTop = Number(preservedScrollState.get(preserveId) || 0);
    });

    current.replaceWith(next);
    updatedTargets.push(targetId);
  });

  document.dispatchEvent(new CustomEvent("charsheet:partials-applied", {
    detail: { targets: updatedTargets },
  }));

  return updatedTargets;
}
