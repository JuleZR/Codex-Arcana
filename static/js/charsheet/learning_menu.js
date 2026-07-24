import { createChoiceModalController } from "./choice_modal.js";
import { clamp, escapeHtml, initPersistentDetails, readInt } from "./utils.js?v=20260622a";

const LANGUAGE_LITERACY_MIN_LEVEL = 3;
const renderOpenSpellSlotMarkup = (remaining) => {
  const count = Math.max(0, readInt(String(remaining), 0));
  if (count <= 0) {
    return "";
  }
  const label = `${count} offener Slot${count === 1 ? "" : "s"}`;
  return `<span class="learn_magic_slot_cell_open" title="${label}" aria-label="${label}">&#10022;${count > 1 ? `<span class="learn_magic_slot_cell_count">${count}</span>` : ""}</span>`;
};

function initLearningCart(form, cartBody, budgetEl, spentEl, remainingEl, validationHint, applyBtn) {
  const getBudget = () => readInt(document.getElementById("learnBudgetPanel")?.getAttribute("data-learn-budget") || "0", 0);
  let newSpecCounter = 0;
  const getRows = () => Array.from(cartBody.querySelectorAll("[data-learn-cart-item]"));
  const ensureEmptyRow = () => {
    const emptyRow = cartBody.querySelector("[data-learn-empty-row]");
    if (emptyRow) {
      emptyRow.hidden = getRows().length > 0;
    }
  };

  const calcSkillCost = (level, aboveBaseCost = 2) => {
    const rank = Math.max(0, level);
    const regularRank = Math.min(rank, 10);
    const regularCost = regularRank <= 5 ? regularRank : 5 + ((regularRank - 5) * 2);
    return regularCost + Math.max(0, rank - 10) * Math.max(0, aboveBaseCost);
  };
  const calcLanguageCost = (level, write, mother) => (mother ? 0 : Math.max(0, level)) + (write ? 1 : 0);
  const calcTraitCost = (level, pointsPerLevel, traitType) => {
    const rank = Math.max(0, level);
    return rank * Math.max(0, pointsPerLevel);
  };
  const calcTraitDeltaCost = (base, value, pointsPerLevel, traitType) => (
    Math.abs(value) * Math.max(0, pointsPerLevel)
  );
  const calcAttributeTotalCost = (targetLevel, maxValue) => {
    const level = Math.max(0, targetLevel);
    const threshold = maxValue - 2;
    if (level <= threshold) {
      return level * 10;
    }
    let cost = threshold * 10;
    for (let value = threshold + 1; value <= level; value += 1) {
      cost += 20;
    }
    return cost;
  };

  const selectedMagicAspectLevels = (exceptRow = null) => {
    let total = 0;
    cartBody.querySelectorAll('[data-learn-cart-item][data-kind="magic-aspect"]').forEach((cartRow) => {
      if (cartRow === exceptRow) {
        return;
      }
      const input = cartRow.querySelector("[data-learn-value]");
      if (input instanceof HTMLInputElement) {
        total += Math.max(0, readInt(input.value, 0));
      }
    });
    return total;
  };

  const syncSpellSlotTable = () => {
    const table = document.querySelector("[data-learn-slot-table]");
    if (!(table instanceof HTMLElement)) {
      return;
    }
    const selectedBySourceGrade = new Map();
    getRows().forEach((row) => {
      if (!(row instanceof HTMLElement) || row.getAttribute("data-kind") !== "magic-spell") {
        return;
      }
      const sourceKey = row.getAttribute("data-slot-source-key") || "";
      const grade = row.getAttribute("data-slot-grade") || "";
      const input = row.querySelector("[data-learn-value]");
      const value = input instanceof HTMLInputElement ? readInt(input.value, 0) : 0;
      const slotCost = readInt(row.getAttribute("data-slot-source-cost") || row.getAttribute("data-slot-cost") || "1", 1);
      if (sourceKey && grade && value > 0) {
        const key = `${sourceKey}::${grade}`;
        selectedBySourceGrade.set(key, (selectedBySourceGrade.get(key) || 0) + (value * slotCost));
      }
    });
    Array.from(table.querySelectorAll("[data-learn-slot-cell]")).forEach((cell) => {
      if (!(cell instanceof HTMLElement)) {
        return;
      }
      const sourceKey = cell.getAttribute("data-slot-source-key") || "";
      const grade = cell.getAttribute("data-slot-source-grade") || "";
      const baseRemaining = readInt(cell.getAttribute("data-slot-source-remaining") || "0", 0);
      const selected = selectedBySourceGrade.get(`${sourceKey}::${grade}`) || 0;
      const remaining = Math.max(0, baseRemaining - selected);
      cell.innerHTML = renderOpenSpellSlotMarkup(remaining);
      if (remaining > 0) {
        cell.setAttribute("aria-label", `${remaining} offener Slot${remaining === 1 ? "" : "s"}`);
      } else {
        cell.removeAttribute("aria-label");
      }
    });
  };

  const syncRow = (row) => {
    const kind = row.getAttribute("data-kind") || "";
    const valueInput = row.querySelector("[data-learn-value]");
    const costCell = row.querySelector("[data-learn-cost]");
    const infoEl = row.querySelector("[data-learn-level-info]");
    if (!(valueInput instanceof HTMLInputElement) || !costCell) {
      return { cost: 0, invalidWrite: false };
    }

    let value = readInt(valueInput.value, 0);
    let cost = 0;
    let invalidWrite = false;

    if (kind === "attr") {
      const base = readInt(row.getAttribute("data-base"), 0);
      const min = readInt(row.getAttribute("data-min"), 0);
      const max = readInt(row.getAttribute("data-max"), 0);
      const minAdd = Math.min(0, min - base);
      const maxAdd = Math.max(0, max - base);
      const hidden = row.querySelector("[data-learn-hidden]");
      value = clamp(value, minAdd, maxAdd);
      cost = calcAttributeTotalCost(base + value, max) - calcAttributeTotalCost(base, max);
      if (hidden instanceof HTMLInputElement) {
        hidden.value = String(value);
      }
      if (infoEl) {
        infoEl.textContent = `(${base + value})`;
      }
      valueInput.min = String(minAdd);
      valueInput.max = String(maxAdd);
    } else if (kind === "trait") {
      const base = readInt(row.getAttribute("data-base"), 0);
      const max = readInt(row.getAttribute("data-max"), 0);
      const pointsPerLevel = readInt(row.getAttribute("data-ppl"), 0);
      const traitType = row.getAttribute("data-trait-type") || "";
      const minAdd = -base;
      const maxAdd = Math.max(0, max - base);
      const hidden = row.querySelector("[data-learn-hidden]");
      value = clamp(value, minAdd, maxAdd);
      cost = calcTraitDeltaCost(base, value, pointsPerLevel, traitType);
      if (hidden instanceof HTMLInputElement) {
        hidden.value = String(value);
      }
      if (infoEl) {
        infoEl.textContent = `(${base + value})`;
      }
      valueInput.min = String(minAdd);
      valueInput.max = String(maxAdd);
    } else if (kind === "skill" || kind === "skill-cs" || kind === "skill-new-spec") {
      const base = readInt(row.getAttribute("data-base"), 0);
      const max = readInt(row.getAttribute("data-max"), 10);
      const aboveBaseCost = readInt(row.getAttribute("data-above-base-cost"), 2);
      const minAdd = kind === "skill-new-spec" ? 0 : -base;
      const maxAdd = Math.max(0, max - base);
      const hidden = row.querySelector("[data-learn-hidden]");
      value = clamp(value, minAdd, maxAdd);
      cost = calcSkillCost(base + value, aboveBaseCost) - calcSkillCost(base, aboveBaseCost);
      if (hidden instanceof HTMLInputElement) {
        hidden.value = String(value);
      }
      if (infoEl) {
        infoEl.textContent = `(${base + value})`;
      }
      valueInput.min = String(minAdd);
      valueInput.max = String(maxAdd);
    } else if (kind === "lang") {
      const base = readInt(row.getAttribute("data-base"), 0);
      const minAdd = -base;
      const max = readInt(row.getAttribute("data-max"), 0);
      const maxAdd = Math.max(0, max - base);
      const hidden = row.querySelector("[data-learn-hidden]");
      const writeHidden = row.querySelector("[data-learn-lang-write-hidden]");
      const writeInput = row.querySelector("[data-learn-lang-write]");
      const baseWrite = row.getAttribute("data-write") === "1";
      const mother = row.getAttribute("data-mother") === "1";
      value = clamp(value, minAdd, maxAdd);
      const targetLevel = base + value;
      let targetWrite = baseWrite;
      if (writeInput instanceof HTMLInputElement) {
        if (targetLevel < LANGUAGE_LITERACY_MIN_LEVEL && !baseWrite) {
          writeInput.checked = false;
          writeInput.disabled = true;
        } else {
          writeInput.disabled = false;
        }
        if (baseWrite && !writeInput.dataset.learnWriteTouched) {
          writeInput.checked = true;
        }
        targetWrite = writeInput.checked;
      }
      invalidWrite = targetWrite && targetLevel < LANGUAGE_LITERACY_MIN_LEVEL;
      cost = calcLanguageCost(targetLevel, targetWrite, mother) - calcLanguageCost(base, baseWrite, mother);
      if (hidden instanceof HTMLInputElement) {
        hidden.value = String(value);
      }
      if (writeHidden instanceof HTMLInputElement) {
        writeHidden.value = targetWrite === baseWrite ? "0" : targetWrite ? "1" : "-1";
      }
      if (infoEl) {
        infoEl.textContent = `(${targetLevel})`;
      }
      valueInput.min = String(minAdd);
      valueInput.max = String(maxAdd);
    } else if (kind === "school") {
      const base = readInt(row.getAttribute("data-base"), 0);
      const minAdd = -base;
      const max = readInt(row.getAttribute("data-max"), base);
      const maxAdd = Math.max(0, max - base);
      const hidden = row.querySelector("[data-learn-hidden]");
      value = clamp(value, minAdd, maxAdd);
      cost = value * 8;
      if (hidden instanceof HTMLInputElement) {
        hidden.value = String(value);
      }
      if (infoEl) {
        infoEl.textContent = `(${base + value})`;
      }
      valueInput.min = String(minAdd);
      valueInput.max = String(maxAdd);
    } else if (kind === "lesson") {
      const base = readInt(row.getAttribute("data-base"), 0);
      const canUnlearn = row.getAttribute("data-can-unlearn") === "1";
      const minAdd = base > 0 && canUnlearn ? -1 : 0;
      const maxAdd = base > 0 ? 0 : 1;
      const hidden = row.querySelector("[data-learn-hidden]");
      value = clamp(value, minAdd, maxAdd);
      cost = value > 0
        ? readInt(row.getAttribute("data-purchase-cost"), 8)
        : value < 0
          ? -readInt(row.getAttribute("data-paid-ep"), 0)
          : 0;
      if (hidden instanceof HTMLInputElement) {
        hidden.value = String(value);
      }
      if (infoEl) {
        infoEl.textContent = base + value > 0 ? "(erlernt)" : "(verlernt)";
      }
      valueInput.min = String(minAdd);
      valueInput.max = String(maxAdd);
    } else if (kind === "magic-spell") {
      const hidden = row.querySelector("[data-learn-hidden]");
      value = clamp(value, 0, 1);
      cost = 0;
      if (hidden instanceof HTMLInputElement) {
        hidden.value = String(value);
      }
    } else if (kind === "magic-aspect") {
      const base = readInt(row.getAttribute("data-base"), 0);
      const minAdd = -base;
      const max = readInt(row.getAttribute("data-max"), base);
      const remaining = readInt(row.getAttribute("data-remaining"), max);
      const maxAdd = Math.max(0, Math.min(max - base, remaining - selectedMagicAspectLevels(row)));
      const hidden = row.querySelector("[data-learn-hidden]");
      value = clamp(value, minAdd, maxAdd);
      cost = value * readInt(row.getAttribute("data-cost-per-level"), 4);
      if (hidden instanceof HTMLInputElement) {
        hidden.value = String(value);
      }
      if (infoEl) {
        infoEl.textContent = `(${base + value})`;
      }
      valueInput.min = String(minAdd);
      valueInput.max = String(maxAdd);
    }

    valueInput.value = String(value);
    if (kind === "magic-spell") {
      const slotCost = readInt(row.getAttribute("data-slot-cost"), 1);
      const costLabel = row.getAttribute("data-cost-label") || `${slotCost} Slot${slotCost === 1 ? "" : "s"}`;
      costCell.textContent = value > 0 ? costLabel : "0";
    } else {
      costCell.textContent = `${cost} EP`;
    }
    return {
      cost,
      invalidWrite,
      spellSlots: kind === "magic-spell" ? value * readInt(row.getAttribute("data-slot-cost"), 1) : 0,
      spellSlotSourceCost: kind === "magic-spell"
        ? value * readInt(row.getAttribute("data-slot-source-cost"), readInt(row.getAttribute("data-slot-cost"), 1))
        : 0,
      spellSlotSourceKey: kind === "magic-spell" ? row.getAttribute("data-slot-source-key") || "" : "",
      spellSlotSourceName: kind === "magic-spell" ? row.getAttribute("data-slot-source-name") || "" : "",
      spellSlotSourceRemaining: kind === "magic-spell"
        ? readInt(row.getAttribute("data-slot-source-remaining"), Number.MAX_SAFE_INTEGER)
        : Number.MAX_SAFE_INTEGER,
    };
  };

  const refreshTotals = () => {
    let spent = 0;
    let spentSpellSlots = 0;
    let invalidWrite = false;
    const spentSpellSlotsBySource = new Map();
    const spellSlotSourceLimits = new Map();
    getRows().forEach((row) => {
      const result = syncRow(row);
      spent += result.cost;
      spentSpellSlots += result.spellSlots;
      invalidWrite = invalidWrite || result.invalidWrite;
      if (result.spellSlotSourceCost > 0 && result.spellSlotSourceKey) {
        spentSpellSlotsBySource.set(
          result.spellSlotSourceKey,
          (spentSpellSlotsBySource.get(result.spellSlotSourceKey) || 0) + result.spellSlotSourceCost,
        );
        spellSlotSourceLimits.set(result.spellSlotSourceKey, {
          name: result.spellSlotSourceName || result.spellSlotSourceKey,
          remaining: result.spellSlotSourceRemaining,
        });
      }
    });
    const budget = getBudget();
    const remaining = budget - spent;
    const spellSlotBudget = readInt(document.getElementById("learnBudgetPanel")?.getAttribute("data-learn-spell-slot-budget") || "0", 0);
    const magicBudgetPanel = document.querySelector("[data-learn-magic-budget]");
    const spellSlotSpentBase = readInt(
      magicBudgetPanel?.getAttribute("data-base-spent-slots")
        || document.getElementById("learnSpellSlotSpentValue")?.getAttribute("data-base-spent-slots")
        || "0",
      0,
    );
    const spellSlotSpentTotal = spellSlotSpentBase + spentSpellSlots;
    const spellSlotRemaining = spellSlotBudget - spellSlotSpentTotal;
    const liveBudgetEl = document.getElementById("learnBudgetValue");
    const liveSpentEl = document.getElementById("learnSpentValue");
    const liveRemainingEl = document.getElementById("learnRemainingValue");
    const liveSpellSlotBudgetEl = document.getElementById("learnSpellSlotBudgetValue");
    const liveSpellSlotSpentEl = document.getElementById("learnSpellSlotSpentValue");
    const liveSpellSlotRemainingEl = document.getElementById("learnSpellSlotRemainingValue");
    const liveValidationHint = document.getElementById("learnValidationHint");
    if (liveBudgetEl) {
      liveBudgetEl.textContent = `${budget} EP`;
    }
    if (liveSpentEl) {
      liveSpentEl.textContent = `${spent} EP`;
    }
    if (liveRemainingEl) {
      liveRemainingEl.textContent = `${remaining} EP`;
      liveRemainingEl.classList.toggle("is-negative", remaining < 0);
    }
    if (liveSpellSlotBudgetEl) {
      liveSpellSlotBudgetEl.textContent = `${spellSlotBudget}`;
    }
    if (liveSpellSlotSpentEl) {
      liveSpellSlotSpentEl.textContent = `${spellSlotSpentTotal}`;
      liveSpellSlotSpentEl.classList.toggle("is-negative", spellSlotRemaining < 0);
    }
    if (liveSpellSlotRemainingEl) {
      liveSpellSlotRemainingEl.textContent = `${spellSlotRemaining}`;
      liveSpellSlotRemainingEl.classList.toggle("is-negative", spellSlotRemaining < 0);
    }
    Array.from(document.querySelectorAll("[data-learn-slot-source-chip]")).forEach((chip) => {
      if (!(chip instanceof HTMLElement)) {
        return;
      }
      const sourceKey = chip.getAttribute("data-slot-source-key") || "";
      const baseRemaining = readInt(chip.getAttribute("data-slot-source-remaining"), 0);
      const selected = spentSpellSlotsBySource.get(sourceKey) || 0;
      const sourceRemaining = baseRemaining - selected;
      const countEl = chip.querySelector("[data-learn-slot-source-count]");
      if (countEl) {
        countEl.textContent = String(sourceRemaining);
      }
      chip.setAttribute("data-slot-source-current-remaining", String(sourceRemaining));
      chip.classList.toggle("is-negative", sourceRemaining < 0);
      chip.classList.toggle("is-empty", sourceRemaining === 0);
    });
    syncSpellSlotTable();
    if (liveValidationHint) {
      const messages = [];
      if (remaining < 0) {
        messages.push("Zu wenig EP fuer die ausgewaehlten Lernschritte.");
      }
      if (spellSlotRemaining < 0) {
        messages.push("Zu viele Zauber-Slots ausgewaehlt.");
      }
      Array.from(spentSpellSlotsBySource.entries()).forEach(([sourceKey, selected]) => {
        const limit = spellSlotSourceLimits.get(sourceKey);
        if (limit && selected > limit.remaining) {
          messages.push(`${limit.name}: Zu viele gebundene Zauber-Slots ausgewaehlt.`);
        }
      });
      if (invalidWrite) {
        messages.push("Lesen und Schreiben benoetigt Sprachlevel 3.");
      }
      liveValidationHint.hidden = messages.length === 0;
      liveValidationHint.textContent = messages.join(" ");
    }
  };

  const bindRow = (row) => {
    const valueInput = row.querySelector("[data-learn-value]");
    const removeBtn = row.querySelector("[data-learn-remove]");
    const writeInput = row.querySelector("[data-learn-lang-write]");
    const decBtn = row.querySelector("[data-learn-step-dec]");
    const incBtn = row.querySelector("[data-learn-step-inc]");

    if (valueInput instanceof HTMLInputElement) {
      valueInput.addEventListener("input", refreshTotals);
      valueInput.addEventListener("change", refreshTotals);
    }
    if (valueInput instanceof HTMLInputElement && decBtn instanceof HTMLButtonElement) {
      decBtn.addEventListener("click", () => {
        const current = readInt(valueInput.value, 0);
        const min = readInt(valueInput.min, 0);
        const max = valueInput.max ? readInt(valueInput.max, Number.MAX_SAFE_INTEGER) : Number.MAX_SAFE_INTEGER;
        valueInput.value = String(clamp(current - 1, min, max));
        refreshTotals();
      });
    }
    if (valueInput instanceof HTMLInputElement && incBtn instanceof HTMLButtonElement) {
      incBtn.addEventListener("click", () => {
        const current = readInt(valueInput.value, 0);
        const min = readInt(valueInput.min, 0);
        const max = valueInput.max ? readInt(valueInput.max, Number.MAX_SAFE_INTEGER) : Number.MAX_SAFE_INTEGER;
        valueInput.value = String(clamp(current + 1, min, max));
        refreshTotals();
      });
    }
    if (writeInput instanceof HTMLInputElement) {
      writeInput.addEventListener("change", () => {
        writeInput.dataset.learnWriteTouched = "1";
        refreshTotals();
      });
    }
    if (removeBtn instanceof HTMLButtonElement) {
      removeBtn.addEventListener("click", () => {
        row.remove();
        ensureEmptyRow();
        refreshTotals();
      });
    }
  };

  const createRowFromSource = (source) => {
    const kind = source.getAttribute("data-kind") || "";
    const key = source.getAttribute("data-key") || "";
    const name = source.getAttribute("data-name") || key;
    const safeName = escapeHtml(name);
    if (!kind || (!key && kind !== "skill-new-spec")) {
      return null;
    }

    const row = document.createElement("tr");
    row.setAttribute("data-learn-cart-item", "");
    row.setAttribute("data-kind", kind);
    row.setAttribute("data-key", key);

    if (kind === "attr") {
      const shortName = source.getAttribute("data-short") || "";
      const base = readInt(source.getAttribute("data-base"), 0);
      const min = readInt(source.getAttribute("data-min"), 0);
      const max = readInt(source.getAttribute("data-max"), 0);
      const minAdd = Math.min(0, min - base);
      const maxAdd = Math.max(0, max - base);
      if (maxAdd < 1 && minAdd === 0) {
        return null;
      }
      const startAdd = maxAdd > 0 ? 1 : 0;
      row.setAttribute("data-base", String(base));
      row.setAttribute("data-min", String(min));
      row.setAttribute("data-max", String(max));
      row.innerHTML = `
        <td><span>${safeName}</span> <span data-learn-level-info>(${base + startAdd})</span><input type="hidden" name="learn_attr_add_${shortName}" value="${startAdd}" data-learn-hidden></td>
        <td>
          <div class="shop_qty_stepper">
            <button type="button" class="shop_step_btn" data-learn-step-dec aria-label="Wert verringern">-</button>
            <input class="shop_cart_qty_input" type="number" min="${minAdd}" max="${maxAdd}" value="${startAdd}" data-learn-value>
            <button type="button" class="shop_step_btn" data-learn-step-inc aria-label="Wert erhoehen">+</button>
          </div>
        </td>
        <td data-learn-cost>0 EP</td>
        <td><button type="button" class="shop_cart_remove_btn" data-learn-remove aria-label="Eintrag entfernen">x</button></td>
      `;
      return row;
    }

    if (kind === "skill") {
      const slug = source.getAttribute("data-slug") || "";
      const base = readInt(source.getAttribute("data-base"), 0);
      const max = readInt(source.getAttribute("data-max"), 10);
      const aboveBaseCost = readInt(source.getAttribute("data-above-base-cost"), 2);
      const minAdd = -base;
      const maxAdd = Math.max(0, max - base);
      if (maxAdd < 1 && minAdd === 0) {
        return null;
      }
      const startAdd = maxAdd > 0 ? 1 : 0;
      row.setAttribute("data-base", String(base));
      row.setAttribute("data-max", String(max));
      row.setAttribute("data-above-base-cost", String(aboveBaseCost));
      row.innerHTML = `
        <td><span>${safeName}</span> <span data-learn-level-info>(${base + startAdd})</span><input type="hidden" name="learn_skill_add_${slug}" value="${startAdd}" data-learn-hidden></td>
        <td>
          <div class="shop_qty_stepper">
            <button type="button" class="shop_step_btn" data-learn-step-dec aria-label="Wert verringern">-</button>
            <input class="shop_cart_qty_input" type="number" min="${minAdd}" max="${maxAdd}" value="${startAdd}" data-learn-value>
            <button type="button" class="shop_step_btn" data-learn-step-inc aria-label="Wert erhoehen">+</button>
          </div>
        </td>
        <td data-learn-cost>0 EP</td>
        <td><button type="button" class="shop_cart_remove_btn" data-learn-remove aria-label="Eintrag entfernen">x</button></td>
      `;
      return row;
    }

    if (kind === "skill-cs") {
      const csId = source.getAttribute("data-cs-id") || "";
      const base = readInt(source.getAttribute("data-base"), 0);
      const max = readInt(source.getAttribute("data-max"), 10);
      const aboveBaseCost = readInt(source.getAttribute("data-above-base-cost"), 2);
      const minAdd = -base;
      const maxAdd = Math.max(0, max - base);
      if (maxAdd < 1 && minAdd === 0) {
        return null;
      }
      const startAdd = maxAdd > 0 ? 1 : 0;
      row.setAttribute("data-base", String(base));
      row.setAttribute("data-max", String(max));
      row.setAttribute("data-above-base-cost", String(aboveBaseCost));
      row.innerHTML = `
        <td><span>${safeName}</span> <span data-learn-level-info>(${base + startAdd})</span><input type="hidden" name="learn_skill_cs_${csId}" value="${startAdd}" data-learn-hidden></td>
        <td>
          <div class="shop_qty_stepper">
            <button type="button" class="shop_step_btn" data-learn-step-dec aria-label="Wert verringern">-</button>
            <input class="shop_cart_qty_input" type="number" min="${minAdd}" max="${maxAdd}" value="${startAdd}" data-learn-value>
            <button type="button" class="shop_step_btn" data-learn-step-inc aria-label="Wert erhoehen">+</button>
          </div>
        </td>
        <td data-learn-cost>0 EP</td>
        <td><button type="button" class="shop_cart_remove_btn" data-learn-remove aria-label="Eintrag entfernen">x</button></td>
      `;
      return row;
    }

    if (kind === "skill-new-spec") {
      const slug = source.getAttribute("data-slug") || "";
      const max = readInt(source.getAttribute("data-max"), 10);
      const aboveBaseCost = readInt(source.getAttribute("data-above-base-cost"), 2);
      // eslint-disable-next-line no-alert
      const spec = window.prompt(`Spezialisierung für "${name}" eingeben:`);
      if (!spec || !spec.trim()) {
        return null;
      }
      const specTrimmed = spec.trim();
      const uniqueKey = `skill-new-spec:${slug}:${specTrimmed}`;
      const existingInCart = cartBody.querySelector(`[data-learn-cart-item][data-key="${uniqueKey}"]`);
      if (existingInCart) {
        const input = existingInCart.querySelector("[data-learn-value]");
        if (input instanceof HTMLInputElement) {
          input.focus();
        }
        return null;
      }
      const idx = newSpecCounter;
      newSpecCounter += 1;
      const startAdd = 1;
      row.setAttribute("data-key", uniqueKey);
      row.setAttribute("data-base", "0");
      row.setAttribute("data-max", String(max));
      row.setAttribute("data-above-base-cost", String(aboveBaseCost));
      row.innerHTML = `
        <td>
          <span>${escapeHtml(name)}: ${escapeHtml(specTrimmed)}</span>
          <span data-learn-level-info>(${startAdd})</span>
          <input type="hidden" name="learn_new_skill_slug_${idx}" value="${escapeHtml(slug)}">
          <input type="hidden" name="learn_new_skill_spec_${idx}" value="${escapeHtml(specTrimmed)}">
          <input type="hidden" name="learn_new_skill_level_${idx}" value="${startAdd}" data-learn-hidden>
        </td>
        <td>
          <div class="shop_qty_stepper">
            <button type="button" class="shop_step_btn" data-learn-step-dec aria-label="Wert verringern">-</button>
            <input class="shop_cart_qty_input" type="number" min="0" max="${max}" value="${startAdd}" data-learn-value>
            <button type="button" class="shop_step_btn" data-learn-step-inc aria-label="Wert erhoehen">+</button>
          </div>
        </td>
        <td data-learn-cost>0 EP</td>
        <td><button type="button" class="shop_cart_remove_btn" data-learn-remove aria-label="Eintrag entfernen">x</button></td>
      `;
      return row;
    }

    if (kind === "trait") {
      const slug = source.getAttribute("data-slug") || "";
      const base = readInt(source.getAttribute("data-base"), 0);
      const max = readInt(source.getAttribute("data-max"), 0);
      const pointsPerLevel = readInt(source.getAttribute("data-ppl"), 0);
      const traitType = source.getAttribute("data-trait-type") || "";
      const minAdd = -base;
      const maxAdd = Math.max(0, max - base);
      if (maxAdd < 1 && minAdd === 0) {
        return null;
      }
      const startAdd = maxAdd > 0 ? 1 : 0;
      row.setAttribute("data-base", String(base));
      row.setAttribute("data-max", String(max));
      row.setAttribute("data-ppl", String(pointsPerLevel));
      row.setAttribute("data-trait-type", traitType);
      row.innerHTML = `
        <td><span>${safeName}</span> <span data-learn-level-info>(${base + startAdd})</span><input type="hidden" name="learn_trait_add_${slug}" value="${startAdd}" data-learn-hidden></td>
        <td>
          <div class="shop_qty_stepper">
            <button type="button" class="shop_step_btn" data-learn-step-dec aria-label="Wert verringern">-</button>
            <input class="shop_cart_qty_input" type="number" min="${minAdd}" max="${maxAdd}" value="${startAdd}" data-learn-value>
            <button type="button" class="shop_step_btn" data-learn-step-inc aria-label="Wert erhoehen">+</button>
          </div>
        </td>
        <td data-learn-cost>0 EP</td>
        <td><button type="button" class="shop_cart_remove_btn" data-learn-remove aria-label="Eintrag entfernen">x</button></td>
      `;
      return row;
    }

    if (kind === "lang") {
      const slug = source.getAttribute("data-slug") || "";
      const base = readInt(source.getAttribute("data-base"), 0);
      const minAdd = -base;
      const max = readInt(source.getAttribute("data-max"), 0);
      const maxAdd = Math.max(0, max - base);
      const baseWrite = source.getAttribute("data-write") === "1";
      const mother = source.getAttribute("data-mother") === "1";
      if (maxAdd < 1 && minAdd === 0 && !baseWrite) {
        return null;
      }
      const startAdd = maxAdd > 0 ? 1 : 0;
      row.setAttribute("data-base", String(base));
      row.setAttribute("data-max", String(max));
      row.setAttribute("data-write", baseWrite ? "1" : "0");
      row.setAttribute("data-mother", mother ? "1" : "0");
      row.innerHTML = `
        <td>
          <div class="learn_lang_name_wrap">
            <span>${safeName}</span>
            <span data-learn-level-info>(${base + startAdd})</span>
            <label class="learn_lang_write"><input type="checkbox" data-learn-lang-write ${baseWrite ? "checked" : ""}> Schreiben</label>
          </div>
          <input type="hidden" name="learn_lang_add_${slug}" value="${startAdd}" data-learn-hidden>
          <input type="hidden" name="learn_lang_write_${slug}" value="0" data-learn-lang-write-hidden>
        </td>
        <td>
          <div class="learn_lang_value_wrap">
            <div class="shop_qty_stepper">
              <button type="button" class="shop_step_btn" data-learn-step-dec aria-label="Wert verringern">-</button>
              <input class="shop_cart_qty_input" type="number" min="${minAdd}" max="${maxAdd}" value="${startAdd}" data-learn-value>
              <button type="button" class="shop_step_btn" data-learn-step-inc aria-label="Wert erhoehen">+</button>
            </div>
          </div>
        </td>
        <td data-learn-cost>0 EP</td>
        <td><button type="button" class="shop_cart_remove_btn" data-learn-remove aria-label="Eintrag entfernen">x</button></td>
      `;
      return row;
    }

    if (kind === "school") {
      const schoolId = source.getAttribute("data-id") || "";
      const base = readInt(source.getAttribute("data-base"), 0);
      const minAdd = -base;
      const max = readInt(source.getAttribute("data-max"), base);
      const maxAdd = Math.max(0, max - base);
      if (maxAdd < 1 && minAdd === 0) {
        return null;
      }
      const startAdd = maxAdd > 0 ? 1 : 0;
      row.setAttribute("data-base", String(base));
      row.setAttribute("data-max", String(max));
      row.innerHTML = `
        <td><span>${safeName}</span> <span data-learn-level-info>(${base + startAdd})</span><input type="hidden" name="learn_school_add_${schoolId}" value="${startAdd}" data-learn-hidden></td>
        <td>
          <div class="shop_qty_stepper">
            <button type="button" class="shop_step_btn" data-learn-step-dec aria-label="Wert verringern">-</button>
            <input class="shop_cart_qty_input" type="number" min="${minAdd}" max="${maxAdd}" value="${startAdd}" data-learn-value>
            <button type="button" class="shop_step_btn" data-learn-step-inc aria-label="Wert erhoehen">+</button>
          </div>
        </td>
        <td data-learn-cost>0 EP</td>
        <td><button type="button" class="shop_cart_remove_btn" data-learn-remove aria-label="Eintrag entfernen">x</button></td>
      `;
      return row;
    }

    if (kind === "lesson") {
      const lessonId = source.getAttribute("data-id") || "";
      const base = readInt(source.getAttribute("data-base"), 0);
      const purchaseCost = readInt(source.getAttribute("data-purchase-cost"), 8);
      const paidEp = readInt(source.getAttribute("data-paid-ep"), 0);
      const canUnlearn = source.getAttribute("data-can-unlearn") === "1";
      if (base > 0 && !canUnlearn) {
        return null;
      }
      const minAdd = base > 0 ? -1 : 0;
      const maxAdd = base > 0 ? 0 : 1;
      const startAdd = base > 0 ? -1 : 1;
      row.setAttribute("data-base", String(base));
      row.setAttribute("data-purchase-cost", String(purchaseCost));
      row.setAttribute("data-paid-ep", String(paidEp));
      row.setAttribute("data-can-unlearn", canUnlearn ? "1" : "0");
      row.innerHTML = `
        <td><span>${safeName}</span> <span data-learn-level-info>${base + startAdd > 0 ? "(erlernt)" : "(verlernt)"}</span><input type="hidden" name="learn_lesson_add_${lessonId}" value="${startAdd}" data-learn-hidden></td>
        <td>
          <div class="shop_qty_stepper">
            <input class="shop_cart_qty_input" type="number" min="${minAdd}" max="${maxAdd}" value="${startAdd}" data-learn-value readonly>
          </div>
        </td>
        <td data-learn-cost>${startAdd > 0 ? purchaseCost : -paidEp} EP</td>
        <td><button type="button" class="shop_cart_remove_btn" data-learn-remove aria-label="Eintrag entfernen">x</button></td>
      `;
      return row;
    }

    if (kind === "magic-spell") {
      const spellId = source.getAttribute("data-id") || "";
      const ownerName = source.getAttribute("data-owner-name") || "";
      const ownerSymbol = source.getAttribute("data-owner-symbol") || "*";
      const ownerSymbolImageUrl = source.getAttribute("data-owner-symbol-image-url") || "";
      const inputName = source.getAttribute("data-input-name") || `learn_magic_spell_${spellId}`;
      const level = readInt(source.getAttribute("data-level"), 1);
      const gradeLabel = source.getAttribute("data-grade-label") || String(level);
      const slotCost = readInt(source.getAttribute("data-slot-cost"), 1);
      const costLabel = source.getAttribute("data-cost-label") || `${slotCost} Slot${slotCost === 1 ? "" : "s"}`;
      const slotSourceKey = source.getAttribute("data-slot-source-key") || "";
      const slotSourceName = source.getAttribute("data-slot-source-name") || ownerName;
      const slotSourceRemaining = source.getAttribute("data-slot-source-remaining") || "0";
      const slotSourceCost = source.getAttribute("data-slot-source-cost") || String(slotCost);
      const symbolMarkup = ownerSymbolImageUrl
        ? `<img class="learn_spell_symbol__image" src="${escapeHtml(ownerSymbolImageUrl)}" alt="" width="18" height="18">`
        : escapeHtml(ownerSymbol);
      row.setAttribute("data-slot-cost", String(slotCost));
      row.setAttribute("data-cost-label", costLabel);
      row.setAttribute("data-slot-source-key", slotSourceKey);
      row.setAttribute("data-slot-source-name", slotSourceName);
      row.setAttribute("data-slot-source-remaining", slotSourceRemaining);
      row.setAttribute("data-slot-source-cost", slotSourceCost);
      row.setAttribute("data-slot-grade", String(level));
      row.innerHTML = `
        <td>
          <span>${safeName}</span>
          <span class="learn_meta_value learn_cart_spell_meta" aria-label="${escapeHtml(ownerName)}, Grad ${escapeHtml(gradeLabel)}">
            <span class="learn_spell_symbol" title="${escapeHtml(ownerName)}" aria-hidden="true">${symbolMarkup}</span>
            <span class="learn_spell_grade">Grad ${escapeHtml(gradeLabel)}</span>
          </span>
          <input type="hidden" name="${escapeHtml(inputName)}" value="1" data-learn-hidden>
        </td>
        <td>
          <div class="shop_qty_stepper">
            <input class="shop_cart_qty_input" type="number" min="0" max="1" value="1" data-learn-value>
          </div>
        </td>
        <td data-learn-cost>${escapeHtml(costLabel)}</td>
        <td><button type="button" class="shop_cart_remove_btn" data-learn-remove aria-label="Eintrag entfernen">x</button></td>
      `;
      return row;
    }

    if (kind === "magic-aspect") {
      const aspectId = source.getAttribute("data-id") || "";
      const base = readInt(source.getAttribute("data-base"), 0);
      const minAdd = -base;
      const max = readInt(source.getAttribute("data-max"), base);
      const remaining = readInt(source.getAttribute("data-remaining"), max);
      const maxAdd = Math.max(0, Math.min(max - base, remaining - selectedMagicAspectLevels()));
      const costPerLevel = readInt(source.getAttribute("data-cost-per-level"), 4);
      if (maxAdd < 1 && minAdd === 0) {
        return null;
      }
      const startAdd = maxAdd > 0 ? 1 : Math.max(minAdd, -1);
      row.setAttribute("data-base", String(base));
      row.setAttribute("data-max", String(max));
      row.setAttribute("data-remaining", String(remaining));
      row.setAttribute("data-cost-per-level", String(costPerLevel));
      row.innerHTML = `
        <td><span>${safeName}</span> <span data-learn-level-info>(${base + startAdd})</span><input type="hidden" name="learn_magic_aspect_${aspectId}" value="${startAdd}" data-learn-hidden></td>
        <td>
          <div class="shop_qty_stepper">
            <button type="button" class="shop_step_btn" data-learn-step-dec aria-label="Wert verringern">-</button>
            <input class="shop_cart_qty_input" type="number" min="${minAdd}" max="${maxAdd}" value="${startAdd}" data-learn-value>
            <button type="button" class="shop_step_btn" data-learn-step-inc aria-label="Wert erhoehen">+</button>
          </div>
        </td>
        <td data-learn-cost>0 EP</td>
        <td><button type="button" class="shop_cart_remove_btn" data-learn-remove aria-label="Eintrag entfernen">x</button></td>
      `;
      return row;
    }

    return null;
  };

  const addFromSource = (source) => {
    const key = source.getAttribute("data-key") || "";
    const kind = source.getAttribute("data-kind") || "";
    if (!key && kind !== "skill-new-spec") {
      return;
    }
    if (key) {
      const existing = cartBody.querySelector(`[data-learn-cart-item][data-key="${key}"]`);
      if (existing) {
        const input = existing.querySelector("[data-learn-value]");
        if (input instanceof HTMLInputElement) {
          input.focus();
        }
        return;
      }
    }
    const row = createRowFromSource(source);
    if (!row) {
      return;
    }
    cartBody.appendChild(row);
    bindRow(row);
    ensureEmptyRow();
    refreshTotals();
  };

  Array.from(document.querySelectorAll("[data-learn-source]")).forEach((source) => {
    source.addEventListener("click", () => {
      addFromSource(source);
    });
    source.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        addFromSource(source);
      }
    });
  });

  if (form.dataset.learnTotalsBound !== "1") {
    document.addEventListener("learn:refresh-totals", refreshTotals);
    form.dataset.learnTotalsBound = "1";
  }

  refreshTotals();

  const clearCart = () => {
    getRows().forEach((row) => row.remove());
    ensureEmptyRow();
    refreshTotals();
  };

  return { clearCart, refreshTotals };
}

