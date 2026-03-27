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

    const template = document.createElement("template");
    template.innerHTML = html.trim();
    const next = template.content.firstElementChild;
    if (!(next instanceof HTMLElement)) {
      return;
    }

    current.replaceWith(next);
    updatedTargets.push(targetId);
  });

  document.dispatchEvent(new CustomEvent("charsheet:partials-applied", {
    detail: { targets: updatedTargets },
  }));

  return updatedTargets;
}
