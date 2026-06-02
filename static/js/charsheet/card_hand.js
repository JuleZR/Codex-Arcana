export function initCardHand() {
  const hand = document.querySelector("[data-card-hand]");
  if (!(hand instanceof HTMLElement) || hand.dataset.cardHandBound === "1") {
    return;
  }
  hand.dataset.cardHandBound = "1";

  const toggle = hand.querySelector("[data-card-hand-toggle]");
  const tray = hand.querySelector("[data-card-hand-tray]");
  const openCardButton = hand.querySelector("[data-card-hand-open-card]");
  const floating = hand.querySelector("[data-card-hand-floating]");
  const dragHandles = Array.from(hand.querySelectorAll("[data-card-hand-drag-handle]"));
  const dragStartThreshold = 8;
  const storageKey = hand.getAttribute("data-card-hand-storage-key") || "";

  const loadTableState = () => {
    if (!storageKey) {
      return null;
    }
    try {
      const raw = window.localStorage.getItem(storageKey);
      const parsed = raw ? JSON.parse(raw) : null;
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch (_error) {
      return null;
    }
  };

  const saveTableState = () => {
    if (!storageKey || !(floating instanceof HTMLElement) || floating.hidden) {
      return;
    }
    const rect = floating.getBoundingClientRect();
    try {
      window.localStorage.setItem(storageKey, JSON.stringify({
        isOnTable: true,
        left: Math.round(rect.left),
        top: Math.round(rect.top),
      }));
    } catch (_error) {
      // Ignore storage failures; the card still works for the current session.
    }
  };

  const clearTableState = () => {
    if (!storageKey) {
      return;
    }
    try {
      window.localStorage.removeItem(storageKey);
    } catch (_error) {
      // no-op
    }
  };

  const setHandOpen = (isOpen) => {
    hand.classList.toggle("is-open", isOpen);
    if (tray instanceof HTMLElement) {
      tray.hidden = !isOpen;
    }
    if (toggle instanceof HTMLElement) {
      toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    }
  };

  const isPointInsideHand = (clientX, clientY) => {
    const handRect = hand.getBoundingClientRect();
    const dropLeft = Math.max(0, (window.innerWidth - Math.min(360, window.innerWidth - 24)) / 2);
    const dropRight = window.innerWidth - dropLeft;
    const dropTop = Math.max(0, handRect.bottom - 118);
    const dropBottom = handRect.bottom + 8;
    return (
      clientX >= dropLeft
      && clientX <= dropRight
      && clientY >= dropTop
      && clientY <= dropBottom
    );
  };

  const isFloatingOverHand = () => {
    if (!(floating instanceof HTMLElement)) {
      return false;
    }
    const rect = floating.getBoundingClientRect();
    const probeX = rect.left + rect.width / 2;
    const probeY = rect.bottom - Math.min(84, rect.height * 0.18);
    return isPointInsideHand(probeX, probeY);
  };

  const syncDropTarget = (clientX, clientY) => {
    const isDropTarget = isPointInsideHand(clientX, clientY) || isFloatingOverHand();
    hand.classList.toggle("is-drop-target", isDropTarget);
    return isDropTarget;
  };

  const clampFloating = () => {
    if (!(floating instanceof HTMLElement)) {
      return;
    }
    const rect = floating.getBoundingClientRect();
    const padding = 10;
    let left = rect.left;
    let top = rect.top;
    left = Math.min(Math.max(padding, left), Math.max(padding, window.innerWidth - rect.width - padding));
    top = Math.min(Math.max(padding, top), Math.max(padding, window.innerHeight - rect.height - padding));
    floating.style.left = `${left}px`;
    floating.style.top = `${top}px`;
    floating.style.transform = "none";
  };

  const openFloating = ({ clientX = null, clientY = null } = {}) => {
    if (!(floating instanceof HTMLElement)) {
      return;
    }
    floating.hidden = false;
    if (Number.isFinite(clientX) && Number.isFinite(clientY)) {
      floating.style.left = `${clientX}px`;
      floating.style.top = `${clientY}px`;
      floating.style.transform = "translate(-50%, -18px)";
      floating.dataset.positioned = "1";
      requestAnimationFrame(clampFloating);
      return;
    }
    if (!floating.dataset.positioned) {
      floating.dataset.positioned = "1";
      requestAnimationFrame(clampFloating);
    }
  };

  const closeFloating = () => {
    if (floating instanceof HTMLElement) {
      floating.hidden = true;
      floating.classList.remove("is-dragging");
      hand.classList.remove("is-drop-target");
      clearTableState();
    }
  };

  const moveFloatingTo = (clientX, clientY, offsetX, offsetY) => {
    if (!(floating instanceof HTMLElement)) {
      return;
    }
    const currentRect = floating.getBoundingClientRect();
    const padding = 10;
    const maxLeft = Math.max(padding, window.innerWidth - currentRect.width - padding);
    const maxTop = Math.max(padding, window.innerHeight - currentRect.height - padding);
    const left = Math.min(Math.max(padding, clientX - offsetX), maxLeft);
    const top = Math.min(Math.max(padding, clientY - offsetY), maxTop);
    floating.style.left = `${left}px`;
    floating.style.top = `${top}px`;
    floating.style.transform = "none";
  };

  const startFloatingDrag = (event, { fromMiniCard = false } = {}) => {
    if (!(floating instanceof HTMLElement)) {
      return;
    }

    if (fromMiniCard) {
      openFloating({ clientX: event.clientX, clientY: event.clientY });
      setHandOpen(false);
    } else if (floating.hidden) {
      openFloating();
    }
    const rect = floating.getBoundingClientRect();
    const offsetX = fromMiniCard ? rect.width / 2 : event.clientX - rect.left;
    const offsetY = fromMiniCard ? 18 : event.clientY - rect.top;

    floating.classList.add("is-dragging");
    moveFloatingTo(event.clientX, event.clientY, offsetX, offsetY);

    const moveFloating = (moveEvent) => {
      moveFloatingTo(moveEvent.clientX, moveEvent.clientY, offsetX, offsetY);
      syncDropTarget(moveEvent.clientX, moveEvent.clientY);
    };

    const finishFloatingDrag = (upEvent) => {
      document.removeEventListener("pointermove", moveFloating);
      document.removeEventListener("pointerup", finishFloatingDrag);
      document.removeEventListener("pointercancel", finishFloatingDrag);
      floating.classList.remove("is-dragging");
      const droppedIntoHand = syncDropTarget(upEvent.clientX, upEvent.clientY) || isFloatingOverHand();
      hand.classList.remove("is-drop-target");
      if (droppedIntoHand) {
        closeFloating();
      } else {
        saveTableState();
      }
    };

    document.addEventListener("pointermove", moveFloating);
    document.addEventListener("pointerup", finishFloatingDrag);
    document.addEventListener("pointercancel", finishFloatingDrag);
  };

  if (toggle instanceof HTMLElement) {
    toggle.addEventListener("click", () => {
      setHandOpen(!hand.classList.contains("is-open"));
    });
  }

  if (openCardButton instanceof HTMLElement) {
    openCardButton.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      const pointerId = event.pointerId;
      const startX = event.clientX;
      const startY = event.clientY;
      let isDragging = false;

      const handleMove = (moveEvent) => {
        if (moveEvent.pointerId !== pointerId) {
          return;
        }
        const distance = Math.hypot(moveEvent.clientX - startX, moveEvent.clientY - startY);
        if (!isDragging && distance >= dragStartThreshold) {
          isDragging = true;
          startFloatingDrag(moveEvent, { fromMiniCard: true });
        }
      };

      const handleUp = (upEvent) => {
        if (upEvent.pointerId !== pointerId) {
          return;
        }
        document.removeEventListener("pointermove", handleMove);
        document.removeEventListener("pointerup", handleUp);
        document.removeEventListener("pointercancel", handleUp);
        if (!isDragging) {
          openFloating();
          setHandOpen(false);
        }
      };

      document.addEventListener("pointermove", handleMove);
      document.addEventListener("pointerup", handleUp);
      document.addEventListener("pointercancel", handleUp);
    });
  }

  if (floating instanceof HTMLElement && dragHandles.length > 0) {
    dragHandles.forEach((dragHandle) => {
      dragHandle.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        setHandOpen(false);
        startFloatingDrag(event);
      });
    });
    window.addEventListener("resize", clampFloating);
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setHandOpen(false);
      closeFloating();
    }
  });

  const restoredState = loadTableState();
  if (
    restoredState?.isOnTable
    && Number.isFinite(restoredState.left)
    && Number.isFinite(restoredState.top)
    && floating instanceof HTMLElement
  ) {
    floating.hidden = false;
    floating.dataset.positioned = "1";
    floating.style.left = `${restoredState.left}px`;
    floating.style.top = `${restoredState.top}px`;
    floating.style.transform = "none";
    requestAnimationFrame(clampFloating);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initCardHand, { once: true });
} else {
  initCardHand();
}
