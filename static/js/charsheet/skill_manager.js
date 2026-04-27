export function initSkillManager() {
  if (document.body.dataset.skillManagerBound === "1") {
    return;
  }
  document.body.dataset.skillManagerBound = "1";

  const applyFilter = (input) => {
    if (!(input instanceof HTMLInputElement)) {
      return;
    }
    const menu = input.closest(".skill_manager_menu");
    if (!(menu instanceof HTMLElement)) {
      return;
    }
    const term = String(input.value || "").trim().toLowerCase();
    const items = Array.from(menu.querySelectorAll(".skill_manager_item"));
    let visibleCount = 0;

    items.forEach((item) => {
      if (!(item instanceof HTMLElement)) {
        return;
      }
      const haystack = String(item.dataset.skillSearch || "").toLowerCase();
      const isVisible = !term || haystack.includes(term);
      item.hidden = !isVisible;
      if (isVisible) {
        visibleCount += 1;
      }
    });

    const emptyState = menu.querySelector(".skill_manager_empty");
    if (emptyState instanceof HTMLElement) {
      emptyState.hidden = visibleCount > 0;
    }
  };

  document.addEventListener("input", (event) => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || !input.hasAttribute("data-skill-manager-search")) {
      return;
    }
    applyFilter(input);
  });

  document.querySelectorAll("input[data-skill-manager-search]").forEach((input) => {
    if (input instanceof HTMLInputElement) {
      applyFilter(input);
    }
  });

  document.addEventListener("charsheet:partials-applied", () => {
    document.querySelectorAll("input[data-skill-manager-search]").forEach((input) => {
      if (input instanceof HTMLInputElement) {
        applyFilter(input);
      }
    });
  });
}
