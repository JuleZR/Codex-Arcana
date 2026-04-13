import { clamp, loadJsonStorage, saveJsonStorage } from "./utils.js";

export function placeWindow(windowEl, left, top) {
  const rect = windowEl.getBoundingClientRect();
  const maxLeft = Math.max(12, window.innerWidth - rect.width - 12);
  const maxTop = Math.max(12, window.innerHeight - rect.height - 12);
  windowEl.style.left = `${clamp(left, 12, maxLeft)}px`;
  windowEl.style.top = `${clamp(top, 12, maxTop)}px`;
}

export function createFloatingWindowController({
  trigger = null,
  windowEl,
  closeButton,
  handle,
  startTop = 120,
  storageKey = "",
  allowPersistedOpen = true,
  startRightInset = 176,
}) {
  if (!windowEl || !closeButton || !handle) {
    return null;
  }

  const existingController = windowEl.__floatingWindowController;
  if (existingController) {
    if (trigger instanceof HTMLElement && !existingController.boundTriggers.has(trigger)) {
      trigger.addEventListener("click", existingController.open);
      existingController.boundTriggers.add(trigger);
    }
    return existingController;
  }

  const readWindowState = () => {
    const left = Number.parseFloat(windowEl.style.left || "");
    const top = Number.parseFloat(windowEl.style.top || "");
    return {
      isOpen: windowEl.classList.contains("is-open"),
      left: Number.isFinite(left) ? left : null,
      top: Number.isFinite(top) ? top : null,
    };
  };

  const loadState = () => (storageKey ? loadJsonStorage(storageKey, null) : null);
  const saveState = () => {
    if (!storageKey) {
      return;
    }
    saveJsonStorage(storageKey, readWindowState());
  };

  const open = () => {
    windowEl.classList.add("is-open");
    windowEl.setAttribute("aria-hidden", "false");
    const rect = windowEl.getBoundingClientRect();
    const saved = loadState();
    if (saved && Number.isFinite(saved.left) && Number.isFinite(saved.top)) {
      placeWindow(windowEl, saved.left, saved.top);
    } else {
      const startLeft = window.innerWidth - rect.width - startRightInset;
      placeWindow(windowEl, startLeft, startTop);
    }
    saveState();
  };

  const close = () => {
    windowEl.classList.remove("is-open");
    windowEl.setAttribute("aria-hidden", "true");
    saveState();
  };

  const persistedState = loadState();
  if (persistedState && Number.isFinite(persistedState.left) && Number.isFinite(persistedState.top)) {
    placeWindow(windowEl, persistedState.left, persistedState.top);
  }
  if (allowPersistedOpen && persistedState?.isOpen) {
    windowEl.classList.add("is-open");
    windowEl.setAttribute("aria-hidden", "false");
  }

  if (trigger instanceof HTMLElement) {
    trigger.addEventListener("click", open);
  }

  closeButton.addEventListener("click", close);
  closeButton.addEventListener("pointerdown", (event) => {
    event.stopPropagation();
  });

  let dragPointerId = null;
  let dragOffsetX = 0;
  let dragOffsetY = 0;

  handle.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) {
      return;
    }
    const rect = windowEl.getBoundingClientRect();
    dragPointerId = event.pointerId;
    dragOffsetX = event.clientX - rect.left;
    dragOffsetY = event.clientY - rect.top;
    handle.setPointerCapture(event.pointerId);
    windowEl.classList.add("is-dragging");
  });

  handle.addEventListener("pointermove", (event) => {
    if (dragPointerId !== event.pointerId) {
      return;
    }
    placeWindow(windowEl, event.clientX - dragOffsetX, event.clientY - dragOffsetY);
    saveState();
  });

  const stopDragging = (event) => {
    if (dragPointerId !== event.pointerId) {
      return;
    }
    windowEl.classList.remove("is-dragging");
    try {
      handle.releasePointerCapture(event.pointerId);
    } catch (_error) {
      // no-op
    }
    dragPointerId = null;
    saveState();
  };

  handle.addEventListener("pointerup", stopDragging);
  handle.addEventListener("pointercancel", stopDragging);

  const controller = {
    boundTriggers: new Set(trigger instanceof HTMLElement ? [trigger] : []),
    close,
    open,
    saveState,
    windowEl,
  };
  windowEl.__floatingWindowController = controller;
  return controller;
}

