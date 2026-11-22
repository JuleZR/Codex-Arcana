import { initTooltips } from "./tooltip.js";
import { createDamageEditor } from "./creature_damage_editor.js?v=20261121-damage-heading";

const form = document.getElementById("creature-builder");
const rules = new Map(JSON.parse(document.getElementById("creature-power-rules").textContent)
  .map((rule) => [String(rule.id), rule]));
const status = document.querySelector("[data-builder-status]");
const errors = document.querySelector("[data-builder-errors]");
const errorToast = document.querySelector("[data-builder-error-toast]");
const total = document.querySelector("[data-power-total]");
const damageEditors = new Map();
let revision = 0;
let timer;
let saving = false;
let lastPower = null;
let activeErrorKey = "";
const steps = Array.from(form.querySelectorAll("fieldset[data-step]"));
const introPage = document.createElement("section");
introPage.className = "builder-intro-page";
introPage.setAttribute("aria-label", "Kategorie, Name, Größe, Eigenschaften und Initiative");
steps[0].before(introPage);
steps.slice(0, 5).forEach((step) => introPage.append(step));
form.querySelectorAll(".builder-attribute-table input[type='checkbox'], .builder-attribute-table button").forEach((control) => {
  control.tabIndex = -1;
});
let currentStep = 0;

const showStep = (index) => {
  const targetIndex = Math.max(0, Math.min(steps.length - 1, index));
  const intro = targetIndex < 5;
  currentStep = intro ? 0 : targetIndex;
  introPage.hidden = !intro;
  steps.forEach((step, position) => { step.hidden = intro ? position >= 5 : position !== currentStep; });
  document.querySelector("[data-step-back]").hidden = currentStep === 0;
  document.querySelector("[data-step-next]").hidden = currentStep === steps.length - 1;
  document.querySelector("[data-builder-publish]").hidden = currentStep !== steps.length - 1;
  document.querySelector("[data-builder-step-title]").textContent = intro ? `Schritte 1–5 von ${steps.length}` : `Schritt ${currentStep + 1} von ${steps.length}`;
  document.querySelector("[data-builder-progress]").value = intro ? 5 : currentStep + 1;
  if (form.elements._wizard_step) form.elements._wizard_step.value = currentStep + 1;
  const legend = steps[targetIndex].querySelector("legend");
  legend.tabIndex = -1;
  legend.focus({ preventScroll: true });
  if (lastPower) displayPower(lastPower);
};

const nextStep = () => {
  const step = currentStep === 0 ? introPage : steps[currentStep];
  for (const input of step.querySelectorAll("input[name$='-base_value']")) {
    const absent = form.elements[input.name.replace(/-base_value$/, "-absent")];
    input.setCustomValidity(!input.value && !absent?.checked ? "Bonus oder „nicht vorhanden“ wählen." : "");
  }
  const messages = [];
  let firstInvalid = null;
  for (const input of step.querySelectorAll("input, select, textarea")) {
    const row = input.closest(".builder-row");
    const deletion = row?.dataset.attackIndex !== undefined
      ? form.elements[`attacks-${row.dataset.attackIndex}-DELETE`]
      : row?.querySelector("input[name$='-DELETE']");
    if (deletion?.checked) continue;
    if (input.willValidate && !input.checkValidity()) {
      firstInvalid ||= input;
      const ownerLabel = input.labels?.[0];
      const label = (ownerLabel?.querySelector("span")?.textContent || ownerLabel?.textContent || "Eingabe").trim().replace(/:$/, "");
      messages.push(`${label}: ${input.validationMessage}`);
    }
  }
  if (messages.length) {
    showErrors(messages);
    firstInvalid.focus({ preventScroll: true });
    return;
  }
  showStep(currentStep === 0 ? 5 : currentStep + 1);
};
document.querySelector("[data-step-back]").addEventListener("click", () => showStep(currentStep === 5 ? 0 : currentStep - 1));
document.querySelector("[data-step-next]").addEventListener("click", nextStep);

const notifyParent = (data) => {
  if (window.parent !== window) window.parent.postMessage({ creatureBuilder: true, ...data }, window.location.origin);
};

