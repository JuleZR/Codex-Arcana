export function initQuickslotHistory(root) {
  if (!root) return null;
  const toggle = root.querySelector("[data-quickslot-history-toggle]");
  const panel = root.querySelector("[data-quickslot-history-panel]");
  const list = root.querySelector("[data-quickslot-history-list]");
  const bonusToggle = root.querySelector("[data-quickslot-modifiers-toggle]");
  const bonusPanel = root.querySelector("[data-quickslot-modifiers-panel]");
  const storageKey = `${root.dataset.storageKey}.history`;
  let entries = [], expanded = false;
  function valid(entry) {
    return entry && Number.isFinite(entry.total) && typeof entry.label === "string"
      && Number.isInteger(entry.sides) && Number.isInteger(entry.count)
      && Array.isArray(entry.dice) && entry.dice.every(Number.isFinite)
      && Array.isArray(entry.modifiers) && entry.modifiers.every(modifier =>
        modifier && Number.isFinite(modifier.value) && typeof modifier.label === "string",
      ) && Number.isFinite(Date.parse(entry.time));
  }
  try {
    const saved = JSON.parse(window.localStorage.getItem(storageKey));
    if (Array.isArray(saved)) entries = saved.filter(valid).slice(0, 10);
  } catch (_error) { /* Keep an empty history when storage is unavailable. */ }

  function renderExpanded() {
    panel.classList.toggle("is-open", expanded);
    panel.inert = !expanded;
    panel.setAttribute("aria-hidden", String(!expanded));
    toggle.setAttribute("aria-expanded", String(expanded));
  }
  function close() { expanded = false; renderExpanded(); }
  function render() {
    list.replaceChildren();
    if (!entries.length) {
      const empty = document.createElement("li");
      empty.className = "quickslot-history__empty"; empty.textContent = "Noch keine Würfe.";
      list.append(empty);
    }
    entries.forEach(entry => {
      const row = document.createElement("li"); row.className = "quickslot-history__entry";
      const debug = entry.debug === true || /^DEBUG\b/i.test(entry.label);
      row.classList.toggle("is-debug", debug);
      const modifierValues = entry.modifiers.map(modifier =>
        `${modifier.operator === "/" ? "/" : modifier.operator === "*" ? "×" : modifier.value >= 0 ? "+" : ""}${modifier.value}`,
      );
      const namedModifiers = entry.modifiers.map(modifier => !modifier.operator
        && modifier.label !== "Würfelsumme"
        && (modifier.named === true || (modifier.named === undefined
          && !["Modifikator", "Freier Bonus", "Slot-Bonus", entry.label].includes(modifier.label))));
      const formulaValues = modifierValues.filter((_value, index) => !namedModifiers[index]);
      const formula = document.createElement("strong"); formula.className = "quickslot-history__formula";
      const label = entry.label.replace(/^DEBUG\b\s*[-·:]?\s*/i, "").trim();
      const action = /^\d+[wd]\d+(?:[+\-×/]-?\d+(?:\.\d+)?)?$/i.test(label) ? "" : label;
      formula.textContent = `${debug ? "DEBUG · " : ""}${action ? `${action} · ` : ""}${entry.count}d${entry.sides}${formulaValues.length ? ` ${formulaValues.join(" ")}` : ""}`;
      formula.title = [entry.label, ...entry.modifiers.map((modifier, index) => `${modifier.label}: ${modifierValues[index]}`)].join(" · ");
      const time = document.createElement("time"); time.dateTime = entry.time;
      const date = new Date(entry.time);
      time.textContent = date.toLocaleTimeString("de-DE"); time.title = date.toLocaleString("de-DE");
      const modifierList = document.createElement("ul"); modifierList.className = "quickslot-history__modifiers";
      entry.modifiers.forEach((modifier, index) => {
        if (!namedModifiers[index]) return;
        const item = document.createElement("li");
        item.textContent = `${modifier.label} ${modifierValues[index]}`;
        modifierList.append(item);
      });
      modifierList.hidden = !modifierList.childElementCount;
      const dice = document.createElement("div"); dice.className = "quickslot-history__dice";
      dice.setAttribute("aria-label", "Einzelne Würfelergebnisse");
      entry.dice.forEach(value => {
        const die = document.createElement("span"); die.className = "quickslot-history__die";
        die.textContent = value; dice.append(die);
      });
      const result = document.createElement("strong"); result.className = "quickslot-history__result";
      const critical = entry.critical === "success" ? " · Kritischer Erfolg"
        : entry.critical === "failure" ? " · Kritischer Fehlschlag"
          : entry.specialFailure === true ? " · Fehlschlag" : "";
      result.textContent = `Ergebnis: ${entry.total}${critical}`;
      row.append(formula, time, modifierList, dice, result); list.append(row);
    });
  }
  toggle.addEventListener("click", () => {
    if (bonusPanel.classList.contains("is-open")) bonusToggle.click();
    expanded = !expanded; renderExpanded();
  });
  bonusToggle.addEventListener("click", close);
  root.querySelector("[data-quickslot-toggle]").addEventListener("click", close);
  render(); renderExpanded();
  return {
    record(entry) {
      entry = { ...entry, time: new Date().toISOString() };
      if (!valid(entry)) return;
      entries = [entry, ...entries].slice(0, 10);
      try { window.localStorage.setItem(storageKey, JSON.stringify(entries)); }
      catch (_error) { /* Keep recent rolls available for the current page. */ }
      render();
    },
  };
}
