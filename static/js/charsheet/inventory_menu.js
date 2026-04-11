function parseIdList(rawValue) {
  return String(rawValue || "")
    .split(",")
    .map((value) => Number.parseInt(value.trim(), 10))
    .filter((value) => Number.isInteger(value) && value > 0);
}

function centerWindow(windowEl) {
  if (!(windowEl instanceof HTMLElement)) {
    return;
  }
  const rect = windowEl.getBoundingClientRect();
  const left = Math.max(12, (window.innerWidth - rect.width) / 2);
  const top = Math.max(24, (window.innerHeight - rect.height) / 2);
  windowEl.style.left = `${left}px`;
  windowEl.style.top = `${top}px`;
}

function normalizeSearchValue(value) {
  return String(value || "").trim().toLowerCase();
}

function closeMenu(menu) {
  if (!(menu instanceof HTMLElement)) {
    return;
  }
  const trigger = menu.querySelector(".inv_menu_trigger");
  const panel = menu.querySelector(".inv_menu_panel");
  if (!(trigger instanceof HTMLButtonElement) || !(panel instanceof HTMLElement)) {
    return;
  }
  panel.hidden = true;
  trigger.setAttribute("aria-expanded", "false");
  menu.classList.remove("is-open");
  menu.closest(".inv_row")?.classList.remove("is-menu-open");
}

