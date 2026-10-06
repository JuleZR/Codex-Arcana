export function sortSkillRowGroups(rows, column, kind, direction) {
  const groups = [];
  rows.forEach((row) => {
    if (row.classList.contains("skill_context_row") && groups.length) {
      groups[groups.length - 1].push(row);
    } else {
      groups.push([row]);
    }
  });
  const rowValue = (row) => {
    const cell = row.cells[column];
    const text = String((column === 0
      ? cell?.querySelector(".skill_name_text")?.textContent
      : cell?.textContent) ?? cell?.textContent ?? "").trim();
    if (!text) return null;
    if (kind === "text") return text;
    const number = Number(text.replace(/\s/g, "").replace(/−/g, "-").replace(",", "."));
    return Number.isFinite(number) ? number : null;
  };
  const value = (group) => {
    const parentValue = rowValue(group[0]);
    if (parentValue !== null) return parentValue;
    const childValues = group.slice(1).map(rowValue).filter((entry) => entry !== null);
    if (!childValues.length) return null;
    return kind === "number" ? Math.max(...childValues) : childValues[0];
  };
  const collator = new Intl.Collator("de", { numeric: true, sensitivity: "base" });
  return groups.sort((left, right) => {
    const a = value(left);
    const b = value(right);
    if (a === null) return b === null ? 0 : 1;
    if (b === null) return -1;
    const comparison = kind === "number" ? a - b : collator.compare(a, b);
    return direction === "descending" ? -comparison : comparison;
  });
}

export function initSkillManager() {
  if (document.body.dataset.skillManagerBound === "1") {
    return;
  }
  document.body.dataset.skillManagerBound = "1";

  let activeSort = null;
  const applySort = () => {
    const table = document.querySelector("#sheetSkillsPanel .skills_table");
    const tbody = table?.tBodies[0];
    if (!tbody || !activeSort) return;
    const { column, kind, direction } = activeSort;
    const groups = sortSkillRowGroups(Array.from(tbody.rows), column, kind, direction);
    groups.forEach((group) => group.forEach((row) => tbody.appendChild(row)));
    table.querySelectorAll("[data-skill-sort]").forEach((header) => {
      header.setAttribute("aria-sort", header.cellIndex === column ? direction : "none");
    });
  };
  const handleSort = (event) => {
    const header = event.target instanceof Element
      ? event.target.closest("#sheetSkillsPanel [data-skill-sort]")
      : null;
    if (!header) return;
    if (event.type === "keydown" && event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    activeSort = {
      column: header.cellIndex,
      kind: header.dataset.skillSort,
      direction: activeSort?.column === header.cellIndex && activeSort.direction === "ascending"
        ? "descending" : "ascending",
    };
    applySort();
  };
  document.addEventListener("click", handleSort);
  document.addEventListener("keydown", handleSort);

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
    applySort();
  });
}
