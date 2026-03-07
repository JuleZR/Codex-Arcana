document.addEventListener("DOMContentLoaded", () => {
  const targets = document.querySelectorAll(".tooltip_target[data-tooltip]");
  if (!targets.length) {
    return;
  }

  const tooltip = document.createElement("div");
  tooltip.className = "floating-tooltip";
  document.body.appendChild(tooltip);
  const SHOW_DELAY_MS = 1100;
  const HIDE_HOLD_MS = 380;

  let activeTarget = null;
  let pendingTarget = null;
  let showTimeoutId = null;
  let hideTimeoutId = null;

  function clearShowTimer() {
    if (showTimeoutId) {
      window.clearTimeout(showTimeoutId);
      showTimeoutId = null;
    }
  }

  function scheduleHide() {
    if (hideTimeoutId) {
      window.clearTimeout(hideTimeoutId);
    }
    hideTimeoutId = window.setTimeout(() => {
      tooltip.classList.remove("is-visible");
      activeTarget = null;
      pendingTarget = null;
      hideTimeoutId = null;
    }, HIDE_HOLD_MS);
  }

  function positionTooltip(target) {
    const gap = 10;
    const viewportPadding = 8;
    const panel = target.closest(".p2_panel");
    const panelRect = (panel || target).getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    const preferredSide = target.getAttribute("data-tooltip-side") || "left";

    let left = preferredSide === "right"
      ? panelRect.right + gap
      : panelRect.left - tooltipRect.width - gap;

    if (left < viewportPadding || left + tooltipRect.width > window.innerWidth - viewportPadding) {
      left = panelRect.right + gap;
    }
    if (left + tooltipRect.width > window.innerWidth - viewportPadding) {
      left = panelRect.left - tooltipRect.width - gap;
    }

    let top = targetRect.top + (targetRect.height / 2) - (tooltipRect.height / 2);
    const maxTop = window.innerHeight - tooltipRect.height - viewportPadding;
    if (top > maxTop) {
      top = maxTop;
    }

    tooltip.style.left = `${Math.max(viewportPadding, left)}px`;
    tooltip.style.top = `${Math.max(viewportPadding, top)}px`;
  }

  targets.forEach((target) => {
    target.addEventListener("mouseenter", () => {
      const text = target.getAttribute("data-tooltip") || "";
      if (!text.trim()) {
        return;
      }

      if (hideTimeoutId) {
        window.clearTimeout(hideTimeoutId);
        hideTimeoutId = null;
      }
      clearShowTimer();
      if (activeTarget && activeTarget !== target) {
        tooltip.classList.remove("is-visible");
        activeTarget = null;
      }

      pendingTarget = target;
      showTimeoutId = window.setTimeout(() => {
        if (pendingTarget !== target) {
          return;
        }
        tooltip.textContent = text;
        activeTarget = target;
        tooltip.classList.add("is-visible");
        positionTooltip(target);
        showTimeoutId = null;
      }, SHOW_DELAY_MS);
    });

    target.addEventListener("mouseleave", () => {
      if (pendingTarget === target) {
        pendingTarget = null;
      }
      clearShowTimer();
      scheduleHide();
    });
  });

  window.addEventListener(
    "scroll",
    () => {
      if (activeTarget) {
        positionTooltip(activeTarget);
      }
    },
    true,
  );

  window.addEventListener("resize", () => {
    if (activeTarget) {
      positionTooltip(activeTarget);
    }
  });

  document.addEventListener("mouseleave", () => {
    clearShowTimer();
    scheduleHide();
  });
});
