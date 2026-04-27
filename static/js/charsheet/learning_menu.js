import { createChoiceModalController } from "./choice_modal.js";
import { clamp, escapeHtml, readInt } from "./utils.js";

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

  const calcSkillCost = (level) => (level <= 5 ? Math.max(0, level) : 5 + ((Math.max(0, level) - 5) * 2));
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
      const minAdd = kind === "skill-new-spec" ? 0 : -base;
      const maxAdd = Math.max(0, 10 - base);
      const hidden = row.querySelector("[data-learn-hidden]");
      value = clamp(value, minAdd, maxAdd);
      cost = calcSkillCost(base + value) - calcSkillCost(base);
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
      let writeAdd = false;
      value = clamp(value, minAdd, maxAdd);
      if (writeInput instanceof HTMLInputElement) {
        if (baseWrite) {
          writeInput.checked = true;
          writeInput.disabled = true;
        } else {
          writeAdd = writeInput.checked;
        }
      }
      const write = baseWrite || writeAdd;
      invalidWrite = write && base + value < 1;
      cost = calcLanguageCost(base + value, write, mother) - calcLanguageCost(base, baseWrite, mother);
      if (hidden instanceof HTMLInputElement) {
        hidden.value = String(value);
      }
      if (writeHidden instanceof HTMLInputElement) {
        writeHidden.value = writeAdd ? "1" : "0";
      }
      if (infoEl) {
        infoEl.textContent = `(${base + value})`;
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
    } else if (kind === "magic-spell") {
      const hidden = row.querySelector("[data-learn-hidden]");
      value = clamp(value, 0, 1);
      cost = value * readInt(row.getAttribute("data-cost"), 2);
      if (hidden instanceof HTMLInputElement) {
        hidden.value = String(value);
      }
    } else if (kind === "magic-aspect") {
      const base = readInt(row.getAttribute("data-base"), 0);
      const minAdd = -base;
      const max = readInt(row.getAttribute("data-max"), base);
      const maxAdd = Math.max(0, max - base);
      const hidden = row.querySelector("[data-learn-hidden]");
      value = clamp(value, minAdd, maxAdd);
      cost = Math.max(0, value) * readInt(row.getAttribute("data-cost-per-level"), 4);
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
    costCell.textContent = `${cost} EP`;
    return { cost, invalidWrite };
  };

  const refreshTotals = () => {
    let spent = 0;
    let invalidWrite = false;
    getRows().forEach((row) => {
      const result = syncRow(row);
      spent += result.cost;
      invalidWrite = invalidWrite || result.invalidWrite;
    });
    const budget = getBudget();
    const remaining = budget - spent;
    const liveBudgetEl = document.getElementById("learnBudgetValue");
    const liveSpentEl = document.getElementById("learnSpentValue");
    const liveRemainingEl = document.getElementById("learnRemainingValue");
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
    if (liveValidationHint) {
      const messages = [];
      if (remaining < 0) {
        messages.push("Zu wenig EP fuer die ausgewaehlten Lernschritte.");
      }
      if (invalidWrite) {
        messages.push("Schreiben benoetigt mindestens Sprachlevel 1.");
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
      writeInput.addEventListener("change", refreshTotals);
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
      const minAdd = -base;
      const maxAdd = Math.max(0, 10 - base);
      if (maxAdd < 1 && minAdd === 0) {
        return null;
      }
      const startAdd = maxAdd > 0 ? 1 : 0;
      row.setAttribute("data-base", String(base));
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
      const minAdd = -base;
      const maxAdd = Math.max(0, 10 - base);
      if (maxAdd < 1 && minAdd === 0) {
        return null;
      }
      const startAdd = maxAdd > 0 ? 1 : 0;
      row.setAttribute("data-base", String(base));
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
            <input class="shop_cart_qty_input" type="number" min="0" max="10" value="${startAdd}" data-learn-value>
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
      if (maxAdd < 1 && minAdd === 0 && baseWrite) {
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
            <label class="learn_lang_write"><input type="checkbox" data-learn-lang-write ${baseWrite ? "checked disabled" : ""}> Schreiben</label>
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

    if (kind === "magic-spell") {
      const spellId = source.getAttribute("data-id") || "";
      const ownerName = source.getAttribute("data-owner-name") || "";
      const level = readInt(source.getAttribute("data-level"), 1);
      const cost = readInt(source.getAttribute("data-cost"), 2);
      row.setAttribute("data-cost", String(cost));
      row.innerHTML = `
        <td><span>${safeName}</span> <span class="learn_meta_value">(${ownerName} | Grad ${level})</span><input type="hidden" name="learn_magic_spell_${spellId}" value="1" data-learn-hidden></td>
        <td>
          <div class="shop_qty_stepper">
            <input class="shop_cart_qty_input" type="number" min="0" max="1" value="1" data-learn-value>
          </div>
        </td>
        <td data-learn-cost>0 EP</td>
        <td><button type="button" class="shop_cart_remove_btn" data-learn-remove aria-label="Eintrag entfernen">x</button></td>
      `;
      return row;
    }

    if (kind === "magic-aspect") {
      const aspectId = source.getAttribute("data-id") || "";
      const base = readInt(source.getAttribute("data-base"), 0);
      const minAdd = -base;
      const max = readInt(source.getAttribute("data-max"), base);
      const maxAdd = Math.max(0, max - base);
      const costPerLevel = readInt(source.getAttribute("data-cost-per-level"), 4);
      if (maxAdd < 1 && minAdd === 0) {
        return null;
      }
      const startAdd = maxAdd > 0 ? 1 : 0;
      row.setAttribute("data-base", String(base));
      row.setAttribute("data-max", String(max));
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

  return { refreshTotals };
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
  const pendingNotice = document.getElementById("learnPendingChoiceNotice");
  const pendingTrigger = document.getElementById("learnPendingChoiceTrigger");
  if (!form || !cartBody || !budgetEl || !spentEl || !remainingEl || !applyBtn || !hiddenInputContainer) {
    return null;
  }

  const cartController = initLearningCart(form, cartBody, budgetEl, spentEl, remainingEl, validationHint, applyBtn);
  const choiceController = createChoiceModalController({
    hiddenInputContainer,
    windowController: choiceWindowController,
  });

  const syncPendingNotice = () => {
    if (!pendingNotice) {
      return;
    }
    const hasPending = choiceController ? choiceController.hasPendingChoices() : false;
    pendingNotice.hidden = !hasPending;
  };

  pendingTrigger?.addEventListener("click", () => {
    choiceController?.openNextPendingChoice();
  });
  document.addEventListener("learn:choices-updated", syncPendingNotice);
  syncPendingNotice();

  if (filterInput instanceof HTMLInputElement) {
    filterInput.addEventListener("input", () => {
      const needle = String(filterInput.value || "").trim().toLowerCase();
      const rows = Array.from(document.querySelectorAll("[data-learn-source]"));
      rows.forEach((row) => {
        const haystack = String(row.getAttribute("data-learn-search") || "").toLowerCase();
        row.hidden = needle.length > 0 && !haystack.includes(needle);
      });
      Array.from(document.querySelectorAll("[data-learn-group]")).forEach((group) => {
        const visible = Array.from(group.querySelectorAll("tr[data-learn-source]")).some((row) => !row.hidden);
        group.hidden = !visible;
        if (needle && visible && group instanceof HTMLDetailsElement) {
          group.open = true;
        }
      });
    });
  }

  return { cartController, choiceController };
}