document.querySelectorAll("[data-builder-cancel]").forEach((button) => {
  button.addEventListener("click", () => notifyParent({ cancelled: true }));
});

const errorMessages = (value) => {
  if (typeof value === "string") return [value];
  if (!value || typeof value !== "object") return [];
  return Object.values(value).flatMap(errorMessages);
};

const showErrors = (messages) => {
  const values = [...new Set(messages.filter(Boolean))];
  const key = values.join("\n");
  if (key !== activeErrorKey) {
    activeErrorKey = key;
    errors.replaceChildren();
    values.forEach((message, index) => {
      if (index) errors.append(document.createElement("hr"));
      const line = document.createElement("div");
      line.textContent = message;
      errors.append(line);
    });
  }
  errorToast.hidden = !values.length;
};

const displayPower = (power) => {
  lastPower = power;
  const attackRows = Array.from(form.querySelectorAll("[data-formset='attacks'] [data-formset-rows] > .builder-row"));
  const activeAttacks = attackRows.filter((row) => {
    const index = row.dataset.attackIndex;
    return !form.elements[`attacks-${index}-DELETE`]?.checked
      && form.elements[`attacks-${index}-name`]?.value.trim();
  });
  const prefixes = power.attack_prefixes || activeAttacks.map((row) => `attacks-${row.dataset.attackIndex}`);
  const calculatedAttacks = prefixes.map((prefix) => attackRows.find((row) => `attacks-${row.dataset.attackIndex}` === prefix));
  const resultIndex = (row) => prefixes.indexOf(`attacks-${row.dataset.attackIndex}`) + 1;
  const attackDescriptions = activeAttacks.map((row, index) => {
    const value = power.derived[`attack_${resultIndex(row)}`];
    const name = row.querySelector("input[name$='-name']").value;
    return value === undefined ? name : `${name} ${value}`;
  });
  const attackCost = power.steps.find((step) => Number(step.step) === 6)?.cost;
  const damageCost = power.steps.find((step) => Number(step.step) === 7)?.cost;
  const damageDescriptions = activeAttacks.map((row) => {
    const name = row.querySelector("input[name$='-name']").value;
    const prefix = `attacks-${row.dataset.attackIndex}`;
    const damage = power.damage_previews?.[prefix] || power.damage_editor_states?.[prefix]?.display || "—";
    return `${name} · ${damage}`;
  });
  const attackEntries = attackDescriptions.map((label, index) => ({ label, cost: power.derived[`attack_cost_${resultIndex(activeAttacks[index])}`] }));
  const damageEntries = damageDescriptions.map((label, index) => ({ label, cost: power.derived[`damage_cost_${resultIndex(activeAttacks[index])}`] }));
  const generalAttack = form.elements.general_attack.checked;
  const body = document.querySelector("[data-power-steps]");
  body.replaceChildren();
  for (const step of power.steps) {
    let entries = [{ label: step.label, cost: step.cost }];
    if (Number(step.step) === 6 && attackEntries.length) {
      entries = generalAttack ? [{ label: attackDescriptions.join("\n"), cost: attackCost }] : attackEntries;
    }
    if (Number(step.step) === 7 && damageEntries.length) entries = damageEntries;
    for (const entry of entries) {
    const row = document.createElement("tr");
    const label = document.createElement("td");
    const cost = document.createElement("td");
    const targetIndex = steps.findIndex((target) => Number(target.dataset.step) === Number(step.step));
    const link = document.createElement("button");
    link.type = "button";
    link.className = "builder-step-link";
    link.textContent = `${step.step} · ${entry.label}`;
    link.style.whiteSpace = "pre-line";
    link.disabled = targetIndex < 0;
    if (targetIndex === currentStep || (currentStep === 0 && targetIndex < 5)) link.setAttribute("aria-current", "step");
    row.classList.add("builder-step-target");
    row.addEventListener("click", () => {
      if (!saving && targetIndex >= 0) showStep(targetIndex);
    });
    label.append(link);
    cost.textContent = step.cost == null || entry.cost == null ? "offen" : Number(entry.cost).toLocaleString("de-DE", { maximumFractionDigits: 10 });
    row.classList.toggle("is-open", step.cost === null || Boolean(step.error));
    if (step.error) row.title = step.error;
    row.append(label, cost);
    body.append(row);
    }
  }
  total.textContent = `${Number(power.subtotal).toLocaleString("de-DE", { maximumFractionDigits: 10 })} MP`;
  total.setAttribute("aria-busy", "false");
  form.elements.kp_override.placeholder = power.derived.arcane_power == null ? "Automatisch" : `Automatisch: ${power.derived.arcane_power}`;
  form.elements.potential_override.placeholder = power.derived.potential == null ? "Automatisch" : `Automatisch: ${power.derived.potential}`;
  const derived = document.querySelector("[data-derived-values]");
  attackRows.forEach((row) => {
    const output = row.querySelector("[data-final-attack]");
    if (output) output.textContent = "—";
  });
  form.querySelectorAll("[data-damage-rows] [data-attack-index]").forEach((row) => {
    const prefix = `attacks-${row.dataset.attackIndex}`;
    row.querySelector("[data-final-damage]").textContent = "—";
    row.querySelector("[data-damage-expression]").textContent = power.damage_previews?.[`attacks-${row.dataset.attackIndex}`] || "—";
    damageEditors.get(row.dataset.attackIndex)?.update(power.damage_editor_states?.[prefix]);
  });
  const labels = { size_modifier: "GK-Modifikator", initiative: "Initiative", vw: "VW", sr: "SR", gw: "GW", wound_step: "LP pro Wundgrad", arcane_power: "Arkane Macht", potential: "Potential" };
  derived.replaceChildren();
  for (const [key, value] of Object.entries(power.derived)) {
    if (/^(attack|damage)_cost_/.test(key)) continue;
    const damageMatch = key.match(/^damage_(\d+)$/);
    if (damageMatch) {
      const damageRow = calculatedAttacks[Number(damageMatch[1]) - 1];
      const output = form.querySelector(`[data-damage-rows] [data-attack-index='${damageRow?.dataset.attackIndex}'] [data-final-damage]`);
      if (output) output.textContent = value;
    }
    const name = document.createElement("dt");
    const content = document.createElement("dd");
    if (damageMatch && damageDescriptions.length) {
      const entry = damageEntries[activeAttacks.indexOf(calculatedAttacks[Number(damageMatch[1]) - 1])];
      name.textContent = entry?.label || `Schaden ${damageMatch[1]}`;
      content.textContent = damageCost == null || entry?.cost == null ? "offen" : Number(entry.cost).toLocaleString("de-DE", { maximumFractionDigits: 10 });
      derived.append(name, content);
      continue;
    }
    const attackMatch = key.match(/^attack_(\d+)$/);
    const attackRow = attackMatch ? calculatedAttacks[Number(attackMatch[1]) - 1] : null;
    const attackName = attackRow?.querySelector("input[name$='-name']")?.value;
    name.textContent = attackName || labels[key] || key.replace(/^attack_/, "Angriffswert ").replace(/^damage_/, "Schadensstufe ");
    if (attackRow) attackRow.querySelector("[data-final-attack]").textContent = value;
    if (attackRow) {
      const entry = attackEntries[activeAttacks.indexOf(attackRow)];
      name.textContent = entry.label;
      const cost = generalAttack ? attackCost : entry.cost;
      content.textContent = generalAttack && Number(attackMatch[1]) > 1 ? "" : cost == null ? "offen" : Number(cost).toLocaleString("de-DE", { maximumFractionDigits: 10 });
      derived.append(name, content);
      continue;
    }
    content.textContent = value;
    derived.append(name, content);
  }
  document.querySelector("[data-natural-survival-status]").hidden = !power.natural_survival_eligible;
  form.querySelectorAll("[data-formset='skills'] [data-formset-rows] > .builder-row").forEach((row) => {
    const select = row.querySelector("select[name$='-skill']");
    const prefix = select.name.replace(/-skill$/, "");
    const preview = power.skill_previews?.[prefix];
    const output = row.querySelector("[data-skill-total]");
    if (!output) return;
    output.closest(".builder-skill-effective").hidden = !select.value;
    output.textContent = preview ? preview.total : "—";
    if (preview) {
      const signed = (value) => value >= 0 ? `+${value}` : String(value);
      const deviation = Number(form.elements[`${prefix}-deviation`].value || 0);
      output.title = `${preview.level} Stufen · Abweichung ${signed(deviation)} · ${preview.attribute} ${signed(preview.attribute_bonus)} · GK ${signed(preview.size_bonus)} · weitere Boni ${signed(preview.other_bonus)} = ${preview.total}${preview.natural_survival ? " · bis Gesamtwert 6 natürlich kostenlos" : ""}`;
    } else output.title = "";
  });
  const visibleStep = currentStep === 0 ? 5 : currentStep + 1;
  showErrors([
    ...power.steps.filter((step) => step.error && step.step <= visibleStep)
      .map((step) => `${step.label}: ${step.error}`),
    ...(power.validation_errors || []).filter((error) => error.step <= visibleStep)
      .map((error) => error.message),
  ]);
};

