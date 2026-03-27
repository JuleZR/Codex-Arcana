export function initInventoryMenu() {
  if (document.body.dataset.inventoryMenuBound === "1") {
    return;
  }
  document.body.dataset.inventoryMenuBound = "1";

  const closeMenu = (menu) => {
    const trigger = menu.querySelector(".inv_menu_trigger");
    const panel = menu.querySelector(".inv_menu_panel");
    if (!(trigger instanceof HTMLButtonElement) || !(panel instanceof HTMLElement)) {
      return;
    }
    panel.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
  };

  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const trigger = target?.closest(".inv_menu_trigger");
    const menu = trigger?.closest(".inv_menu");

    document.querySelectorAll(".inv_menu").forEach((entry) => {
      if (entry !== menu) {
        closeMenu(entry);
      }
    });

    if (trigger instanceof HTMLButtonElement && menu instanceof HTMLElement) {
      event.preventDefault();
      event.stopPropagation();
      const panel = menu.querySelector(".inv_menu_panel");
      if (panel instanceof HTMLElement && panel.hidden) {
        panel.hidden = false;
        trigger.setAttribute("aria-expanded", "true");
      } else {
        closeMenu(menu);
      }
      return;
    }

    if (target?.closest(".inv_menu_panel")) {
      return;
    }

    document.querySelectorAll(".inv_menu").forEach(closeMenu);
  });

  document.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-require-shift-delete]") : null;
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    if (event.shiftKey) {
      return;
    }
    event.preventDefault();
    window.alert("Zum Entfernen bitte Shift gedrueckt halten und erneut klicken.");
  });
}