export function initInventoryMenu({ warningWindowController = null } = {}) {
  if (document.body.dataset.inventoryMenuBound === "1") {
    return;
  }
  document.body.dataset.inventoryMenuBound = "1";

  const runeWindow = document.getElementById("runeRetrofitWindow");
  const runeCloseButton = document.getElementById("runeRetrofitWindowClose");
  const runeCancelButton = document.getElementById("runeRetrofitCancelBtn");
  const runeForm = document.getElementById("runeRetrofitForm");
  const runeOptions = document.getElementById("runeRetrofitOptions");
  const runeItemName = document.getElementById("runeRetrofitItemName");
  const runeBaseInfo = document.getElementById("runeRetrofitBaseInfo");
  const runeSearchInput = document.getElementById("runeRetrofitSearch");
  const runeDropdown = document.getElementById("runeRetrofitDropdown");
  const runeDropdownTrigger = document.getElementById("runeRetrofitDropdownTrigger");
  const runeDropdownPanel = document.getElementById("runeRetrofitDropdownPanel");
  const runeSelectionCount = document.getElementById("runeRetrofitSelectionCount");

  let runeChoices = [];
  try {
    runeChoices = JSON.parse(
      document.getElementById("rune-retrofit-choices")?.textContent || "[]",
    );
  } catch (_error) {
    runeChoices = [];
  }

  let pendingRuneSubmit = false;

  const syncRuneSelectionCount = () => {
    if (!(runeSelectionCount instanceof HTMLElement) || !(runeOptions instanceof HTMLElement)) {
      return;
    }
    const selectedCount = runeOptions.querySelectorAll("input[name='runes']:checked").length;
    runeSelectionCount.textContent = String(selectedCount);
  };

  const toggleRuneDropdown = (forceOpen = null) => {
    if (!(runeDropdownPanel instanceof HTMLElement) || !(runeDropdownTrigger instanceof HTMLButtonElement)) {
      return;
    }
    const shouldOpen = forceOpen === null ? runeDropdownPanel.hidden : Boolean(forceOpen);
    runeDropdownPanel.hidden = !shouldOpen;
    runeDropdownTrigger.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
  };

  const openRuneWindow = () => {
    if (!(runeWindow instanceof HTMLElement)) {
      return;
    }
    runeWindow.classList.add("is-open");
    runeWindow.setAttribute("aria-hidden", "false");
    centerWindow(runeWindow);
    runeSearchInput?.focus();
  };

  const closeRuneWindow = () => {
    if (!(runeWindow instanceof HTMLElement)) {
      return;
    }
    runeWindow.classList.remove("is-open");
    runeWindow.setAttribute("aria-hidden", "true");
    pendingRuneSubmit = false;
    if (runeSearchInput instanceof HTMLInputElement) {
      runeSearchInput.value = "";
    }
    toggleRuneDropdown(false);
  };

  const filterRuneEntries = () => {
    const query = normalizeSearchValue(runeSearchInput?.value);
    runeOptions?.querySelectorAll(".rune_option").forEach((entry) => {
      if (!(entry instanceof HTMLElement)) {
        return;
      }
      const haystack = normalizeSearchValue(entry.dataset.runeSearch || "");
      entry.hidden = query ? !haystack.includes(query) : false;
    });
  };

  document.addEventListener("click", (event) => {
    const toggleBtn = event.target instanceof Element
      ? event.target.closest("[data-rune-toggle]")
      : null;
    if (toggleBtn instanceof HTMLButtonElement) {
      event.preventDefault();
      event.stopPropagation();
      const controlsId = toggleBtn.getAttribute("aria-controls");
      const list = controlsId
        ? document.getElementById(controlsId)
        : toggleBtn.closest(".inv_row")?.querySelector(".inv_rune_list");
      if (list instanceof HTMLElement) {
        const willOpen = list.hidden;
        list.hidden = !willOpen;
        toggleBtn.setAttribute("aria-expanded", willOpen ? "true" : "false");
        toggleBtn.classList.toggle("is-open", willOpen);
      }
      return;
    }
  });

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
        menu.classList.add("is-open");
        menu.closest(".inv_row")?.classList.add("is-menu-open");
      } else {
        closeMenu(menu);
      }
      return;
    }

    if (target?.closest(".inv_menu_panel")) {
      return;
    }

    if (
      runeDropdown instanceof HTMLElement &&
      !target?.closest("#runeRetrofitDropdown") &&
      runeWindow?.classList.contains("is-open")
    ) {
      toggleRuneDropdown(false);
    }

    document.querySelectorAll(".inv_menu").forEach((entry) => closeMenu(entry));
  });

  document.addEventListener("click", (event) => {
    const button = event.target instanceof Element
      ? event.target.closest("[data-require-shift-delete]")
      : null;
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    if (event.shiftKey) {
      warningWindowController?.close?.();
      return;
    }
    event.preventDefault();
    warningWindowController?.open?.();
  });

  document.addEventListener("click", (event) => {
    const button = event.target instanceof Element
      ? event.target.closest("[data-open-rune-window]")
      : null;
    if (
      !(button instanceof HTMLButtonElement) ||
      !(runeForm instanceof HTMLFormElement) ||
      !(runeOptions instanceof HTMLElement)
    ) {
      return;
    }

    const characterItemId = button.getAttribute("data-character-item-id") || "";
    const itemName = button.getAttribute("data-item-name") || "-";
    const baseRuneIds = new Set(parseIdList(button.getAttribute("data-base-rune-ids")));
    const extraRuneIds = new Set(parseIdList(button.getAttribute("data-extra-rune-ids")));
    const baseRuneNames = String(button.getAttribute("data-base-rune-names") || "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);

    runeForm.action = `/character-item/${characterItemId}/runes/update/`;
    runeOptions.innerHTML = "";
    if (runeSearchInput instanceof HTMLInputElement) {
      runeSearchInput.value = "";
    }
    if (runeItemName instanceof HTMLElement) {
      runeItemName.textContent = itemName;
    }
    if (runeBaseInfo instanceof HTMLElement) {
      runeBaseInfo.textContent = baseRuneNames.length
        ? `Basis-Runen: ${baseRuneNames.join(", ")}`
        : "Keine Basis-Runen vorhanden.";
    }

    let availableCount = 0;
    runeChoices.forEach((rune) => {
      if (baseRuneIds.has(Number(rune?.id))) {
        return;
      }
      availableCount += 1;

      const label = document.createElement("label");
      label.className = "shop_item_form_checklist_item rune_option";
      label.dataset.runeSearch = `${rune.name || ""} ${rune.description || ""}`;

      const input = document.createElement("input");
      input.type = "checkbox";
      input.name = "runes";
      input.value = String(rune.id);
      input.checked = extraRuneIds.has(Number(rune.id));
      input.addEventListener("change", syncRuneSelectionCount);

      const copy = document.createElement("span");
      copy.className = "rune_option_copy";

      const name = document.createElement("span");
      name.className = "rune_option_name";
      name.textContent = rune.name || "Unbenannte Rune";

      const body = document.createElement("span");
      body.className = "rune_option_body";
      body.textContent = rune.description || "Keine Beschreibung vorhanden.";

      copy.append(name, body);
      label.append(input, copy);
      runeOptions.append(label);
    });

    if (!availableCount) {
      const empty = document.createElement("p");
      empty.className = "shop_empty";
      empty.textContent = "Keine weiteren Runen zum Nachrüsten verfügbar.";
      runeOptions.append(empty);
    }

    syncRuneSelectionCount();
    filterRuneEntries();
    openRuneWindow();
    closeMenu(button.closest(".inv_menu"));
  });

  runeSearchInput?.addEventListener("input", filterRuneEntries);
  runeDropdownTrigger?.addEventListener("click", () => {
    toggleRuneDropdown();
  });
  runeCloseButton?.addEventListener("click", closeRuneWindow);
  runeCancelButton?.addEventListener("click", closeRuneWindow);

  runeForm?.addEventListener("submit", () => {
    pendingRuneSubmit = true;
  });

  document.addEventListener("charsheet:partials-applied", () => {
    if (pendingRuneSubmit) {
      closeRuneWindow();
    }
  });

  window.addEventListener("resize", () => {
    if (runeWindow?.classList.contains("is-open")) {
      centerWindow(runeWindow);
    }
  });
}