const send = async (action) => {
  const current = ++revision;
  const body = new FormData(form);
  body.set("action", action);
  if (action !== "preview") {
    saving = true;
    form.querySelectorAll("button").forEach((button) => { button.disabled = true; });
  }
  try {
    const response = await fetch(window.location.href, { method: "POST", body, headers: { "X-Requested-With": "XMLHttpRequest" } });
    const result = await response.json();
    if (current !== revision) return;
    if (result.power) displayPower(result.power);
    if (!response.ok || !result.ok) {
      if (!result.power) total.textContent = "—";
      if (result.error || result.errors) showErrors(result.error ? [result.error] : errorMessages(result.errors));
      status.textContent = "";
      return;
    }
    if (result.saved) {
      status.textContent = "Kreatur gespeichert. Rückkehr zur Wildcard …";
      notifyParent({ saved: true, id: result.id, name: result.name, instanceName: result.instance_name, typeId: result.type_id });
    } else if (result.draft) {
      status.textContent = result.message;
      window.history.replaceState(null, "", result.url);
    } else {
      status.textContent = "";
    }
  } catch {
    total.textContent = "—";
    status.textContent = "";
    showErrors(["Die Anfrage konnte nicht abgeschlossen werden. Bitte erneut versuchen."]);
  } finally {
    if (current === revision) total.setAttribute("aria-busy", "false");
    if (action !== "preview") {
      saving = false;
      form.querySelectorAll("button").forEach((button) => { button.disabled = false; });
    }
  }
};

