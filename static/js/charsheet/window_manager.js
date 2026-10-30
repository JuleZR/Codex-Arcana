import { clamp, loadJsonStorage, saveJsonStorage } from "./utils.js";

export function placeWindow(windowEl, left, top) {
  const rect = windowEl.getBoundingClientRect();
  const maxLeft = Math.max(12, window.innerWidth - rect.width - 12);
  const maxTop = Math.max(12, window.innerHeight - rect.height - 12);
  windowEl.style.left = `${clamp(left, 12, maxLeft)}px`;
  windowEl.style.top = `${clamp(top, 12, maxTop)}px`;
}

function bindWindowDragging(windowEl, handle, saveState, canDrag = () => true) {
  let dragPointerId = null;
  let dragOffsetX = 0;
  let dragOffsetY = 0;

  handle.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || !canDrag()
        || event.target?.closest?.("button, input, select, textarea, a")) {
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
    if (windowEl.id === "battleCalculatorWindow" && window.matchMedia("(max-width: 900px)").matches) return;
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

  if (windowEl.id === "battleCalculatorWindow") {
    window.matchMedia("(max-width: 900px)").addEventListener("change", (event) => {
      if (event.matches) close();
    });
  }

  const persistedState = loadState();
  if (persistedState && Number.isFinite(persistedState.left) && Number.isFinite(persistedState.top)) {
    placeWindow(windowEl, persistedState.left, persistedState.top);
  }
  if (allowPersistedOpen && persistedState?.isOpen
      && !(windowEl.id === "battleCalculatorWindow" && window.matchMedia("(max-width: 900px)").matches)) {
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

  bindWindowDragging(windowEl, handle, saveState);

  const controller = {
    boundTriggers: new Set(trigger instanceof HTMLElement ? [trigger] : []),
    close,
    destroy: () => {
      controller.boundTriggers.forEach((boundTrigger) => {
        boundTrigger.removeEventListener("click", open);
      });
      controller.boundTriggers.clear();
      delete windowEl.__floatingWindowController;
    },
    open,
    saveState,
    windowEl,
  };
  windowEl.__floatingWindowController = controller;
  return controller;
}

export function createOverlayWindowController({ trigger, windowEl, closeButton, handle, overlayEl, storageKey }) {
  if (!windowEl || !closeButton || !overlayEl) return null;
  const existingController = windowEl.__floatingWindowController;
  if (existingController) {
    if (trigger instanceof HTMLElement && !existingController.boundTriggers.has(trigger)) {
      trigger.addEventListener("click", existingController.open);
      existingController.boundTriggers.add(trigger);
    }
    return existingController;
  }
  let previousFocus = null;
  const desktop = window.matchMedia("(min-width: 761px)");
  const positionWindow = () => {
    if (!desktop.matches) {
      windowEl.style.position = "";
      windowEl.style.left = "";
      windowEl.style.top = "";
      return;
    }
    windowEl.style.position = "fixed";
    const rect = windowEl.getBoundingClientRect();
    const left = Number.parseFloat(windowEl.style.left);
    const top = Number.parseFloat(windowEl.style.top);
    placeWindow(
      windowEl,
      Number.isFinite(left) ? left : (window.innerWidth - rect.width) / 2,
      Number.isFinite(top) ? top : (window.innerHeight - rect.height) / 2,
    );
  };
  const saveState = () => saveJsonStorage(storageKey, {
    isOpen: !overlayEl.hidden, left: null, top: null,
  });
  const open = () => {
    if (!overlayEl.hidden) return;
    previousFocus = document.activeElement;
    overlayEl.hidden = false;
    windowEl.classList.add("is-open");
    windowEl.setAttribute("aria-hidden", "false");
    document.body.classList.add("market-modal-open");
    positionWindow();
    windowEl.querySelector("[aria-selected='true']")?.focus();
    saveState();
  };
  const close = () => {
    const editor = document.getElementById("shopItemWindow");
    if (editor?.classList.contains("is-open")) editor.__floatingWindowController?.close();
    overlayEl.hidden = true;
    windowEl.classList.remove("is-open");
    windowEl.setAttribute("aria-hidden", "true");
    document.body.classList.remove("market-modal-open");
    previousFocus?.focus();
    saveState();
  };
  const backdropClick = (event) => { if (event.target === overlayEl) close(); };
  const keydown = (event) => {
    if (overlayEl.hidden) return;
    const editor = document.getElementById("shopItemWindow");
    const editorOpen = editor?.classList.contains("is-open");
    if (event.key === "Escape") {
      event.preventDefault();
      if (editorOpen) editor.__floatingWindowController?.close();
      else close();
      return;
    }
    if (event.key !== "Tab") return;
    const focusRoot = editorOpen ? editor : windowEl;
    const controls = Array.from(focusRoot.querySelectorAll(
      'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex="0"]',
    )).filter((control) => control.getClientRects().length
      && control.getAttribute("tabindex") !== "-1" && !control.closest("[hidden]"));
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (!first) { event.preventDefault(); return; }
    if (event.shiftKey && (document.activeElement === first || !focusRoot.contains(document.activeElement))) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && (document.activeElement === last || !focusRoot.contains(document.activeElement))) {
      event.preventDefault(); first.focus();
    }
  };
  trigger?.addEventListener("click", open);
  closeButton.addEventListener("click", close);
  overlayEl.addEventListener("click", backdropClick);
  document.addEventListener("keydown", keydown);
  if (handle) bindWindowDragging(windowEl, handle, saveState, () => desktop.matches);
  window.addEventListener("resize", positionWindow);
  const controller = {
    boundTriggers: new Set(trigger instanceof HTMLElement ? [trigger] : []),
    windowEl, open, close, saveState,
    destroy() {
      controller.boundTriggers.forEach((boundTrigger) => {
        boundTrigger.removeEventListener("click", open);
      });
      controller.boundTriggers.clear();
      closeButton.removeEventListener("click", close);
      overlayEl.removeEventListener("click", backdropClick);
      document.removeEventListener("keydown", keydown);
      window.removeEventListener("resize", positionWindow);
      document.body.classList.remove("market-modal-open");
      delete windowEl.__floatingWindowController;
    },
  };
  windowEl.__floatingWindowController = controller;
  if (loadJsonStorage(storageKey, null)?.isOpen) open();
  return controller;
}

