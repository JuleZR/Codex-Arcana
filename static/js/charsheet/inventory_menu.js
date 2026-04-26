import { createFloatingWindowController } from "./window_manager.js";

function parseIdList(rawValue) {
  return String(rawValue || "")
    .split(",")
    .map((value) => Number.parseInt(value.trim(), 10))
    .filter((value) => Number.isInteger(value) && value > 0);
}

function parseJsonList(rawValue) {
  try {
    const parsed = JSON.parse(String(rawValue || "[]"));
    return Array.isArray(parsed) ? parsed : [];
  } catch (_error) {
    return [];
  }
}

function normalizeSearchValue(value) {
  return String(value || "").trim().toLowerCase();
}

function closeMenu(menu) {
  if (!(menu instanceof HTMLElement)) {
    return;
  }
  const trigger = menu.querySelector(".inv_menu_trigger");
  const panel = menu.querySelector(".inv_menu_panel");
  if (!(trigger instanceof HTMLButtonElement) || !(panel instanceof HTMLElement)) {
    return;
  }
  panel.hidden = true;
  panel.style.left = "";
  panel.style.top = "";
  trigger.setAttribute("aria-expanded", "false");
  menu.classList.remove("is-open");
  menu.closest(".inv_row")?.classList.remove("is-menu-open");
}

function positionMenuPanel(menu) {
  if (!(menu instanceof HTMLElement)) {
    return;
  }
  const trigger = menu.querySelector(".inv_menu_trigger");
  const panel = menu.querySelector(".inv_menu_panel");
  if (!(trigger instanceof HTMLButtonElement) || !(panel instanceof HTMLElement)) {
    return;
  }
  const triggerRect = trigger.getBoundingClientRect();
  const panelRect = panel.getBoundingClientRect();
  const maxLeft = Math.max(12, window.innerWidth - panelRect.width - 12);
  const left = Math.min(Math.max(12, triggerRect.right - panelRect.width), maxLeft);
  const top = Math.min(
    Math.max(12, triggerRect.bottom + 4),
    Math.max(12, window.innerHeight - panelRect.height - 12),
  );
  panel.style.left = `${left}px`;
  panel.style.top = `${top}px`;
}