const schedulePreview = () => {
  if (saving) return;
  clearTimeout(timer);
  total.setAttribute("aria-busy", "true");
  ++revision;
  timer = setTimeout(() => send("preview"), 350);
};

const prepareAbility = (row) => {
  const select = row.querySelector("select[name$='-rule']");
  const deletion = row.querySelector("input[name$='-DELETE']");
  if (deletion) {
    row.hidden = deletion.checked;
    deletion.closest("p").hidden = true;
    let remove = row.querySelector("[data-remove-ability]");
    if (!remove) {
      remove = createRemoveButton();
      remove.dataset.removeAbility = "";
      remove.addEventListener("click", () => {
        deletion.checked = true;
        row.hidden = true;
        deletion.dispatchEvent(new Event("change", { bubbles: true }));
        const next = form.querySelector("[data-ability-row]:not([hidden]) select[name$='-rule']")
          || form.querySelector("[data-formset='abilities'] [data-add-row]");
        next.focus({ preventScroll: true });
      });
      row.append(remove);
    }
    remove.setAttribute("aria-label", `${select.value ? select.selectedOptions[0].text : "Fähigkeit"} entfernen`);
  }
  const rule = rules.get(select.value);
  const previous = Object.fromEntries(Array.from(row.querySelectorAll("input[name*='-param_'], select[name*='-param_']"))
    .map((input) => [input.name, input.value]));
  row.querySelectorAll("[data-ability-parameters], [data-ability-help]").forEach((element) => element.remove());
  row.querySelectorAll("p").forEach((element) => {
    if (element.querySelector("input[name*='-param_']")) element.remove();
  });
  if (!rule) return;
  const help = document.createElement("p");
  help.dataset.abilityHelp = "";
  help.textContent = rule.description || "";
  help.hidden = !help.textContent;
  row.append(help);
  const parameters = document.createElement("div");
  parameters.dataset.abilityParameters = "";
  for (const [key, spec] of Object.entries(rule.parameters)) {
    const label = document.createElement("label");
    label.className = "shop_item_form_row";
    label.textContent = spec.label || key;
    const input = document.createElement(spec.choices ? "select" : "input");
    input.name = select.name.replace(/-rule$/, `-param_${key}`);
    if (spec.choices) {
      input.add(new Option("Bitte wählen", ""));
      spec.choices.forEach((value) => input.add(new Option(String(value), String(value))));
    } else {
      input.type = "number";
      input.step = spec.integer ? "1" : "any";
      if (spec.min !== undefined) input.min = spec.min;
      if (spec.max !== undefined) input.max = spec.max;
    }
    input.required = true;
    input.value = previous[input.name] ?? "";
    label.append(input);
    parameters.append(label);
  }
  row.append(parameters);
};

