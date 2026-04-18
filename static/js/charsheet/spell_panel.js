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
      return { filter: "", expandedGroups: [] };
    }
    const parsed = JSON.parse(raw);
    return {
      filter: String(parsed?.filter || ""),
      expandedGroups: Array.isArray(parsed?.expandedGroups)
        ? parsed.expandedGroups.map((value) => String(value))
        : [],
    };
  } catch (_error) {
    return { filter: "", expandedGroups: [] };
  }
}

function saveSpellPanelState({ filterInput = null, groups = [] }) {
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

function applySpellFilter(input, rows, groups) {
  const needle = normalizeText(input.value);

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

    if (!needle) {
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
        btn.hidden = true;
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
  const groups = Array.from(panel.querySelectorAll("[data-spell-group]"));
  const rows = Array.from(panel.querySelectorAll("[data-spell-search]"));
  const storedState = loadSpellPanelState();

  if (filterInput instanceof HTMLInputElement && storedState.filter) {
    filterInput.value = storedState.filter;
  }

  if (filterInput instanceof HTMLInputElement) {
    const runFilter = () => {
      applySpellFilter(filterInput, rows, groups);
      if (!String(filterInput.value || "").trim()) {
        restoreExpandedSpellGroups(groups, storedState.expandedGroups);
      }
      saveSpellPanelState({ filterInput, groups });
    };
    filterInput.addEventListener("input", runFilter);
    filterInput.addEventListener("search", runFilter);
    filterInput.addEventListener("change", runFilter);
  }

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
      saveSpellPanelState({ filterInput, groups });
    });
  });

  if (filterInput instanceof HTMLInputElement) {
    applySpellFilter(filterInput, rows, groups);
    if (!String(filterInput.value || "").trim()) {
      restoreExpandedSpellGroups(groups, storedState.expandedGroups);
    }
    saveSpellPanelState({ filterInput, groups });
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
      saveSpellPanelState({ filterInput, groups });
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
