import { applySheetPartials } from "./partial_updates.js";
import { getCsrfToken } from "./utils.js";

const SPELL_PANEL_STATE_KEY = "charsheet:spell-panel-state";

function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function loadSpellPanelState() {
  try {
    const raw = window.sessionStorage.getItem(SPELL_PANEL_STATE_KEY);
    if (!raw) {
      return { filter: "", schoolFilter: "all", expandedGroups: [] };
    }
    const parsed = JSON.parse(raw);
    const hasSchoolFilters = Array.isArray(parsed?.schoolFilters);
    const storedSchools = hasSchoolFilters
      ? parsed.schoolFilters.map((value) => String(value)).filter(Boolean)
      : [];
    return {
      filter: String(parsed?.filter || ""),
      schoolFilter: String(parsed?.schoolFilter || "all") || "all",
      schoolFilters: storedSchools,
      hasSchoolFilters,
      expandedGroups: Array.isArray(parsed?.expandedGroups)
        ? parsed.expandedGroups.map((value) => String(value))
        : [],
    };
  } catch (_error) {
    return { filter: "", schoolFilter: "all", expandedGroups: [] };
  }
}

function saveSpellPanelState({ filterInput = null, schoolFilters = [], groups = [] }) {
  try {
    const expandedGroups = groups
      .map((group) => {
        const button = group.querySelector("[data-spell-group-toggle]");
        const rowList = group.querySelector(".spell_group_rows");
        if (!(button instanceof HTMLElement) || !(rowList instanceof HTMLElement) || rowList.hidden) {
          return "";
        }
        return String(button.getAttribute("data-spell-group-name") || "").trim();
      })
      .filter(Boolean);
    window.sessionStorage.setItem(SPELL_PANEL_STATE_KEY, JSON.stringify({
      filter: filterInput instanceof HTMLInputElement ? String(filterInput.value || "") : "",
      schoolFilters: Array.from(schoolFilters).map((value) => String(value)),
      expandedGroups,
    }));
  } catch (_error) {
    // Ignore storage failures and keep the panel functional.
  }
}

function restoreExpandedSpellGroups(groups, expandedGroupNames) {
  groups.forEach((group) => {
    const button = group.querySelector("[data-spell-group-toggle]");
    const rowList = group.querySelector(".spell_group_rows");
    if (!(button instanceof HTMLElement) || !(rowList instanceof HTMLElement)) {
      return;
    }
    const groupName = String(button.getAttribute("data-spell-group-name") || "").trim();
    const shouldOpen = expandedGroupNames.includes(groupName);
    rowList.hidden = !shouldOpen;
    button.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
  });
}

function applySpellFilter(input, rows, groups, selectedSchools = null, schoolNames = []) {
  const needle = normalizeText(input instanceof HTMLInputElement ? input.value : "");
  const selectedSchoolSet = selectedSchools instanceof Set ? selectedSchools : new Set();
  const allSchoolsSelected = schoolNames.length === 0 || selectedSchoolSet.size === schoolNames.length;
  const schoolFilterActive = !allSchoolsSelected;
  const singleSchoolFilterActive = selectedSchoolSet.size === 1 && !allSchoolsSelected;

  rows.forEach((row) => {
    const haystack = normalizeText(row.getAttribute("data-spell-search"));
    row.hidden = needle ? !haystack.includes(needle) : false;
  });

  groups.forEach((group) => {
    const btn = group.querySelector("[data-spell-group-toggle]");
    const rowList = group.querySelector(".spell_group_rows");
    if (!(rowList instanceof HTMLElement)) {
      return;
    }
    const groupName = String(btn?.getAttribute("data-spell-group-name") || "").trim();
    const groupKind = String(btn?.getAttribute("data-spell-group-kind") || "").trim();
    const schoolMatches = !schoolFilterActive || (groupKind === "arcane" && selectedSchoolSet.has(groupName));

    if (!schoolMatches) {
      group.hidden = true;
      if (btn instanceof HTMLElement) {
        btn.hidden = false;
        btn.setAttribute("aria-expanded", "false");
      }
      rowList.hidden = true;
      return;
    }

    if (!needle && allSchoolsSelected) {
      group.hidden = false;
      if (btn instanceof HTMLElement) {
        btn.hidden = false;
        btn.setAttribute("aria-expanded", "false");
      }
      rowList.hidden = true;
      return;
    }

    const subRows = Array.from(rowList.querySelectorAll("[data-spell-search]"));
    const anyVisible = subRows.some((row) => !row.hidden);
    if (anyVisible) {
      group.hidden = false;
      if (btn instanceof HTMLElement) {
        btn.hidden = Boolean(needle) || singleSchoolFilterActive;
        btn.setAttribute("aria-expanded", "true");
      }
      rowList.hidden = false;
    } else {
      group.hidden = true;
      if (btn instanceof HTMLElement) {
        btn.hidden = false;
        btn.setAttribute("aria-expanded", "false");
      }
      rowList.hidden = true;
    }
  });
}