const filterAbilities = () => {
  const category = form.elements.category.value;
  form.elements.element.closest("label").hidden = category !== "EW";
  const vampire = category === "V";
  form.elements.has_kp.closest("label").hidden = vampire;
  document.querySelector("[data-arcane-label]").textContent = vampire ? "Blutpunkte" : "Arkane Macht";
  const categories = new Set([category]);
  if (["W", "KU", "GU", "V"].includes(category)) categories.add("U");
  if (category === "EW") categories.add(`EW_${form.elements.element.value}`);
  form.querySelectorAll("select[name$='-rule']").forEach((select) => {
    Array.from(select.options).forEach((option) => {
      const rule = rules.get(option.value);
      const allowed = !category || !rule || !rule.categories.length || rule.categories.some((key) => categories.has(key));
      option.hidden = !allowed && !option.selected;
      option.disabled = !allowed && !option.selected;
    });
  });
};

const prepareMovement = () => {
  const completeSwimming = ["combat_swimming_speed", "march_swimming_speed", "sprint_swimming_speed"]
    .every((name) => form.elements[name].value.trim() !== "");
  const single = form.elements.swimming_speed;
  single.disabled = completeSwimming;
  single.closest("label").hidden = completeSwimming;
  document.querySelector("[data-single-swim-unavailable]").hidden = !completeSwimming;
};

const createRemoveButton = () => {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "builder-attack-remove workshop_submit";
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("viewBox", "0 0 16 16");
  icon.setAttribute("aria-hidden", "true");
  const cross = document.createElementNS("http://www.w3.org/2000/svg", "path");
  cross.setAttribute("d", "M4 4L12 12M12 4L4 12");
  cross.setAttribute("fill", "none");
  cross.setAttribute("stroke", "currentColor");
  cross.setAttribute("stroke-width", "2");
  cross.setAttribute("stroke-linecap", "round");
  icon.append(cross);
  button.append(icon);
  return button;
};

const prepareLanguages = () => {
  form.querySelectorAll("[data-formset='languages'] [data-formset-rows] > .builder-row").forEach((row) => {
    const deletion = row.querySelector("input[name$='-DELETE']");
    if (!deletion) return;
    row.classList.add("builder-language-row");
    row.hidden = deletion.checked;
    deletion.closest("p").hidden = true;
    if (row.querySelector("[data-remove-language]")) return;
    const remove = createRemoveButton();
    remove.dataset.removeLanguage = "";
    remove.setAttribute("aria-label", "Sprache entfernen");
    remove.addEventListener("click", () => {
      deletion.checked = true;
      deletion.dispatchEvent(new Event("change", { bubbles: true }));
      form.querySelector("[data-formset='languages'] [data-add-row]").focus({ preventScroll: true });
    });
    row.append(remove);
  });
};