export function initStandardFloatingWindows() {
  const controllers = {
    shop: createFloatingWindowController({
      trigger: document.getElementById("shopScaleTrigger"),
      windowEl: document.getElementById("shopWindow"),
      closeButton: document.getElementById("shopWindowClose"),
      handle: document.getElementById("shopWindowHandle"),
      startTop: 92,
      storageKey: "charsheet.shopWindow",
    }),
    shopItem: createFloatingWindowController({
      trigger: document.getElementById("shopAddItemBtn"),
      windowEl: document.getElementById("shopItemWindow"),
      closeButton: document.getElementById("shopItemWindowClose"),
      handle: document.getElementById("shopItemWindowHandle"),
      startTop: 128,
      storageKey: "charsheet.shopItemWindow",
    }),
    learn: createFloatingWindowController({
      trigger: document.getElementById("learnMenuTrigger"),
      windowEl: document.getElementById("learnWindow"),
      closeButton: document.getElementById("learnWindowClose"),
      handle: document.getElementById("learnWindowHandle"),
      startTop: 138,
      storageKey: "charsheet.learnWindow",
    }),
    diary: createFloatingWindowController({
      trigger: document.getElementById("diaryTrigger"),
      windowEl: document.getElementById("diaryWindow"),
      closeButton: document.getElementById("diaryWindowClose"),
      handle: document.getElementById("diaryWindowHandle"),
      startTop: 86,
      storageKey: "charsheet.diaryWindow",
    }),
    charInfo: createFloatingWindowController({
      trigger: document.getElementById("charInfoEditTrigger"),
      windowEl: document.getElementById("charInfoWindow"),
      closeButton: document.getElementById("charInfoWindowClose"),
      handle: document.getElementById("charInfoWindowHandle"),
      startTop: 132,
      storageKey: "charsheet.charInfoWindow",
    }),
    learnChoice: createFloatingWindowController({
      windowEl: document.getElementById("learnChoiceWindow"),
      closeButton: document.getElementById("learnChoiceWindowClose"),
      handle: document.getElementById("learnChoiceWindowHandle"),
      startTop: 164,
      storageKey: "charsheet.learnChoiceWindow",
      allowPersistedOpen: false,
      startRightInset: 222,
    }),
    inventoryDeleteWarning: createFloatingWindowController({
      windowEl: document.getElementById("inventoryDeleteWarningWindow"),
      closeButton: document.getElementById("inventoryDeleteWarningWindowClose"),
      handle: document.getElementById("inventoryDeleteWarningWindowHandle"),
      startTop: 188,
      storageKey: "charsheet.inventoryDeleteWarningWindow",
      allowPersistedOpen: false,
      startRightInset: 246,
    }),
    runeRetrofit: createFloatingWindowController({
      windowEl: document.getElementById("runeRetrofitWindow"),
      closeButton: document.getElementById("runeRetrofitWindowClose"),
      handle: document.getElementById("runeRetrofitWindowHandle"),
      startTop: 116,
      storageKey: "charsheet.runeRetrofitWindow",
      allowPersistedOpen: false,
      startRightInset: 214,
    }),
  };

  if (document.getElementById("learnWindow")?.getAttribute("data-force-close") === "1") {
    controllers.learn?.close();
  }

  document.getElementById("shopItemCancelBtn")?.addEventListener("click", () => {
    controllers.shopItem?.close();
  });
  document.getElementById("charInfoCancelBtn")?.addEventListener("click", () => {
    controllers.charInfo?.close();
  });
  document.getElementById("charInfoForm")?.addEventListener("submit", () => {
    controllers.charInfo?.close();
  });
  document.getElementById("inventoryDeleteWarningOkBtn")?.addEventListener("click", () => {
    controllers.inventoryDeleteWarning?.close();
  });

  return controllers;
}
