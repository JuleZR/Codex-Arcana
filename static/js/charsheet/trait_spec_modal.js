import { createFloatingWindowController } from "./window_manager.js";

export function initTraitSpecModal() {
  const traitSpecWindow = document.getElementById("traitSpecWindow");
  const traitSpecWindowClose = document.getElementById("traitSpecWindowClose");
  const traitSpecWindowHandle = document.getElementById("traitSpecWindowHandle");
  const traitSpecWindowTitle = document.getElementById("traitSpecWindowTitle");
  const traitSpecCancelBtn = document.getElementById("traitSpecCancelBtn");
  const traitSpecForm = document.getElementById("traitSpecForm");
  const traitSpecInput = document.getElementById("id_trait_specification");
  const traitSpecOption = document.getElementById("id_specification_option");
  const freeRow = traitSpecForm?.querySelector("[data-trait-free-specification]");
  const controlledRow = traitSpecForm?.querySelector("[data-trait-controlled-specification]");
  if (
    !traitSpecWindow
    || !traitSpecWindowClose
    || !traitSpecWindowHandle
    || !traitSpecWindowTitle
    || !traitSpecForm
    || !traitSpecInput
    || !traitSpecOption
    || !freeRow
    || !controlledRow
  ) {
    return;
  }
  if (traitSpecWindow.dataset.modalBound === "1") {
    return;
  }
  traitSpecWindow.dataset.modalBound = "1";

  const controller = createFloatingWindowController({
    windowEl: traitSpecWindow,
    closeButton: traitSpecWindowClose,
    handle: traitSpecWindowHandle,
    startTop: 168,
    startRightInset: 212,
    storageKey: "charsheet.traitSpecWindow",
    allowPersistedOpen: false,
  });
  if (!controller) {
    return;
  }

  document.addEventListener("click", (event) => {
    const trigger = event.target instanceof Element ? event.target.closest("[data-trait-spec-trigger]") : null;
    if (!(trigger instanceof HTMLElement)) {
      return;
    }
    traitSpecWindowTitle.textContent = `${trigger.dataset.traitName || "Trait"} bearbeiten`;
    traitSpecForm.action = trigger.dataset.action || "";
    let options = [];
    try {
      options = JSON.parse(trigger.dataset.specificationOptions || "[]");
    } catch (_error) {
      options = [];
    }
    const controlled = options.length > 0;
    freeRow.hidden = controlled;
    controlledRow.hidden = !controlled;
    traitSpecInput.disabled = controlled;
    traitSpecOption.disabled = !controlled;
    traitSpecInput.value = controlled ? "" : (trigger.dataset.specification || "");
    traitSpecOption.replaceChildren(new Option("---------", ""));
    options.forEach((option) => {
      traitSpecOption.add(new Option(option.name, String(option.id)));
    });
    traitSpecOption.value = trigger.dataset.specificationOption || "";
    controller.open();
    window.setTimeout(() => {
      const target = controlled ? traitSpecOption : traitSpecInput;
      target.focus();
      if (!controlled) target.select();
    }, 0);
  });

  traitSpecCancelBtn?.addEventListener("click", () => {
    controller.close();
  });
  traitSpecForm.addEventListener("submit", () => {
    controller.close();
  });
}
