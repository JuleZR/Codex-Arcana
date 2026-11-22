const termsOf = (formula) => formula.kind === "sum" ? formula.terms : [formula];

export const renderDamageFormula = (formula) => {
  if (formula.kind === "constant") return String(formula.value);
  if (formula.kind === "range") return `${formula.minimum}–${formula.maximum}`;
  if (formula.kind === "dice") {
    return `${formula.count}w${formula.sides}${formula.divisor === 1 ? "" : `/${formula.divisor}`}`;
  }
  return formula.terms.map((term, index) => {
    const sign = index && !(term.kind === "constant" && term.value < 0) ? "+" : "";
    return sign + renderDamageFormula(term);
  }).join("");
};

export function createDamageEditor(form, index, section, onChange) {
  const prefix = `attacks-${index}`;
  const field = form.elements[`${prefix}-damage_formula_input`];
  const active = form.elements[`${prefix}-damage_editor_active`];
  const level = form.elements[`${prefix}-damage_level`];
  const confirmed = form.elements[`${prefix}-damage_level_confirmed`];
  const damageRow = form.querySelector(`[data-damage-rows] [data-attack-index='${index}']`);
  const root = document.createElement("div");
  root.className = "builder-formula-editor";
  const header = document.createElement("div");
  header.className = "builder-dice-head";
  ["Anzahl", "Würfel", "Teiler"].forEach((text) => {
    const caption = document.createElement("span");
    caption.textContent = text;
    header.append(caption);
  });
  const rows = document.createElement("div");
  rows.className = "builder-dice-terms";
  const actions = document.createElement("div");
  actions.className = "builder-formula-actions";
  const add = document.createElement("button");
  add.type = "button";
  add.textContent = "Formel ersetzen";
  add.hidden = true;
  const bonusLabel = document.createElement("label");
  bonusLabel.append("Bonus / Malus ");
  const bonus = document.createElement("input");
  bonus.type = "number";
  bonus.min = "-1000000";
  bonus.max = "1000000";
  bonus.step = "1";
  bonus.value = "0";
  bonus.required = true;
  bonusLabel.append(bonus);
  actions.append(add, bonusLabel);
  const status = document.createElement("p");
  status.className = "builder-formula-status";
  status.setAttribute("role", "status");
  root.append(header, rows, actions, status);
  section.append(root);
  let initialized = false;
  let range = null;
  let legacy = false;
  let preserved = false;

  const manual = (show) => {
    level.closest("p").hidden = !show;
    confirmed.closest("p").hidden = !show;
    level.required = show;
    confirmed.required = show;
  };
  manual(false);

  const preview = (formula) => {
    const output = damageRow.querySelector("[data-damage-expression]");
    if (output) {
      const type = form.elements[`${prefix}-damage_type`].value;
      output.textContent = formula ? `${renderDamageFormula(formula)}${type ? ` ${type}` : ""}` : "—";
    }
  };

  const commit = () => {
    if (!initialized) return;
    legacy = false;
    active.value = "on";
    confirmed.checked = false;
    level.value = "";
    const inputs = [...rows.querySelectorAll("input, select"), bonus];
    if (inputs.some((input) => !input.checkValidity() || (input.required && input.value === ""))) {
      field.value = "";
      status.textContent = "Bitte gültige Würfelwerte eingeben.";
      preview(null);
    } else {
      const terms = [...rows.children].map((row) => ({
        kind: "dice",
        count: Number(row.querySelector("[data-dice-count]").value),
        sides: Number(row.querySelector("[data-dice-sides]").value),
        divisor: Number(row.querySelector("[data-dice-divisor]").value || 1),
      })).filter((term) => term.count > 0);
      if (range) terms.push(range);
      if (Number(bonus.value) || !terms.length) terms.push({ kind: "constant", value: Number(bonus.value) });
      const formula = terms.length === 1 ? terms[0] : { kind: "sum", terms };
      field.value = JSON.stringify(formula);
      preview(formula);
      status.textContent = "Schadensstufe wird geprüft …";
    }
    const output = section.querySelector("[data-final-damage]");
    if (output) output.textContent = "—";
    manual(false);
    onChange();
  };

  const addRow = (term) => {
    const row = document.createElement("div");
    row.className = "builder-dice-row";
    const count = document.createElement("input");
    count.type = "number";
    count.min = "0";
    count.max = "10000";
    count.step = "1";
    count.required = true;
    count.value = term.count;
    count.dataset.diceCount = "";
    count.setAttribute("aria-label", "Anzahl der Würfel");
    const sides = document.createElement("select");
    sides.dataset.diceSides = "";
    sides.setAttribute("aria-label", "Würfelart");
    const choices = [...new Set([4, 6, 8, 10, 12, 20, 100, term.sides])].sort((a, b) => a - b);
    choices.forEach((value) => sides.append(new Option(`w${value}`, value, false, value === term.sides)));
    const divisor = document.createElement("input");
    divisor.type = "number";
    divisor.min = "1";
    divisor.max = "10000";
    divisor.step = "1";
    divisor.value = term.divisor === 1 ? "" : term.divisor;
    divisor.placeholder = "1";
    divisor.dataset.diceDivisor = "";
    divisor.setAttribute("aria-label", "Optionaler Divisor");
    [count, sides, divisor].forEach((input) => {
      input.addEventListener(input === sides ? "change" : "input", commit);
    });
    row.append(count, sides, divisor);
    rows.append(row);
  };

  const initialize = (formula) => {
    rows.replaceChildren();
    range = null;
    let fixed = 0;
    const terms = termsOf(formula);
    const dice = terms.filter((term) => term.kind === "dice");
    preserved = dice.length > 1 || terms.some((term) => term.kind === "range");
    terms.forEach((term) => {
      if (term.kind === "constant") fixed += term.value;
      else if (term.kind === "range") range = term;
    });
    if (!preserved) addRow(dice[0] || { count: 0, sides: 10, divisor: 1 });
    bonus.value = fixed;
    field.value = JSON.stringify(formula);
    active.value = "on";
    initialized = true;
    legacy = false;
    header.hidden = preserved;
    bonusLabel.hidden = preserved;
    add.hidden = !preserved;
    preview(formula);
  };
  add.addEventListener("click", () => {
    initialize({ kind: "dice", count: 1, sides: 10, divisor: 1 });
    commit();
  });
  bonus.addEventListener("input", commit);

  if (field.value && field.value !== "null") {
    try { initialize(JSON.parse(field.value)); } catch { /* Server reports invalid draft JSON. */ }
  }

  return {
    update(state) {
      if (!state) return;
      if (state.error) {
        status.hidden = false;
        status.textContent = state.error;
        manual(false);
        preview(null);
        return;
      }
      if (!initialized && state.formula) initialize(state.formula);
      else if (!initialized && !state.display && !form.elements[`${prefix}-id`]?.value) {
        initialize({ kind: "dice", count: 1, sides: 10, divisor: 2 });
        commit();
        return;
      } else if (!initialized) {
        status.hidden = false;
        legacy = true;
        header.hidden = true;
        bonusLabel.hidden = true;
        add.hidden = false;
        add.textContent = "Formel ersetzen";
        manual(true);
        status.textContent = "Bisheriger Schaden bleibt unverändert. Stufe manuell zuordnen oder Formel bearbeiten.";
        const output = damageRow.querySelector("[data-damage-expression]");
        if (output) output.textContent = state.display || "—";
        const stage = section.querySelector("[data-final-damage]");
        if (stage) stage.textContent = state.level ?? "—";
        return;
      }
      if (legacy) return;
      preview(JSON.parse(field.value || "null"));
      const unknown = state.matched_level == null;
      manual(unknown);
      status.textContent = unknown && state.manual_confirmed
        ? `Manuell zugeordnet: Schadensstufe ${state.level}.`
        : unknown
        ? "Keine offizielle Schadensstufe. Stufe manuell angeben und Zuordnung bestätigen."
        : `Kompendium: Schadensstufe ${state.matched_level}.`;
      status.classList.toggle("is-open", unknown && !state.manual_confirmed);
      status.hidden = !unknown && !preserved;
      if (preserved && !unknown) status.textContent = "Gespeicherte zusammengesetzte Formel bleibt erhalten.";
      const output = section.querySelector("[data-final-damage]");
      if (output) output.textContent = state.level ?? "—";
    },
  };
}
