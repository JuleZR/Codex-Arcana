export function initSkillManager() {
  if (document.body.dataset.skillManagerBound === "1") {
    return;
  }
  document.body.dataset.skillManagerBound = "1";

  const getStatusFilterValue = (menu) => {
    if (!(menu instanceof HTMLElement)) {
      return "all";
    }
    const input = menu.querySelector("input[data-skill-manager-status-filter]");
    if (!(input instanceof HTMLInputElement)) {
      return "all";
    }
    const value = String(input.value || "all").trim().toLowerCase();
    return value || "all";
  };

  const syncStatusFilterButtons = (menu) => {
    if (!(menu instanceof HTMLElement)) {
      return;
    }
    const activeValue = getStatusFilterValue(menu);
    menu.querySelectorAll("[data-skill-manager-status-option]").forEach((button) => {
      if (!(button instanceof HTMLButtonElement)) {
        return;
      }
      const buttonValue = String(button.dataset.skillManagerStatusOption || "").trim().toLowerCase();
      const isActive = buttonValue === activeValue;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
  };

  const applyFilter = (menu) => {
    if (!(menu instanceof HTMLElement)) {
      return;
    }
    const input = menu.querySelector("input[data-skill-manager-search]");
    if (!(input instanceof HTMLInputElement)) {
      return;
    }
    const term = String(input.value || "").trim().toLowerCase();
    const status = getStatusFilterValue(menu);
    const items = Array.from(menu.querySelectorAll(".skill_manager_item"));
    let visibleCount = 0;

    items.forEach((item) => {
      if (!(item instanceof HTMLElement)) {
        return;
      }
      const haystack = String(item.dataset.skillSearch || "").toLowerCase();
      const visibility = String(item.dataset.skillVisibility || "").toLowerCase();
      const matchesTerm = !term || haystack.includes(term);
      const matchesStatus = status === "all" || visibility === status;
      const isVisible = matchesTerm && matchesStatus;
      item.hidden = !isVisible;
      if (isVisible) {
        visibleCount += 1;
      }
    });

    const emptyState = menu.querySelector(".skill_manager_empty");
    if (emptyState instanceof HTMLElement) {
      emptyState.hidden = visibleCount > 0;
    }
    syncStatusFilterButtons(menu);
  };

  document.addEventListener("input", (event) => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || !input.hasAttribute("data-skill-manager-search")) {
      return;
    }
    const menu = input.closest(".skill_manager_menu");
    applyFilter(menu);
  });

  document.addEventListener("click", (event) => {
    const button = event.target instanceof Element
      ? event.target.closest("[data-skill-manager-status-option]")
      : null;
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    const menu = button.closest(".skill_manager_menu");
    if (!(menu instanceof HTMLElement)) {
      return;
    }
    const input = menu.querySelector("input[data-skill-manager-status-filter]");
    if (!(input instanceof HTMLInputElement)) {
      return;
    }
    const nextValue = String(button.dataset.skillManagerStatusOption || "all").trim().toLowerCase() || "all";
    if (input.value === nextValue) {
      syncStatusFilterButtons(menu);
      return;
    }
    input.value = nextValue;
    const filterDetails = menu.querySelector(".skill_manager_filter");
    if (filterDetails instanceof HTMLDetailsElement) {
      filterDetails.open = false;
    }
    applyFilter(menu);
  });

  document.querySelectorAll(".skill_manager_menu").forEach((menu) => {
    if (menu instanceof HTMLElement) {
      applyFilter(menu);
    }
  });

  document.addEventListener("charsheet:partials-applied", () => {
    document.querySelectorAll(".skill_manager_menu").forEach((menu) => {
      if (menu instanceof HTMLElement) {
        applyFilter(menu);
      }
    });
  });
}
