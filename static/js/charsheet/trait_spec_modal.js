import { createFloatingWindowController } from "./window_manager.js";

export function initTraitSpecModal() {
  const traitSpecWindow = document.getElementById("traitSpecWindow");
  const traitSpecWindowClose = document.getElementById("traitSpecWindowClose");
  const traitSpecWindowHandle = document.getElementById("traitSpecWindowHandle");
  const traitSpecWindowTitle = document.getElementById("traitSpecWindowTitle");
  const traitSpecCancelBtn = document.getElementById("traitSpecCancelBtn");
  const traitSpecForm = document.getElementById("traitSpecForm");
  const traitSpecInput = document.getElementById("id_trait_specification");
  if (
    !traitSpecWindow
    || !traitSpecWindowClose
    || !traitSpecWindowHandle
    || !traitSpecWindowTitle
    || !traitSpecForm
    || !traitSpecInput
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
    traitSpecInput.value = trigger.dataset.specification || "";
    controller.open();
    window.setTimeout(() => {
      traitSpecInput.focus();
      traitSpecInput.select();
    }, 0);
  });

  traitSpecCancelBtn?.addEventListener("click", () => {
    controller.close();
  });
  traitSpecForm.addEventListener("submit", () => {
    controller.close();
  });
}