const prepareSkills = () => {
  form.querySelectorAll("[data-formset='skills'] [data-formset-rows] > .builder-row").forEach((row) => {
    const deletion = row.querySelector("input[name$='-DELETE']");
    if (!deletion) return;
    row.classList.add("builder-skill-row");
    row.hidden = deletion.checked;
    deletion.closest("p").hidden = true;
    let remove = row.querySelector("[data-remove-skill]");
    if (!remove) {
      remove = createRemoveButton();
      remove.dataset.removeSkill = "";
      remove.addEventListener("click", () => {
        deletion.checked = true;
        deletion.dispatchEvent(new Event("change", { bubbles: true }));
        const next = form.querySelector("[data-formset='skills'] .builder-row:not([hidden]) select[name$='-skill']")
          || form.querySelector("[data-formset='skills'] [data-add-row]");
        next.focus({ preventScroll: true });
      });
      row.append(remove);
    }
    const select = row.querySelector("select[name$='-skill']");
    const prefix = select.name.replace(/-skill$/, "");
    ["skill", "level", "deviation", "notes"].forEach((field, index) => {
      form.elements[`${prefix}-${field}`].closest("p").style.order = field === "notes" ? 4 : index;
    });
    if (!row.querySelector("[data-skill-total]")) {
      const effective = document.createElement("div");
      effective.className = "builder-skill-effective shop_item_form_row";
      effective.style.order = 3;
      const caption = document.createElement("label");
      caption.textContent = "Effektiver Wert";
      const output = document.createElement("output");
      output.id = `${prefix}-effective-value`;
      output.dataset.skillTotal = "";
      output.setAttribute("aria-live", "polite");
      output.textContent = "—";
      caption.htmlFor = output.id;
      effective.append(caption, output);
      row.append(effective);
    }
    row.querySelector(".builder-skill-effective").hidden = !select.value;
    remove.setAttribute("aria-label", `${select.value ? select.selectedOptions[0].text : "Fertigkeit"} entfernen`);
  });
};

