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

function bindEquippedTileHolo(tile) {
  if (!(tile instanceof HTMLElement) || !tile.classList.contains("equipped_item_tile--magic")) {
    return;
  }
  if (tile.dataset.equippedTileHoloBound === "1") {
    return;
  }
  tile.dataset.equippedTileHoloBound = "1";

  const syncHoloPosition = (event) => {
    const rect = tile.getBoundingClientRect();
    const width = Math.max(1, rect.width);
    const height = Math.max(1, rect.height);
    const left = Math.min(Math.max(0, event.clientX - rect.left), width);
    const top = Math.min(Math.max(0, event.clientY - rect.top), height);
    const xPercent = Math.abs(Math.floor((100 / width) * left) - 100);
    const yPercent = Math.abs(Math.floor((100 / height) * top) - 100);

    tile.classList.add("active");
    tile.style.setProperty("--card-holo-bg-x", `${xPercent}%`);
    tile.style.setProperty("--card-holo-bg-y", `${yPercent}%`);
  };

  tile.addEventListener("mousemove", syncHoloPosition);
  tile.addEventListener("pointermove", syncHoloPosition);
  tile.addEventListener("mouseleave", () => {
    tile.classList.remove("active");
  });
  tile.addEventListener("pointerleave", () => {
    tile.classList.remove("active");
  });
}

export function initArmorPanel() {
  document.querySelectorAll("[data-armor-scroll]").forEach((scrollArea) => {
    if (!(scrollArea instanceof HTMLElement)) {
      return;
    }
    if (scrollArea.dataset.armorScrollBound !== "1") {
      scrollArea.addEventListener("wheel", (event) => {
        if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) {
          return;
        }
        const maxScrollLeft = scrollArea.scrollWidth - scrollArea.clientWidth;
        if (maxScrollLeft <= 2) {
          return;
        }
        const nextScrollLeft = Math.min(Math.max(0, scrollArea.scrollLeft + event.deltaY), maxScrollLeft);
        if (nextScrollLeft === scrollArea.scrollLeft) {
          return;
        }
        scrollArea.scrollLeft = nextScrollLeft;
        event.preventDefault();
      }, { passive: false });
      scrollArea.dataset.armorScrollBound = "1";
    }
  });

  document.querySelectorAll("#sheetArmorPanel .equipped_item_tile").forEach((tile) => {
    if (!(tile instanceof HTMLElement) || tile.dataset.equippedTileBound === "1") {
      return;
    }
    tile.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      event.preventDefault();
      tile.click();
    });
    bindEquippedTileHolo(tile);
    tile.dataset.equippedTileBound = "1";
  });

  initBodyArmorMap();
}
