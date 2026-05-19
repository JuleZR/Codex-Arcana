import { parseJsonScript, readInt } from "./utils.js";

const STORAGE_KEY = "charsheet.battleCalculator.state";

function rollD10() {
  return Math.floor(Math.random() * 10) + 1;
}

function loadState() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (_error) {
    return {};
  }
}

function saveState(state) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (_error) {
    // no-op
  }
}

function formatSigned(value) {
  if (value > 0) {
    return `+${value}`;
  }
  if (value < 0) {
    return `-${Math.abs(value)}`;
  }
  return "0";
}

function buildSelectOptions(select, options, placeholder) {
  select.innerHTML = "";
  if (!options.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = placeholder;
    select.append(option);
    return;
  }
  for (const entry of options) {
    const option = document.createElement("option");
    option.value = entry.id;
    option.textContent = entry.label;
    select.append(option);
  }
}

function cleanModifierText(value) {
  return String(value || "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/__(.*?)__/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

function renderModifierList(container, entries, emptyLabel) {
  container.innerHTML = "";
  if (!entries.length) {
    const empty = document.createElement("li");
    empty.className = "combat-calculator__modifier-empty";
    empty.textContent = emptyLabel;
    container.append(empty);
    return;
  }
  for (const entry of entries) {
    const item = document.createElement("li");
    const numericMatch = String(entry.value || "").match(/^[+\-]\d+/);
    const numericValue = numericMatch ? Number.parseInt(numericMatch[0], 10) : 0;
    item.className = "combat-calculator__modifier-item";
    if (numericValue > 0) {
      item.classList.add("is-positive");
    } else if (numericValue < 0) {
      item.classList.add("is-negative");
    }

    const main = document.createElement("div");
    main.className = "combat-calculator__modifier-main";
    const mark = document.createElement("span");
    mark.className = "combat-calculator__modifier-mark";
    mark.textContent = "\u2726";
    const label = document.createElement("span");
    label.className = "combat-calculator__modifier-label";
    label.textContent = cleanModifierText(entry.label || "Modifier");
    main.append(mark, label);
    if (entry.source) {
      const source = document.createElement("span");
      source.className = "combat-calculator__modifier-source";
      source.textContent = cleanModifierText(entry.source);
      main.append(source);
    }

    const value = document.createElement("span");
    value.className = "combat-calculator__modifier-value";
    value.textContent = entry.value || "0";

    item.append(main, value);
    container.append(item);
  }
}

function setAnimatedValue(element, nextValue) {
  const nextText = String(nextValue);
  element.dataset.displayValue = nextText;
  element.textContent = nextText;
}

export function initBattleCalculator() {
  const root = document.getElementById("battleCalculatorRoot");
  if (!root || root.dataset.battleCalculatorBound === "1") {
    return;
  }
  root.dataset.battleCalculatorBound = "1";

  const payload = parseJsonScript("battle-calculator-data", {
    attack_options: [],
    weapon_options: [],
    meta: {},
  });
  const attackOptions = Array.isArray(payload.attack_options) ? payload.attack_options : [];
  const weaponOptions = Array.isArray(payload.weapon_options) ? payload.weapon_options : [];
  const attackById = new Map(attackOptions.map((entry) => [entry.id, entry]));
  const weaponById = new Map(weaponOptions.map((entry) => [entry.id, entry]));

  const attackSkillSelect = document.getElementById("battleCalculatorAttackSkill");
  const weaponSelect = document.getElementById("battleCalculatorWeapon");
  const maneuverValueInput = document.getElementById("battleCalculatorManeuverValue");
  const usedApInput = document.getElementById("battleCalculatorUsedAp");
  const accumulatedSuccessesInput = document.getElementById("battleCalculatorAccumulatedSuccesses");
  const multipleActionInput = document.getElementById("battleCalculatorMultipleAction");
  const attackDieOneInput = document.getElementById("battleCalculatorAttackDieOne");
  const attackDieTwoInput = document.getElementById("battleCalculatorAttackDieTwo");
  const attackFormula = document.getElementById("battleCalculatorAttackFormula");
  const attackTotal = document.getElementById("battleCalculatorAttackTotal");
  const attackDieOneDisplay = document.getElementById("battleCalculatorAttackDieOneDisplay");
  const attackDieTwoDisplay = document.getElementById("battleCalculatorAttackDieTwoDisplay");
  const attackDieOneButtons = document.getElementById("battleCalculatorAttackDieOneButtons");
  const attackDieTwoButtons = document.getElementById("battleCalculatorAttackDieTwoButtons");
  const attackResetButton = document.getElementById("battleCalculatorAttackReset");
  const damageDiceAmountInput = document.getElementById("battleCalculatorDamageDiceAmount");
  const flatOperatorSelect = document.getElementById("battleCalculatorFlatOperator");
  const flatBonusInput = document.getElementById("battleCalculatorFlatBonus");
  const bonusSuccessesInput = document.getElementById("battleCalculatorBonusSuccesses");
  const manualBonusInput = document.getElementById("battleCalculatorManualBonus");
  const multiplierInput = document.getElementById("battleCalculatorMultiplier");
  const damageDiceList = document.getElementById("battleCalculatorDamageDiceList");
  const damageResetButton = document.getElementById("battleCalculatorDamageReset");
  const damageFormula = document.getElementById("battleCalculatorDamageFormula");
  const damageTotal = document.getElementById("battleCalculatorDamageTotal");
  const attackModifiersList = document.getElementById("battleCalculatorAttackModifiers");
  const damageModifiersList = document.getElementById("battleCalculatorDamageModifiers");
  const modifierHighlights = document.getElementById("battleCalculatorModifierHighlights");
  const damageDiceDisplay = document.getElementById("battleCalculatorDamageDiceDisplay");
  const flatBonusField = document.getElementById("battleCalculatorFlatBonusField");
  const bonusSuccessesField = document.getElementById("battleCalculatorBonusSuccessesField");
  const manualBonusField = document.getElementById("battleCalculatorManualBonusField");
  const multiplierField = document.getElementById("battleCalculatorMultiplierField");
  const attackPanel = document.getElementById("battleCalculatorAttackPanel");
  const damagePanel = document.getElementById("battleCalculatorDamagePanel");
  const resultPanel = document.getElementById("battleCalculatorResultPanel");

  if (
    !attackSkillSelect
    || !weaponSelect
    || !maneuverValueInput
    || !usedApInput
    || !accumulatedSuccessesInput
    || !multipleActionInput
    || !attackDieOneInput
    || !attackDieTwoInput
    || !attackFormula
    || !attackTotal
    || !attackDieOneDisplay
    || !attackDieTwoDisplay
    || !attackDieOneButtons
    || !attackDieTwoButtons
    || !attackResetButton
    || !damageDiceAmountInput
    || !flatOperatorSelect
    || !flatBonusInput
    || !bonusSuccessesInput
    || !manualBonusInput
    || !multiplierInput
    || !damageDiceList
    || !damageResetButton
    || !damageFormula
    || !damageTotal
    || !attackModifiersList
    || !damageModifiersList
    || !modifierHighlights
    || !damageDiceDisplay
    || !flatBonusField
    || !bonusSuccessesField
    || !manualBonusField
    || !multiplierField
    || !attackPanel
    || !damagePanel
    || !resultPanel
  ) {
    return;
  }

  let attackPulseTimer = null;
  let damagePulseTimer = null;
  let attackValueCache = null;
  let damageValueCache = null;

  function pulsePanel(panel, timerKey) {
    panel.classList.remove("is-recalculating");
    void panel.offsetWidth;
    panel.classList.add("is-recalculating");
    if (timerKey === "attack") {
      window.clearTimeout(attackPulseTimer);
      attackPulseTimer = window.setTimeout(() => panel.classList.remove("is-recalculating"), 360);
    } else {
      window.clearTimeout(damagePulseTimer);
      damagePulseTimer = window.setTimeout(() => panel.classList.remove("is-recalculating"), 360);
    }
  }

  buildSelectOptions(attackSkillSelect, attackOptions, "Keine Fertigkeiten verfügbar");
  buildSelectOptions(weaponSelect, weaponOptions, "Keine Waffen ausgerüstet");

  const persistedState = loadState();
  const preferredAttackId = attackById.has(persistedState.attackSkillId) ? persistedState.attackSkillId : attackOptions[0]?.id || "";
  const preferredWeaponId = weaponById.has(persistedState.weaponId) ? persistedState.weaponId : weaponOptions[0]?.id || "";
  if (preferredAttackId) {
    attackSkillSelect.value = preferredAttackId;
  }
  if (preferredWeaponId) {
    weaponSelect.value = preferredWeaponId;
  }

  function currentAttack() {
    return attackById.get(attackSkillSelect.value) || null;
  }

  function currentWeapon() {
    return weaponById.get(weaponSelect.value) || null;
  }

  function currentDamageDiceValues() {
    return [...damageDiceList.querySelectorAll("[data-damage-die-value]")].map((input) => Math.max(0, readInt(input.value, 0)));
  }

  function syncAttackDieButtons(container, value) {
    for (const button of container.querySelectorAll("button")) {
      button.classList.toggle("is-selected", Number(button.dataset.value) === value);
    }
  }

  function syncDamageDieButtons(group, value) {
    for (const button of group.querySelectorAll(".combat-calculator__die-button")) {
      button.classList.toggle("is-selected", Number(button.dataset.value) === value);
    }
  }

  function saveCurrentState() {
    saveState({
      attackSkillId: attackSkillSelect.value,
      weaponId: weaponSelect.value,
      usedAp: readInt(usedApInput.value, 0),
      sharedSuccesses: readInt(accumulatedSuccessesInput.value, 0),
      multipleAction: readInt(multipleActionInput.value, 0),
      attackDieOne: readInt(attackDieOneInput.value, 0),
      attackDieTwo: readInt(attackDieTwoInput.value, 0),
      manualBonus: readInt(manualBonusInput.value, 0),
      multiplier: Math.max(1, readInt(multiplierInput.value, 1)),
      flatBonus: Math.max(0, readInt(flatBonusInput.value, 0)),
      flatOperator: flatOperatorSelect.value,
      damageDiceAmount: Math.max(1, readInt(damageDiceAmountInput.value, 1)),
      damageDiceValues: currentDamageDiceValues(),
    });
  }

  function renderDamageDiceList(preserveValues = true) {
    const previousValues = preserveValues ? currentDamageDiceValues() : [];
    const amount = Math.max(1, readInt(damageDiceAmountInput.value, 1));
    damageDiceList.innerHTML = "";
    for (let index = 0; index < amount; index += 1) {
      const label = document.createElement("div");
      label.className = "combat-calculator__field combat-calculator__damage-die";
      const row = document.createElement("div");
      row.className = "combat-calculator__die-row";
      const title = document.createElement("span");
      title.className = "combat-calculator__die-label";
      title.textContent = `Wurf ${index + 1}`;
      const hiddenInput = document.createElement("input");
      hiddenInput.type = "hidden";
      hiddenInput.value = String(previousValues[index] ?? 0);
      hiddenInput.dataset.damageDieValue = "1";
      const buttonGrid = document.createElement("div");
      buttonGrid.className = "combat-calculator__die-button-grid";

      function selectValue(nextValue) {
        hiddenInput.value = String(nextValue);
        syncDamageDieButtons(label, nextValue);
        updateDamageResult();
        renderModifierPanels();
        saveCurrentState();
      }

      for (let face = 1; face <= 10; face += 1) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "combat-calculator__die-button";
        button.dataset.value = String(face);
        button.textContent = String(face);
        button.addEventListener("click", () => selectValue(face));
        buttonGrid.append(button);
      }

      row.append(title, buttonGrid);
      label.append(row, hiddenInput);
      damageDiceList.append(label);
      selectValue(Math.max(0, readInt(hiddenInput.value, 0)));
    }
  }

  function renderAttackDieButtons(container, input) {
    container.innerHTML = "";

    function selectValue(nextValue) {
      input.value = String(nextValue);
      syncAttackDieButtons(container, nextValue);
      updateAttackResult();
      updateDamageResult();
      renderModifierPanels();
      saveCurrentState();
    }

    for (let face = 1; face <= 10; face += 1) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "combat-calculator__die-button";
      button.dataset.value = String(face);
      button.textContent = String(face);
      button.addEventListener("click", () => selectValue(face));
      container.append(button);
    }

    selectValue(Math.max(0, readInt(input.value, 0)));
  }

  function renderDiceFocus() {
    attackDieOneDisplay.textContent = String(Math.max(0, readInt(attackDieOneInput.value, 0)));
    attackDieTwoDisplay.textContent = String(Math.max(0, readInt(attackDieTwoInput.value, 0)));
    damageDiceDisplay.innerHTML = "";
    for (const value of currentDamageDiceValues()) {
      const plate = document.createElement("span");
      plate.className = "combat-calculator__die-plate";
      plate.textContent = String(value);
      damageDiceDisplay.append(plate);
    }
    if (!damageDiceDisplay.children.length) {
      const plate = document.createElement("span");
      plate.className = "combat-calculator__die-plate";
      plate.textContent = "0";
      damageDiceDisplay.append(plate);
    }
  }

  function syncAttackFromSelectedSkill() {
    const option = currentAttack();
    maneuverValueInput.value = String(readInt(option?.maneuver_value, 0));
  }

  function syncSharedSuccesses(value) {
    const normalized = String(Math.max(0, readInt(value, 0)));
    accumulatedSuccessesInput.value = normalized;
    bonusSuccessesInput.value = normalized;
  }

  function ensureMatchingAttackSkill(weapon) {
    if (!weapon || !Array.isArray(weapon.skill_ids) || !weapon.skill_ids.length) {
      return;
    }
    const current = currentAttack();
    if (current && weapon.skill_ids.includes(readInt(current.skill_id, 0))) {
      return;
    }
    const next = attackOptions.find((entry) => weapon.skill_ids.includes(readInt(entry.skill_id, 0)));
    if (next) {
      attackSkillSelect.value = next.id;
      syncAttackFromSelectedSkill();
    }
  }

  function syncDamageFromWeapon() {
    const weapon = currentWeapon();
    if (!weapon) {
      damageDiceAmountInput.value = "1";
      flatBonusInput.value = "0";
      flatOperatorSelect.value = "+";
      manualBonusInput.value = "0";
      renderDamageDiceList(false);
      return;
    }
    damageDiceAmountInput.value = String(Math.max(1, readInt(weapon.dice_amount, 1)));
    flatBonusInput.value = String(Math.max(0, readInt(weapon.flat_bonus, 0)));
    flatOperatorSelect.value = String(weapon.flat_operator || "+");
    manualBonusInput.value = String(readInt(weapon.damage_modifier, 0));
    renderDamageDiceList(false);
    ensureMatchingAttackSkill(weapon);
  }

  function renderOptionalFields() {
    flatBonusField.classList.toggle("is-hidden", readInt(flatBonusInput.value, 0) === 0);
    bonusSuccessesField.classList.toggle(
      "is-hidden",
      readInt(bonusSuccessesInput.value, 0) === 0 && Math.max(0, readInt(bonusSuccessesInput.dataset.nat20Bonus, 0)) === 0,
    );
    manualBonusField.classList.toggle("is-hidden", readInt(manualBonusInput.value, 0) === 0);
    multiplierField.classList.toggle("is-hidden", Math.max(1, readInt(multiplierInput.value, 1)) === 1);
  }

  function updateAttackResult() {
    const maneuverValue = readInt(maneuverValueInput.value, 0);
    const usedAp = readInt(usedApInput.value, 0);
    const accumulatedSuccesses = Math.max(0, readInt(accumulatedSuccessesInput.value, 0));
    const multipleAction = Math.max(0, readInt(multipleActionInput.value, 0));
    const dieOne = Math.max(0, readInt(attackDieOneInput.value, 0));
    const dieTwo = Math.max(0, readInt(attackDieTwoInput.value, 0));
    const nat20Bonus = dieOne === 10 && dieTwo === 10 ? 10 : 0;
    const total = maneuverValue + usedAp - accumulatedSuccesses - multipleAction + dieOne + dieTwo;
    attackFormula.textContent = `${maneuverValue} + ${usedAp} - ${accumulatedSuccesses} - ${multipleAction} + ${dieOne} + ${dieTwo}`;
    setAnimatedValue(attackTotal, total);
    bonusSuccessesInput.dataset.nat20Bonus = String(nat20Bonus);
    resultPanel.classList.toggle("is-critical", nat20Bonus > 0);
    attackPanel.classList.toggle("is-critical", nat20Bonus > 0);
    renderDiceFocus();
    if (attackValueCache !== total) {
      pulsePanel(resultPanel, "attack");
      attackValueCache = total;
    }
  }

  function updateDamageResult() {
    const diceValues = currentDamageDiceValues();
    const diceTotal = diceValues.reduce((sum, value) => sum + value, 0);
    const manualSuccesses = Math.max(0, readInt(bonusSuccessesInput.value, 0));
    const nat20Bonus = Math.max(0, readInt(bonusSuccessesInput.dataset.nat20Bonus, 0));
    const bonusSuccesses = manualSuccesses + nat20Bonus;
    const manualBonus = readInt(manualBonusInput.value, 0);
    const flatBonus = Math.max(0, readInt(flatBonusInput.value, 0));
    const flatOperator = flatOperatorSelect.value || "+";
    const multiplier = Math.max(1, readInt(multiplierInput.value, 1));

    let subtotal = diceTotal + bonusSuccesses + manualBonus;
    let flatSegment = "";
    if (flatOperator === "-") {
      subtotal -= flatBonus;
      flatSegment = flatBonus ? ` - ${flatBonus}` : "";
    } else if (flatOperator === "/") {
      subtotal = flatBonus > 0 ? Math.floor(subtotal / flatBonus) : subtotal;
      flatSegment = flatBonus > 0 ? ` / ${flatBonus}` : "";
    } else {
      subtotal += flatBonus;
      flatSegment = flatBonus ? ` + ${flatBonus}` : "";
    }

    const total = subtotal * multiplier;
    const diceFormula = diceValues.length ? diceValues.join(" + ") : "0";
    const formulaTail = multiplier > 1 ? `) x ${multiplier}` : ")";
    damageFormula.textContent = `(${diceFormula} + ${manualSuccesses}${nat20Bonus ? " + 10" : ""}${manualBonus ? ` ${formatSigned(manualBonus)}` : ""}${flatSegment}${formulaTail}`;
    setAnimatedValue(damageTotal, total);
    resultPanel.classList.toggle("is-critical", nat20Bonus > 0 || multiplier > 1);
    damagePanel.classList.toggle("is-critical", nat20Bonus > 0 || multiplier > 1);
    renderDiceFocus();
    if (damageValueCache !== total) {
      pulsePanel(resultPanel, "damage");
      damageValueCache = total;
    }
    renderOptionalFields();
  }

  function renderModifierPanels() {
    const weapon = currentWeapon();
    const attackEntries = [];
    const damageEntries = [];

    if (weapon) {
      attackEntries.push(...(weapon.attack_modifiers || []));
      damageEntries.push(...(weapon.damage_bonus_breakdown || []));
      damageEntries.push(...(weapon.damage_modifiers || []));
    }

    const usedAp = readInt(usedApInput.value, 0);
    if (usedAp) {
      attackEntries.push({ label: "Verwendete AP", value: formatSigned(usedAp), source: "Eingabe" });
    }
    const accumulatedSuccesses = Math.max(0, readInt(accumulatedSuccessesInput.value, 0));
    if (accumulatedSuccesses) {
      attackEntries.push({ label: "Angesagte Erfolge", value: `-${accumulatedSuccesses}`, source: "Eingabe" });
    }
    const multipleAction = Math.max(0, readInt(multipleActionInput.value, 0));
    if (multipleAction) {
      attackEntries.push({ label: "Mehrfachaktion", value: `-${multipleAction}`, source: "Regel" });
    }

    const bonusSuccesses = Math.max(0, readInt(bonusSuccessesInput.value, 0));
    if (bonusSuccesses) {
      damageEntries.push({ label: "Erfolgsschaden", value: `+${bonusSuccesses}`, source: "Treffer" });
    }
    const nat20Bonus = Math.max(0, readInt(bonusSuccessesInput.dataset.nat20Bonus, 0));
    if (nat20Bonus) {
      damageEntries.push({ label: "Natürliche 20", value: `+${nat20Bonus}`, source: "Kritischer Treffer" });
    }
    const weaponBaseBonus = weapon ? readInt(weapon.damage_modifier, 0) : 0;
    const manualBonus = readInt(manualBonusInput.value, 0);
    const manualBonusDelta = manualBonus - weaponBaseBonus;
    if (manualBonusDelta) {
      damageEntries.push({
        label: "Zusätzlicher Bonusschaden",
        value: formatSigned(manualBonusDelta),
        source: "Eingabe",
      });
    }
    const flatBonus = Math.max(0, readInt(flatBonusInput.value, 0));
    if (flatBonus) {
      damageEntries.push({ label: "Waffenzusatz", value: `${flatOperatorSelect.value}${flatBonus}`, source: "Waffe" });
    }
    const multiplier = Math.max(1, readInt(multiplierInput.value, 1));
    if (multiplier > 1) {
      damageEntries.push({ label: "Multiplikator", value: `x${multiplier}`, source: "Sonderregel" });
    }

    renderModifierList(attackModifiersList, attackEntries, "Keine aktiven Treffermodifikatoren.");
    renderModifierList(damageModifiersList, damageEntries, "Keine aktiven Schadensmodifikatoren.");

    const highlightEntries = [];
    if (nat20Bonus) {
      highlightEntries.push("Natürliche 20: +10 Erfolge");
    }
    if (multipleAction) {
      highlightEntries.push(`Mehrfachaktion -${multipleAction}`);
    }
    for (const entry of damageEntries) {
      if (highlightEntries.length >= 4) {
        break;
      }
      if (entry.label === "Natürliche 20" || entry.label === "Mehrfachaktion") {
        continue;
      }
      if (entry.label === "Erfolgsschaden" || entry.label === "Zusätzlicher Bonusschaden" || entry.label === "Waffenzusatz") {
        highlightEntries.push(`${entry.label} ${entry.value}`);
        continue;
      }
    }
    if (multiplier > 1 && !highlightEntries.includes(`Kritischer Treffer x${multiplier}`)) {
      highlightEntries.push(`Kritischer Treffer x${multiplier}`);
    }

    const limitedHighlights = highlightEntries.slice(0, 4);

    modifierHighlights.innerHTML = "";
    if (!limitedHighlights.length) {
      const item = document.createElement("li");
      item.textContent = "Keine besonderen Effekte aktiv";
      modifierHighlights.append(item);
      return;
    }
    for (const text of limitedHighlights) {
      const item = document.createElement("li");
      item.textContent = text;
      modifierHighlights.append(item);
    }
  }

  attackSkillSelect.addEventListener("change", () => {
    syncAttackFromSelectedSkill();
    updateAttackResult();
    renderModifierPanels();
    saveCurrentState();
  });

  attackResetButton.addEventListener("click", () => {
    attackDieOneInput.value = "0";
    attackDieTwoInput.value = "0";
    syncAttackDieButtons(attackDieOneButtons, 0);
    syncAttackDieButtons(attackDieTwoButtons, 0);
    updateAttackResult();
    updateDamageResult();
    renderModifierPanels();
    saveCurrentState();
  });

  weaponSelect.addEventListener("change", () => {
    syncDamageFromWeapon();
    updateAttackResult();
    updateDamageResult();
    renderModifierPanels();
    saveCurrentState();
  });

  damageDiceAmountInput.addEventListener("input", () => {
    renderDamageDiceList(false);
    updateDamageResult();
    renderModifierPanels();
    saveCurrentState();
  });

  damageResetButton.addEventListener("click", () => {
    for (const input of damageDiceList.querySelectorAll("[data-damage-die-value]")) {
      input.value = "0";
    }
    for (const group of damageDiceList.querySelectorAll(".combat-calculator__damage-die")) {
      syncDamageDieButtons(group, 0);
    }
    updateDamageResult();
    renderModifierPanels();
    saveCurrentState();
  });

  [
    maneuverValueInput,
    usedApInput,
  ].forEach((input) => {
    input.addEventListener("input", () => {
      updateAttackResult();
      renderModifierPanels();
      saveCurrentState();
    });
  });

  multipleActionInput.addEventListener("change", () => {
    updateAttackResult();
    renderModifierPanels();
    saveCurrentState();
  });

  accumulatedSuccessesInput.addEventListener("input", () => {
    syncSharedSuccesses(accumulatedSuccessesInput.value);
    updateAttackResult();
    updateDamageResult();
    renderModifierPanels();
    saveCurrentState();
  });

  bonusSuccessesInput.addEventListener("input", () => {
    syncSharedSuccesses(bonusSuccessesInput.value);
    updateAttackResult();
    updateDamageResult();
    renderModifierPanels();
    saveCurrentState();
  });

  [
    flatOperatorSelect,
    flatBonusInput,
    manualBonusInput,
    multiplierInput,
  ].forEach((input) => {
    input.addEventListener("input", () => {
      updateDamageResult();
      renderModifierPanels();
      saveCurrentState();
    });
    input.addEventListener("change", () => {
      updateDamageResult();
      renderModifierPanels();
      saveCurrentState();
    });
  });

  syncAttackFromSelectedSkill();
  syncDamageFromWeapon();
  renderAttackDieButtons(attackDieOneButtons, attackDieOneInput);
  renderAttackDieButtons(attackDieTwoButtons, attackDieTwoInput);
  usedApInput.value = String(readInt(persistedState.usedAp, 0));
  syncSharedSuccesses(readInt(persistedState.sharedSuccesses, 0));
  multipleActionInput.value = String(Math.max(0, Math.min(8, readInt(persistedState.multipleAction, 0))));
  attackDieOneInput.value = String(readInt(persistedState.attackDieOne, 0));
  attackDieTwoInput.value = String(readInt(persistedState.attackDieTwo, 0));
  for (const [input, container] of [[attackDieOneInput, attackDieOneButtons], [attackDieTwoInput, attackDieTwoButtons]]) {
    const nextValue = Math.max(0, readInt(input.value, 0));
    syncAttackDieButtons(container, nextValue);
  }
  manualBonusInput.value = String(readInt(persistedState.manualBonus, readInt(manualBonusInput.value, 0)));
  multiplierInput.value = String(Math.max(1, readInt(persistedState.multiplier, 1)));
  flatBonusInput.value = String(Math.max(0, readInt(persistedState.flatBonus, readInt(flatBonusInput.value, 0))));
  flatOperatorSelect.value = String(persistedState.flatOperator || flatOperatorSelect.value || "+");
  damageDiceAmountInput.value = String(Math.max(1, readInt(persistedState.damageDiceAmount, readInt(damageDiceAmountInput.value, 1))));
  renderDamageDiceList(false);
  const persistedDamageDice = Array.isArray(persistedState.damageDiceValues) ? persistedState.damageDiceValues : [];
  [...damageDiceList.querySelectorAll("[data-damage-die-value]")].forEach((input, index) => {
    input.value = String(readInt(persistedDamageDice[index], 0));
  });
  for (const group of damageDiceList.querySelectorAll(".combat-calculator__damage-die")) {
    const input = group.querySelector("[data-damage-die-value]");
    if (!input) {
      continue;
    }
    const nextValue = Math.max(0, readInt(input.value, 0));
    syncDamageDieButtons(group, nextValue);
  }

  updateAttackResult();
  updateDamageResult();
  renderModifierPanels();
  saveCurrentState();
}