const prepareAttacks = () => {
  const attackFields = new Set(["name", "attack_type", "attack_value", "automatic_attack", "attack_bonus", "order", "DELETE"]);
  form.querySelectorAll("[data-formset='attacks'] [data-formset-rows] > .builder-row").forEach((row) => {
    const name = row.querySelector("input[name$='-name']");
    const index = name.name.split("-")[1];
    row.dataset.attackIndex = index;
    row.classList.add("builder-attack-row");
    let damage = form.querySelector(`[data-damage-rows] [data-attack-index='${index}']`);
    if (!damage) {
      damage = document.createElement("div");
      damage.className = "builder-row builder-damage-row";
      damage.dataset.attackIndex = index;
      const title = document.createElement("strong");
      title.dataset.damageAttackName = "";
      const heading = document.createElement("header");
      heading.className = "builder-damage-heading";
      heading.append(title);
      damage.append(heading);
      document.querySelector("[data-damage-rows]").append(damage);
      Array.from(row.querySelectorAll("p")).forEach((part) => {
        const control = part.querySelector("input:not([type='hidden']), select, textarea");
        if (control && !attackFields.has(control.name.replace(/^attacks-\d+-/, ""))) damage.append(part);
      });
      const groups = [
        ["Schadensformel", "Ein Würfelblock je Angriff: Anzahl, Würfelart, optionaler Teiler und fester Bonus oder Malus. Anzahl 0 bedeutet festen Schaden ohne Würfel. B- oder T-Schaden hat dieselben Machtkosten. Die Schadensstufe folgt der passenden Formel auf S. 465, niemals einem Durchschnitt. Unbekannte Formeln benötigen eine bestätigte manuelle Stufenzuordnung. Die Kosten vergleichen diese Stufe mit der Grundstufe aus Stärke; der Vorteil Ätherisch ändert diese Berechnung automatisch.", ["damage_level", "damage_level_confirmed", "damage_type"]],
        ["Schadensart", "Körperliche und andere kostenlose Schadensarten kosten keinen Aufschlag. Feuer mit Entflammchance: Schadenskosten × 1,25. Rüstungsumgehende Energie: × 2. Säure: zusätzlich halbe Säuremacht. Jede weitere kostenlose Schadensart kostet zusätzlich 3.", ["damage_kind", "acid_power", "extra_damage_types"]],
        ["Reichweite und Hinweis", "0 m bedeutet Nahkampf. Für Fernkampf geben Sie die kurze Reichweite an: jeder Meter erhöht die Machtkosten um 1. Mittlere Reichweite = doppelte, weite Reichweite = vierfache kurze Reichweite. Der Hinweis ist optional und verändert die Machtkosten nicht.", ["short_range", "notes"]],
      ];
      groups.forEach(([groupLabel, help, fields]) => {
        const section = document.createElement("section");
        section.className = "builder-damage-group";
        section.dataset.damageGroup = fields.includes("damage_level") ? "formula" : fields.includes("damage_kind") ? "kind" : "range";
        const title = document.createElement("h4");
        title.textContent = groupLabel;
        const info = document.createElement("button");
        info.type = "button";
        info.className = "builder-info tooltip_target";
        info.dataset.tooltipTrigger = "click";
        info.dataset.tooltip = help;
        info.setAttribute("aria-label", `Informationen: ${groupLabel}`);
        info.textContent = "i";
        title.append(info);
        section.append(title);
        if (fields.includes("damage_level")) {
          damageEditors.set(index, createDamageEditor(form, index, section, schedulePreview));
        }
        fields.forEach((field) => {
          const control = form.elements[`attacks-${index}-${field}`];
          const part = control?.closest("p");
          if (!part) return;
          part.dataset.damageField = field;
          const label = part.querySelector("label");
          const captions = { automatic_damage: "Aus Stärke berechnen", damage_adjustment: "Anpassung der Schadensstufe (+ / −)", damage_level: "Feste Schadensstufe", damage_type: "B- oder T-Schaden", damage_kind: "Schadensart", acid_power: "Macht der Säure", extra_damage_types: "Anzahl zusätzlicher kostenloser Schadensarten", short_range: "Kurze Reichweite (m; 0 = Nahkampf)", notes: "Hinweis zum Schaden (optional)" };
          const compactCaptions = { damage_type: "B / T", damage_kind: "Schadensart", acid_power: "Säuremacht", short_range: "Reichweite (m)", extra_damage_types: "Zusatzarten", notes: "Hinweis" };
          if (!["damage_level", "damage_level_confirmed"].includes(field)) label.textContent = compactCaptions[field] || captions[field];
          section.append(part);
        });
        if (fields.includes("damage_level")) {
          const result = document.createElement("p");
          result.className = "builder-damage-result";
          result.append("Stufe: ");
          const output = document.createElement("output");
          output.dataset.finalDamage = "";
          output.textContent = "—";
          result.append(output);
          section.append(result);
          const expression = document.createElement("p");
          expression.className = "builder-damage-result";
          expression.append("· ");
          const damageOutput = document.createElement("output");
          damageOutput.dataset.damageExpression = "";
          damageOutput.textContent = "—";
          expression.append(damageOutput);
          heading.append(expression);
        }
        damage.append(section);
      });
    }
    damage.querySelector("[data-damage-attack-name]").textContent = name.value || `Angriff ${Number(index) + 1}`;
    const deletion = form.elements[`attacks-${index}-DELETE`];
    row.hidden = Boolean(deletion?.checked);
    damage.hidden = row.hidden;
    if (deletion) {
      deletion.closest("p").hidden = true;
      let remove = row.querySelector("[data-remove-attack]");
      if (!remove) {
        remove = createRemoveButton();
        remove.dataset.removeAttack = "";
        remove.addEventListener("click", () => {
          deletion.checked = true;
          deletion.dispatchEvent(new Event("change", { bubbles: true }));
          const next = form.querySelector("[data-formset='attacks'] .builder-row:not([hidden]) input[name$='-name']")
            || form.querySelector("[data-formset='attacks'] [data-add-row]");
          next.focus({ preventScroll: true });
        });
        row.append(remove);
      }
      remove.setAttribute("aria-label", `${name.value || "Angriff"} entfernen`);
    }
    const automaticAttack = form.elements[`attacks-${index}-automatic_attack`]?.checked;
    const attackOrder = ["name", "attack_type", "automatic_attack", "attack_bonus", "attack_value", "DELETE"];
    attackOrder.forEach((field, position) => {
      const control = form.elements[`attacks-${index}-${field}`];
      const part = control?.closest("p");
      if (!part) return;
      part.style.order = position;
      part.dataset.attackField = field;
      const label = part.querySelector("label");
      if (field === "automatic_attack") label.textContent = "Automatisch berechnen (GE + GK + Bonus)";
      if (field === "DELETE") label.textContent = "Angriff entfernen";
      if (field === "attack_value") label.textContent = "Fester Angriffswert";
      if (field === "attack_bonus") part.hidden = !automaticAttack;
    });
    const orderControl = form.elements[`attacks-${index}-order`];
    if (orderControl) orderControl.closest("p").hidden = true;
    if (!row.querySelector("[data-final-attack]")) {
      const result = document.createElement("div");
      result.className = "builder-attack-result shop_item_form_row";
      result.style.order = 4;
      const caption = document.createElement("label");
      caption.textContent = "Angriffswert: ";
      const output = document.createElement("output");
      output.id = `attacks-${index}-computed-attack`;
      caption.htmlFor = output.id;
      output.dataset.finalAttack = "";
      output.textContent = "—";
      result.append(caption, output);
      row.append(result);
    }
    const fixedAttack = form.elements[`attacks-${index}-attack_value`];
    if (fixedAttack) {
      fixedAttack.closest("p").hidden = automaticAttack;
      fixedAttack.required = !automaticAttack;
    }
    const level = form.elements[`attacks-${index}-damage_level`];
    form.elements[`attacks-${index}-damage_adjustment`].closest("p").hidden = true;
    form.elements[`attacks-${index}-automatic_damage`].closest("p").hidden = true;
    form.elements[`attacks-${index}-acid_power`].closest("p").hidden = form.elements[`attacks-${index}-damage_kind`].value !== "acid";
  });
};

