import { applySheetPartials } from "./partial_updates.js";

export function initItemTransferWindow() {
  if (document.body?.dataset.itemTransferWindowInitialized === "1") return;
  const windowElement = document.querySelector("[data-item-transfer-window]");
  const backdrop = document.querySelector("[data-item-transfer-window-backdrop]");
  const frame = document.querySelector("[data-item-transfer-window-frame]");
  const handle = windowElement?.querySelector("[data-item-transfer-window-handle]");
  if (!windowElement || !backdrop || !frame || !handle) return;
  document.body.dataset.itemTransferWindowInitialized = "1";

  let dragPointerId = null;
  let dragOffsetX = 0;
  let dragOffsetY = 0;

  const place = (left, top) => {
    const rect = windowElement.getBoundingClientRect();
    const margin = 8;
    const maxLeft = Math.max(margin, window.innerWidth - rect.width - margin);
    const maxTop = Math.max(margin, window.innerHeight - rect.height - margin);
    windowElement.style.left = `${Math.min(Math.max(left, margin), maxLeft)}px`;
    windowElement.style.top = `${Math.min(Math.max(top, margin), maxTop)}px`;
    windowElement.style.transform = "none";
  };

  const resetPosition = () => {
    windowElement.style.removeProperty("left");
    windowElement.style.removeProperty("top");
    windowElement.style.removeProperty("transform");
  };

  const close = () => {
    windowElement.hidden = true;
    backdrop.hidden = true;
    frame.src = "about:blank";
    windowElement.classList.remove("is-dragging");
    dragPointerId = null;
  };
  const open = (url) => {
    frame.src = url;
    resetPosition();
    backdrop.hidden = false;
    windowElement.hidden = false;
    windowElement.querySelector("[data-close-item-transfer-window]")?.focus();
  };

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-open-item-transfer-window]");
    if (trigger) {
      event.preventDefault();
      open(trigger.dataset.transferUrl || "");
    }
    if (event.target.closest("[data-close-item-transfer-window]")) close();
  });

  handle.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || event.target.closest("button")) return;
    const rect = windowElement.getBoundingClientRect();
    dragPointerId = event.pointerId;
    dragOffsetX = event.clientX - rect.left;
    dragOffsetY = event.clientY - rect.top;
    place(rect.left, rect.top);
    handle.setPointerCapture(event.pointerId);
    windowElement.classList.add("is-dragging");
    event.preventDefault();
  });
  handle.addEventListener("pointermove", (event) => {
    if (dragPointerId !== event.pointerId) return;
    place(event.clientX - dragOffsetX, event.clientY - dragOffsetY);
  });
  const stopDragging = (event) => {
    if (dragPointerId !== event.pointerId) return;
    windowElement.classList.remove("is-dragging");
    try { handle.releasePointerCapture(event.pointerId); } catch (_error) { /* no-op */ }
    dragPointerId = null;
  };
  handle.addEventListener("pointerup", stopDragging);
  handle.addEventListener("pointercancel", stopDragging);
  window.addEventListener("resize", () => {
    if (windowElement.hidden || !windowElement.style.left) return;
    const rect = windowElement.getBoundingClientRect();
    place(rect.left, rect.top);
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !windowElement.hidden) close();
  });
  window.addEventListener("message", (event) => {
    if (
      event.origin !== window.location.origin
      || event.source !== frame.contentWindow
      || event.data?.type !== "codex:item-transfer-accepted"
    ) {
      return;
    }
    applySheetPartials(event.data.payload);
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initItemTransferWindow, { once: true });
} else {
  initItemTransferWindow();
}
