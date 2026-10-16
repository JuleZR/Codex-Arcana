/* Filter server-rendered rows; links and mutations retain their existing routes. */
(() => {
  "use strict";

  const register = document.querySelector(".dashboard_register");
  if (!register) return;
  let filter = "all";
  const normalize = value => String(value || "").toLocaleLowerCase("de");

  function updateRegister() {
    const region = register.querySelector("#dashboardCharacterTableRegion");
    if (!region) return;
    const query = normalize(register.querySelector("#dashboardCharacterSearch")?.value.trim());
    const filtering = Boolean(query || filter !== "all");
    let count = 0;
    let visibleGroups = 0;

    region.querySelectorAll("[data-register-group]").forEach(group => {
      let visibleRows = 0;
      const groupName = normalize(group.dataset.groupName);
      const rows = group.querySelectorAll("[data-register-character]");
      rows.forEach(row => {
        const own = row.dataset.characterOwn === "1";
        const matchesFilter = filter === "all"
          || (filter === "own" && own)
          || (filter === "foreign" && !own)
          || (filter === "npc" && row.dataset.characterNpc === "1");
        row.hidden = !matchesFilter || !normalize(row.dataset.characterName + " " + groupName).includes(query);
        if (!row.hidden) visibleRows += 1;
      });
      // Empty groups stay reachable, including when searching their names.
      group.hidden = filtering && visibleRows === 0
        && !(rows.length === 0 && filter === "all" && groupName.includes(query));
      if (!group.hidden) visibleGroups += 1;
      count += visibleRows;
    });

    const empty = region.querySelector("[data-register-no-results]");
    if (empty) empty.hidden = !filtering || visibleGroups > 0;
    const output = register.querySelector("#dashboardRegisterCount");
    if (output) output.textContent = `${count} ${count === 1 ? "Eintrag" : "Einträge"}`;
    register.querySelectorAll("[data-character-filter]").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.characterFilter === filter));
    });
  }

  register.addEventListener("click", event => {
    const button = event.target.closest("[data-character-filter]");
    if (!button) return;
    filter = button.dataset.characterFilter;
    updateRegister();
  });
  register.addEventListener("input", event => {
    if (event.target.id === "dashboardCharacterSearch") updateRegister();
  });

  // The group window replaces this region after membership changes.
  // Observe child replacements only, so changing hidden attributes cannot loop.
  new MutationObserver(records => {
    if (records.some(record => Array.from(record.addedNodes).some(node =>
      node.nodeType === 1 && (node.id === "dashboardCharacterTableRegion"
        || node.matches("[data-register-group], [data-register-character]"))
    ))) updateRegister();
  }).observe(register.querySelector(".dashboard_active_block"), { childList: true, subtree: true });

  updateRegister();
})();
