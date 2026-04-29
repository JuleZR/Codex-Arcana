function syncArmorScrollIndicator(scrollArea) {
  if (!(scrollArea instanceof HTMLElement)) {
    return;
  }
  const panel = scrollArea.closest("#sheetArmorPanel");
  if (!(panel instanceof HTMLElement)) {
    return;
  }
  const indicator = panel.querySelector("[data-armor-scroll-indicator]");
  if (!(indicator instanceof HTMLElement)) {
    return;
  }

  const hasOverflow = scrollArea.scrollHeight - scrollArea.clientHeight > 2;
  const hasMoreBelow = scrollArea.scrollTop + scrollArea.clientHeight < scrollArea.scrollHeight - 2;
  indicator.hidden = !(hasOverflow && hasMoreBelow);
}

function syncAllArmorScrollIndicators() {
  document.querySelectorAll("[data-armor-scroll]").forEach((scrollArea) => {
    syncArmorScrollIndicator(scrollArea);
  });
}

export function initArmorPanel() {
  if (document.body?.dataset.armorPanelResizeBound !== "1") {
    window.addEventListener("resize", () => {
      syncAllArmorScrollIndicators();
    });
    document.body.dataset.armorPanelResizeBound = "1";
  }

  document.querySelectorAll("[data-armor-scroll]").forEach((scrollArea) => {
    if (!(scrollArea instanceof HTMLElement)) {
      return;
    }
    if (scrollArea.dataset.armorScrollBound !== "1") {
      scrollArea.addEventListener("scroll", () => {
        syncArmorScrollIndicator(scrollArea);
      });
      scrollArea.dataset.armorScrollBound = "1";
    }
    window.requestAnimationFrame(() => {
      syncArmorScrollIndicator(scrollArea);
    });
  });
}
