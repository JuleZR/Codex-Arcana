export function applySheetPartials(payload) {
  const partials = Array.isArray(payload?.partials) ? payload.partials : [];
  const updatedTargets = [];

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
