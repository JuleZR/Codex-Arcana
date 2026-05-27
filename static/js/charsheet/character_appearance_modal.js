import { createFloatingWindowController } from "./window_manager.js";

let listenersBound = false;

function hasMeaningfulAppearance(previewEl) {
  const value = (previewEl?.textContent || "").trim();
  return value !== "" && value !== "-";
}

function syncAppearanceTriggerState() {
  const trigger = document.getElementById("appearanceDetailTrigger");
  const preview = document.getElementById("appearanceDetailPreview");
  const windowEl = document.getElementById("appearanceDetailWindow");

  if (!trigger || !preview) {
    return;
  }

  const isInteractive =
    hasMeaningfulAppearance(preview) && preview.scrollWidth > preview.clientWidth + 1;
  trigger.disabled = !isInteractive;
  trigger.classList.toggle("is-interactive", isInteractive);
  trigger.title = isInteractive ? "Vollständiges Aussehen anzeigen" : "";
  if (!isInteractive) {
    windowEl?.__floatingWindowController?.close?.();
  }
}

export function initCharacterAppearanceModal() {
  const trigger = document.getElementById("appearanceDetailTrigger");
  const windowEl = document.getElementById("appearanceDetailWindow");
  const closeButton = document.getElementById("appearanceDetailWindowClose");
  const handle = document.getElementById("appearanceDetailWindowHandle");

  if (!trigger || !windowEl || !closeButton || !handle) {
    return null;
  }

  const controller = createFloatingWindowController({
    trigger,
    windowEl,
    closeButton,
    handle,
    startTop: 148,
    startRightInset: 208,
    storageKey: "charsheet.appearanceDetailWindow",
    allowPersistedOpen: false,
  });

  requestAnimationFrame(syncAppearanceTriggerState);

  if (!listenersBound) {
    listenersBound = true;
    window.addEventListener("resize", syncAppearanceTriggerState);
    document.addEventListener("charsheet:appearance-refresh", syncAppearanceTriggerState);
  }

  return controller;
}
