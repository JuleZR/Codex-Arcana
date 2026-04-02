function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function applySchoolsFilter(input, rows) {
  const needle = normalizeText(input.value);
  rows.forEach((row) => {
    const haystack = normalizeText(row.getAttribute("data-school-search"));
    row.hidden = needle ? !haystack.includes(needle) : false;
  });
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

  const rows = Array.from(list.querySelectorAll("[data-school-search]"));
  const runFilter = () => applySchoolsFilter(input, rows);

  input.addEventListener("input", runFilter);
  input.addEventListener("search", runFilter);
  input.addEventListener("change", runFilter);
  runFilter();
}
