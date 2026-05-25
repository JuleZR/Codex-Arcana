function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function readSchoolsState(storageKey) {
  try {
    const raw = window.localStorage.getItem(storageKey);
    const parsed = raw ? JSON.parse(raw) : {};
    return {
      pinnedItemKeys: Array.isArray(parsed?.pinnedItemKeys) ? parsed.pinnedItemKeys.map(String) : [],
      pinnedGroupKeys: Array.isArray(parsed?.pinnedGroupKeys) ? parsed.pinnedGroupKeys.map(String) : [],
    };
  } catch (_error) {
    return { pinnedItemKeys: [], pinnedGroupKeys: [] };
  }
}

function saveSchoolsState(storageKey, state) {
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(state));
  } catch (_error) {
    // no-op
  }
}

function setPinButtonState(button, isPinned, activeLabel, inactiveLabel) {
  if (!(button instanceof HTMLButtonElement)) {
    return;
  }
  button.setAttribute("aria-pressed", isPinned ? "true" : "false");
  button.classList.toggle("is-active", isPinned);
  const icon = button.querySelector("span[aria-hidden='true']");
  if (icon instanceof HTMLElement) {
    icon.innerHTML = isPinned ? "&#x25C6;" : "&#x25C7;";
  }
  const nextLabel = isPinned ? activeLabel : inactiveLabel;
  button.setAttribute("aria-label", nextLabel);
  button.setAttribute("title", nextLabel);
}

function applySchoolsFilter(input, rows, groups, pinnedGroupKeys) {
  const needle = normalizeText(input.value);

  rows.forEach((row) => {
    const haystack = normalizeText(row.getAttribute("data-school-search"));
    row.hidden = needle ? !haystack.includes(needle) : false;
  });

  groups.forEach((group) => {
    const btn = group.querySelector("[data-school-group-toggle]");
    const rowList = group.querySelector(".school_group_rows");
    const groupKey = String(group.getAttribute("data-school-group-key") || "");
    const keepOpen = Boolean(groupKey && pinnedGroupKeys.includes(groupKey));

    if (!(rowList instanceof HTMLElement)) {
      return;
    }

    if (!needle) {
      group.hidden = false;
      if (btn instanceof HTMLElement) {
        btn.hidden = false;
        btn.setAttribute("aria-expanded", keepOpen ? "true" : "false");
      }
      rowList.hidden = !keepOpen;
      return;
    }

    const subRows = Array.from(rowList.querySelectorAll("[data-school-search]"));
    const anyVisible = subRows.some((row) => !row.hidden);

    if (anyVisible) {
      group.hidden = false;
      if (btn instanceof HTMLElement) {
        btn.hidden = true;
      }
      rowList.hidden = false;
      return;
    }

    group.hidden = true;
    if (btn instanceof HTMLElement) {
      btn.hidden = false;
      btn.setAttribute("aria-expanded", keepOpen ? "true" : "false");
    }
    rowList.hidden = true;
  });
}

export function initWmArcanaFilter() {
  const input = document.getElementById("wmArcanaFilterInput");
  const panel = document.getElementById("wmArcanaList");
  if (!(input instanceof HTMLInputElement) || !(panel instanceof HTMLElement)) {
    return;
  }

  if (input.dataset.wmFilterBound === "1") {
    return;
  }
  input.dataset.wmFilterBound = "1";

  const rows = Array.from(panel.querySelectorAll("[data-wm-search]"));
  const sections = Array.from(panel.querySelectorAll("[data-wm-section]"));

  const runFilter = () => {
    const needle = normalizeText(input.value);
    rows.forEach((row) => {
      const haystack = normalizeText(row.getAttribute("data-wm-search"));
      row.hidden = needle ? !haystack.includes(needle) : false;
    });
    sections.forEach((section) => {
      const sectionRows = Array.from(section.querySelectorAll("[data-wm-search]"));
      section.hidden = needle ? sectionRows.every((row) => row.hidden) : false;
    });
  };

  input.addEventListener("input", runFilter);
  input.addEventListener("search", runFilter);
  input.addEventListener("change", runFilter);
  runFilter();
}

