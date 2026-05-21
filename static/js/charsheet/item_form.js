export function initItemForm() {
  const typeSelect = document.getElementById("shopItemTypeSelect");
  const armorFields = document.getElementById("shopItemArmorFields");
  const weaponFields = document.getElementById("shopItemWeaponFields");
  const shieldFields = document.getElementById("shopItemShieldFields");
  const magicFields = document.getElementById("shopItemMagicFields");
  if (!typeSelect || !armorFields || !weaponFields || !shieldFields || !magicFields) {
    return;
  }

  const armorInput = armorFields.querySelector("input[name='armor_rs_total']");
  const stackableRow = document.getElementById("shopItemStackableRow");
  const stackableInput = document.getElementById("shopItemStackableInput");
  const magicInput = document.getElementById("shopItemMagicInput");
  const armorModeInputs = armorFields.querySelectorAll("input[name='armor_mode']");
  const armorTotalFields = document.getElementById("shopArmorTotalFields");
  const armorZoneFields = document.getElementById("shopArmorZoneFields");
  const runeDropdown = document.getElementById("shopItemRuneDropdown");
  const runeDropdownTrigger = document.getElementById("shopItemRuneDropdownTrigger");
  const runeDropdownPanel = document.getElementById("shopItemRuneDropdownPanel");
  const runeSelectionCount = document.getElementById("shopItemRuneSelectionCount");
  const runeTriggerLabel = document.getElementById("shopItemRuneTriggerLabel");
  const runeSearchInput = document.getElementById("shopItemRuneSearch");
  const runeOptions = document.getElementById("shopItemRuneOptions");
  const magicEffectsList = document.getElementById("shopMagicEffectsList");
  const magicEffectTemplate = document.getElementById("shopMagicEffectTemplate");
  const magicAddEffectButton = document.getElementById("shopMagicAddEffectBtn");
  const magicPayloadInput = document.getElementById("shopMagicModifierPayloads");
  const detailPlaceholder = document.getElementById("shopItemDetailPlaceholder");
  const form = typeSelect.closest("form");
  const armorZoneInputs = armorFields.querySelectorAll(
    "input[name='armor_rs_head'], input[name='armor_rs_torso'], input[name='armor_rs_arm_left'], input[name='armor_rs_arm_right'], input[name='armor_rs_leg_left'], input[name='armor_rs_leg_right']",
  );
  const weaponDamageAmountInput = weaponFields.querySelector("input[name='weapon_damage_dice_amount']");
  const weaponDamageFacesInput = weaponFields.querySelector("input[name='weapon_damage_dice_faces']");
  const weaponDamageSourceSelect = weaponFields.querySelector("select[name='weapon_damage_source']");
  const weaponMinStInput = weaponFields.querySelector("input[name='weapon_min_st']");
  const weaponWieldModeSelect = document.getElementById("shopWeaponWieldMode");
  const weaponTwoHandFields = document.getElementById("shopWeaponTwoHandFields");
  const weaponH2AmountInput = weaponFields.querySelector("input[name='weapon_h2_dice_amount']");
  const weaponH2FacesInput = weaponFields.querySelector("input[name='weapon_h2_dice_faces']");
  const WEAPON_ONLY_MAGIC_TARGET_KINDS = ["weapon_maneuver", "weapon_damage", "weapon_damage_dice", "weapon_mastery_bonus"];
  const WEAPON_MASTERY_BONUS_KIND = "weapon_mastery_bonus";
  const WEAPON_MASTERY_BONUS_DESCRIPTION = "Waffenmeister-Bonus +1/+1";

  const syncArmorModeFields = () => {
    const selectedModeInput = armorFields.querySelector("input[name='armor_mode']:checked");
    const totalMode = (selectedModeInput ? selectedModeInput.value : "total") === "total";

    armorTotalFields.hidden = !totalMode;
    armorZoneFields.hidden = totalMode;
    if (armorInput) {
      armorInput.required = totalMode;
    }
    armorZoneInputs.forEach((input) => {
      input.required = !totalMode;
    });
  };

  const syncWeaponWieldModeFields = () => {
    const mode = String(weaponWieldModeSelect?.value || "1h");
    const hasTwoHandProfile = mode === "vh";
    if (weaponTwoHandFields) {
      weaponTwoHandFields.hidden = !hasTwoHandProfile;
    }
    if (weaponH2AmountInput) {
      weaponH2AmountInput.required = hasTwoHandProfile;
    }
    if (weaponH2FacesInput) {
      weaponH2FacesInput.required = hasTwoHandProfile;
    }
  };

  const syncRuneSelectionCount = () => {
    if (!(runeSelectionCount instanceof HTMLElement) || !(runeOptions instanceof HTMLElement)) {
      return;
    }
    const selectedInputs = Array.from(runeOptions.querySelectorAll("input[name='runes']:checked"));
    const selectedCount = selectedInputs.length;
    runeSelectionCount.textContent = String(selectedCount);

    if (!(runeTriggerLabel instanceof HTMLElement)) {
      return;
    }

    if (selectedCount === 0) {
      runeTriggerLabel.textContent = "Keine Runen ausgew\u00e4hlt";
      return;
    }

    const selectedNames = selectedInputs
      .map((input) => input.closest("label")?.querySelector(".rune_option_name")?.textContent?.trim() || "")
      .filter(Boolean);

    if (selectedCount <= 2) {
      runeTriggerLabel.textContent = selectedNames.join(", ");
      return;
    }

    runeTriggerLabel.textContent = `${selectedCount} Runen ausgew\u00e4hlt`;
  };

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

  const filterRuneEntries = () => {
    if (!(runeOptions instanceof HTMLElement)) {
      return;
    }
    const query = String(runeSearchInput?.value || "").trim().toLowerCase();
    runeOptions.querySelectorAll(".rune_option").forEach((entry) => {
      if (!(entry instanceof HTMLElement)) {
        return;
      }
      const haystack = String(entry.dataset.runeSearch || "");
      entry.hidden = query.length > 0 && !haystack.includes(query);
    });
  };

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
        select.required = isActive;
      }
    });

    if (valueInput instanceof HTMLInputElement) {
      valueInput.setCustomValidity("");
      if (valueRow instanceof HTMLElement) {
        valueRow.hidden = isTextOnly;
      }
      valueInput.required = selectedKind !== "" && !isTextOnly;
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
      const value = String(row.querySelector("[data-magic-value-input]")?.value || "0").trim();
      const effectDescription = String(row.querySelector("[data-magic-effect-description]")?.value || "").trim();
      const payload = {
        target_kind: targetKind,
        value: isTextOnly ? "0" : value,
        effect_description: effectDescription,
      };
      const attributeSelect = row.querySelector("[data-magic-target-select='attribute']");
      const statSelect = row.querySelector("[data-magic-target-select='stat']");
      const skillSelect = row.querySelector("[data-magic-target-select='skill']");
      const categorySelect = row.querySelector("[data-magic-target-select='category']");
      const itemCategorySelect = row.querySelector("[data-magic-target-select='item_category']");
      const specializationSelect = row.querySelector("[data-magic-target-select='specialization']");

      if (targetKind === "attribute") {
        payload.target_attribute = String(attributeSelect?.value || "").trim();
      } else if (targetKind === "stat") {
        payload.target_stat = String(statSelect?.value || "").trim();
      } else if (targetKind === "skill") {
        payload.target_skill = String(skillSelect?.value || "").trim();
      } else if (targetKind === "category") {
        payload.target_skill_category = String(categorySelect?.value || "").trim();
      } else if (targetKind === "item_category") {
        payload.target_item_category = String(itemCategorySelect?.value || "").trim();
      } else if (targetKind === "specialization") {
        payload.target_specialization = String(specializationSelect?.value || "").trim();
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

  const addMagicEffectRow = () => {
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
          const isWeapon = String(typeSelect.value || "") === "weapon";
          weaponOnlyOption.hidden = !isWeapon;
          weaponOnlyOption.disabled = !isWeapon;
        }
      });
      if (String(typeSelect.value || "") !== "weapon" && WEAPON_ONLY_MAGIC_TARGET_KINDS.includes(targetKindSelect.value)) {
        targetKindSelect.value = "";
      }
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

  const ensureMagicEffectRow = () => {
    if (!(magicEffectsList instanceof HTMLElement)) {
      return;
    }
    if (!magicEffectsList.querySelector("[data-magic-effect-row]")) {
      addMagicEffectRow();
    }
  };

  const syncItemTypeFields = () => {
    const value = String(typeSelect.value || "");
    const isArmor = value === "armor";
    const isWeapon = value === "weapon";
    const isShield = value === "shield";
    const isMagicItem = Boolean(magicInput?.checked) || value === "magic_item";

    armorFields.hidden = !isArmor;
    weaponFields.hidden = !isWeapon;
    shieldFields.hidden = !isShield;
    magicFields.hidden = !isMagicItem;

    if (armorInput) {
      armorInput.required = isArmor;
    }
    if (weaponDamageAmountInput) {
      weaponDamageAmountInput.required = isWeapon;
    }
    if (weaponDamageFacesInput) {
      weaponDamageFacesInput.required = isWeapon;
    }
    if (weaponDamageSourceSelect) {
      weaponDamageSourceSelect.required = isWeapon;
    }
    if (weaponMinStInput) {
      weaponMinStInput.required = isWeapon;
    }

    if (stackableRow && stackableInput) {
      const lockStackableOff = isArmor || isWeapon || isShield || isMagicItem;
      stackableRow.hidden = lockStackableOff;
      stackableInput.disabled = lockStackableOff;
      if (lockStackableOff) {
        stackableInput.checked = false;
      }
    }

    if (isArmor) {
      syncArmorModeFields();
    } else {
      armorTotalFields.hidden = false;
      armorZoneFields.hidden = true;
      if (armorInput) {
        armorInput.required = false;
      }
      armorZoneInputs.forEach((input) => {
        input.required = false;
      });
    }

    if (isWeapon) {
      syncWeaponWieldModeFields();
    } else if (weaponTwoHandFields) {
      weaponTwoHandFields.hidden = true;
      if (weaponH2AmountInput) {
        weaponH2AmountInput.required = false;
      }
      if (weaponH2FacesInput) {
        weaponH2FacesInput.required = false;
      }
    }

    if (isMagicItem) {
      ensureMagicEffectRow();
      magicEffectsList?.querySelectorAll("[data-magic-effect-row]").forEach((row) => {
        const targetKindSelect = row.querySelector("[data-magic-target-kind]");
        if (targetKindSelect instanceof HTMLSelectElement) {
          WEAPON_ONLY_MAGIC_TARGET_KINDS.forEach((optionValue) => {
            const weaponOnlyOption = targetKindSelect.querySelector(`option[value='${optionValue}']`);
            if (weaponOnlyOption instanceof HTMLOptionElement) {
              weaponOnlyOption.hidden = !isWeapon;
              weaponOnlyOption.disabled = !isWeapon;
            }
          });
          if (!isWeapon && WEAPON_ONLY_MAGIC_TARGET_KINDS.includes(targetKindSelect.value)) {
            targetKindSelect.value = "";
          }
        }
        syncMagicEffectRow(row);
      });
      serializeMagicEffects();
    } else if (magicPayloadInput instanceof HTMLInputElement) {
      magicPayloadInput.value = "[]";
    }

    const hasDetailFields = isArmor || isWeapon || isShield || isMagicItem;
    if (detailPlaceholder instanceof HTMLElement) {
      detailPlaceholder.hidden = hasDetailFields;
    }
  };

  runeOptions?.querySelectorAll("input[name='runes']").forEach((input) => {
    input.addEventListener("change", syncRuneSelectionCount);
  });

  armorModeInputs.forEach((input) => {
    input.addEventListener("change", syncArmorModeFields);
  });
  magicInput?.addEventListener("change", syncItemTypeFields);
  weaponWieldModeSelect?.addEventListener("change", syncWeaponWieldModeFields);
  magicAddEffectButton?.addEventListener("click", () => {
    addMagicEffectRow();
  });
  runeDropdownTrigger?.addEventListener("click", () => {
    toggleRuneDropdown();
  });
  runeSearchInput?.addEventListener("input", filterRuneEntries);
  document.addEventListener("click", (event) => {
    const target = event.target instanceof HTMLElement ? event.target : null;
    if (!(runeDropdown instanceof HTMLElement) || !target || target.closest("#shopItemRuneDropdown")) {
      return;
    }
    toggleRuneDropdown(false);
  });
  form?.addEventListener("submit", serializeMagicEffects);
  typeSelect.addEventListener("change", syncItemTypeFields);
  stackableInput?.addEventListener("change", syncItemTypeFields);
  syncRuneSelectionCount();
  filterRuneEntries();
  ensureMagicEffectRow();
  syncItemTypeFields();
}
