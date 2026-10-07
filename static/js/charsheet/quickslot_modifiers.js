export function initModifierList(list, add, onChange = () => {}) {
  let entries = [];
  function renderEntries() {
    list.replaceChildren();
    entries.forEach((entry, index) => {
      const row = document.createElement("div");
      row.className = "quickslot-modifiers__entry";
      const value = document.createElement("input");
      value.type = "number"; value.step = "1"; value.value = entry.value;
      value.setAttribute("aria-label", "Bonus oder Malus");
      const name = document.createElement("input");
      name.type = "text"; name.maxLength = 80; name.value = entry.name;
      name.placeholder = "Name"; name.setAttribute("aria-label", "Name des Werts");
      const remove = document.createElement("button");
      remove.type = "button"; remove.textContent = "×";
      remove.setAttribute("aria-label", "Eintrag entfernen");
      value.addEventListener("input", () => { entry.value = value.validity?.badInput ? "NaN" : value.value; onChange(); });
      name.addEventListener("input", () => { entry.name = name.value; onChange(); });
      remove.addEventListener("click", () => { entries.splice(index, 1); onChange(); renderEntries(); });
      row.append(value, name, remove); list.append(row);
    });
  }
  add.addEventListener("click", () => {
    entries.push({ value: "0", name: "" }); onChange(); renderEntries();
    list.lastElementChild?.querySelector("input")?.focus();
  });
  return {
    getEntries: () => entries.map(entry => ({ ...entry })),
    setEntries(value) { entries = value.map(entry => ({ value: String(entry.value), name: entry.name })); renderEntries(); },
    getTotal: () => entries.reduce((total, entry) => total + Number(entry.value || 0), 0),
  };
}

export function initQuickslotModifiers(root, notify) {
  const toggle = root.querySelector("[data-quickslot-modifiers-toggle]");
  const panel = root.querySelector("[data-quickslot-modifiers-panel]");
  const storageKey = `${root.dataset.storageKey}.modifiers`;
  let expanded = false, collapsed = false;
  const editor = initModifierList(root.querySelector("[data-quickslot-modifiers-list]"),
    root.querySelector("[data-quickslot-modifiers-add]"), persist);
  try {
    const saved = JSON.parse(window.localStorage.getItem(storageKey));
    if (Array.isArray(saved?.entries)) editor.setEntries(saved.entries.filter(entry =>
      entry && typeof entry.value === "string" && typeof entry.name === "string",
    ).map(entry => ({ value: entry.value, name: entry.name.slice(0, 80) })));
    expanded = saved?.expanded === true;
  } catch (_error) { /* Start empty when browser storage is unavailable. */ }
  function persist() {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify({ entries: editor.getEntries(), expanded }));
    } catch (_error) { notify("Die Boni und Mali konnten in diesem Browser nicht gespeichert werden."); }
  }
  function renderExpanded() {
    fitMenu();
    const visible = expanded && !collapsed;
    panel.classList.toggle("is-open", visible);
    panel.inert = !visible;
    panel.setAttribute("aria-hidden", String(!visible));
    toggle.setAttribute("aria-expanded", String(visible));
  }
  function fitMenu() {
    if (collapsed) return;
    const pages = [...document.querySelectorAll(".book-spread > .page")]
      .filter(page => page.getClientRects().length).map(page => page.getBoundingClientRect());
    if (!pages.length) return;
    const pageRight = Math.max(...pages.map(page => page.right));
    const hotbarLeft = root.querySelector(".quickslots__body").getBoundingClientRect().left;
    root.style.setProperty("--quickslots-menu-width", `${Math.max(190, hotbarLeft - pageRight - 12)}px`);
  }
  window.addEventListener("resize", fitMenu);
  if (typeof ResizeObserver !== "undefined") {
    const observer = new ResizeObserver(fitMenu);
    for (const page of document.querySelectorAll(".book-spread > .page")) observer.observe(page);
  }
  toggle.addEventListener("click", () => { expanded = !expanded; persist(); renderExpanded(); });
  renderExpanded();
  return {
    getTotal: editor.getTotal,
    getEntries: editor.getEntries,
    setCollapsed(value) { collapsed = value; renderExpanded(); },
  };
}
