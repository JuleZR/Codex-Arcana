import { createFloatingWindowController } from "./window_manager.js";

export function initTechniqueSpecModal() {
  const techniqueSpecWindow = document.getElementById("techniqueSpecWindow");
  const techniqueSpecWindowClose = document.getElementById("techniqueSpecWindowClose");
  const techniqueSpecWindowHandle = document.getElementById("techniqueSpecWindowHandle");
  const techniqueSpecWindowTitle = document.getElementById("techniqueSpecWindowTitle");
  const techniqueSpecCancelBtn = document.getElementById("techniqueSpecCancelBtn");
  const techniqueSpecForm = document.getElementById("techniqueSpecForm");
  const techniqueSpecInput = document.getElementById("id_specification_value");
  if (
    !techniqueSpecWindow
    || !techniqueSpecWindowClose
    || !techniqueSpecWindowHandle
    || !techniqueSpecWindowTitle
    || !techniqueSpecForm
    || !techniqueSpecInput
  ) {
    return;
  }
  if (techniqueSpecWindow.dataset.modalBound === "1") {
    return;
  }
  techniqueSpecWindow.dataset.modalBound = "1";

  const controller = createFloatingWindowController({
    windowEl: techniqueSpecWindow,
    closeButton: techniqueSpecWindowClose,
    handle: techniqueSpecWindowHandle,
    startTop: 214,
    startRightInset: 148,
    storageKey: "charsheet.techniqueSpecWindow",
    allowPersistedOpen: false,
  });
  if (!controller) {
    return;
  }

  document.addEventListener("click", (event) => {
    const trigger = event.target instanceof Element ? event.target.closest("[data-technique-spec-trigger]") : null;
    if (!(trigger instanceof HTMLElement)) {
      return;
    }
    techniqueSpecWindowTitle.textContent = `${trigger.dataset.techniqueName || "Technik"} bearbeiten`;
    techniqueSpecForm.action = trigger.dataset.action || "";
    techniqueSpecInput.value = trigger.dataset.specificationValue || "";
    controller.open();
    window.setTimeout(() => {
      techniqueSpecInput.focus();
      techniqueSpecInput.select();
    }, 0);
  });

  techniqueSpecCancelBtn?.addEventListener("click", () => {
    controller.close();
  });
  techniqueSpecForm.addEventListener("submit", () => {
    controller.close();
  });
}