function readInt(value, fallback = 0) {
  const parsed = Number.parseInt(String(value ?? "").trim(), 10);
  return Number.isNaN(parsed) ? fallback : parsed;
}

function renderOptimisticArcaneMeter(nextValue) {
  const arcaneMeter = document.querySelector("#sheetDamagePanel .arcane_meter");
  const fill = arcaneMeter?.querySelector(".arcane_meter_fill");
  const valueNode = arcaneMeter?.querySelector(".arcane_meter_current");
  if (!(arcaneMeter instanceof HTMLElement) || !(fill instanceof HTMLElement) || !(valueNode instanceof HTMLElement)) {
    return null;
  }

  const previous = {
    current: readInt(arcaneMeter.dataset.arcaneCurrent, readInt(valueNode.textContent, 0)),
    max: readInt(arcaneMeter.dataset.arcaneMax, 0),
  };
  const safeMax = Math.max(0, previous.max);
  const clampedNext = Math.max(0, Math.min(readInt(nextValue, previous.current), safeMax));
  const ratio = safeMax <= 0 ? 0 : (clampedNext / safeMax) * 100;

  valueNode.textContent = String(clampedNext);
  fill.style.width = `${ratio}%`;
  arcaneMeter.dataset.arcaneCurrent = String(clampedNext);
  return previous;
}

function rollbackOptimisticArcaneMeter(previous) {
  if (!previous || typeof previous !== "object") {
    return;
  }
  renderOptimisticArcaneMeter(readInt(previous.current, 0));
}