export function initStandardFloatingWindows() {
  const controllers = {
    shop: createOverlayWindowController({
      trigger: document.getElementById("shopScaleTrigger"),
      windowEl: document.getElementById("shopWindow"),
      closeButton: document.getElementById("shopWindowClose"),
      handle: document.getElementById("shopWindowHandle"),
      overlayEl: document.getElementById("shopOverlay"),
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
    battleCalculator: createFloatingWindowController({
      trigger: document.getElementById("battleCalculatorTrigger"),
      windowEl: document.getElementById("battleCalculatorWindow"),
      closeButton: document.getElementById("battleCalculatorWindowClose"),
      handle: document.getElementById("battleCalculatorWindowHandle"),
      startTop: 104,
      storageKey: "charsheet.battleCalculatorWindow",
      startRightInset: 196,
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
    itemTransfer: createFloatingWindowController({
      windowEl: document.getElementById("itemTransferDialog"),
      closeButton: document.getElementById("itemTransferDialogClose"),
      handle: document.getElementById("itemTransferDialogHandle"),
      startTop: 142,
      storageKey: "charsheet.itemTransferDialog",
      allowPersistedOpen: false,
      startRightInset: 230,
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
  document.querySelectorAll("#itemTransferDialog [data-close-item-transfer]").forEach((button) => {
    if (button.id !== "itemTransferDialogClose") {
      button.addEventListener("click", () => controllers.itemTransfer?.close());
    }
  });

  return controllers;
}
