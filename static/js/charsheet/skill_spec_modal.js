import { createFloatingWindowController } from "./window_manager.js";

export function initSkillSpecModal() {
  const skillSpecWindow = document.getElementById("skillSpecWindow");
  const skillSpecWindowClose = document.getElementById("skillSpecWindowClose");
  const skillSpecWindowHandle = document.getElementById("skillSpecWindowHandle");
  const skillSpecWindowTitle = document.getElementById("skillSpecWindowTitle");
  const skillSpecCancelBtn = document.getElementById("skillSpecCancelBtn");
  const skillSpecForm = document.getElementById("skillSpecForm");
  const skillSpecInput = document.getElementById("id_specification");
  const skillSpecTriggers = Array.from(document.querySelectorAll("[data-skill-spec-trigger]"));
  if (
    !skillSpecWindow
    || !skillSpecWindowClose
    || !skillSpecWindowHandle
    || !skillSpecWindowTitle
    || !skillSpecForm
    || !skillSpecInput
  ) {
    return;
  }

  const controller = createFloatingWindowController({
    windowEl: skillSpecWindow,
    closeButton: skillSpecWindowClose,
    handle: skillSpecWindowHandle,
    startTop: 168,
    startRightInset: 212,
    storageKey: "charsheet.skillSpecWindow",
    allowPersistedOpen: false,
  });
  if (!controller) {
    return;
  }

  skillSpecTriggers.forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const skillName = trigger.dataset.skillName || "Fertigkeit";
      skillSpecWindowTitle.textContent = `${skillName} bearbeiten`;
      skillSpecForm.action = trigger.dataset.action || "";
      skillSpecInput.value = trigger.dataset.specification || "";
      controller.open();
      window.setTimeout(() => {
        skillSpecInput.focus();
        skillSpecInput.select();
      }, 0);
    });
  });

  skillSpecCancelBtn?.addEventListener("click", () => {
    controller.close();
  });
  skillSpecForm.addEventListener("submit", () => {
    controller.close();
  });
}
