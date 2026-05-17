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

function parseJsonObject(rawValue) {
  try {
    const parsed = JSON.parse(String(rawValue || "{}"));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch (_error) {
    return {};
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
  const runeNameInput = document.getElementById("runeRetrofitCustomName");
  const runePriceInput = document.getElementById("runeRetrofitPrice");
  const runeWeightInput = document.getElementById("runeRetrofitWeight");
  const runeSizeClassSelect = document.getElementById("runeRetrofitSizeClass");
  const runeDescriptionInput = document.getElementById("runeRetrofitDescription");
  const runeImageInput = document.getElementById("runeRetrofitImageInput");
  const runeImagePreview = document.getElementById("runeRetrofitImagePreview");
  const runeImagePreviewImg = document.getElementById("runeRetrofitImagePreviewImg");
  const runeRemoveImageInput = document.getElementById("runeRetrofitRemoveImageInput");
  const runeRemoveImageRow = document.getElementById("runeRetrofitImageRemoveRow");
  const magicEffectsList = document.getElementById("runeRetrofitMagicEffectsList");
  const magicEffectTemplate = document.getElementById("runeRetrofitMagicEffectTemplate");
  const magicAddEffectButton = document.getElementById("runeRetrofitAddEffectBtn");
  const magicPayloadInput = document.getElementById("runeRetrofitMagicModifierPayloads");
  const runePayloadInput = document.getElementById("runeRetrofitRunePayloads");
  const runeArmorFields = document.getElementById("runeRetrofitArmorFields");
  const runeWeaponFields = document.getElementById("runeRetrofitWeaponFields");
  const runeShieldFields = document.getElementById("runeRetrofitShieldFields");
  const runeWeaponWieldMode = document.getElementById("runeRetrofitWeaponWieldMode");
  const runeWeaponTwoHandFields = document.getElementById("runeRetrofitWeaponTwoHandFields");
  let retrofitItemType = "";
  const WEAPON_ONLY_MAGIC_TARGET_KINDS = ["weapon_maneuver", "weapon_damage", "weapon_damage_dice", "weapon_mastery_bonus"];
  const WEAPON_MASTERY_BONUS_KIND = "weapon_mastery_bonus";
  const WEAPON_MASTERY_BONUS_DESCRIPTION = "Waffenmeister-Bonus +1/+1";
  const MAX_RUNES_PER_ITEM = 5;
  const DEFAULT_RUNE_CRAFTER_LEVEL = 1;
  const MAX_RUNE_CRAFTER_LEVEL = 10;
  let maxAdditionalRuneSlots = MAX_RUNES_PER_ITEM;

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
        option.querySelectorAll("[data-rune-slot]").forEach((slotRow, idx) => {
          const specInput = slotRow.querySelector(".rune_option_spec");
          const crafterLevelInput = slotRow.querySelector(".rune_option_crafter_level");
          payloads.push({
            rune_id: runeId,
            specification: String(specInput instanceof HTMLInputElement ? specInput.value : "").trim(),
            slot: idx + 1,
            crafter_level: normalizeCrafterLevel(crafterLevelInput instanceof HTMLInputElement ? crafterLevelInput.value : ""),
          });
        });
      } else {
        const checkbox = option.querySelector("input[type='checkbox']");
        if (checkbox instanceof HTMLInputElement && checkbox.checked) {
          const slotRow = option.querySelector("[data-rune-slot]");
          const specInput = slotRow?.querySelector(".rune_option_spec");
          const crafterLevelInput = slotRow?.querySelector(".rune_option_crafter_level");
          payloads.push({
            rune_id: runeId,
            specification: String(specInput instanceof HTMLInputElement ? specInput.value : "").trim(),
            slot: 1,
            crafter_level: normalizeCrafterLevel(crafterLevelInput instanceof HTMLInputElement ? crafterLevelInput.value : ""),
          });
        }
      }
    });
    runePayloadInput.value = JSON.stringify(payloads);
  };

  const normalizeCrafterLevel = (rawValue) => {
    const parsed = Number.parseInt(String(rawValue || DEFAULT_RUNE_CRAFTER_LEVEL), 10);
    if (!Number.isInteger(parsed)) {
      return DEFAULT_RUNE_CRAFTER_LEVEL;
    }
    return Math.min(MAX_RUNE_CRAFTER_LEVEL, Math.max(DEFAULT_RUNE_CRAFTER_LEVEL, parsed));
  };

  const getSelectedRuneCount = () => {
    if (!(runeOptions instanceof HTMLElement)) {
      return 0;
    }
    let selectedCount = 0;
    runeOptions.querySelectorAll(".rune_option").forEach((option) => {
      if (!(option instanceof HTMLElement)) {
        return;
      }
      const allowMultiple = option.dataset.allowMultiple === "1";
      if (allowMultiple) {
        const countEl = option.querySelector(".rune_option_count");
        selectedCount += Number.parseInt(countEl?.textContent || "0", 10) || 0;
        return;
      }
      const checkbox = option.querySelector("input[type='checkbox']");
      if (checkbox instanceof HTMLInputElement && checkbox.checked) {
        selectedCount += 1;
      }
    });
    return selectedCount;
  };

  const syncRuneOptionAvailability = () => {
    if (!(runeOptions instanceof HTMLElement)) {
      return;
    }
    const selectedCount = getSelectedRuneCount();
    const canAddMore = selectedCount < maxAdditionalRuneSlots;
    runeOptions.querySelectorAll(".rune_option").forEach((option) => {
      if (!(option instanceof HTMLElement)) {
        return;
      }
      const allowMultiple = option.dataset.allowMultiple === "1";
      if (allowMultiple) {
        const countEl = option.querySelector(".rune_option_count");
        const count = Number.parseInt(countEl?.textContent || "0", 10) || 0;
        const incrementBtn = option.querySelector(".rune_option_increment");
        const decrementBtn = option.querySelector(".rune_option_decrement");
        if (incrementBtn instanceof HTMLButtonElement) {
          incrementBtn.disabled = !canAddMore;
          incrementBtn.title = canAddMore ? "" : `Maximal ${MAX_RUNES_PER_ITEM} Runen insgesamt`;
        }
        if (decrementBtn instanceof HTMLButtonElement) {
          decrementBtn.disabled = count <= 0;
        }
        return;
      }
      const checkbox = option.querySelector("input[type='checkbox']");
      if (checkbox instanceof HTMLInputElement && !checkbox.checked) {
        checkbox.disabled = !canAddMore;
        checkbox.title = canAddMore ? "" : `Maximal ${MAX_RUNES_PER_ITEM} Runen insgesamt`;
      }
    });
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
    syncRuneOptionAvailability();
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
    if (shouldOpen) {
      runeSearchInput?.focus();
    }
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

  const setFormValue = (fieldName, value) => {
    const field = runeForm?.elements?.namedItem?.(fieldName);
    if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement || field instanceof HTMLSelectElement) {
      field.value = value === null || value === undefined ? "" : String(value);
    }
  };

  const syncRetrofitDetailSections = () => {
    if (runeArmorFields instanceof HTMLElement) {
      runeArmorFields.hidden = retrofitItemType !== "armor";
    }
    if (runeWeaponFields instanceof HTMLElement) {
      runeWeaponFields.hidden = retrofitItemType !== "weapon";
    }
    if (runeShieldFields instanceof HTMLElement) {
      runeShieldFields.hidden = retrofitItemType !== "shield";
    }
    if (runeWeaponTwoHandFields instanceof HTMLElement && runeWeaponWieldMode instanceof HTMLSelectElement) {
      runeWeaponTwoHandFields.hidden = runeWeaponWieldMode.value === "1h";
    }
  };

  // ── Magic effect rows ──────────────────────────────────────────────────────

  const syncMagicEffectRow = (row) => {
    if (!(row instanceof HTMLElement)) {
      return;
    }
    const targetKindSelect = row.querySelector("[data-magic-target-kind]");
    const valueInput = row.querySelector("[data-magic-value-input]");
    const valueRow = valueInput?.closest(".shop_item_form_row");
    const descriptionInput = row.querySelector("[data-magic-effect-description]");
    const selectedKind = String(targetKindSelect?.value || "");
    const isTextOnly = selectedKind === "text";
    row.querySelectorAll("[data-magic-target-row]").forEach((targetRow) => {
      if (!(targetRow instanceof HTMLElement)) {
        return;
      }
      const rowKind = String(targetRow.dataset.magicTargetRow || "");
      const isActive = !isTextOnly && selectedKind === rowKind;
      targetRow.hidden = !isActive;
      const select = targetRow.querySelector("select");
      if (select) {
        select.disabled = !isActive;
      }
    });
    if (valueInput instanceof HTMLInputElement) {
      valueInput.setCustomValidity("");
      if (valueRow instanceof HTMLElement) {
        valueRow.hidden = isTextOnly;
      }
      if (isTextOnly) {
        valueInput.value = "0";
      } else if (selectedKind === WEAPON_MASTERY_BONUS_KIND && String(valueInput.value || "").trim() === "") {
        valueInput.value = "1";
      }
    }
    if (descriptionInput instanceof HTMLInputElement && selectedKind === WEAPON_MASTERY_BONUS_KIND) {
      const currentValue = String(descriptionInput.value || "").trim();
      if (!currentValue || currentValue === WEAPON_MASTERY_BONUS_DESCRIPTION) {
        descriptionInput.value = WEAPON_MASTERY_BONUS_DESCRIPTION;
      }
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
      const isTextOnly = targetKind === "text";
      const payload = {
        target_kind: targetKind,
        value: isTextOnly ? "0" : String(row.querySelector("[data-magic-value-input]")?.value || "0").trim(),
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

  const clearMagicEffectDropMarkers = () => {
    if (!(magicEffectsList instanceof HTMLElement)) {
      return;
    }
    magicEffectsList.querySelectorAll(".is-drop-before, .is-drop-after").forEach((row) => {
      if (row instanceof HTMLElement) {
        row.classList.remove("is-drop-before", "is-drop-after");
      }
    });
  };

  let draggedMagicEffectRow = null;

  const bindMagicEffectDragAndDrop = (row) => {
    if (!(row instanceof HTMLElement)) {
      return;
    }
    row.draggable = false;
    const dragHandle = row.querySelector("[data-drag-magic-effect]");
    if (dragHandle instanceof HTMLElement) {
      dragHandle.draggable = true;
    }
    dragHandle?.addEventListener("dragstart", (event) => {
      if (!(dragHandle instanceof HTMLElement)) {
        event.preventDefault();
        return;
      }
      draggedMagicEffectRow = row;
      row.classList.add("is-dragging");
      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", row.querySelector(".shop_magic_effect_title")?.textContent || "Effekt");
      }
    });
    dragHandle?.addEventListener("dragend", () => {
      draggedMagicEffectRow = null;
      row.classList.remove("is-dragging");
      clearMagicEffectDropMarkers();
      syncMagicEffectRemoveButtons();
      serializeMagicEffects();
    });
    row.addEventListener("dragover", (event) => {
      if (!(magicEffectsList instanceof HTMLElement) || !(draggedMagicEffectRow instanceof HTMLElement) || draggedMagicEffectRow === row) {
        return;
      }
      event.preventDefault();
      clearMagicEffectDropMarkers();
      const bounds = row.getBoundingClientRect();
      const insertBefore = event.clientY < bounds.top + (bounds.height / 2);
      row.classList.add(insertBefore ? "is-drop-before" : "is-drop-after");
      if (insertBefore) {
        if (draggedMagicEffectRow !== row.previousElementSibling) {
          magicEffectsList.insertBefore(draggedMagicEffectRow, row);
        }
      } else if (draggedMagicEffectRow !== row.nextElementSibling) {
        magicEffectsList.insertBefore(draggedMagicEffectRow, row.nextElementSibling);
      }
      syncMagicEffectRemoveButtons();
      serializeMagicEffects();
    });
    row.addEventListener("drop", (event) => {
      event.preventDefault();
      clearMagicEffectDropMarkers();
      syncMagicEffectRemoveButtons();
      serializeMagicEffects();
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
    const targetKindSelect = row.querySelector("[data-magic-target-kind]");
    if (targetKindSelect instanceof HTMLSelectElement) {
      WEAPON_ONLY_MAGIC_TARGET_KINDS.forEach((optionValue) => {
        const weaponOnlyOption = targetKindSelect.querySelector(`option[value='${optionValue}']`);
        if (weaponOnlyOption instanceof HTMLOptionElement) {
          weaponOnlyOption.hidden = retrofitItemType !== "weapon";
          weaponOnlyOption.disabled = retrofitItemType !== "weapon";
        }
      });
    }
    if (initialPayload && typeof initialPayload === "object") {
      const valueInput = row.querySelector("[data-magic-value-input]");
      const descriptionInput = row.querySelector("[data-magic-effect-description]");
      if (targetKindSelect instanceof HTMLSelectElement) {
        targetKindSelect.value = String(initialPayload.target_kind || "");
        if (retrofitItemType !== "weapon" && WEAPON_ONLY_MAGIC_TARGET_KINDS.includes(targetKindSelect.value)) {
          targetKindSelect.value = "";
        }
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
    bindMagicEffectDragAndDrop(row);
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

    const wrapper = document.createElement("div");
    wrapper.className = "shop_item_form_checklist_item rune_option";
    if (allowMultiple) {
      wrapper.className += " rune_option--multiple";
    }
    wrapper.dataset.runeId = String(runeId);
    wrapper.dataset.allowMultiple = allowMultiple ? "1" : "0";
    wrapper.dataset.runeSearch = `${rune.name || ""} ${rune.description || ""}`;

    const buildSlotFields = (slot = {}) => {
      const slotRow = document.createElement("div");
      slotRow.className = "rune_option_slot";
      slotRow.dataset.runeSlot = "1";

      const fieldGroup = document.createElement("div");
      fieldGroup.className = "rune_option_slot_fields";

      const crafterWrap = document.createElement("div");
      crafterWrap.className = "rune_option_crafter";
      const crafterInput = document.createElement("input");
      crafterInput.type = "number";
      crafterInput.className = "rune_option_crafter_level sheet-window__field";
      crafterInput.min = String(DEFAULT_RUNE_CRAFTER_LEVEL);
      crafterInput.max = String(MAX_RUNE_CRAFTER_LEVEL);
      crafterInput.step = "1";
      crafterInput.setAttribute("aria-label", `${rune.name || "Rune"} Schmiedestufe`);
      crafterInput.value = String(normalizeCrafterLevel(slot.crafter_level));
      crafterInput.addEventListener("input", () => {
        crafterInput.value = String(normalizeCrafterLevel(crafterInput.value));
        serializeRunePayloads();
      });
      crafterWrap.append(crafterInput);
      fieldGroup.append(crafterWrap);

      if (hasSpec) {
        const specInput = document.createElement("input");
        specInput.type = "text";
        specInput.className = "rune_option_spec sheet-window__field";
        specInput.placeholder = specLabel;
        specInput.maxLength = 100;
        specInput.value = String(slot.specification || "");
        specInput.addEventListener("input", serializeRunePayloads);
        fieldGroup.append(specInput);
      }

      slotRow.append(fieldGroup);
      return slotRow;
    };

    const buildRuneCopy = () => {
      const copy = document.createElement("span");
      copy.className = "rune_option_copy";

      const image = document.createElement(rune.image ? "img" : "span");
      image.className = rune.image ? "rune_option_image" : "rune_option_image rune_option_image--placeholder";
      if (rune.image) {
        image.src = rune.image;
        image.alt = "";
        image.loading = "lazy";
      } else {
        image.setAttribute("aria-hidden", "true");
      }

      const textWrap = document.createElement("span");
      textWrap.className = "rune_option_text";
      const nameSpan = document.createElement("span");
      nameSpan.className = "rune_option_name";
      nameSpan.textContent = rune.name || "Unbenannte Rune";
      const bodySpan = document.createElement("span");
      bodySpan.className = "rune_option_body";
      bodySpan.textContent = rune.description || "Keine Beschreibung vorhanden.";
      textWrap.append(nameSpan, bodySpan);
      copy.append(image, textWrap);
      return copy;
    };

    if (allowMultiple) {
      // ── Counter UI ─────────────────────────────────────────────────────────
      const header = document.createElement("div");
      header.className = "rune_option_header";

      const stepper = document.createElement("div");
      stepper.className = "rune_option_stepper";

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

      const copy = buildRuneCopy();

      stepper.append(incrementBtn, countDisplay, decrementBtn);
      header.append(stepper, copy);

      const specsContainer = document.createElement("div");
      specsContainer.className = "rune_option_specs";

      const addSlotFields = (slot = {}) => {
        specsContainer.append(buildSlotFields(slot));
      };

      // Pre-populate existing slots
      existingSlots.forEach((slot) => {
        addSlotFields(slot);
      });

      decrementBtn.addEventListener("click", () => {
        const current = Number.parseInt(countDisplay.textContent || "0", 10) || 0;
        if (current <= 0) {
          return;
        }
        countDisplay.textContent = String(current - 1);
        const slotRows = specsContainer.querySelectorAll("[data-rune-slot]");
        slotRows[slotRows.length - 1]?.remove();
        syncRuneSelectionCount();
        serializeRunePayloads();
      });

      incrementBtn.addEventListener("click", () => {
        const current = Number.parseInt(countDisplay.textContent || "0", 10) || 0;
        countDisplay.textContent = String(current + 1);
        addSlotFields();
        syncRuneSelectionCount();
        serializeRunePayloads();
      });

      wrapper.append(header, specsContainer);
    } else {
      // ── Checkbox UI ────────────────────────────────────────────────────────
      const checkRow = document.createElement("div");
      checkRow.className = "rune_option_single";

      const toggleLabel = document.createElement("label");
      toggleLabel.className = "rune_option_single_toggle";

      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = String(runeId);
      input.checked = existingSlots.length > 0;

      const content = document.createElement("div");
      content.className = "rune_option_single_content";
      const image = document.createElement(rune.image ? "img" : "span");
      image.className = rune.image ? "rune_option_image" : "rune_option_image rune_option_image--placeholder";
      if (rune.image) {
        image.src = rune.image;
        image.alt = "";
        image.loading = "lazy";
      } else {
        image.setAttribute("aria-hidden", "true");
      }

      const textWrap = document.createElement("span");
      textWrap.className = "rune_option_text";
      const nameSpan = document.createElement("span");
      nameSpan.className = "rune_option_name";
      nameSpan.textContent = rune.name || "Unbenannte Rune";
      const bodySpan = document.createElement("span");
      bodySpan.className = "rune_option_body";
      bodySpan.textContent = rune.description || "Keine Beschreibung vorhanden.";
      textWrap.append(nameSpan, bodySpan);

      const slotRow = buildSlotFields(existingSlots[0] || {});
      slotRow.classList.add("rune_option_slot--single");
      slotRow.hidden = !input.checked;

      toggleLabel.append(input);
      content.append(image, textWrap, slotRow);
      checkRow.append(toggleLabel, content);
      wrapper.append(checkRow);

      input.addEventListener("change", () => {
        slotRow.hidden = !input.checked;
        if (!input.checked) {
          slotRow.querySelectorAll("input").forEach((slotInput) => {
            if (!(slotInput instanceof HTMLInputElement)) {
              return;
            }
            if (slotInput.classList.contains("rune_option_crafter_level")) {
              slotInput.value = String(DEFAULT_RUNE_CRAFTER_LEVEL);
            } else {
              slotInput.value = "";
            }
          });
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
      !target?.closest(".rune_window_search_row") &&
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
    const currentQuality = String(button.getAttribute("data-current-quality") || "common");
    const description = String(button.getAttribute("data-description") || "");
    const itemImage = String(button.getAttribute("data-item-image") || "");
    const itemImageOverride = String(button.getAttribute("data-item-image-override") || "");
    retrofitItemType = String(button.getAttribute("data-item-type") || "");
    const magicModifierPayloads = parseJsonList(button.getAttribute("data-magic-modifier-payloads"));
    const modifyPayload = parseJsonObject(button.getAttribute("data-modify-payload"));

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
        crafter_level: normalizeCrafterLevel(spec.crafter_level),
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
    if (runeNameInput instanceof HTMLInputElement) {
      runeNameInput.value = String(modifyPayload.name || itemName);
    }
    if (runePriceInput instanceof HTMLInputElement) {
      runePriceInput.value = String(modifyPayload.price ?? "0");
    }
    if (runeWeightInput instanceof HTMLInputElement) {
      runeWeightInput.value = String(modifyPayload.weight ?? "0");
    }
    if (runeSizeClassSelect instanceof HTMLSelectElement) {
      runeSizeClassSelect.value = String(modifyPayload.size_class || "");
    }
    if (runeDescriptionInput instanceof HTMLTextAreaElement) {
      runeDescriptionInput.value = description;
    }
    if (runeImageInput instanceof HTMLInputElement) {
      runeImageInput.value = "";
    }
    if (runeRemoveImageInput instanceof HTMLInputElement) {
      runeRemoveImageInput.checked = false;
    }
    if (runeImagePreview instanceof HTMLElement && runeImagePreviewImg instanceof HTMLImageElement) {
      if (itemImage) {
        runeImagePreviewImg.src = itemImage;
        runeImagePreviewImg.alt = `${itemName} Bild`;
        runeImagePreview.hidden = false;
        if (runeRemoveImageRow instanceof HTMLElement) {
          runeRemoveImageRow.hidden = !itemImageOverride;
        }
      } else {
        runeImagePreviewImg.removeAttribute("src");
        runeImagePreviewImg.alt = "";
        runeImagePreview.hidden = true;
        if (runeRemoveImageRow instanceof HTMLElement) {
          runeRemoveImageRow.hidden = true;
        }
      }
    }
    if (runeItemName instanceof HTMLElement) {
      runeItemName.textContent = itemName;
    }
    if (runeBaseInfo instanceof HTMLElement) {
      runeBaseInfo.textContent = `Maximal ${MAX_RUNES_PER_ITEM} Runen insgesamt.`;
    }

    maxAdditionalRuneSlots = MAX_RUNES_PER_ITEM;
    let availableCount = 0;
    runeChoices.forEach((rune) => {
      availableCount += 1;

      const runeId = Number(rune.id);
      let existingSlots = runeSpecsByRuneId[runeId] || [];

      // Legacy: single checked slot without spec
      if (useLegacy && existingSlots.length === 0 && extraRuneIds.has(runeId)) {
        existingSlots = [{ specification: "", slot: 1, crafter_level: DEFAULT_RUNE_CRAFTER_LEVEL }];
      }

      runeOptions.append(buildRuneOption(rune, existingSlots));
    });

    [
      "weapon_type",
      "weapon_min_st",
      "weapon_damage_source",
      "weapon_damage_dice_amount",
      "weapon_damage_dice_faces",
      "weapon_damage_flat_operator",
      "weapon_damage_flat_bonus",
      "weapon_wield_mode",
      "weapon_damage_type",
      "weapon_h2_dice_amount",
      "weapon_h2_dice_faces",
      "weapon_h2_flat_operator",
      "weapon_h2_flat_bonus",
      "armor_rs_total",
      "armor_rs_head",
      "armor_rs_torso",
      "armor_rs_arm_left",
      "armor_rs_arm_right",
      "armor_rs_leg_left",
      "armor_rs_leg_right",
      "armor_encumbrance",
      "armor_min_st",
      "shield_rs",
      "shield_encumbrance",
      "shield_min_st",
    ].forEach((fieldName) => {
      setFormValue(fieldName, modifyPayload[fieldName]);
    });

    if (!availableCount) {
      const empty = document.createElement("p");
      empty.className = "shop_empty";
      empty.textContent = "Keine Runen verfügbar.";
      runeOptions.append(empty);
    }

    populateMagicEffects(magicModifierPayloads);
    syncRetrofitDetailSections();
    syncRuneSelectionCount();
    serializeRunePayloads();
    filterRuneEntries();
    openRuneWindow();
    closeMenu(button.closest(".inv_menu"));
  });

  runeSearchInput?.addEventListener("input", filterRuneEntries);
  runeRemoveImageInput?.addEventListener("change", () => {
    if (!(runeImagePreview instanceof HTMLElement) || !(runeRemoveImageInput instanceof HTMLInputElement)) {
      return;
    }
    runeImagePreview.hidden = runeRemoveImageInput.checked;
  });
  runeDropdownTrigger?.addEventListener("click", () => {
    toggleRuneDropdown();
  });
  runeWeaponWieldMode?.addEventListener("change", syncRetrofitDetailSections);
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