export function initSpellPanel() {
  const panel = document.getElementById("sheetSpellPanel");
  if (!panel || panel.dataset.spellPanelBound === "1") {
    return;
  }
  panel.dataset.spellPanelBound = "1";

  const filterInput = document.getElementById("spellFilterInput");
  const schoolFilterTrigger = panel.querySelector("[data-spell-school-filter-trigger]");
  const schoolFilterTriggerIcon = panel.querySelector("[data-spell-school-filter-trigger-icon]");
  const schoolFilterPopover = panel.querySelector("[data-spell-school-filter-popover]");
  const schoolFilterButtons = Array.from(panel.querySelectorAll("[data-spell-school-filter]"));
  const schoolNames = schoolFilterButtons
    .map((button) => String(button.getAttribute("data-spell-school-filter") || ""))
    .filter((value) => value && value !== "all");
  const groups = Array.from(panel.querySelectorAll("[data-spell-group]"));
  const rows = Array.from(panel.querySelectorAll("[data-spell-search]"));
  const storedState = loadSpellPanelState();
  const initialSchoolFilters = storedState.hasSchoolFilters
    ? storedState.schoolFilters
    : (storedState.schoolFilter && storedState.schoolFilter !== "all" ? [storedState.schoolFilter] : schoolNames);
  let activeSchoolFilters = new Set(initialSchoolFilters.filter((name) => schoolNames.includes(name)));
  const defaultSchoolFilterTriggerIcon = schoolFilterTriggerIcon instanceof HTMLElement
    ? schoolFilterTriggerIcon.innerHTML
    : "";

  if (filterInput instanceof HTMLInputElement && storedState.filter) {
    filterInput.value = storedState.filter;
  }

  if (filterInput instanceof HTMLInputElement) {
    const runFilter = () => {
      applySpellFilter(filterInput, rows, groups, activeSchoolFilters, schoolNames);
      if (!String(filterInput.value || "").trim() && activeSchoolFilters.size === schoolNames.length) {
        restoreExpandedSpellGroups(groups, storedState.expandedGroups);
      }
      saveSpellPanelState({ filterInput, schoolFilters: activeSchoolFilters, groups });
    };
    filterInput.addEventListener("input", runFilter);
    filterInput.addEventListener("search", runFilter);
    filterInput.addEventListener("change", runFilter);
  }

  const syncSchoolFilterButtons = () => {
    const allSelected = activeSchoolFilters.size === schoolNames.length;
    schoolFilterButtons.forEach((button) => {
      if (!(button instanceof HTMLButtonElement)) {
        return;
      }
      const filterName = String(button.getAttribute("data-spell-school-filter") || "all");
      const isActive = filterName === "all"
        ? allSelected
        : (!allSelected && activeSchoolFilters.has(filterName));
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
  };

  const syncSchoolFilterTrigger = () => {
    const isFiltered = activeSchoolFilters.size !== schoolNames.length;
    const isSingleSelection = activeSchoolFilters.size === 1 && isFiltered;
    if (schoolFilterTrigger instanceof HTMLButtonElement) {
      schoolFilterTrigger.classList.toggle("is-filtered", isFiltered);
      schoolFilterTrigger.classList.toggle("is-single-filtered", isSingleSelection);
    }
    if (!(schoolFilterTriggerIcon instanceof HTMLElement)) {
      return;
    }
    if (!isSingleSelection) {
      schoolFilterTriggerIcon.innerHTML = defaultSchoolFilterTriggerIcon;
      return;
    }
    const selectedSchool = Array.from(activeSchoolFilters)[0];
    const selectedButton = schoolFilterButtons.find((button) => (
      button instanceof HTMLButtonElement
      && String(button.getAttribute("data-spell-school-filter") || "") === selectedSchool
    ));
    const selectedSymbol = selectedButton?.querySelector(".spell_school_filter_symbol");
    schoolFilterTriggerIcon.innerHTML = selectedSymbol instanceof HTMLElement
      ? selectedSymbol.innerHTML
      : defaultSchoolFilterTriggerIcon;
  };

  const applyCurrentFilters = () => {
    applySpellFilter(filterInput, rows, groups, activeSchoolFilters, schoolNames);
    panel.classList.toggle("spell_panel--single-school-filtered", activeSchoolFilters.size === 1 && activeSchoolFilters.size !== schoolNames.length);
    if (filterInput instanceof HTMLInputElement && !String(filterInput.value || "").trim() && activeSchoolFilters.size === schoolNames.length) {
      restoreExpandedSpellGroups(groups, storedState.expandedGroups);
    }
    syncSchoolFilterButtons();
    syncSchoolFilterTrigger();
    saveSpellPanelState({ filterInput, schoolFilters: activeSchoolFilters, groups });
  };

  syncSchoolFilterButtons();
  syncSchoolFilterTrigger();

  const closeSchoolFilterMenu = () => {
    if (schoolFilterPopover instanceof HTMLElement) {
      schoolFilterPopover.hidden = true;
    }
    if (schoolFilterTrigger instanceof HTMLButtonElement) {
      schoolFilterTrigger.classList.toggle("is-active", activeSchoolFilters.size !== schoolNames.length);
      syncSchoolFilterTrigger();
      schoolFilterTrigger.setAttribute("aria-expanded", "false");
    }
  };

  if (schoolFilterTrigger instanceof HTMLButtonElement && schoolFilterPopover instanceof HTMLElement) {
    schoolFilterTrigger.classList.toggle("is-active", activeSchoolFilters.size !== schoolNames.length);
    schoolFilterTrigger.addEventListener("click", (event) => {
      event.stopPropagation();
      const willOpen = schoolFilterPopover.hidden;
      schoolFilterPopover.hidden = !willOpen;
      schoolFilterTrigger.setAttribute("aria-expanded", willOpen ? "true" : "false");
      schoolFilterTrigger.classList.add("is-active");
    });
    schoolFilterPopover.addEventListener("click", (event) => {
      event.stopPropagation();
    });
    document.addEventListener("click", (event) => {
      if (!panel.contains(event.target)) {
        closeSchoolFilterMenu();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeSchoolFilterMenu();
      }
    });
  }

  schoolFilterButtons.forEach((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    button.addEventListener("click", () => {
      const filterName = String(button.getAttribute("data-spell-school-filter") || "all");
      const wasAllSelected = activeSchoolFilters.size === schoolNames.length;
      if (filterName === "all") {
        activeSchoolFilters = wasAllSelected ? new Set() : new Set(schoolNames);
      } else if (wasAllSelected) {
        activeSchoolFilters = new Set([filterName]);
      } else if (activeSchoolFilters.has(filterName)) {
        activeSchoolFilters.delete(filterName);
      } else if (schoolNames.includes(filterName)) {
        activeSchoolFilters.add(filterName);
      }
      applyCurrentFilters();
      if (schoolFilterTrigger instanceof HTMLButtonElement) {
        schoolFilterTrigger.classList.toggle("is-active", activeSchoolFilters.size !== schoolNames.length);
      }
    });
  });

  panel.querySelectorAll("[data-spell-group-toggle]").forEach((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    const group = button.closest("[data-spell-group]");
    const rowList = group?.querySelector(".spell_group_rows");
    if (!(rowList instanceof HTMLElement)) {
      return;
    }
    const groupName = String(button.getAttribute("data-spell-group-name") || "").trim();
    const shouldOpen = !storedState.filter && storedState.expandedGroups.includes(groupName);
    rowList.hidden = !shouldOpen;
    button.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
    button.addEventListener("click", () => {
      const willOpen = rowList.hidden;
      rowList.hidden = !willOpen;
      button.setAttribute("aria-expanded", willOpen ? "true" : "false");
      saveSpellPanelState({ filterInput, schoolFilters: activeSchoolFilters, groups });
    });
  });

  if (filterInput instanceof HTMLInputElement) {
    applySpellFilter(filterInput, rows, groups, activeSchoolFilters, schoolNames);
    panel.classList.toggle("spell_panel--single-school-filtered", activeSchoolFilters.size === 1 && activeSchoolFilters.size !== schoolNames.length);
    syncSchoolFilterTrigger();
    if (!String(filterInput.value || "").trim() && activeSchoolFilters.size === schoolNames.length) {
      restoreExpandedSpellGroups(groups, storedState.expandedGroups);
    }
    saveSpellPanelState({ filterInput, schoolFilters: activeSchoolFilters, groups });
  }

  panel.querySelectorAll("[data-cast-spell-trigger]").forEach((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    button.addEventListener("click", async () => {
      const url = button.getAttribute("data-cast-url") || "";
      if (!url || button.disabled) {
        return;
      }
      const kpCost = readInt(button.getAttribute("data-spell-kp-cost"), 0);
      const arcaneMeter = document.querySelector("#sheetDamagePanel .arcane_meter");
      const currentArcanePower = readInt(
        arcaneMeter?.dataset.arcaneCurrent,
        readInt(document.querySelector("#sheetDamagePanel .arcane_meter_current")?.textContent, 0),
      );
      saveSpellPanelState({ filterInput, schoolFilters: activeSchoolFilters, groups });
      button.disabled = true;
      const optimisticArcaneSnapshot = kpCost > 0
        ? renderOptimisticArcaneMeter(currentArcanePower - kpCost)
        : null;
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": getCsrfToken(),
            Accept: "application/json",
          },
          credentials: "same-origin",
        });
        const payload = await response.json();
        if (!response.ok || !payload?.ok) {
          rollbackOptimisticArcaneMeter(optimisticArcaneSnapshot);
          window.alert(String(payload?.message || "Zauber konnte nicht gewirkt werden."));
          return;
        }
        if (Array.isArray(payload.partials) && payload.partials.length) {
          applySheetPartials(payload);
        }
      } catch (_error) {
        rollbackOptimisticArcaneMeter(optimisticArcaneSnapshot);
        window.alert("Zauber konnte nicht gewirkt werden.");
      } finally {
        button.disabled = false;
      }
    });
  });
}
