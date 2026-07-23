document.addEventListener("DOMContentLoaded", () => {
  const floating = ({ win, backdrop, handle, opener, closeButtons, beforeOpen, afterClose }) => {
    if (!win || !backdrop || !handle) return null;
    const center = () => {
      const rect = win.getBoundingClientRect();
      win.style.left = Math.max(12, (window.innerWidth - rect.width) / 2) + "px";
      win.style.top = Math.max(12, Math.min(62, window.innerHeight - rect.height - 12)) + "px";
    };
    const show = (trigger) => {
      if (beforeOpen && beforeOpen(trigger) === false) return;
      win.classList.add("is-open");
      win.setAttribute("aria-hidden", "false");
      backdrop.classList.add("is-open");
      center();
    };
    const hide = () => {
      win.classList.remove("is-open");
      win.setAttribute("aria-hidden", "true");
      backdrop.classList.remove("is-open");
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
      const rect = win.getBoundingClientRect();
      win.style.left = Math.min(window.innerWidth - rect.width - 12, Math.max(12, event.clientX - offsetX)) + "px";
      win.style.top = Math.min(window.innerHeight - rect.height - 12, Math.max(12, event.clientY - offsetY)) + "px";
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

  const syncTypeSections = (form, type) => {
    form.querySelectorAll("[data-item-fields]").forEach((section) => {
      const active = section.dataset.itemFields === type;
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
    const magicFields = baseItemForm.querySelector("[data-sl-magic-fields]");
    const stackableRow = baseItemForm.querySelector("[data-sl-stackable]");
    const stackableInput = stackableRow?.querySelector("input");
    const wieldMode = baseItemForm.querySelector("[data-sl-wield-mode]");
    const twoHandFields = baseItemForm.querySelector("[data-sl-two-hand]");
    const armorModeInputs = baseItemForm.querySelectorAll("input[name='armor_mode']");
    const effectsList = baseItemForm.querySelector("[data-sl-magic-effects]");
    const effectTemplate = baseItemForm.querySelector("[data-sl-magic-effect-template]");
    const addEffectButton = baseItemForm.querySelector("[data-add-sl-magic-effect]");
    const effectPayloads = baseItemForm.querySelector("[data-sl-magic-payloads]");

    const serializeEffects = () => {
      if (!effectsList || !effectPayloads) return;
      const payloads = Array.from(effectsList.querySelectorAll("[data-sl-magic-effect]")).map((row) => {
        const targetKind = row.querySelector("[data-effect-kind]")?.value || "";
        const payload = {
          target_kind: targetKind,
          value: Number.parseInt(row.querySelector("[data-effect-value]")?.value || "0", 10) || 0,
          effect_description: row.querySelector("[data-effect-description]")?.value?.trim() || "",
        };
        const target = row.querySelector(`[data-effect-target='${targetKind}'] select`);
        if (targetKind === "attribute") payload.target_attribute = target?.value || "";
        if (targetKind === "stat") payload.target_stat = target?.value || "";
        if (targetKind === "rule_flag") payload.target_rule_flag = target?.value || "";
        if (targetKind === "skill") payload.target_skill = target?.value || "";
        if (targetKind === "category") payload.target_skill_category = target?.value || "";
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
      const visible = wieldMode?.value === "2h" || wieldMode?.value === "vh";
      twoHandFields.hidden = !visible;
      twoHandFields.querySelectorAll("input, select").forEach((field) => {
        field.disabled = !visible;
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
      const isMagic = Boolean(magicInput?.checked) || type === "magic_item";
      syncTypeSections(baseItemForm, type);
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
      const nonStackable = ["weapon", "armor", "shield", "clothing"].includes(type) || isMagic;
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
        };
        const target = row.querySelector(`[data-effect-target='${kind}'] select`)?.value || "";
        if (kind === "attribute") payload.target_attribute = target;
        if (kind === "stat") payload.target_stat = target;
        if (kind === "rule_flag") payload.target_rule_flag = target;
        if (kind === "skill") payload.target_skill = target;
        if (kind === "category") payload.target_skill_category = target;
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
      if (kind && payload.target_kind) kind.value = payload.target_kind;
      if (value) value.value = String(payload.value ?? 0);
      if (description) description.value = payload.effect_description || "";
      const selectedKind = kind?.value || "text";
      const targetValues = {
        attribute: payload.target_attribute,
        stat: payload.target_stat,
        rule_flag: payload.target_rule_flag,
        skill: payload.target_skill,
        category: payload.target_skill_category,
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

  document.querySelectorAll("[data-sl-instance-magic-editor]").forEach(setupInstanceMagicEditor);

  document.querySelectorAll("[data-sl-rune-picker]").forEach((picker) => {
    const trigger = picker.querySelector("[data-sl-rune-trigger]");
    const panel = picker.querySelector("[data-sl-rune-panel]");
    const search = picker.querySelector("[data-sl-rune-search]");
    const list = picker.querySelector("[data-sl-rune-list]");
    const label = picker.querySelector("[data-sl-rune-label]");
    const count = picker.querySelector("[data-sl-rune-count]");
    if (!trigger || !panel || !list) return;

    const updateSelection = () => {
      const selected = Array.from(list.querySelectorAll("input[type='checkbox']:checked"));
      if (count) count.textContent = String(selected.length);
      if (!label) return;
      if (!selected.length) {
        label.textContent = "Keine Runen ausgewählt";
      } else if (selected.length <= 2) {
        label.textContent = selected
          .map((input) => input.closest("label")?.querySelector("strong")?.textContent?.trim() || "")
          .filter(Boolean)
          .join(", ");
      } else {
        label.textContent = `${selected.length} Runen ausgewählt`;
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
  const actionTitle = document.getElementById("slItemActionTitle");
  let sourceCell = null;
  let activeForm = null;
  const actionFrame = floating({
    win: document.querySelector("[data-sl-item-action-window]"),
    backdrop: document.querySelector("[data-sl-item-action-backdrop]"),
    handle: document.querySelector("[data-sl-item-action-handle]"),
    closeButtons: Array.from(document.querySelectorAll("[data-close-sl-item-action]")),
    beforeOpen: (button) => {
      const row = document.getElementById(button.dataset.toggleSlInventoryPanel || "");
      const form = row?.querySelector("form");
      if (!form || !actionBody) return false;
      sourceCell = row.querySelector("td");
      activeForm = form;
      actionBody.append(form);
      if (actionTitle) {
        actionTitle.textContent = String(button.dataset.toggleSlInventoryPanel || "").startsWith("send-")
          ? "Gegenstand senden"
          : "Instanz anpassen";
      }
    },
    afterClose: () => {
      if (sourceCell && activeForm) sourceCell.append(activeForm);
      sourceCell = null;
      activeForm = null;
    },
  });
  document.querySelectorAll("[data-toggle-sl-inventory-panel]").forEach((button) => {
    button.addEventListener("click", () => actionFrame?.show(button));
  });

  document.querySelectorAll("[data-confirm-inventory-delete]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm("Diesen Gegenstand wirklich aus dem SL-Inventar entfernen?")) {
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