form.querySelectorAll("[data-ability-row]").forEach(prepareAbility);
const useWorkshopRows = () => {
  form.querySelectorAll(".builder-fields p, .builder-row p").forEach((row) => row.classList.add("shop_item_form_row"));
};
useWorkshopRows();
prepareLanguages();
prepareAttacks();
prepareSkills();
prepareMovement();
filterAbilities();
showStep((Number(form.elements._wizard_step?.value) || 1) - 1);
form.addEventListener("click", (event) => {
  const add = event.target.closest("[data-add-row]");
  if (!add) return;
  const section = add.closest("[data-formset]");
  const count = section.querySelector("input[name$='-TOTAL_FORMS']");
  const content = section.querySelector("template").innerHTML.replaceAll("__prefix__", count.value);
  section.querySelector("[data-formset-rows]").insertAdjacentHTML("beforeend", content);
  count.value = Number(count.value) + 1;
  section.querySelectorAll("[data-ability-row]").forEach(prepareAbility);
  useWorkshopRows();
  prepareLanguages();
  prepareAttacks();
  prepareSkills();
  filterAbilities();
});
form.addEventListener("input", () => {
  prepareMovement();
  schedulePreview();
});
form.addEventListener("change", (event) => {
  prepareLanguages();
  prepareAttacks();
  prepareSkills();
  if (event.target.matches("select[name$='-rule']")) prepareAbility(event.target.closest("[data-ability-row]"));
  if (["category", "element"].includes(event.target.name)) filterAbilities();
  schedulePreview();
});
form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (currentStep < steps.length - 1) {
    nextStep();
    return;
  }
  clearTimeout(timer);
  if (!saving) send("publish");
});
document.querySelector("[data-save-draft]").addEventListener("click", () => {
  clearTimeout(timer);
  if (!saving) send("draft");
});
document.querySelector("[data-builder-duplicate-url]")?.addEventListener("click", (event) => {
  window.location.assign(event.currentTarget.dataset.builderDuplicateUrl);
});
initTooltips();
schedulePreview();