export function initInventoryMenu({ warningWindowController = null, modifyWindowController = null } = {}) {
  if (document.body.dataset.inventoryMenuBound === "1") {
    return;
  }
  document.body.dataset.inventoryMenuBound = "1";

  const runeWindow = document.getElementById("runeRetrofitWindow");
  const runeCloseButton = document.getElementById("runeRetrofitWindowClose");
  const runeCancelButton = document.getElementById("runeRetrofitCancelBtn");
  const runeForm = document.getElementById("runeRetrofitForm");
  const runeOptions = document.getElementById("runeRetrofitOptions");
  const runeItemName = document.getElementById("runeRetrofitItemName");
  const runeBaseInfo = document.getElementById("runeRetrofitBaseInfo");
  const runeSearchInput = document.getElementById("runeRetrofitSearch");
  const runeDropdown = document.getElementById("runeRetrofitDropdown");
  const runeDropdownTrigger = document.getElementById("runeRetrofitDropdownTrigger");
  const runeDropdownPanel = document.getElementById("runeRetrofitDropdownPanel");
  const runeSelectionCount = document.getElementById("runeRetrofitSelectionCount");
  const runeTriggerLabel = document.getElementById("runeRetrofitTriggerLabel");
  const runeQualitySelect = document.getElementById("runeRetrofitQuality");
  const runeExperienceCostInput = document.querySelector("#runeRetrofitForm input[name='experience_cost']");
  const runeMoneyCostInput = document.querySelector("#runeRetrofitForm input[name='money_cost']");
  const runeDescriptionInput = document.getElementById("runeRetrofitDescription");
  const magicEffectsList = document.getElementById("runeRetrofitMagicEffectsList");
  const magicEffectTemplate = document.getElementById("runeRetrofitMagicEffectTemplate");
  const magicAddEffectButton = document.getElementById("runeRetrofitAddEffectBtn");
  const magicPayloadInput = document.getElementById("runeRetrofitMagicModifierPayloads");
  const runePayloadInput = document.getElementById("runeRetrofitRunePayloads");

  let runeChoices = [];
  try {
    runeChoices = JSON.parse(document.getElementById("rune-retrofit-choices")?.textContent || "[]");
  } catch (_error) {
    runeChoices = [];
  }

  let pendingRuneSubmit = false;
  const floatingController = modifyWindowController || createFloatingWindowController({
    windowEl: runeWindow,
    closeButton: runeCloseButton,
    handle: document.getElementById("runeRetrofitWindowHandle"),
    startTop: 116,
    storageKey: "charsheet.runeRetrofitWindow",
    allowPersistedOpen: false,
    startRightInset: 214,
  });

  // ── Rune payload serialization ─────────────────────────────────────────────

  const serializeRunePayloads = () => {
    if (!(runePayloadInput instanceof HTMLInputElement) || !(runeOptions instanceof HTMLElement)) {
      return;
    }
    const payloads = [];
    runeOptions.querySelectorAll(".rune_option").forEach((option) => {
      if (!(option instanceof HTMLElement)) {
        return;
      }
      const runeId = Number.parseInt(option.dataset.runeId || "0", 10);
      if (!runeId) {
        return;
      }
      const allowMultiple = option.dataset.allowMultiple === "1";
      if (allowMultiple) {
        option.querySelectorAll(".rune_option_spec").forEach((input, idx) => {
          payloads.push({
            rune_id: runeId,
            specification: String(input instanceof HTMLInputElement ? input.value : "").trim(),
            slot: idx + 1,
          });
        });
      } else {
        const checkbox = option.querySelector("input[type='checkbox']");
        if (checkbox instanceof HTMLInputElement && checkbox.checked) {
          const specInput = option.querySelector(".rune_option_spec");
          payloads.push({
            rune_id: runeId,
            specification: String(specInput instanceof HTMLInputElement ? specInput.value : "").trim(),
            slot: 1,
          });
        }
      }
    });
    runePayloadInput.value = JSON.stringify(payloads);
  };

  // ── Selection count / label ────────────────────────────────────────────────

  const syncRuneSelectionCount = () => {
    if (!(runeSelectionCount instanceof HTMLElement) || !(runeOptions instanceof HTMLElement)) {
      return;
    }
    let selectedCount = 0;
    const selectedNames = [];

    runeOptions.querySelectorAll(".rune_option").forEach((option) => {
      if (!(option instanceof HTMLElement)) {
        return;
      }
      const allowMultiple = option.dataset.allowMultiple === "1";
      if (allowMultiple) {
        const countEl = option.querySelector(".rune_option_count");
        const count = Number.parseInt(countEl?.textContent || "0", 10) || 0;
        if (count > 0) {
          selectedCount += count;
          const name = option.querySelector(".rune_option_name")?.textContent?.trim() || "";
          selectedNames.push(count > 1 ? `${name} ×${count}` : name);
        }
      } else {
        const checkbox = option.querySelector("input[type='checkbox']");
        if (checkbox instanceof HTMLInputElement && checkbox.checked) {
          selectedCount += 1;
          const name = option.querySelector(".rune_option_name")?.textContent?.trim() || "";
          selectedNames.push(name);
        }
      }
    });

    runeSelectionCount.textContent = String(selectedCount);
    if (!(runeTriggerLabel instanceof HTMLElement)) {
      return;
    }
    if (!selectedCount) {
      runeTriggerLabel.textContent = "Keine Runen ausgewählt";
      return;
    }
    runeTriggerLabel.textContent =
      selectedCount <= 2 ? selectedNames.join(", ") : `${selectedCount} Runen ausgewählt`;
  };

  // ── Dropdown open/close ────────────────────────────────────────────────────

  const toggleRuneDropdown = (forceOpen = null) => {
    if (!(runeDropdownPanel instanceof HTMLElement) || !(runeDropdownTrigger instanceof HTMLButtonElement)) {
      return;
    }
    const shouldOpen = forceOpen === null ? runeDropdownPanel.hidden : Boolean(forceOpen);
    runeDropdownPanel.hidden = !shouldOpen;
    runeDropdownTrigger.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
    runeDropdown?.classList.toggle("is-open", shouldOpen);
  };

  const openRuneWindow = () => {
    runeForm?.querySelector(".rune_window_save_error")?.remove();
    floatingController?.open?.();
    runeSearchInput?.focus();
  };

  const closeRuneWindow = () => {
    floatingController?.close?.();
    pendingRuneSubmit = false;
    if (runeSearchInput instanceof HTMLInputElement) {
      runeSearchInput.value = "";
    }
    toggleRuneDropdown(false);
  };

  const filterRuneEntries = () => {
    const query = normalizeSearchValue(runeSearchInput?.value);
    runeOptions?.querySelectorAll(".rune_option").forEach((entry) => {
      if (!(entry instanceof HTMLElement)) {
        return;
      }
      const haystack = normalizeSearchValue(entry.dataset.runeSearch || "");
      entry.hidden = query ? !haystack.includes(query) : false;
    });
  };

  // ── Magic effect rows ──────────────────────────────────────────────────────

  const syncMagicEffectRow = (row) => {
    if (!(row instanceof HTMLElement)) {
      return;
    }
    const targetKindSelect = row.querySelector("[data-magic-target-kind]");
    const valueInput = row.querySelector("[data-magic-value-input]");
    const selectedKind = String(targetKindSelect?.value || "");
    row.querySelectorAll("[data-magic-target-row]").forEach((targetRow) => {
      if (!(targetRow instanceof HTMLElement)) {
        return;
      }
      const rowKind = String(targetRow.dataset.magicTargetRow || "");
      const isActive = selectedKind === rowKind;
      targetRow.hidden = !isActive;
      const select = targetRow.querySelector("select");
      if (select) {
        select.disabled = !isActive;
      }
    });
    if (valueInput instanceof HTMLInputElement) {
      valueInput.setCustomValidity("");
    }
  };

  const serializeMagicEffects = () => {
    if (!(magicPayloadInput instanceof HTMLInputElement) || !(magicEffectsList instanceof HTMLElement)) {
      return;
    }
    const payloads = [];
    magicEffectsList.querySelectorAll("[data-magic-effect-row]").forEach((row) => {
      if (!(row instanceof HTMLElement)) {
        return;
      }
      const targetKind = String(row.querySelector("[data-magic-target-kind]")?.value || "").trim();
      if (!targetKind) {
        return;
      }
      const payload = {
        target_kind: targetKind,
        value: String(row.querySelector("[data-magic-value-input]")?.value || "0").trim(),
        effect_description: String(row.querySelector("[data-magic-effect-description]")?.value || "").trim(),
      };
      if (targetKind === "attribute") {
        payload.target_attribute = String(row.querySelector("[data-magic-target-select='attribute']")?.value || "").trim();
      } else if (targetKind === "stat") {
        payload.target_stat = String(row.querySelector("[data-magic-target-select='stat']")?.value || "").trim();
      } else if (targetKind === "skill") {
        payload.target_skill = String(row.querySelector("[data-magic-target-select='skill']")?.value || "").trim();
      } else if (targetKind === "category") {
        payload.target_skill_category = String(row.querySelector("[data-magic-target-select='category']")?.value || "").trim();
      } else if (targetKind === "item_category") {
        payload.target_item_category = String(row.querySelector("[data-magic-target-select='item_category']")?.value || "").trim();
      } else if (targetKind === "specialization") {
        payload.target_specialization = String(row.querySelector("[data-magic-target-select='specialization']")?.value || "").trim();
      }
      payloads.push(payload);
    });
    magicPayloadInput.value = JSON.stringify(payloads);
  };

  const syncMagicEffectRemoveButtons = () => {
    if (!(magicEffectsList instanceof HTMLElement)) {
      return;
    }
    const rows = Array.from(magicEffectsList.querySelectorAll("[data-magic-effect-row]"));
    rows.forEach((row, index) => {
      if (!(row instanceof HTMLElement)) {
        return;
      }
      const title = row.querySelector(".shop_magic_effect_title");
      if (title instanceof HTMLElement) {
        title.textContent = `Effekt ${index + 1}`;
      }
      const removeButton = row.querySelector("[data-remove-magic-effect]");
      if (removeButton instanceof HTMLButtonElement) {
        removeButton.hidden = false;
      }
    });
  };

  const addMagicEffectRow = (initialPayload = null) => {
    if (!(magicEffectsList instanceof HTMLElement) || !(magicEffectTemplate instanceof HTMLTemplateElement)) {
      return null;
    }
    const fragment = magicEffectTemplate.content.cloneNode(true);
    const row = fragment.querySelector("[data-magic-effect-row]");
    if (!(row instanceof HTMLElement)) {
      return null;
    }
    magicEffectsList.append(row);
    if (initialPayload && typeof initialPayload === "object") {
      const targetKindSelect = row.querySelector("[data-magic-target-kind]");
      const valueInput = row.querySelector("[data-magic-value-input]");
      const descriptionInput = row.querySelector("[data-magic-effect-description]");
      if (targetKindSelect instanceof HTMLSelectElement) {
        targetKindSelect.value = String(initialPayload.target_kind || "");
      }
      if (valueInput instanceof HTMLInputElement) {
        valueInput.value = String(initialPayload.value ?? "0");
      }
      if (descriptionInput instanceof HTMLInputElement) {
        descriptionInput.value = String(initialPayload.effect_description || "");
      }
      const targetFieldMap = {
        attribute: "target_attribute",
        stat: "target_stat",
        skill: "target_skill",
        category: "target_skill_category",
        item_category: "target_item_category",
        specialization: "target_specialization",
      };
      Object.entries(targetFieldMap).forEach(([kind, fieldName]) => {
        const select = row.querySelector(`[data-magic-target-select='${kind}']`);
        if (select instanceof HTMLSelectElement && initialPayload[fieldName] !== undefined) {
          select.value = String(initialPayload[fieldName] || "");
        }
      });
    }
    row.querySelector("[data-magic-target-kind]")?.addEventListener("change", () => {
      syncMagicEffectRow(row);
      serializeMagicEffects();
    });
    row.querySelector("[data-magic-value-input]")?.addEventListener("input", serializeMagicEffects);
    row.querySelector("[data-magic-effect-description]")?.addEventListener("input", serializeMagicEffects);
    row.querySelectorAll("[data-magic-target-select]").forEach((select) => {
      select.addEventListener("change", serializeMagicEffects);
    });
    row.querySelector("[data-remove-magic-effect]")?.addEventListener("click", () => {
      row.remove();
      syncMagicEffectRemoveButtons();
      serializeMagicEffects();
    });
    syncMagicEffectRow(row);
    syncMagicEffectRemoveButtons();
    serializeMagicEffects();
    return row;
  };

  const populateMagicEffects = (payloads) => {
    if (!(magicEffectsList instanceof HTMLElement)) {
      return;
    }
    magicEffectsList.innerHTML = "";
    payloads.forEach((payload) => {
      addMagicEffectRow(payload);
    });
    if (!payloads.length) {
      serializeMagicEffects();
    }
  };

  // ── Build one rune option element ─────────────────────────────────────────

  const buildRuneOption = (rune, existingSlots) => {
    const runeId = Number(rune.id);
    const allowMultiple = Boolean(rune.allow_multiple);
    const hasSpec = Boolean(rune.has_specialization);
    const specLabel = String(rune.specialization_label || "Bezeichnung");

    const wrapper = document.createElement(allowMultiple ? "div" : "label");
    wrapper.className = "shop_item_form_checklist_item rune_option";
    if (allowMultiple) {
      wrapper.className += " rune_option--multiple";
    }
    wrapper.dataset.runeId = String(runeId);
    wrapper.dataset.allowMultiple = allowMultiple ? "1" : "0";
    wrapper.dataset.runeSearch = `${rune.name || ""} ${rune.description || ""}`;

    if (allowMultiple) {
      // ── Counter UI ─────────────────────────────────────────────────────────
      const header = document.createElement("div");
      header.className = "rune_option_header";

      const decrementBtn = document.createElement("button");
      decrementBtn.type = "button";
      decrementBtn.className = "rune_option_decrement shop_step_btn";
      decrementBtn.textContent = "−";
      decrementBtn.setAttribute("aria-label", "Slot entfernen");

      const countDisplay = document.createElement("span");
      countDisplay.className = "rune_option_count";
      countDisplay.textContent = String(existingSlots.length);

      const incrementBtn = document.createElement("button");
      incrementBtn.type = "button";
      incrementBtn.className = "rune_option_increment shop_step_btn";
      incrementBtn.textContent = "+";
      incrementBtn.setAttribute("aria-label", "Slot hinzufügen");

      const copy = document.createElement("span");
      copy.className = "rune_option_copy";
      const nameSpan = document.createElement("span");
      nameSpan.className = "rune_option_name";
      nameSpan.textContent = rune.name || "Unbenannte Rune";
      const bodySpan = document.createElement("span");
      bodySpan.className = "rune_option_body";
      bodySpan.textContent = rune.description || "Keine Beschreibung vorhanden.";
      copy.append(nameSpan, bodySpan);

      header.append(decrementBtn, countDisplay, incrementBtn, copy);

      const specsContainer = document.createElement("div");
      specsContainer.className = "rune_option_specs";

      const addSpecInput = (initialValue = "") => {
        if (!hasSpec) {
          return;
        }
        const specInput = document.createElement("input");
        specInput.type = "text";
        specInput.className = "rune_option_spec sheet-window__field";
        specInput.placeholder = specLabel;
        specInput.maxLength = 100;
        specInput.value = initialValue;
        specsContainer.append(specInput);
        specInput.addEventListener("input", serializeRunePayloads);
      };

      // Pre-populate existing slots
      existingSlots.forEach((slot) => {
        addSpecInput(slot.specification);
      });

      decrementBtn.addEventListener("click", () => {
        const current = Number.parseInt(countDisplay.textContent || "0", 10) || 0;
        if (current <= 0) {
          return;
        }
        countDisplay.textContent = String(current - 1);
        if (hasSpec) {
          const inputs = specsContainer.querySelectorAll(".rune_option_spec");
          inputs[inputs.length - 1]?.remove();
        }
        syncRuneSelectionCount();
        serializeRunePayloads();
      });

      incrementBtn.addEventListener("click", () => {
        const current = Number.parseInt(countDisplay.textContent || "0", 10) || 0;
        countDisplay.textContent = String(current + 1);
        addSpecInput();
        syncRuneSelectionCount();
        serializeRunePayloads();
      });

      wrapper.append(header, specsContainer);
    } else {
      // ── Checkbox UI ────────────────────────────────────────────────────────
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = String(runeId);
      input.checked = existingSlots.length > 0;

      const copy = document.createElement("span");
      copy.className = "rune_option_copy";
      const nameSpan = document.createElement("span");
      nameSpan.className = "rune_option_name";
      nameSpan.textContent = rune.name || "Unbenannte Rune";
      const bodySpan = document.createElement("span");
      bodySpan.className = "rune_option_body";
      bodySpan.textContent = rune.description || "Keine Beschreibung vorhanden.";
      copy.append(nameSpan, bodySpan);

      wrapper.append(input, copy);

      let specInput = null;
      if (hasSpec) {
        specInput = document.createElement("input");
        specInput.type = "text";
        specInput.className = "rune_option_spec sheet-window__field";
        specInput.placeholder = specLabel;
        specInput.maxLength = 100;
        specInput.hidden = !input.checked;
        if (existingSlots.length > 0) {
          specInput.value = existingSlots[0].specification;
        }
        wrapper.append(specInput);
        specInput.addEventListener("input", serializeRunePayloads);
      }

      input.addEventListener("change", () => {
        if (specInput) {
          specInput.hidden = !input.checked;
          if (!input.checked) {
            specInput.value = "";
          }
        }
        syncRuneSelectionCount();
        serializeRunePayloads();
      });
    }

    return wrapper;
  };

  // ── Open rune window ───────────────────────────────────────────────────────

  document.addEventListener("click", (event) => {
    const toggleBtn = event.target instanceof Element
      ? event.target.closest("[data-rune-toggle]")
      : null;
    if (toggleBtn instanceof HTMLButtonElement) {
      event.preventDefault();
      event.stopPropagation();
      const controlsId = toggleBtn.getAttribute("aria-controls");
      const list = controlsId
        ? document.getElementById(controlsId)
        : toggleBtn.closest(".inv_row")?.querySelector(".inv_rune_list");
      if (list instanceof HTMLElement) {
        const willOpen = list.hidden;
        list.hidden = !willOpen;
        toggleBtn.setAttribute("aria-expanded", willOpen ? "true" : "false");
        toggleBtn.classList.toggle("is-open", willOpen);
      }
      return;
    }
  });

  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const trigger = target?.closest(".inv_menu_trigger");
    const menu = trigger?.closest(".inv_menu");

    document.querySelectorAll(".inv_menu").forEach((entry) => {
      if (entry !== menu) {
        closeMenu(entry);
      }
    });

    if (trigger instanceof HTMLButtonElement && menu instanceof HTMLElement) {
      event.preventDefault();
      event.stopPropagation();
      const panel = menu.querySelector(".inv_menu_panel");
      if (panel instanceof HTMLElement && panel.hidden) {
        panel.hidden = false;
        trigger.setAttribute("aria-expanded", "true");
        menu.classList.add("is-open");
        menu.closest(".inv_row")?.classList.add("is-menu-open");
        positionMenuPanel(menu);
      } else {
        closeMenu(menu);
      }
      return;
    }

    if (target?.closest(".inv_menu_panel")) {
      return;
    }

    if (
      runeDropdown instanceof HTMLElement &&
      !target?.closest("#runeRetrofitDropdown") &&
      runeWindow?.classList.contains("is-open")
    ) {
      toggleRuneDropdown(false);
    }

    document.querySelectorAll(".inv_menu").forEach((entry) => closeMenu(entry));
  });

  document.addEventListener("click", (event) => {
    const button = event.target instanceof Element
      ? event.target.closest("[data-require-shift-delete]")
      : null;
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    if (event.shiftKey) {
      warningWindowController?.close?.();
      return;
    }
    event.preventDefault();
    warningWindowController?.open?.();
  });

  document.addEventListener("click", (event) => {
    const button = event.target instanceof Element
      ? event.target.closest("[data-open-rune-window]")
      : null;
    if (
      !(button instanceof HTMLButtonElement) ||
      !(runeForm instanceof HTMLFormElement) ||
      !(runeOptions instanceof HTMLElement)
    ) {
      return;
    }

    const characterItemId = button.getAttribute("data-character-item-id") || "";
    const itemName = button.getAttribute("data-item-name") || "-";
    const baseRuneIds = new Set(parseIdList(button.getAttribute("data-base-rune-ids")));
    const currentQuality = String(button.getAttribute("data-current-quality") || "common");
    const baseRuneNames = String(button.getAttribute("data-base-rune-names") || "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    const description = String(button.getAttribute("data-description") || "");
    const magicModifierPayloads = parseJsonList(button.getAttribute("data-magic-modifier-payloads"));

    // Build spec map: rune_id → [{specification, slot}]
    const rawRuneSpecs = parseJsonList(button.getAttribute("data-rune-specs"));
    const runeSpecsByRuneId = {};
    rawRuneSpecs.forEach((spec) => {
      const runeId = Number(spec.rune_id);
      if (!runeId) {
        return;
      }
      if (!runeSpecsByRuneId[runeId]) {
        runeSpecsByRuneId[runeId] = [];
      }
      runeSpecsByRuneId[runeId].push({
        specification: String(spec.specification || ""),
        slot: Number(spec.slot || 1),
      });
    });

    // Legacy fallback: use extra_rune_ids when no rune_specs exist yet
    const extraRuneIds = new Set(parseIdList(button.getAttribute("data-extra-rune-ids")));
    const useLegacy = rawRuneSpecs.length === 0 && extraRuneIds.size > 0;

    runeForm.action = `/character-item/${characterItemId}/runes/update/`;
    runeOptions.innerHTML = "";
    if (runeSearchInput instanceof HTMLInputElement) {
      runeSearchInput.value = "";
    }
    if (runeQualitySelect instanceof HTMLSelectElement) {
      runeQualitySelect.value = currentQuality;
    }
    if (runeExperienceCostInput instanceof HTMLInputElement) {
      runeExperienceCostInput.value = "0";
    }
    if (runeMoneyCostInput instanceof HTMLInputElement) {
      runeMoneyCostInput.value = "0";
    }
    if (runeDescriptionInput instanceof HTMLTextAreaElement) {
      runeDescriptionInput.value = description;
    }
    if (runeItemName instanceof HTMLElement) {
      runeItemName.textContent = itemName;
    }
    if (runeBaseInfo instanceof HTMLElement) {
      runeBaseInfo.textContent = baseRuneNames.length
        ? `Basis-Runen: ${baseRuneNames.join(", ")}`
        : "Keine Basis-Runen vorhanden.";
    }

    let availableCount = 0;
    runeChoices.forEach((rune) => {
      if (baseRuneIds.has(Number(rune?.id))) {
        return;
      }
      availableCount += 1;

      const runeId = Number(rune.id);
      let existingSlots = runeSpecsByRuneId[runeId] || [];

      // Legacy: single checked slot without spec
      if (useLegacy && existingSlots.length === 0 && extraRuneIds.has(runeId)) {
        existingSlots = [{ specification: "", slot: 1 }];
      }

      runeOptions.append(buildRuneOption(rune, existingSlots));
    });

    if (!availableCount) {
      const empty = document.createElement("p");
      empty.className = "shop_empty";
      empty.textContent = "Keine weiteren Runen zum Nachrüsten verfügbar.";
      runeOptions.append(empty);
    }

    populateMagicEffects(magicModifierPayloads);
    syncRuneSelectionCount();
    serializeRunePayloads();
    filterRuneEntries();
    openRuneWindow();
    closeMenu(button.closest(".inv_menu"));
  });

  runeSearchInput?.addEventListener("input", filterRuneEntries);
  runeDropdownTrigger?.addEventListener("click", () => {
    toggleRuneDropdown();
  });
  runeCloseButton?.addEventListener("click", closeRuneWindow);
  runeCancelButton?.addEventListener("click", closeRuneWindow);
  magicAddEffectButton?.addEventListener("click", () => {
    addMagicEffectRow();
  });

  runeForm?.addEventListener("submit", () => {
    pendingRuneSubmit = true;
    serializeMagicEffects();
    serializeRunePayloads();
    runeForm?.querySelector(".rune_window_save_error")?.remove();
  });

  runeForm?.addEventListener("sheet:action-failed", () => {
    pendingRuneSubmit = false;
    const saveBtn = runeForm?.querySelector(".shop_item_save_btn");
    if (saveBtn instanceof HTMLButtonElement) {
      saveBtn.disabled = false;
    }
    const existingError = runeForm?.querySelector(".rune_window_save_error");
    if (!existingError) {
      const msg = document.createElement("p");
      msg.className = "rune_window_save_error shop_item_form_hint shop_item_form_hint--error";
      msg.textContent = "Speichern fehlgeschlagen. Bitte Eingaben prüfen.";
      runeForm?.querySelector(".shop_item_form_actions")?.before(msg);
    }
  });

  document.addEventListener("charsheet:partials-applied", () => {
    if (pendingRuneSubmit) {
      closeRuneWindow();
    }
  });
  window.addEventListener("resize", () => {
    document.querySelectorAll(".inv_menu.is-open").forEach((menu) => {
      positionMenuPanel(menu);
    });
  });
  document.addEventListener("scroll", () => {
    document.querySelectorAll(".inv_menu").forEach((menu) => closeMenu(menu));
  }, true);
}
