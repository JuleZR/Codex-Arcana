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

function setBodyZoneActive(map, zone, active) {
  if (!(map instanceof HTMLElement) || !zone) {
    return;
  }
  map.querySelectorAll("[data-body-zone]").forEach((entry) => {
    if (entry.getAttribute("data-body-zone") === zone) {
      entry.classList.toggle("is-zone-active", active);
    }
  });
}

function initBodyArmorMap() {
  document.querySelectorAll(".body_callout_map").forEach((map) => {
    if (!(map instanceof HTMLElement) || map.dataset.bodyArmorMapBound === "1") {
      return;
    }
    map.addEventListener("pointerover", (event) => {
      const target = event.target instanceof Element ? event.target.closest("[data-body-zone]") : null;
      if (!(target instanceof Element)) {
        return;
      }
      setBodyZoneActive(map, target.getAttribute("data-body-zone"), true);
    });
    map.addEventListener("pointerout", (event) => {
      const target = event.target instanceof Element ? event.target.closest("[data-body-zone]") : null;
      if (!(target instanceof Element)) {
        return;
      }
      const nextTarget = event.relatedTarget instanceof Element ? event.relatedTarget.closest("[data-body-zone]") : null;
      if (nextTarget?.getAttribute("data-body-zone") === target.getAttribute("data-body-zone")) {
        return;
      }
      setBodyZoneActive(map, target.getAttribute("data-body-zone"), false);
    });
    map.dataset.bodyArmorMapBound = "1";
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

  initBodyArmorMap();
}
