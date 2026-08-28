document.addEventListener("DOMContentLoaded", () => {
  const floating = ({ win, backdrop, handle, opener, closeButtons, beforeOpen, afterClose }) => {
    if (!win || !backdrop || !handle) return null;

    // Keep floating inventory dialogs outside the scrollable/clipped workspace.
    // Otherwise their fixed z-index is still trapped by an ancestor stacking
    // context and the backdrop can cover the actual window.
    document.body.append(backdrop, win);

    const constrainDisclosureWindow = () => {
      if (!win.classList.contains("is-disclosure-card")) return;
      const height = Math.max(320, Math.min(1074, window.innerHeight - 28));
      win.style.height = `${height}px`;
      win.style.maxHeight = `${height}px`;
    };
    const center = () => {
      constrainDisclosureWindow();
      const rect = win.getBoundingClientRect();
      win.style.left = Math.max(12, (window.innerWidth - rect.width) / 2) + "px";
      win.style.top = Math.max(12, Math.min(62, window.innerHeight - rect.height - 12)) + "px";
    };
    const show = (trigger) => {
      if (beforeOpen && beforeOpen(trigger) === false) return;
      win.classList.add("is-open");
      win.setAttribute("aria-hidden", "false");
      backdrop.classList.add("is-open");
      backdrop.setAttribute("aria-hidden", "false");
      center();
    };
    const hide = () => {
      win.classList.remove("is-open");
      win.setAttribute("aria-hidden", "true");
      backdrop.classList.remove("is-open");
      backdrop.setAttribute("aria-hidden", "true");
      if (afterClose) afterClose();
    };
    opener?.addEventListener("click", () => show(opener));
    closeButtons.forEach((button) => button.addEventListener("click", hide));
    backdrop.addEventListener("click", hide);
    window.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && win.classList.contains("is-open")) hide();
    });
    let pointerId = null;
    let offsetX = 0;
    let offsetY = 0;
    handle.addEventListener("pointerdown", (event) => {
      if ((event.pointerType === "mouse" && event.button !== 0) || event.target.closest("button, a, input")) return;
      const rect = win.getBoundingClientRect();
      pointerId = event.pointerId;
      offsetX = event.clientX - rect.left;
      offsetY = event.clientY - rect.top;
      handle.setPointerCapture(event.pointerId);
      win.classList.add("is-dragging");
    });
    handle.addEventListener("pointermove", (event) => {
      if (event.pointerId !== pointerId) return;
      constrainDisclosureWindow();
      const rect = win.getBoundingClientRect();
      win.style.left = Math.min(window.innerWidth - rect.width - 12, Math.max(12, event.clientX - offsetX)) + "px";
      win.style.top = Math.max(12, Math.min(window.innerHeight - rect.height - 12, Math.max(12, event.clientY - offsetY))) + "px";
    });
    const stop = (event) => {
      if (event.pointerId !== pointerId) return;
      win.classList.remove("is-dragging");
      try { handle.releasePointerCapture(event.pointerId); } catch (_error) {}
      pointerId = null;
    };
    handle.addEventListener("pointerup", stop);
    handle.addEventListener("pointercancel", stop);
    return { show, hide };
  };

  floating({
    win: document.querySelector("[data-sl-item-add-window]"),
    backdrop: document.querySelector("[data-sl-item-add-backdrop]"),
    handle: document.querySelector("[data-sl-item-add-handle]"),
    opener: document.querySelector("[data-open-sl-item-add]"),
    closeButtons: Array.from(document.querySelectorAll("[data-close-sl-item-add]")),
  });

  floating({
    win: document.querySelector("[data-sl-item-create-window]"),
    backdrop: document.querySelector("[data-sl-item-create-backdrop]"),
    handle: document.querySelector("[data-sl-item-create-handle]"),
    opener: document.querySelector("[data-open-sl-item-create]"),
    closeButtons: Array.from(document.querySelectorAll("[data-close-sl-item-create]")),
  });

  const WEAPON_ITEM_TYPES = new Set(["weapon", "magical_weapon"]);
  const ARMOR_ITEM_TYPES = new Set(["armor", "magical_armor"]);
  const MAGIC_ITEM_TYPES = new Set(["ring", "amulet", "magical_weapon", "magical_armor"]);
  const FORCED_MAGIC_ITEM_TYPES = new Set(["magical_weapon", "magical_armor"]);

  const detailTypeFor = (type) => {
    if (WEAPON_ITEM_TYPES.has(type)) return "weapon";
    if (ARMOR_ITEM_TYPES.has(type)) return "armor";
    return type;
  };

  const syncTypeSections = (form, type) => {
    const detailType = detailTypeFor(type);
    form.querySelectorAll("[data-item-fields]").forEach((section) => {
      const active = section.dataset.itemFields === detailType;
      section.hidden = !active;
      section.querySelectorAll("input, select, textarea").forEach((field) => {
        field.disabled = !active;
      });
    });
  };

  const baseItemForm = document.querySelector("[data-sl-base-item-form]");
  if (baseItemForm) {
    const typeSelect = baseItemForm.querySelector("[data-sl-item-type]");
    const magicInput = baseItemForm.querySelector("[data-sl-is-magic]");
    const forcedMagicInput = baseItemForm.querySelector("[data-sl-forced-magic]");
    const magicFields = baseItemForm.querySelector("[data-sl-magic-fields]");
    const detailPlaceholder = baseItemForm.querySelector("[data-sl-detail-placeholder]");
    const stackableRow = baseItemForm.querySelector("[data-sl-stackable]");
    const stackableInput = stackableRow?.querySelector("input");
    const wieldMode = baseItemForm.querySelector("[data-sl-wield-mode]");
    const twoHandFields = baseItemForm.querySelector("[data-sl-two-hand]");
    const armorModeInputs = baseItemForm.querySelectorAll("input[name='armor_mode']");
    const effectsList = baseItemForm.querySelector("[data-sl-magic-effects]");
    const effectTemplate = baseItemForm.querySelector("[data-sl-magic-effect-template]");
    const addEffectButton = baseItemForm.querySelector("[data-add-sl-magic-effect]");
    const effectPayloads = baseItemForm.querySelector("[data-sl-magic-payloads]");
    const oneHandDamageRow = baseItemForm.querySelector("input[name='weapon_damage_dice_amount']")?.closest(".sl-editor-row--damage");
    const twoHandDamageRow = baseItemForm.querySelector("input[name='weapon_h2_dice_amount']")?.closest(".sl-editor-row--damage");

    const formatDamageSummary = (prefix, names) => {
      const amount = baseItemForm.querySelector(`[name='${names.amount}']`)?.value || "1";
      const faces = baseItemForm.querySelector(`[name='${names.faces}']`)?.value || "10";
      const operator = baseItemForm.querySelector(`[name='${names.operator}']`)?.value || "";
      const bonus = baseItemForm.querySelector(`[name='${names.bonus}']`)?.value || "0";
      const typeLabel = baseItemForm.querySelector(`[name='${names.type}'] option:checked`)?.textContent?.trim() || "";
      const bonusLabel = operator && Number.parseInt(bonus, 10) ? `${operator}${bonus}` : "";
      return `${amount}w${faces}${bonusLabel} ${typeLabel}`.trim();
    };

    const setupDamageSummary = (row, prefix, labelText, names) => {
      if (!row) return null;
      const trigger = document.createElement("button");
      trigger.type = "button";
      trigger.className = "sl-damage-summary";
      trigger.innerHTML = `<span class="sl-damage-summary__mode"></span><span class="sl-damage-summary__value"></span><span class="sl-damage-summary__edit" aria-hidden="true">&#9998;</span>`;
      row.before(trigger);
      row.hidden = true;
      const modeLabel = trigger.querySelector(".sl-damage-summary__mode");
      if (modeLabel) modeLabel.textContent = labelText;
      const update = () => {
        const label = trigger.querySelector(".sl-damage-summary__value");
        if (label) label.textContent = formatDamageSummary(prefix, names);
      };
      trigger.addEventListener("click", () => {
        row.hidden = !row.hidden;
      });
      Object.values(names).forEach((name) => {
        baseItemForm.querySelector(`[name='${name}']`)?.addEventListener("input", update);
        baseItemForm.querySelector(`[name='${name}']`)?.addEventListener("change", update);
      });
      update();
      return trigger;
    };

    const oneHandDamageSummary = setupDamageSummary(oneHandDamageRow, "1H", "1 Hand", {
      amount: "weapon_damage_dice_amount",
      faces: "weapon_damage_dice_faces",
      operator: "weapon_damage_flat_operator",
      bonus: "weapon_damage_flat_bonus",
      type: "weapon_damage_type",
    });
    const twoHandDamageSummary = setupDamageSummary(twoHandDamageRow, "2H", "2 Hand", {
      amount: "weapon_h2_dice_amount",
      faces: "weapon_h2_dice_faces",
      operator: "weapon_h2_flat_operator",
      bonus: "weapon_h2_flat_bonus",
      type: "weapon_h2_damage_type",
    });
    const damageSummaryGroup = document.createElement("div");
    damageSummaryGroup.className = "sl-damage-summary-group";
    if (oneHandDamageSummary) {
      oneHandDamageSummary.before(damageSummaryGroup);
      damageSummaryGroup.append(oneHandDamageSummary);
    }
    if (twoHandDamageSummary) {
      damageSummaryGroup.append(twoHandDamageSummary);
    }

    const serializeEffects = () => {
      if (!effectsList || !effectPayloads) return;
      const payloads = Array.from(effectsList.querySelectorAll("[data-sl-magic-effect]")).map((row) => {
        const targetKind = row.querySelector("[data-effect-kind]")?.value || "";
        const payload = {
          target_kind: targetKind,
          value: Number.parseInt(row.querySelector("[data-effect-value]")?.value || "0", 10) || 0,
          effect_description: row.querySelector("[data-effect-description]")?.value?.trim() || "",
          rules_text: row.querySelector("[data-effect-rules-text]")?.value?.trim() || "",
          active_flag: row.dataset.effectActiveFlag !== "0",
          toggleable: Boolean(row.querySelector("[data-effect-toggleable]")?.checked),
          toggle_state_inverted: Boolean(row.querySelector("[data-effect-toggle-inverted]")?.checked),
        };
        if (row.dataset.displayGroup) {
          payload.display_group = Number.parseInt(row.dataset.displayGroup, 10) || row.dataset.displayGroup;
        }
        if (row.dataset.displayGroupAppend === "1") {
          payload.display_group_append = true;
        }
        const displayGroupValue = String(row.querySelector("[data-effect-display-group]")?.value || "").trim();
        if (displayGroupValue) {
          payload.display_group = Number.parseInt(displayGroupValue, 10) || displayGroupValue;
        }
        if (row.querySelector("[data-effect-display-group-append]")?.checked) {
          payload.display_group_append = true;
        }
        const scaleSource = row.querySelector("[data-effect-scale-source]")?.value || "";
        if (!["text", "rule_flag"].includes(targetKind) && scaleSource) {
          payload.scale_source = scaleSource;
          payload.scale_divisor = Number.parseInt(row.querySelector("[data-effect-scale-divisor]")?.value || "0", 10) || 0;
        }
        const target = row.querySelector(`[data-effect-target='${targetKind}'] select`);
        if (targetKind === "attribute") payload.target_attribute = target?.value || "";
        if (targetKind === "stat") payload.target_stat = target?.value || "";
        if (targetKind === "rule_flag") payload.target_rule_flag = target?.value || "";
        if (targetKind === "skill") payload.target_skill = target?.value || "";
        if (targetKind === "category") payload.target_skill_category = target?.value || "";
        if (targetKind === "movement") payload.target_movement = target?.value || "";
        if (targetKind === "item") payload.target_item = target?.value || "";
        if (targetKind === "item_category") payload.target_item_category = target?.value || "";
        if (targetKind === "specialization") payload.target_specialization = target?.value || "";
        return payload;
      });
      effectPayloads.value = JSON.stringify(payloads);
    };

    const syncEffectRow = (row) => {
      const kind = row.querySelector("[data-effect-kind]")?.value || "text";
      row.querySelectorAll("[data-effect-target]").forEach((targetRow) => {
        const active = targetRow.dataset.effectTarget === kind;
        targetRow.hidden = !active;
        targetRow.querySelectorAll("select").forEach((select) => {
          select.disabled = !active;
        });
      });
      const valueRow = row.querySelector("[data-effect-value-row]");
      const hasCalculation = !["text", "rule_flag"].includes(kind);
      if (valueRow) valueRow.hidden = !hasCalculation;
      const valueInput = row.querySelector("[data-effect-value]");
      if (valueInput) valueInput.disabled = !hasCalculation;
      const scaleSource = row.querySelector("[data-effect-scale-source]");
      const scaleSourceRow = row.querySelector("[data-effect-scale-source-row]");
      const scaleDivisor = row.querySelector("[data-effect-scale-divisor]");
      const scaleDivisorRow = row.querySelector("[data-effect-scale-divisor-row]");
      if (scaleSourceRow) scaleSourceRow.hidden = !hasCalculation;
      if (scaleSource) {
        scaleSource.disabled = !hasCalculation;
        if (!hasCalculation) scaleSource.value = "";
      }
      if (scaleDivisorRow) scaleDivisorRow.hidden = !hasCalculation || !scaleSource?.value;
      if (scaleDivisor) scaleDivisor.disabled = !hasCalculation || !scaleSource?.value;
      serializeEffects();
    };

    const renumberEffects = () => {
      effectsList?.querySelectorAll("[data-sl-magic-effect]").forEach((row, index) => {
        const title = row.querySelector("[data-sl-effect-title]");
        if (title) title.textContent = `Effekt ${index + 1}`;
      });
    };

    const addEffect = () => {
      if (!effectsList || !(effectTemplate instanceof HTMLTemplateElement)) return;
      const row = effectTemplate.content.firstElementChild.cloneNode(true);
      effectsList.append(row);
      row.querySelector("[data-effect-kind]")?.addEventListener("change", () => syncEffectRow(row));
      row.querySelector("[data-effect-scale-source]")?.addEventListener("change", () => syncEffectRow(row));
      row.querySelectorAll("input, select").forEach((field) => {
        field.addEventListener("input", serializeEffects);
        field.addEventListener("change", serializeEffects);
      });
      row.querySelector("[data-remove-sl-magic-effect]")?.addEventListener("click", () => {
        row.remove();
        renumberEffects();
        serializeEffects();
      });
      syncEffectRow(row);
      renumberEffects();
    };

    const syncWieldMode = () => {
      if (!twoHandFields) return;
      const mode = wieldMode?.value || "1h";
      const showOneHand = mode === "1h" || mode === "vh";
      const showTwoHand = mode === "2h" || mode === "vh";
      if (damageSummaryGroup) {
        damageSummaryGroup.classList.toggle("sl-damage-summary-group--split", showOneHand && showTwoHand);
      }
      if (oneHandDamageSummary) oneHandDamageSummary.hidden = !showOneHand;
      if (oneHandDamageRow) oneHandDamageRow.hidden = true;
      twoHandFields.hidden = !showTwoHand;
      if (twoHandDamageSummary) twoHandDamageSummary.hidden = !showTwoHand;
      if (twoHandDamageRow) twoHandDamageRow.hidden = true;
      twoHandFields.querySelectorAll("input, select").forEach((field) => {
        field.disabled = !showTwoHand;
      });
    };
    const syncArmorMode = () => {
      const mode = baseItemForm.querySelector("input[name='armor_mode']:checked")?.value || "total";
      baseItemForm.querySelectorAll("[data-armor-mode]").forEach((section) => {
        const active = section.dataset.armorMode === mode;
        section.hidden = !active;
        section.querySelectorAll("input").forEach((field) => {
          field.disabled = !active;
        });
      });
    };
    const syncBaseForm = () => {
      const type = typeSelect?.value || "misc";
      const detailType = detailTypeFor(type);
      const isMagicType = MAGIC_ITEM_TYPES.has(type);
      const isForcedMagicType = FORCED_MAGIC_ITEM_TYPES.has(type);
      if (magicInput instanceof HTMLInputElement) {
        magicInput.checked = isForcedMagicType || magicInput.checked;
        magicInput.disabled = isForcedMagicType;
      }
      if (forcedMagicInput instanceof HTMLInputElement) {
        forcedMagicInput.disabled = !isForcedMagicType;
      }
      const isMagic = Boolean(magicInput?.checked) || isForcedMagicType;
      syncTypeSections(baseItemForm, type);
      if (detailPlaceholder) {
        const hasTypeFields = Boolean(baseItemForm.querySelector(`[data-item-fields='${detailType}']`));
        detailPlaceholder.hidden = hasTypeFields || isMagic;
      }
      if (magicFields) {
        magicFields.hidden = !isMagic;
        magicFields.querySelectorAll("input, select, textarea").forEach((field) => {
          field.disabled = !isMagic;
        });
      }
      if (isMagic && effectsList && !effectsList.querySelector("[data-sl-magic-effect]")) {
        addEffect();
      }
      effectsList?.querySelectorAll("[data-sl-magic-effect]").forEach(syncEffectRow);
      const nonStackable = WEAPON_ITEM_TYPES.has(type) || ARMOR_ITEM_TYPES.has(type) || ["shield", "clothing"].includes(type) || isMagic;
      if (stackableRow && stackableInput) {
        stackableRow.hidden = nonStackable;
        stackableInput.disabled = nonStackable;
        if (nonStackable) stackableInput.checked = false;
      }
      syncWieldMode();
      syncArmorMode();
    };
    typeSelect?.addEventListener("change", syncBaseForm);
    magicInput?.addEventListener("change", syncBaseForm);
    wieldMode?.addEventListener("change", syncWieldMode);
    armorModeInputs.forEach((input) => input.addEventListener("change", syncArmorMode));
    addEffectButton?.addEventListener("click", addEffect);
    baseItemForm.addEventListener("submit", (event) => {
      serializeEffects();
      if (Boolean(magicInput?.checked) && !effectsList?.querySelector("[data-sl-magic-effect]")) {
        event.preventDefault();
        addEffect();
        effectsList?.querySelector("[data-effect-kind]")?.focus();
      }
    });
    syncBaseForm();
  }

  const setupInstanceMagicEditor = (editor) => {
    if (editor.closest("[data-sl-base-item-form]")) return;
    const list = editor.querySelector("[data-sl-magic-effects]");
    const template = editor.querySelector("[data-sl-magic-effect-template]");
    const payloadInput = editor.querySelector("[data-sl-magic-payloads]");
    const addButton = editor.querySelector("[data-add-sl-magic-effect]");
    if (!list || !(template instanceof HTMLTemplateElement) || !payloadInput) return;

    const serialize = () => {
      const payloads = Array.from(list.querySelectorAll("[data-sl-magic-effect]")).map((row) => {
        const kind = row.querySelector("[data-effect-kind]")?.value || "";
        const payload = {
          target_kind: kind,
          value: Number.parseInt(row.querySelector("[data-effect-value]")?.value || "0", 10) || 0,
          effect_description: row.querySelector("[data-effect-description]")?.value?.trim() || "",
          rules_text: row.querySelector("[data-effect-rules-text]")?.value?.trim() || "",
          active_flag: row.dataset.effectActiveFlag !== "0",
          toggleable: Boolean(row.querySelector("[data-effect-toggleable]")?.checked),
          toggle_state_inverted: Boolean(row.querySelector("[data-effect-toggle-inverted]")?.checked),
        };
        if (row.dataset.displayGroup) {
          payload.display_group = Number.parseInt(row.dataset.displayGroup, 10) || row.dataset.displayGroup;
        }
        if (row.dataset.displayGroupAppend === "1") {
          payload.display_group_append = true;
        }
        const displayGroupValue = String(row.querySelector("[data-effect-display-group]")?.value || "").trim();
        if (displayGroupValue) {
          payload.display_group = Number.parseInt(displayGroupValue, 10) || displayGroupValue;
        }
        if (row.querySelector("[data-effect-display-group-append]")?.checked) {
          payload.display_group_append = true;
        }
        const scaleSource = row.querySelector("[data-effect-scale-source]")?.value || "";
        if (!["text", "rule_flag"].includes(kind) && scaleSource) {
          payload.scale_source = scaleSource;
          payload.scale_divisor = Number.parseInt(row.querySelector("[data-effect-scale-divisor]")?.value || "0", 10) || 0;
        }
        const target = row.querySelector(`[data-effect-target='${kind}'] select`)?.value || "";
        if (kind === "attribute") payload.target_attribute = target;
        if (kind === "stat") payload.target_stat = target;
        if (kind === "rule_flag") payload.target_rule_flag = target;
        if (kind === "skill") payload.target_skill = target;
        if (kind === "category") payload.target_skill_category = target;
        if (kind === "movement") payload.target_movement = target;
        if (kind === "item") payload.target_item = target;
        if (kind === "item_category") payload.target_item_category = target;
        if (kind === "specialization") payload.target_specialization = target;
        return payload;
      });
      payloadInput.value = JSON.stringify(payloads);
    };

    const sync = (row) => {
      const kind = row.querySelector("[data-effect-kind]")?.value || "text";
      row.querySelectorAll("[data-effect-target]").forEach((targetRow) => {
        const active = targetRow.dataset.effectTarget === kind;
        targetRow.hidden = !active;
        targetRow.querySelectorAll("select").forEach((select) => {
          select.disabled = !active;
        });
      });
      const valueRow = row.querySelector("[data-effect-value-row]");
      const calculated = !["text", "rule_flag"].includes(kind);
      if (valueRow) valueRow.hidden = !calculated;
      const value = row.querySelector("[data-effect-value]");
      if (value) value.disabled = !calculated;
      const scaleSource = row.querySelector("[data-effect-scale-source]");
      const scaleSourceRow = row.querySelector("[data-effect-scale-source-row]");
      const scaleDivisor = row.querySelector("[data-effect-scale-divisor]");
      const scaleDivisorRow = row.querySelector("[data-effect-scale-divisor-row]");
      if (scaleSourceRow) scaleSourceRow.hidden = !calculated;
      if (scaleSource) {
        scaleSource.disabled = !calculated;
        if (!calculated) scaleSource.value = "";
      }
      if (scaleDivisorRow) scaleDivisorRow.hidden = !calculated || !scaleSource?.value;
      if (scaleDivisor) scaleDivisor.disabled = !calculated || !scaleSource?.value;
      serialize();
    };

    const renumber = () => {
      list.querySelectorAll("[data-sl-magic-effect]").forEach((row, index) => {
        const title = row.querySelector("[data-sl-effect-title]");
        if (title) title.textContent = `Effekt ${index + 1}`;
      });
    };

    const add = (payload = {}) => {
      const row = template.content.firstElementChild.cloneNode(true);
      list.append(row);
      const kind = row.querySelector("[data-effect-kind]");
      const value = row.querySelector("[data-effect-value]");
      const description = row.querySelector("[data-effect-description]");
      const rulesText = row.querySelector("[data-effect-rules-text]");
      const displayGroup = row.querySelector("[data-effect-display-group]");
      const displayGroupAppend = row.querySelector("[data-effect-display-group-append]");
      const toggleable = row.querySelector("[data-effect-toggleable]");
      const toggleInverted = row.querySelector("[data-effect-toggle-inverted]");
      row.dataset.effectActiveFlag = payload.active_flag === false ? "0" : "1";
      row.dataset.displayGroup = payload.display_group == null ? "" : String(payload.display_group);
      row.dataset.displayGroupAppend = payload.display_group_append ? "1" : "0";
      if (kind && payload.target_kind) kind.value = payload.target_kind;
      if (value) value.value = String(payload.value ?? 0);
      if (description) description.value = payload.effect_description || "";
      if (rulesText) rulesText.value = payload.rules_text || "";
      if (displayGroup) displayGroup.value = payload.display_group == null ? "" : String(payload.display_group);
      if (displayGroupAppend) displayGroupAppend.checked = Boolean(payload.display_group_append);
      if (toggleable) toggleable.checked = Boolean(payload.toggleable);
      if (toggleInverted) toggleInverted.checked = Boolean(payload.toggle_state_inverted);
      const scaleSource = row.querySelector("[data-effect-scale-source]");
      const scaleDivisor = row.querySelector("[data-effect-scale-divisor]");
      if (scaleSource) scaleSource.value = payload.scale_source || "";
      if (scaleDivisor) scaleDivisor.value = String(payload.scale_divisor ?? 2);
      const selectedKind = kind?.value || "text";
      const targetValues = {
        attribute: payload.target_attribute,
        stat: payload.target_stat,
        rule_flag: payload.target_rule_flag,
        skill: payload.target_skill,
        category: payload.target_skill_category,
        movement: payload.target_movement,
        item: payload.target_item,
        item_category: payload.target_item_category,
        specialization: payload.target_specialization,
      };
      const targetSelect = row.querySelector(`[data-effect-target='${selectedKind}'] select`);
      if (targetSelect && targetValues[selectedKind] !== undefined && targetValues[selectedKind] !== null) {
        targetSelect.value = String(targetValues[selectedKind]);
      }
      row.querySelectorAll("input, select").forEach((field) => {
        field.addEventListener("input", serialize);
        field.addEventListener("change", serialize);
      });
      kind?.addEventListener("change", () => sync(row));
      row.querySelector("[data-effect-scale-source]")?.addEventListener("change", () => sync(row));
      row.querySelector("[data-remove-sl-magic-effect]")?.addEventListener("click", () => {
        row.remove();
        renumber();
        serialize();
      });
      sync(row);
      renumber();
    };

    let initialPayloads = [];
    try {
      initialPayloads = JSON.parse(payloadInput.value || "[]");
    } catch (_error) {
      initialPayloads = [];
    }
    if (Array.isArray(initialPayloads)) initialPayloads.forEach(add);
    addButton?.addEventListener("click", () => add());
    editor.closest("form")?.addEventListener("submit", serialize);
  };

  document.querySelectorAll("[data-sl-magic-effect-editor]").forEach(setupInstanceMagicEditor);

  document.querySelectorAll("[data-sl-rune-picker]").forEach((picker) => {
    const trigger = picker.querySelector("[data-sl-rune-trigger]");
    const panel = picker.querySelector("[data-sl-rune-panel]");
    const search = picker.querySelector("[data-sl-rune-search]");
    const list = picker.querySelector("[data-sl-rune-list]");
    const label = picker.querySelector("[data-sl-rune-label]");
    const count = picker.querySelector("[data-sl-rune-count]");
    if (!trigger || !panel || !list) return;
    const emptyLabel = label?.textContent?.trim() || "Keine Auswahl";
    const selectedSuffix = emptyLabel.includes("Fertigkeiten") ? "Fertigkeiten ausgewählt" : "Runen ausgewählt";

    const updateSelection = () => {
      const selected = Array.from(list.querySelectorAll("input[type='checkbox']:checked"));
      if (count) count.textContent = String(selected.length);
      if (!label) return;
      if (!selected.length) {
        label.textContent = emptyLabel;
      } else if (selected.length <= 2) {
        label.textContent = selected
          .map((input) => input.closest("label")?.querySelector("strong")?.textContent?.trim() || "")
          .filter(Boolean)
          .join(", ");
      } else {
        label.textContent = `${selected.length} ${selectedSuffix}`;
      }
    };

    const setOpen = (open) => {
      panel.hidden = !open;
      trigger.setAttribute("aria-expanded", open ? "true" : "false");
      picker.classList.toggle("is-open", open);
      if (open) search?.focus();
    };

    const filter = () => {
      const query = String(search?.value || "").trim().toLowerCase();
      list.querySelectorAll("[data-rune-search]").forEach((row) => {
        row.hidden = Boolean(query) && !String(row.dataset.runeSearch || "").includes(query);
      });
    };

    trigger.addEventListener("click", () => setOpen(panel.hidden));
    search?.addEventListener("input", filter);
    list.querySelectorAll("input[type='checkbox']").forEach((input) => {
      input.addEventListener("change", updateSelection);
    });
    document.addEventListener("click", (event) => {
      if (!picker.contains(event.target)) setOpen(false);
    });
    updateSelection();
    filter();
  });

  document.querySelectorAll("[data-sl-instance-form]").forEach((form) => {
    syncTypeSections(form, form.dataset.itemType || "misc");
  });

  const actionBody = document.querySelector("[data-sl-item-action-body]");
  const actionWindow = document.querySelector("[data-sl-item-action-window]");
  const actionTitle = document.getElementById("slItemActionTitle");
  let sourceCell = null;
  let activeForm = null;
  let movedNodes = [];
  const actionFrame = floating({
    win: actionWindow,
    backdrop: document.querySelector("[data-sl-item-action-backdrop]"),
    handle: document.querySelector("[data-sl-item-action-handle]"),
    closeButtons: Array.from(document.querySelectorAll("[data-close-sl-item-action]")),
    beforeOpen: (button) => {
      const row = document.getElementById(button.dataset.toggleSlInventoryPanel || "");
      const panelId = String(button.dataset.toggleSlInventoryPanel || "");
      if (!row || !actionBody) return false;
      sourceCell = row.querySelector("td") || row;
      if (panelId.startsWith("disclosure-")) {
        actionWindow?.classList.add("is-disclosure-card");
        movedNodes = Array.from(sourceCell.childNodes);
        if (!movedNodes.length) return false;
        actionBody.append(...movedNodes);
      } else {
        const form = row.querySelector("form");
        if (!form) return false;
        activeForm = form;
        actionBody.append(form);
      }
      if (actionTitle) {
        actionTitle.textContent = panelId.startsWith("bulk-send-")
          ? "Auswahl senden"
          : panelId.startsWith("catalog-edit-")
          ? "Basisitem bearbeiten"
          : panelId.startsWith("disclosure-")
          ? "Sichtbarkeit verwalten"
          : panelId.startsWith("send-")
          ? "Gegenstand senden"
          : "Instanz anpassen";
      }
    },
    afterClose: () => {
      if (sourceCell && movedNodes.length) sourceCell.append(...movedNodes);
      if (sourceCell && activeForm) sourceCell.append(activeForm);
      sourceCell = null;
      activeForm = null;
      movedNodes = [];
      actionWindow?.classList.remove("is-disclosure-card");
    },
  });
  document.querySelectorAll("[data-toggle-sl-inventory-panel]").forEach((button) => {
    button.addEventListener("click", () => actionFrame?.show(button));
  });

  const disclosureValueFor = (control) => {
    const checkbox = control?.querySelector(".sl-card-lock-checkbox");
    const alternate = control?.querySelector(".sl-card-alt-field");
    if (!checkbox?.checked) return null;
    const value = String(alternate?.value || "").trim();
    return value || "Verborgen";
  };

  const syncDisclosureControl = (control) => {
    if (!(control instanceof HTMLElement)) return;
    const checkbox = control.querySelector(".sl-card-lock-checkbox");
    if (!(checkbox instanceof HTMLInputElement)) return;
    const rawName = String(checkbox.name || "");
    const fieldKey = rawName.startsWith("revealed_") ? rawName.slice("revealed_".length) : "";
    const card = control.closest("[data-shared-item-card]");
    if (!fieldKey || !(card instanceof HTMLElement)) return;

    if (fieldKey === "image") {
      const image = card.querySelector("[data-sl-disclosure-target='image']");
      if (!(image instanceof HTMLImageElement)) return;
      if (!checkbox.checked) {
        image.src = image.dataset.actual || "";
        image.hidden = !image.src;
        return;
      }
      const clearInput = control.querySelector(".sl-card-image-clear-checkbox");
      if (clearInput instanceof HTMLInputElement && clearInput.checked) {
        image.hidden = true;
        return;
      }
      const fileInput = control.querySelector("input[type='file']");
      if (fileInput instanceof HTMLInputElement && fileInput.files?.[0]) {
        image.src = URL.createObjectURL(fileInput.files[0]);
        image.hidden = false;
        return;
      }
      const pickerImage = control.querySelector(".sl-card-image-picker img");
      if (pickerImage instanceof HTMLImageElement && pickerImage.src) {
        image.src = pickerImage.src;
        image.hidden = false;
        return;
      }
      image.hidden = true;
      return;
    }

    const target = card.querySelector(`[data-sl-disclosure-target='${CSS.escape(fieldKey)}']`);
    if (!(target instanceof HTMLElement)) return;
    if (!target.dataset.actualHtml) target.dataset.actualHtml = target.innerHTML;
    const lockedValue = disclosureValueFor(control);
    if (lockedValue === null) {
      target.innerHTML = target.dataset.actualHtml || "";
      return;
    }
    target.textContent = lockedValue;
  };

  const syncEffectControl = (control) => {
    if (!(control instanceof HTMLElement)) return;
    const checkbox = control.querySelector(".sl-card-lock-checkbox");
    const display = control.closest("td")?.querySelector("[data-sl-effect-display]");
    if (!(checkbox instanceof HTMLInputElement) || !(display instanceof HTMLElement)) return;
    const statusInput = control.querySelector("[data-sl-effect-status-input]");
    if (statusInput instanceof HTMLInputElement) {
      statusInput.value = statusInput.value.replace(/:[01]$/, checkbox.checked ? ":0" : ":1");
    }
    if (!display.dataset.actual) display.dataset.actual = display.textContent || "";
    if (!display.dataset.actualHtml) display.dataset.actualHtml = display.innerHTML;
    display.innerHTML = display.dataset.actualHtml || "";
    display.classList.toggle("is-player-hidden", checkbox.checked);
  };

  document.querySelectorAll(".sl-card-lock-control").forEach((control) => {
    control.addEventListener("change", (event) => {
      if (
        event.target instanceof HTMLInputElement
        && event.target.type === "file"
        && event.target.files?.[0]
      ) {
        const preview = control.querySelector(".sl-card-image-picker img") || document.createElement("img");
        preview.src = URL.createObjectURL(event.target.files[0]);
        if (!preview.parentElement) {
          const picker = control.querySelector(".sl-card-image-picker");
          picker?.prepend(preview);
        }
      }
      syncDisclosureControl(control);
      syncEffectControl(control);
    });
    control.addEventListener("input", () => {
      syncDisclosureControl(control);
      syncEffectControl(control);
    });
    syncDisclosureControl(control);
    syncEffectControl(control);
  });

  document.querySelectorAll("[data-sl-disclosure-save]").forEach((button) => {
    button.addEventListener("click", async () => {
      const disclosureForm = document.getElementById(button.dataset.disclosureForm || "");
      const effectForm = document.getElementById(button.dataset.effectForm || "");
      if (!(disclosureForm instanceof HTMLFormElement) || !(effectForm instanceof HTMLFormElement)) return;
      button.disabled = true;
      const originalText = button.textContent;
      button.textContent = "Speichert...";
      try {
        for (const form of [disclosureForm, effectForm]) {
          const data = new FormData(form);
          data.set("_response_format", "json");
          const response = await fetch(form.action, {
            method: "POST",
            body: data,
            headers: {
              "X-Requested-With": "XMLHttpRequest",
              "Accept": "application/json",
            },
          });
          if (!response.ok) {
            const detail = await response.text();
            throw new Error(`Save failed: ${response.status} ${detail.slice(0, 300)}`);
          }
        }
        window.location.reload();
      } catch (error) {
        console.error(error);
        button.disabled = false;
        button.textContent = originalText || "Speichern";
        window.alert("Speichern fehlgeschlagen.");
      }
    });
  });

  document.querySelectorAll(".sl-inventory").forEach((panel) => {
    const selectAll = panel.querySelector("[data-sl-inventory-select-all]");
    const itemCheckboxes = Array.from(panel.querySelectorAll("[data-sl-inventory-select]"));
    const bulkTrigger = panel.querySelector("[data-sl-bulk-send-trigger]");
    const bulkItems = panel.querySelector("[data-sl-bulk-send-items]");
    const bulkDeleteTrigger = panel.querySelector("[data-sl-bulk-delete-trigger]");
    const bulkDeleteItems = panel.querySelector("[data-sl-bulk-delete-items]");
    const syncBulkSelection = () => {
      const selected = itemCheckboxes.filter((checkbox) => checkbox.checked);
      if (bulkTrigger) {
        bulkTrigger.disabled = selected.length === 0;
        bulkTrigger.title = selected.length
          ? `${selected.length} Gegenstände senden`
          : "Ausgewählte Gegenstände senden";
      }
      if (bulkDeleteTrigger) {
        bulkDeleteTrigger.disabled = selected.length === 0;
        bulkDeleteTrigger.title = selected.length
          ? `${selected.length} Gegenstände entfernen`
          : "Ausgewählte Gegenstände entfernen";
      }
      if (selectAll) {
        selectAll.checked = selected.length > 0 && selected.length === itemCheckboxes.length;
        selectAll.indeterminate = selected.length > 0 && selected.length < itemCheckboxes.length;
      }
      if (bulkItems) {
        bulkItems.replaceChildren(
          ...selected.map((checkbox) => {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = "item_ids";
            input.value = checkbox.value;
            return input;
          })
        );
      }
      if (bulkDeleteItems) {
        bulkDeleteItems.replaceChildren(
          ...selected.map((checkbox) => {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = "item_ids";
            input.value = checkbox.value;
            return input;
          })
        );
      }
    };
    selectAll?.addEventListener("change", () => {
      itemCheckboxes.forEach((checkbox) => {
        checkbox.checked = selectAll.checked;
      });
      syncBulkSelection();
    });
    itemCheckboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", syncBulkSelection);
    });
    syncBulkSelection();
  });

  document.querySelectorAll("[data-confirm-inventory-delete]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm("Diesen Gegenstand wirklich aus dem SL-Inventar entfernen?")) {
        event.preventDefault();
      }
    });
  });

  document.querySelectorAll("[data-confirm-inventory-bulk-delete]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const count = form.querySelectorAll("input[name='item_ids']").length;
      if (!count || !window.confirm(`${count} ausgewählte Gegenstände wirklich aus dem SL-Inventar entfernen?`)) {
        event.preventDefault();
      }
    });
  });

  document.querySelectorAll("[data-sl-item-search]").forEach((picker) => {
    const query = picker.querySelector("[data-sl-item-search-query]");
    const selectedId = picker.querySelector("[data-sl-item-search-id]");
    const results = picker.querySelector("[data-sl-item-search-results]");
    const options = Array.from(results?.querySelectorAll("button[data-item-id]") || []);
    const empty = results?.querySelector("[data-sl-item-search-empty]");
    if (!query || !selectedId || !results) return;

    const filter = () => {
      const term = query.value.trim().toLocaleLowerCase("de");
      let visible = 0;
      options.forEach((option) => {
        const matches = !term || String(option.dataset.itemSearch || "").includes(term);
        option.hidden = !matches;
        if (matches) visible += 1;
      });
      if (empty) empty.hidden = visible !== 0;
      results.hidden = false;
      if (query.value !== query.dataset.selectedName) {
        selectedId.value = "";
        query.setCustomValidity("Bitte einen Gegenstand aus der Trefferliste auswählen.");
      }
    };

    query.addEventListener("input", filter);
    query.addEventListener("focus", filter);
    options.forEach((option) => {
      option.addEventListener("click", () => {
        selectedId.value = option.dataset.itemId;
        query.value = option.dataset.itemName;
        query.dataset.selectedName = option.dataset.itemName;
        query.setCustomValidity("");
        results.hidden = true;
      });
    });
    document.addEventListener("click", (event) => {
      if (!picker.contains(event.target)) results.hidden = true;
    });
  });

  document.querySelectorAll("[data-sl-add-cart]").forEach((form) => {
    const selectedId = form.querySelector("[data-sl-item-search-id]");
    const query = form.querySelector("[data-sl-item-search-query]");
    const quality = form.querySelector("select[name='quality']");
    const amount = form.querySelector("input[name='amount']");
    const addButton = form.querySelector("[data-sl-add-cart-add]");
    const list = form.querySelector("[data-sl-add-cart-list]");
    const empty = form.querySelector("[data-sl-add-cart-empty]");
    const payload = form.querySelector("[data-sl-add-cart-payload]");
    const submit = form.querySelector("[data-sl-add-cart-submit]");
    if (!selectedId || !query || !quality || !amount || !addButton || !list || !payload) return;

    const cart = [];
    const sync = () => {
      list.querySelectorAll("[data-sl-add-cart-row]").forEach((row) => row.remove());
      cart.forEach((entry, index) => {
        const row = document.createElement("div");
        row.className = "sl-add-cart__row";
        row.dataset.slAddCartRow = "1";
        const text = document.createElement("span");
        const name = document.createElement("strong");
        name.textContent = entry.name;
        const meta = document.createElement("small");
        meta.textContent = `${entry.qualityLabel} · ${entry.amount}x`;
        text.append(name, meta);
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "sl-inventory-icon-button sl-inventory-icon-button--danger";
        remove.dataset.slAddCartRemove = String(index);
        remove.setAttribute("aria-label", "Aus Warenkorb entfernen");
        remove.title = "Entfernen";
        remove.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 4V2h8v2h5v2H3V4h5Zm-2 4h12l-1 14H7L6 8Zm4 2v9h2v-9h-2Zm4 0v9h2v-9h-2Z"/></svg>`;
        row.append(text, remove);
        list.append(row);
      });
      if (empty) empty.hidden = cart.length > 0;
      if (submit) submit.disabled = cart.length === 0;
      payload.value = JSON.stringify(cart.map((entry) => ({
        item_id: entry.itemId,
        quality: entry.quality,
        amount: entry.amount,
      })));
    };

    addButton.addEventListener("click", () => {
      const itemId = String(selectedId.value || "");
      if (!itemId) {
        query.setCustomValidity("Bitte einen Gegenstand aus der Trefferliste auswählen.");
        query.reportValidity();
        return;
      }
      const qualityValue = String(quality.value || "common");
      const qty = Math.max(1, Number.parseInt(amount.value || "1", 10) || 1);
      const existing = cart.find((entry) => entry.itemId === itemId && entry.quality === qualityValue);
      if (existing) {
        existing.amount += qty;
      } else {
        cart.push({
          itemId,
          name: String(query.dataset.selectedName || query.value || "Gegenstand"),
          quality: qualityValue,
          qualityLabel: quality.selectedOptions?.[0]?.textContent?.trim() || qualityValue,
          amount: qty,
        });
      }
      selectedId.value = "";
      query.value = "";
      query.dataset.selectedName = "";
      query.setCustomValidity("");
      amount.value = "1";
      sync();
      query.focus();
    });

    list.addEventListener("click", (event) => {
      const button = event.target.closest("[data-sl-add-cart-remove]");
      if (!button) return;
      const index = Number.parseInt(button.dataset.slAddCartRemove || "-1", 10);
      if (index >= 0) {
        cart.splice(index, 1);
        sync();
      }
    });

    form.addEventListener("submit", (event) => {
      if (!cart.length) {
        event.preventDefault();
        query.setCustomValidity("Bitte mindestens einen Gegenstand in den Warenkorb legen.");
        query.reportValidity();
      }
    });

    sync();
  });

  const inventory = document.querySelector("[data-sl-transfer-state-url]");
  const signatureNode = inventory?.querySelector("[data-sl-transfer-signature]");
  if (inventory && signatureNode) {
    let signature = signatureNode.textContent.trim();
    let requestInFlight = false;
    let reloadStarted = false;

    const updateTransferState = async () => {
      if (document.hidden || requestInFlight || reloadStarted) return;
      requestInFlight = true;
      try {
        const response = await fetch(inventory.dataset.slTransferStateUrl, {
          headers: { Accept: "application/json" },
          credentials: "same-origin",
          cache: "no-store",
        });
        if (!response.ok) return;
        const state = await response.json();
        const nextSignature = String(state.signature || "");
        if (nextSignature !== signature) {
          signature = nextSignature;
          reloadStarted = true;
          window.location.reload();
        }
      } catch (_error) {
        // Temporäre Verbindungsfehler dürfen keine Aktualisierungsschleife auslösen.
      } finally {
        requestInFlight = false;
      }
    };

    window.setInterval(updateTransferState, 3000);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) updateTransferState();
    });
  }
});
