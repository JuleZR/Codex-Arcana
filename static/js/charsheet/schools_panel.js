function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function applySchoolsFilter(input, rows, groups) {
  const needle = normalizeText(input.value);

  // Filter individual technique rows (flat race rows + grouped sub-rows).
  rows.forEach((row) => {
    const haystack = normalizeText(row.getAttribute("data-school-search"));
    row.hidden = needle ? !haystack.includes(needle) : false;
  });

  groups.forEach((group) => {
    const btn = group.querySelector("[data-school-group-toggle]");
    const rowList = group.querySelector(".school_group_rows");

    if (!needle) {
      // Restore collapsed state — hide sub-rows, show group header.
      group.hidden = false;
      if (rowList) rowList.hidden = true;
      if (btn) btn.setAttribute("aria-expanded", "false");
      return;
    }

    // Check whether any sub-row matches.
    const subRows = rowList ? Array.from(rowList.querySelectorAll("[data-school-search]")) : [];
    const anyVisible = subRows.some((r) => !r.hidden);

    if (anyVisible) {
      // Expand so matching sub-rows are visible; hide the group header button itself.
      group.hidden = false;
      if (btn) btn.hidden = true;          // hide the "Alchemist X" header line
      if (rowList) rowList.hidden = false;
    } else {
      // No match in this group — hide everything.
      group.hidden = true;
      if (btn) btn.hidden = false;
      if (rowList) rowList.hidden = true;
    }
  });
}

// Toggle collapse/expand for a school group header.
document.addEventListener("click", (event) => {
  const btn = event.target instanceof Element
    ? event.target.closest("[data-school-group-toggle]")
    : null;
  if (!(btn instanceof HTMLButtonElement)) return;
  event.preventDefault();
  event.stopPropagation();

  const group = btn.closest("[data-school-group]");
  const rowList = group?.querySelector(".school_group_rows");
  if (!(rowList instanceof HTMLElement)) return;

  const willOpen = rowList.hidden;
  rowList.hidden = !willOpen;
  btn.setAttribute("aria-expanded", willOpen ? "true" : "false");
});

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
  if (!(input instanceof HTMLInputElement) || !(list instanceof HTMLElement)) {
    return;
  }

  if (input.dataset.schoolsFilterBound === "1") {
    return;
  }
  input.dataset.schoolsFilterBound = "1";

  // Rows that carry a data-school-search attribute (flat race rows + sub-rows).
  const rows = Array.from(list.querySelectorAll("[data-school-search]"));
  // Group <li> elements that wrap a whole school.
  const groups = Array.from(list.querySelectorAll("[data-school-group]"));

  const runFilter = () => applySchoolsFilter(input, rows, groups);

  input.addEventListener("input", runFilter);
  input.addEventListener("search", runFilter);
  input.addEventListener("change", runFilter);
  runFilter();
}