export function initLearningMenu({ choiceWindowController = null } = {}) {
  const form = document.getElementById("learnForm");
  const cartBody = document.getElementById("learnCartBody");
  const budgetEl = document.getElementById("learnBudgetValue");
  const spentEl = document.getElementById("learnSpentValue");
  const remainingEl = document.getElementById("learnRemainingValue");
  const validationHint = document.getElementById("learnValidationHint");
  const applyBtn = document.getElementById("learnApplyBtn");
  const filterInput = document.getElementById("learnFilterInput");
  const hiddenInputContainer = document.getElementById("learnPendingChoiceInputs");
  const pendingNotices = Array.from(document.querySelectorAll("[data-pending-choice-notice]"));
  const pendingTriggers = Array.from(document.querySelectorAll("[data-pending-choice-trigger]"));
  const centerPendingNotice = document.getElementById("learnPendingChoiceCenterNotice");
  const sidebarPendingNotice = document.getElementById("learnPendingChoiceNotice");
  if (!form || !cartBody || !budgetEl || !spentEl || !remainingEl || !applyBtn || !hiddenInputContainer) {
    return null;
  }

  const groupDisclosureState = initPersistentDetails(
    "#learnWindow [data-learn-group]",
    "codexArcana.learn.categoryDisclosure.v1",
  );

  const cartController = initLearningCart(form, cartBody, budgetEl, spentEl, remainingEl, validationHint, applyBtn);
  const choiceController = createChoiceModalController({
    hiddenInputContainer,
    windowController: choiceWindowController,
  });

  const getRenderedPendingChoiceCount = () => Array.from(
    document.querySelectorAll("#learnChoicePanelList [data-choice-decision-id]"),
  ).filter((section) => {
    if (!(section instanceof HTMLElement)) {
      return false;
    }
    return (section.dataset.choiceInputType || "options") !== "unsupported";
  }).length;

  const syncPendingNotice = () => {
    if (!pendingNotices.length) {
      return;
    }
    const hasPending = choiceController
      ? choiceController.hasPendingChoices()
      : getRenderedPendingChoiceCount() > 0;
    pendingNotices.forEach((notice) => {
      if (!(notice instanceof HTMLElement)) {
        return;
      }
      notice.hidden = !hasPending;
    });
    if (sidebarPendingNotice instanceof HTMLElement) {
      sidebarPendingNotice.style.display = hasPending ? "" : "none";
    }
    if (centerPendingNotice instanceof HTMLElement) {
      centerPendingNotice.hidden = true;
      centerPendingNotice.style.display = "none";
    }
  };

  pendingTriggers.forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const opened = choiceController?.openNextPendingChoice() || false;
      if (!opened && choiceWindowController?.open) {
        choiceWindowController.open();
      }
    });
  });
  document.addEventListener("learn:choices-updated", syncPendingNotice);
  syncPendingNotice();

  form.addEventListener("learn:applied", (event) => {
    const level = String(event.detail?.level || "");
    if (level !== "error") {
      cartController.clearCart();
    } else {
      cartController.refreshTotals();
    }
  });

  const sourceFilterMenu = document.querySelector("[data-learn-magic-source-filter-menu]");
  const sourceFilterTrigger = document.querySelector("[data-learn-magic-source-filter-trigger]");
  const sourceFilterTriggerIcon = document.querySelector("[data-learn-magic-source-filter-trigger-icon]");
  const sourceFilterPopover = document.querySelector("[data-learn-magic-source-filter-popover]");
  const sourceFilterButtons = Array.from(document.querySelectorAll("[data-learn-magic-source-filter]"));
  const gradeFilterMenu = document.querySelector("[data-learn-magic-grade-filter-menu]");
  const gradeFilterTrigger = document.querySelector("[data-learn-magic-grade-filter-trigger]");
  const gradeFilterTriggerLabel = document.querySelector("[data-learn-magic-grade-filter-trigger-label]");
  const gradeFilterPopover = document.querySelector("[data-learn-magic-grade-filter-popover]");
  const gradeFilterButtons = Array.from(document.querySelectorAll("[data-learn-magic-grade-filter]"));
  const defaultSourceFilterIcon = sourceFilterTriggerIcon instanceof HTMLElement
    ? sourceFilterTriggerIcon.innerHTML
    : "";
  let activeMagicSourceFilter = "";
  let activeMagicGradeFilter = "";

  const closeMagicFilterMenus = () => {
    if (sourceFilterPopover instanceof HTMLElement) {
      sourceFilterPopover.hidden = true;
    }
    if (sourceFilterTrigger instanceof HTMLButtonElement) {
      sourceFilterTrigger.setAttribute("aria-expanded", "false");
    }
    if (gradeFilterPopover instanceof HTMLElement) {
      gradeFilterPopover.hidden = true;
    }
    if (gradeFilterTrigger instanceof HTMLButtonElement) {
      gradeFilterTrigger.setAttribute("aria-expanded", "false");
    }
  };

  const syncMagicFilterButtons = () => {
    sourceFilterButtons.forEach((button) => {
      if (!(button instanceof HTMLButtonElement)) {
        return;
      }
      const value = String(button.getAttribute("data-learn-magic-source-filter") || "all");
      const isActive = activeMagicSourceFilter ? value === activeMagicSourceFilter : value === "all";
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
    gradeFilterButtons.forEach((button) => {
      if (!(button instanceof HTMLButtonElement)) {
        return;
      }
      const value = String(button.getAttribute("data-learn-magic-grade-filter") || "all");
      const isActive = activeMagicGradeFilter ? value === activeMagicGradeFilter : value === "all";
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
    if (sourceFilterTrigger instanceof HTMLButtonElement) {
      sourceFilterTrigger.classList.toggle("is-filtered", Boolean(activeMagicSourceFilter));
    }
    if (sourceFilterTriggerIcon instanceof HTMLElement) {
      if (!activeMagicSourceFilter) {
        sourceFilterTriggerIcon.innerHTML = defaultSourceFilterIcon;
      } else {
        const selectedButton = sourceFilterButtons.find((button) => (
          button instanceof HTMLButtonElement
          && String(button.getAttribute("data-learn-magic-source-filter") || "") === activeMagicSourceFilter
        ));
        const selectedSymbol = selectedButton?.querySelector(".learn_magic_filter_symbol");
        sourceFilterTriggerIcon.innerHTML = selectedSymbol instanceof HTMLElement
          ? selectedSymbol.innerHTML
          : defaultSourceFilterIcon;
      }
    }
    if (gradeFilterTrigger instanceof HTMLButtonElement) {
      gradeFilterTrigger.classList.toggle("is-filtered", Boolean(activeMagicGradeFilter));
    }
    if (gradeFilterTriggerLabel instanceof HTMLElement) {
      gradeFilterTriggerLabel.textContent = activeMagicGradeFilter || "*";
    }
  };

  const applyLearningFilters = () => {
    const needle = filterInput instanceof HTMLInputElement
      ? String(filterInput.value || "").trim().toLowerCase()
      : "";
    const rows = Array.from(document.querySelectorAll("[data-learn-source]"));
    rows.forEach((row) => {
      if (!(row instanceof HTMLElement)) {
        return;
      }
      const haystack = String(row.getAttribute("data-learn-search") || "").toLowerCase();
      const kind = row.getAttribute("data-kind") || "";
      const matchesText = needle.length === 0 || haystack.includes(needle);
      const matchesSource = !activeMagicSourceFilter
        || kind !== "magic-spell"
        || String(row.getAttribute("data-filter-source-key") || row.getAttribute("data-slot-source-key") || "") === activeMagicSourceFilter;
      const matchesGrade = !activeMagicGradeFilter
        || kind !== "magic-spell"
        || String(row.getAttribute("data-level") || "") === activeMagicGradeFilter;
      row.hidden = !(matchesText && matchesSource && matchesGrade);
    });
    Array.from(document.querySelectorAll("[data-learn-group]")).forEach((group) => {
      const visible = Array.from(group.querySelectorAll("tr[data-learn-source]")).some((row) => !row.hidden);
      group.hidden = !visible;
      if ((needle || activeMagicSourceFilter || activeMagicGradeFilter) && visible && group instanceof HTMLDetailsElement) {
        group.open = true;
      } else if (!needle && !activeMagicSourceFilter && !activeMagicGradeFilter && group instanceof HTMLDetailsElement) {
        groupDisclosureState.restore(group);
      }
    });
    syncMagicFilterButtons();
  };

  if (filterInput instanceof HTMLInputElement) {
    filterInput.addEventListener("input", applyLearningFilters);
  }

  if (sourceFilterTrigger instanceof HTMLButtonElement && sourceFilterPopover instanceof HTMLElement) {
    sourceFilterTrigger.addEventListener("click", (event) => {
      event.stopPropagation();
      const willOpen = sourceFilterPopover.hidden;
      closeMagicFilterMenus();
      sourceFilterPopover.hidden = !willOpen;
      sourceFilterTrigger.setAttribute("aria-expanded", willOpen ? "true" : "false");
    });
    sourceFilterPopover.addEventListener("click", (event) => {
      event.stopPropagation();
    });
  }

  if (gradeFilterTrigger instanceof HTMLButtonElement && gradeFilterPopover instanceof HTMLElement) {
    gradeFilterTrigger.addEventListener("click", (event) => {
      event.stopPropagation();
      const willOpen = gradeFilterPopover.hidden;
      closeMagicFilterMenus();
      gradeFilterPopover.hidden = !willOpen;
      gradeFilterTrigger.setAttribute("aria-expanded", willOpen ? "true" : "false");
    });
    gradeFilterPopover.addEventListener("click", (event) => {
      event.stopPropagation();
    });
  }

  sourceFilterButtons.forEach((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    button.addEventListener("click", () => {
      const value = String(button.getAttribute("data-learn-magic-source-filter") || "all");
      activeMagicSourceFilter = value === "all" ? "" : value;
      closeMagicFilterMenus();
      applyLearningFilters();
    });
  });

  gradeFilterButtons.forEach((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    button.addEventListener("click", () => {
      const value = String(button.getAttribute("data-learn-magic-grade-filter") || "all");
      activeMagicGradeFilter = value === "all" ? "" : value;
      closeMagicFilterMenus();
      applyLearningFilters();
    });
  });

  document.addEventListener("click", (event) => {
    const target = event.target;
    const clickedSourceMenu = sourceFilterMenu instanceof HTMLElement && sourceFilterMenu.contains(target);
    const clickedGradeMenu = gradeFilterMenu instanceof HTMLElement && gradeFilterMenu.contains(target);
    if (!clickedSourceMenu && !clickedGradeMenu) {
      closeMagicFilterMenus();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeMagicFilterMenus();
    }
  });
  syncMagicFilterButtons();

  return { cartController, choiceController };
}





