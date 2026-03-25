export function initInventoryMenu() {
  const menus = Array.from(document.querySelectorAll(".inv_menu"));
  if (!menus.length) {
    return;
  }

  const closeMenu = (menu) => {
    const trigger = menu.querySelector(".inv_menu_trigger");
    const panel = menu.querySelector(".inv_menu_panel");
    if (!(trigger instanceof HTMLButtonElement) || !(panel instanceof HTMLElement)) {
      return;
    }
    panel.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
  };

  const openMenu = (menu) => {
    menus.forEach((other) => {
      if (other !== menu) {
        closeMenu(other);
      }
    });
    const trigger = menu.querySelector(".inv_menu_trigger");
    const panel = menu.querySelector(".inv_menu_panel");
    if (!(trigger instanceof HTMLButtonElement) || !(panel instanceof HTMLElement)) {
      return;
    }
    panel.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
  };

  menus.forEach((menu) => {
    const trigger = menu.querySelector(".inv_menu_trigger");
    const panel = menu.querySelector(".inv_menu_panel");
    if (!(trigger instanceof HTMLButtonElement) || !(panel instanceof HTMLElement)) {
      return;
    }

    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (panel.hidden) {
        openMenu(menu);
      } else {
        closeMenu(menu);
      }
    });

    panel.addEventListener("click", (event) => {
      event.stopPropagation();
    });
  });

  document.addEventListener("click", () => {
    menus.forEach(closeMenu);
  });

  Array.from(document.querySelectorAll("[data-require-shift-delete]"))
    .filter((button) => button instanceof HTMLButtonElement)
    .forEach((button) => {
      button.addEventListener("click", (event) => {
        if (event.shiftKey) {
          return;
        }
        event.preventDefault();
        window.alert("Zum Entfernen bitte Shift gedrueckt halten und erneut klicken.");
      });
    });
}