export function initSchoolsPanel() {
  const input = document.getElementById("schoolsFilterInput");
  const list = document.getElementById("schoolsList");
  const pinnedPanel = document.getElementById("schoolsPinnedPanel");
  const pinnedList = document.getElementById("schoolsPinnedList");
  if (
    !(input instanceof HTMLInputElement)
    || !(list instanceof HTMLElement)
    || !(pinnedPanel instanceof HTMLElement)
    || !(pinnedList instanceof HTMLElement)
  ) {
    return;
  }

  if (input.dataset.schoolsFilterBound === "1") {
    return;
  }
  input.dataset.schoolsFilterBound = "1";

  const characterId = String(list.dataset.characterId || "0");
  const storageKey = `charsheet.schoolsPanel.${characterId}`;
  const state = readSchoolsState(storageKey);

  const rows = Array.from(list.querySelectorAll("[data-school-search]"));
  const groups = Array.from(list.querySelectorAll("[data-school-group]"));
  const pinnableItems = Array.from(list.querySelectorAll("[data-school-pin-item]"));
  const itemPlaceholders = new WeakMap();

  const updatePinnedPanelVisibility = () => {
    pinnedPanel.hidden = pinnedList.childElementCount === 0;
  };

  const persistState = () => {
    saveSchoolsState(storageKey, state);
  };

  const syncItemButton = (row, isPinned) => {
    const button = row.querySelector("[data-school-pin-toggle]");
    const label = String(button?.getAttribute("data-pin-label") || "Eintrag");
    setPinButtonState(
      button,
      isPinned,
      `${label} losloesen`,
      `${label} anheften`,
    );
    row.classList.toggle("is-pinned", isPinned);
  };

  const syncGroupButton = (group, isPinned) => {
    const button = group.querySelector("[data-school-group-pin-toggle]");
    const schoolName = String(group.querySelector(".skill_name_text")?.textContent || "Schule").trim();
    setPinButtonState(
      button,
      isPinned,
      `${schoolName} nicht mehr dauerhaft offen halten`,
      `${schoolName} immer aufgeklappt halten`,
    );
    group.classList.toggle("is-pinned-open", isPinned);
  };

  const pinItemRow = (row) => {
    if (!(row instanceof HTMLLIElement)) {
      return;
    }
    if (!itemPlaceholders.has(row)) {
      const placeholder = document.createComment(`school-pin:${row.getAttribute("data-school-pin-key") || ""}`);
      row.parentNode?.insertBefore(placeholder, row);
      itemPlaceholders.set(row, placeholder);
    }
    pinnedList.appendChild(row);
    syncItemButton(row, true);
  };

  const unpinItemRow = (row) => {
    const placeholder = itemPlaceholders.get(row);
    if (placeholder?.parentNode) {
      placeholder.parentNode.insertBefore(row, placeholder);
      placeholder.parentNode.removeChild(placeholder);
      itemPlaceholders.delete(row);
    }
    syncItemButton(row, false);
  };

  const applyPinnedItemOrder = () => {
    const keySet = new Set(state.pinnedItemKeys);

    pinnableItems.forEach((row) => {
      const key = String(row.getAttribute("data-school-pin-key") || "");
      if (!key) {
        return;
      }
      if (keySet.has(key)) {
        pinItemRow(row);
      } else if (row.parentElement === pinnedList) {
        unpinItemRow(row);
      } else {
        syncItemButton(row, false);
      }
    });

    state.pinnedItemKeys.forEach((key) => {
      const row = pinnableItems.find((entry) => entry.getAttribute("data-school-pin-key") === key);
      if (row && row.parentElement === pinnedList) {
        pinnedList.appendChild(row);
      }
    });

    updatePinnedPanelVisibility();
  };

  const applyPinnedGroupState = () => {
    groups.forEach((group) => {
      const key = String(group.getAttribute("data-school-group-key") || "");
      const rowList = group.querySelector(".school_group_rows");
      const button = group.querySelector("[data-school-group-toggle]");
      const isPinned = Boolean(key && state.pinnedGroupKeys.includes(key));
      syncGroupButton(group, isPinned);
      if (!input.value && rowList instanceof HTMLElement && button instanceof HTMLElement) {
        rowList.hidden = !isPinned;
        button.setAttribute("aria-expanded", isPinned ? "true" : "false");
      }
    });
  };

  const runFilter = () => {
    applySchoolsFilter(input, rows, groups, state.pinnedGroupKeys);
    updatePinnedPanelVisibility();
  };

  const handlePanelClick = (event) => {
    const pinButton = event.target instanceof Element ? event.target.closest("[data-school-pin-toggle]") : null;
    if (pinButton instanceof HTMLButtonElement) {
      event.preventDefault();
      event.stopPropagation();
      const row = pinButton.closest("[data-school-pin-item]");
      if (!(row instanceof HTMLLIElement)) {
        return;
      }
      const key = String(row.getAttribute("data-school-pin-key") || "");
      if (!key) {
        return;
      }
      if (state.pinnedItemKeys.includes(key)) {
        state.pinnedItemKeys = state.pinnedItemKeys.filter((entry) => entry !== key);
      } else {
        state.pinnedItemKeys.unshift(key);
      }
      applyPinnedItemOrder();
      persistState();
      runFilter();
      return;
    }

    const groupPinButton = event.target instanceof Element ? event.target.closest("[data-school-group-pin-toggle]") : null;
    if (groupPinButton instanceof HTMLButtonElement) {
      event.preventDefault();
      event.stopPropagation();
      const group = groupPinButton.closest("[data-school-group]");
      if (!(group instanceof HTMLElement)) {
        return;
      }
      const key = String(group.getAttribute("data-school-group-key") || "");
      if (!key) {
        return;
      }
      if (state.pinnedGroupKeys.includes(key)) {
        state.pinnedGroupKeys = state.pinnedGroupKeys.filter((entry) => entry !== key);
      } else {
        state.pinnedGroupKeys.unshift(key);
      }
      applyPinnedGroupState();
      persistState();
      runFilter();
      return;
    }

    const toggleButton = event.target instanceof Element ? event.target.closest("[data-school-group-toggle]") : null;
    if (!(toggleButton instanceof HTMLButtonElement)) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();

    const group = toggleButton.closest("[data-school-group]");
    const rowList = group?.querySelector(".school_group_rows");
    if (!(rowList instanceof HTMLElement)) {
      return;
    }

    const willOpen = rowList.hidden;
    rowList.hidden = !willOpen;
    toggleButton.setAttribute("aria-expanded", willOpen ? "true" : "false");
  };

  list.addEventListener("click", handlePanelClick);
  pinnedList.addEventListener("click", handlePanelClick);

  input.addEventListener("input", runFilter);
  input.addEventListener("search", runFilter);
  input.addEventListener("change", runFilter);

  applyPinnedItemOrder();
  applyPinnedGroupState();
  runFilter();
}
