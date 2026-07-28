(() => {
  "use strict";

  const inventoryWorkspace = document.querySelector("[data-inventory-workspace]");
  const inventoryArea = inventoryWorkspace?.querySelector("[data-inventory-area]");
  const inventoryToggle = inventoryArea?.querySelector("[data-inventory-toggle]");
  const inventoryContent = inventoryArea?.querySelector(".gm-inventory-area__content");

  if (inventoryWorkspace && inventoryArea && inventoryToggle && inventoryContent) {
    let inventoryTransitionVersion = 0;

    const applyInventoryState = (isCollapsed) => {
      const transitionVersion = ++inventoryTransitionVersion;
      if (!isCollapsed) {
        inventoryContent.hidden = false;
        void inventoryContent.offsetWidth;
      }
      inventoryWorkspace.classList.toggle(
        "is-inventory-collapsed",
        isCollapsed,
      );
      inventoryContent.inert = isCollapsed;
      inventoryContent.setAttribute("aria-hidden", String(isCollapsed));
      inventoryToggle.setAttribute("aria-expanded", String(!isCollapsed));
      const label = isCollapsed
        ? "Inventar ausklappen"
        : "Inventar einklappen";
      inventoryToggle.setAttribute("aria-label", label);
      inventoryToggle.title = label;
      if (isCollapsed) {
        window.setTimeout(() => {
          if (
            transitionVersion === inventoryTransitionVersion
            && inventoryWorkspace.classList.contains(
              "is-inventory-collapsed",
            )
          ) {
            inventoryContent.hidden = true;
          }
        }, 740);
      }
      window.dispatchEvent(new Event("resize"));
    };

    inventoryToggle.addEventListener("click", async () => {
      if (inventoryToggle.disabled) {
        return;
      }
      const wasCollapsed = inventoryWorkspace.classList.contains(
        "is-inventory-collapsed",
      );
      const isCollapsed = !wasCollapsed;
      const stateUrl = inventoryArea.dataset.inventoryStateUrl;
      const csrfToken = inventoryArea.dataset.csrfToken;
      if (!stateUrl || !csrfToken) {
        return;
      }

      applyInventoryState(isCollapsed);
      inventoryToggle.disabled = true;

      try {
        const body = new URLSearchParams({
          is_collapsed: isCollapsed ? "1" : "0",
          csrfmiddlewaretoken: csrfToken,
        });
        const response = await fetch(stateUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-CSRFToken": csrfToken,
            "X-Requested-With": "XMLHttpRequest",
          },
          body: body.toString(),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
          throw new Error(
            result.error || "Der Inventarstatus konnte nicht gespeichert werden.",
          );
        }
        applyInventoryState(Boolean(result.is_collapsed));
      } catch (error) {
        applyInventoryState(wasCollapsed);
        window.alert("Das Inventar konnte nicht ein- oder ausgeklappt werden.");
      } finally {
        inventoryToggle.disabled = false;
      }
    });
  }

  document.querySelectorAll("[data-creature-search]").forEach((picker) => {
    const query = picker.querySelector("[data-creature-search-query]");
    const selectedId = picker.querySelector("[data-creature-search-id]");
    const results = picker.querySelector("[data-creature-search-results]");
    const form = picker.closest("form");
    const details = picker.closest("details");
    const options = Array.from(
      results?.querySelectorAll("button[data-creature-ref]") || [],
    );
    const empty = results?.querySelector("[data-creature-search-empty]");
    if (!query || !selectedId || !results) {
      return;
    }
    const selectionKey = `gm-creature-picker-selection:${window.location.pathname}`;
    const clearSavedSelection = () => {
      try {
        window.sessionStorage.removeItem(selectionKey);
      } catch (error) {
        // The picker also works when browser storage is unavailable.
      }
    };
    const restoreSavedSelection = () => {
      try {
        const savedRef = window.sessionStorage.getItem(selectionKey);
        const option = options.find(
          (candidate) => candidate.dataset.creatureRef === savedRef,
        );
        if (!option) {
          clearSavedSelection();
          return;
        }
        selectedId.value = option.dataset.creatureRef;
        query.value = option.dataset.creatureName;
        query.dataset.selectedName = option.dataset.creatureName;
        query.setCustomValidity("");
      } catch (error) {
        // The picker also works when browser storage is unavailable.
      }
    };
    const resetSelection = () => {
      selectedId.value = "";
      query.value = "";
      delete query.dataset.selectedName;
      query.setCustomValidity("");
      results.hidden = true;
      options.forEach((option) => {
        option.hidden = false;
      });
      if (empty) {
        empty.hidden = true;
      }
      clearSavedSelection();
    };

    const filter = () => {
      const term = query.value.trim().toLocaleLowerCase("de");
      let visible = 0;
      options.forEach((option) => {
        const matches = (
          !term
          || String(option.dataset.creatureSearch || "").includes(term)
        );
        option.hidden = !matches;
        if (matches) {
          visible += 1;
        }
      });
      if (empty) {
        empty.hidden = visible !== 0;
      }
      results.hidden = false;
      if (query.value !== query.dataset.selectedName) {
        selectedId.value = "";
        clearSavedSelection();
        query.setCustomValidity(
          "Bitte eine Kreatur aus der Trefferliste auswählen.",
        );
      }
    };

    query.addEventListener("input", filter);
    query.addEventListener("focus", filter);
    query.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        results.hidden = true;
      }
    });
    options.forEach((option) => {
      option.addEventListener("click", () => {
        selectedId.value = option.dataset.creatureRef;
        query.value = option.dataset.creatureName;
        query.dataset.selectedName = option.dataset.creatureName;
        query.setCustomValidity("");
        results.hidden = true;
      });
    });
    form?.addEventListener("submit", () => {
      if (!selectedId.value) {
        return;
      }
      try {
        window.sessionStorage.setItem(selectionKey, selectedId.value);
      } catch (error) {
        // A blocked storage API must not block the form submission.
      }
    });
    document.addEventListener("click", (event) => {
      if (!picker.contains(event.target)) {
        results.hidden = true;
      }
    });
    details?.addEventListener("toggle", () => {
      if (!details.open) {
        resetSelection();
      }
    });
    restoreSavedSelection();
  });

  const cardRows = [
    {
      scroller: document.querySelector(".gm-roster"),
      host: document.querySelector(".gm-roster-scroll-shell"),
    },
    {
      scroller: document.querySelector(".gm-data-tables"),
      host: document.querySelector(".gm-info-area"),
    },
  ].filter(({ scroller, host }) => scroller && host);

  const updateEdges = ({ scroller, host }) => {
    const tolerance = 2;
    const hasOverflow = scroller.scrollWidth > scroller.clientWidth + tolerance;
    host.classList.toggle(
      "has-card-overflow-left",
      hasOverflow && scroller.scrollLeft > tolerance,
    );
    host.classList.toggle(
      "has-card-overflow-right",
      hasOverflow
        && scroller.scrollLeft + scroller.clientWidth < scroller.scrollWidth - tolerance,
    );
  };

  cardRows.forEach((cardRow) => {
    const update = () => updateEdges(cardRow);
    cardRow.scroller.addEventListener("scroll", update, { passive: true });
    cardRow.scroller.addEventListener("transitionend", update);
    window.addEventListener("resize", update, { passive: true });
    new ResizeObserver(update).observe(cardRow.scroller);
    new MutationObserver(update).observe(cardRow.scroller, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["hidden", "open", "style"],
    });
    update();
  });

  const rosterContainer = document.querySelector(".gm-roster");
  const collapsedRoster = document.querySelector("[data-collapsed-roster]");
  const rosterCardRow = cardRows.find(
    ({ scroller }) => scroller === rosterContainer,
  );

  const syncCollapsedRoster = () => {
    if (!collapsedRoster) {
      return;
    }
    const visiblePortraits = Array.from(
      collapsedRoster.querySelectorAll("[data-collapsed-card-id]"),
    ).filter((portrait) => !portrait.hidden);
    const hasCollapsedCards = visiblePortraits.length > 0;
    collapsedRoster.hidden = !hasCollapsedCards;
    if (!hasCollapsedCards) {
      return;
    }

    const styles = window.getComputedStyle(collapsedRoster);
    const portraitSize = visiblePortraits[0].offsetWidth || 50;
    const rowGap = Number.parseFloat(styles.rowGap) || 7;
    const columnGap = Number.parseFloat(styles.columnGap) || 7;
    const paddingBlock = (
      (Number.parseFloat(styles.paddingTop) || 0)
      + (Number.parseFloat(styles.paddingBottom) || 0)
    );
    const paddingInline = (
      (Number.parseFloat(styles.paddingLeft) || 0)
      + (Number.parseFloat(styles.paddingRight) || 0)
    );
    const borders = (
      (Number.parseFloat(styles.borderLeftWidth) || 0)
      + (Number.parseFloat(styles.borderRightWidth) || 0)
    );
    const availableHeight = Math.max(
      portraitSize,
      collapsedRoster.clientHeight - paddingBlock,
    );
    const rowCapacity = Math.max(
      1,
      Math.floor((availableHeight + rowGap) / (portraitSize + rowGap)),
    );
    const columnCount = Math.ceil(visiblePortraits.length / rowCapacity);
    const requiredWidth = (
      paddingInline
      + borders
      + (columnCount * portraitSize)
      + (Math.max(0, columnCount - 1) * columnGap)
    );
    collapsedRoster.style.setProperty(
      "--gm-collapsed-roster-width",
      `${Math.ceil(requiredWidth)}px`,
    );
  };

  document.querySelectorAll(
    "[data-screen-card-state-url][data-screen-card-id][data-screen-card-collapse-value]",
  ).forEach((button) => {
    button.addEventListener("click", async () => {
      const cardId = button.dataset.screenCardId;
      const isCollapsed = button.dataset.screenCardCollapseValue === "1";
      const csrfToken = rosterContainer?.dataset.csrfToken;
      if (!cardId || !csrfToken || button.disabled) {
        return;
      }

      const card = Array.from(
        rosterContainer.querySelectorAll("[data-reorder-card][data-reorder-id]"),
      ).find((candidate) => candidate.dataset.reorderId === cardId);
      const portrait = Array.from(
        collapsedRoster?.querySelectorAll("[data-collapsed-card-id]") || [],
      ).find(
        (candidate) => candidate.dataset.collapsedCardId === cardId,
      );
      button.disabled = true;

      try {
        const body = new URLSearchParams({
          is_collapsed: isCollapsed ? "1" : "0",
          csrfmiddlewaretoken: csrfToken,
        });
        const response = await fetch(button.dataset.screenCardStateUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-CSRFToken": csrfToken,
            "X-Requested-With": "XMLHttpRequest",
          },
          body: body.toString(),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
          throw new Error(
            result.error || "Die Kartenansicht konnte nicht geändert werden.",
          );
        }
        if (card) {
          card.hidden = result.is_collapsed;
        }
        if (portrait) {
          portrait.hidden = !result.is_collapsed;
        }
        syncCollapsedRoster();
        if (rosterCardRow) {
          updateEdges(rosterCardRow);
        }
      } catch (error) {
        window.alert("Die Karte konnte nicht ein- oder ausgeblendet werden.");
      } finally {
        button.disabled = false;
      }
    });
  });
  syncCollapsedRoster();
  window.addEventListener("resize", syncCollapsedRoster, { passive: true });

  const applyCreatureDamageState = (card, result) => {
    const lifeValue = card.querySelector(".gm-vital--life > div:first-child > span");
    const damageTrack = card.querySelector(".gm-damage-track");
    const stunTrack = card.querySelector(".gm-damage-track__stun");
    const lethalTrack = card.querySelector(".gm-damage-track__lethal");
    const nameContainer = card.querySelector(".gm-character-sheet__name");
    let subtitle = nameContainer?.querySelector("p");

    if (lifeValue) {
      lifeValue.textContent = `${result.current_lp} / ${result.max_lp}`;
    }
    if (damageTrack) {
      damageTrack.setAttribute(
        "aria-label",
        `${result.stun_damage} B-Schaden und ${result.lethal_damage} T-Schaden von ${result.max_lp}`,
      );
    }
    if (stunTrack) {
      stunTrack.style.width = `${result.stun_damage_percent}%`;
    }
    if (lethalTrack) {
      lethalTrack.style.width = `${result.lethal_damage_percent}%`;
    }
    [
      ["b", result.stun_damage],
      ["t", result.lethal_damage],
    ].forEach(([damageType, value]) => {
      const damageValue = card.querySelector(
        `.gm-creature-damage-control--${damageType} > strong`,
      );
      if (damageValue) {
        damageValue.textContent = String(value);
      }
    });

    if (result.subtitle) {
      if (!subtitle && nameContainer) {
        subtitle = document.createElement("p");
        nameContainer.append(subtitle);
      }
      if (subtitle) {
        subtitle.textContent = result.subtitle;
      }
    } else {
      subtitle?.remove();
    }

    card.classList.toggle(
      "gm-character-sheet--incapacitated",
      Boolean(result.is_incapacitated),
    );
    card.classList.toggle(
      "gm-character-sheet--dead",
      Boolean(result.is_dead),
    );
    const portrait = Array.from(
      collapsedRoster?.querySelectorAll("[data-collapsed-card-id]") || [],
    ).find(
      (candidate) => candidate.dataset.collapsedCardId === card.dataset.reorderId,
    );
    portrait?.classList.toggle(
      "gm-roster-collapsed__portrait--incapacitated",
      Boolean(result.is_incapacitated),
    );
    portrait?.classList.toggle(
      "gm-roster-collapsed__portrait--dead",
      Boolean(result.is_dead),
    );
  };

  const applyCreatureKpState = (card, result) => {
    const value = card.querySelector(".gm-creature-kp-controls > span");
    const progress = card.querySelector(".gm-vital--arcane progress");
    const display = `${result.current_kp} / ${result.max_kp}`;
    if (value) {
      value.textContent = display;
    }
    if (progress) {
      progress.value = result.current_kp;
      progress.max = result.max_kp > 0 ? result.max_kp : 1;
      progress.textContent = display;
    }
  };

  document.querySelectorAll(
    ".gm-creature-damage-controls form, .gm-creature-kp-controls form",
  ).forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const card = form.closest(".gm-character-sheet--creature");
      const controls = form.closest(
        ".gm-creature-damage-controls, .gm-creature-kp-controls",
      );
      const buttons = Array.from(controls?.querySelectorAll("button") || []);
      if (!card || buttons.some((button) => button.disabled)) {
        return;
      }

      buttons.forEach((button) => {
        button.disabled = true;
      });
      card.setAttribute("aria-busy", "true");

      try {
        const body = new URLSearchParams(new FormData(form));
        const csrfToken = body.get("csrfmiddlewaretoken");
        // The hidden input named "action" shadows HTMLFormElement.action.
        const actionUrl = form.getAttribute("action");
        if (!actionUrl) {
          throw new Error("Das Ziel für die Statusänderung fehlt.");
        }
        body.set("_response_format", "json");
        const response = await fetch(actionUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-CSRFToken": csrfToken,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
          },
          body: body.toString(),
        });
        const responseType = response.headers.get("content-type") || "";
        if (!responseType.includes("application/json")) {
          throw new Error(
            `Der Server lieferte keine Statusdaten zurück (HTTP ${response.status}).`,
          );
        }
        const result = await response.json();
        if (!response.ok || !result.ok) {
          throw new Error(
            result.error || "Der Kreaturenstatus konnte nicht aktualisiert werden.",
          );
        }
        if (result.kind === "damage") {
          applyCreatureDamageState(card, result);
        } else if (result.kind === "kp") {
          applyCreatureKpState(card, result);
        }
      } catch (error) {
        window.alert(
          error instanceof Error
            ? error.message
            : "Der Kreaturenstatus konnte nicht aktualisiert werden.",
        );
      } finally {
        buttons.forEach((button) => {
          button.disabled = false;
        });
        card.removeAttribute("aria-busy");
      }
    });
  });

  document.querySelectorAll(".gm-table-picker").forEach((picker) => {
    const storageKey = picker.dataset.pickerStorageKey;
    const reopenKey = storageKey
      ? `gm-picker-open:${storageKey}:${window.location.pathname}`
      : "";
    try {
      if (reopenKey && window.sessionStorage.getItem(reopenKey) === "1") {
        picker.open = true;
        window.sessionStorage.removeItem(reopenKey);
      }
    } catch (error) {
      // The picker also works when browser storage is unavailable.
    }

    picker.querySelectorAll("form").forEach((form) => {
      form.addEventListener("submit", () => {
        try {
          if (reopenKey) {
            window.sessionStorage.setItem(reopenKey, "1");
          }
        } catch (error) {
          // A blocked storage API must not block the form submission.
        }
      });
    });

    const showForm = picker.querySelector("[data-table-picker-show]");
    const search = picker.querySelector("[data-table-picker-search]");
    const query = picker.querySelector("[data-table-picker-query]");
    const actionInput = picker.querySelector(
      "[data-table-picker-action-input]",
    );
    const results = picker.querySelector("[data-table-picker-results]");
    const options = Array.from(
      picker.querySelectorAll("[data-table-picker-option]"),
    );
    const empty = picker.querySelector("[data-table-picker-empty]");
    const submit = picker.querySelector("[data-table-picker-submit]");

    if (
      !showForm
      || !search
      || !query
      || !actionInput
      || !results
      || !submit
    ) {
      return;
    }

    const updateSelection = () => {
      const action = actionInput.value;
      submit.disabled = !action;
      if (action) {
        showForm.action = action;
      } else {
        showForm.removeAttribute("action");
      }
    };
    const hideResults = () => {
      results.hidden = true;
      query.setAttribute("aria-expanded", "false");
    };
    const filterOptions = () => {
      const term = query.value.trim().toLocaleLowerCase("de");
      let visible = 0;
      options.forEach((option) => {
        const matches = (
          !term
          || String(option.dataset.tablePickerSearch || "").includes(term)
        );
        option.hidden = !matches;
        if (matches) {
          visible += 1;
        }
      });
      if (empty) {
        empty.hidden = visible !== 0;
      }
      results.hidden = false;
      query.setAttribute("aria-expanded", "true");
      if (query.value !== query.dataset.selectedName) {
        actionInput.value = "";
        query.setCustomValidity(
          query.value
            ? "Bitte eine Karte aus der Trefferliste auswählen."
            : "",
        );
        updateSelection();
      }
    };

    query.addEventListener("input", filterOptions);
    query.addEventListener("focus", filterOptions);
    query.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        hideResults();
      }
    });
    options.forEach((option) => {
      option.addEventListener("click", () => {
        actionInput.value = option.dataset.tablePickerAction;
        query.value = option.dataset.tablePickerName;
        query.dataset.selectedName = option.dataset.tablePickerName;
        query.setCustomValidity("");
        hideResults();
        updateSelection();
      });
    });
    document.addEventListener("click", (event) => {
      if (!search.contains(event.target)) {
        hideResults();
      }
    });
    picker.addEventListener("toggle", () => {
      if (!picker.open) {
        hideResults();
      }
    });
    showForm.addEventListener("submit", (event) => {
      if (!actionInput.value) {
        event.preventDefault();
      }
    });
    updateSelection();
  });

  document.querySelectorAll("[data-table-width-input]").forEach((input) => {
    const tableCard = input.closest(".gm-data-table");
    if (!tableCard) {
      return;
    }
    const refreshDockedLayout = () => {
      tableCard.closest(".gm-data-tables")?.dispatchEvent(
        new Event("gm-refresh-dock"),
      );
    };
    const applyTableWidth = () => {
      const requestedWidth = Number.parseInt(input.value, 10);
      if (!input.value.trim() || !Number.isFinite(requestedWidth)) {
        tableCard.dataset.windowWidth = "";
        const automaticCardWidth = Number.parseInt(
          tableCard.dataset.automaticCardWidth || "320",
          10,
        );
        const automaticEditorWidth = Number.parseInt(
          tableCard.dataset.automaticEditorWidth || "320",
          10,
        );
        tableCard.style.setProperty(
          "--gm-table-card-width",
          `${automaticCardWidth}px`,
        );
        tableCard.style.setProperty(
          "--gm-table-editor-width",
          `${automaticEditorWidth}px`,
        );
        refreshDockedLayout();
        return;
      }
      const boundedWidth = Math.max(320, Math.min(requestedWidth, 6000));
      tableCard.dataset.windowWidth = String(boundedWidth);
      tableCard.style.setProperty(
        "--gm-table-card-width",
        `${boundedWidth}px`,
      );
      tableCard.style.setProperty(
        "--gm-table-editor-width",
        `${boundedWidth}px`,
      );
      refreshDockedLayout();
    };

    input.addEventListener("input", applyTableWidth);
  });

  document.querySelectorAll(".gm-data-table > form").forEach((form) => {
    const saveButton = form.querySelector(
      ".gm-data-table__icon-action--save",
    );
    if (!saveButton) {
      return;
    }
    form.addEventListener("keydown", (event) => {
      if (
        event.key !== "Enter"
        || !event.target.matches("input, select")
        || event.target.disabled
        || event.target.readOnly
      ) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit(saveButton);
      } else {
        saveButton.click();
      }
    });
  });

  document.querySelectorAll("[data-table-markdown-import]").forEach((button) => {
    const form = button.closest("form");
    const payload = form?.querySelector("[data-table-markdown-import-payload]");
    const action = form?.querySelector("[data-table-markdown-import-action]");
    if (!form || !payload || !action) {
      return;
    }

    button.addEventListener("click", async () => {
      if (button.disabled) {
        return;
      }
      button.disabled = true;
      try {
        if (!navigator.clipboard || typeof navigator.clipboard.readText !== "function") {
          throw new Error(
            "Der Browser erlaubt hier keinen direkten Zugriff auf die Zwischenablage.",
          );
        }
        const markdown = await navigator.clipboard.readText();
        if (!markdown.trim()) {
          throw new Error("Die Zwischenablage ist leer.");
        }
        if (!window.confirm(
          "Die vorhandenen Spalten, Zeilen und Zellinhalte durch die Markdown-Tabelle aus der Zwischenablage ersetzen?",
        )) {
          button.disabled = false;
          return;
        }
        if (!form.checkValidity()) {
          form.reportValidity();
          button.disabled = false;
          return;
        }
        payload.value = markdown;
        action.disabled = false;
        if (typeof form.requestSubmit === "function") {
          form.requestSubmit();
        } else {
          form.submit();
        }
      } catch (error) {
        window.alert(
          error instanceof Error
            ? error.message
            : "Die Markdown-Tabelle konnte nicht aus der Zwischenablage gelesen werden.",
        );
        button.disabled = false;
      }
    });
  });

  document.querySelectorAll(".gm-data-table").forEach((tableCard) => {
    const columnWidthInputs = Array.from(
      tableCard.querySelectorAll("[data-table-column-width-input]"),
    );
    const columnGrids = Array.from(
      tableCard.querySelectorAll("[data-table-column-grid]"),
    );
    if (columnWidthInputs.length === 0 || columnGrids.length === 0) {
      return;
    }

    const applyColumnWidths = () => {
      const hasCustomWidths = columnWidthInputs.some(
        (input) => input.value.trim() !== "",
      );
      columnGrids.forEach((grid) => {
        let contentWidth = grid.dataset.tableGridKind === "editor" ? 92 : 0;
        grid.querySelectorAll("col[data-table-column-id]").forEach((column) => {
          const input = columnWidthInputs.find(
            (candidate) => (
              candidate.dataset.tableColumnId === column.dataset.tableColumnId
            ),
          );
          const defaultWidth = Number.parseInt(
            column.dataset.defaultWidth || "140",
            10,
          );
          const requestedWidth = Number.parseInt(input?.value || "", 10);
          let width = input?.value.trim() && Number.isFinite(requestedWidth)
            ? Math.max(60, Math.min(requestedWidth, 1200))
            : defaultWidth;
          if (grid.dataset.tableGridKind === "editor") {
            width = Math.max(width, 180);
          }
          column.style.width = `${width}px`;
          contentWidth += width;
        });
        grid.classList.toggle(
          "gm-data-table__table--custom-widths",
          hasCustomWidths,
        );
        grid.style.setProperty(
          "--gm-table-content-width",
          `${contentWidth}px`,
        );
      });

      const windowWidthInput = tableCard.querySelector(
        "[data-table-width-input]",
      );
      if (windowWidthInput && !windowWidthInput.value.trim()) {
        const previewGrid = columnGrids.find(
          (grid) => grid.dataset.tableGridKind === "preview",
        );
        const editorGrid = columnGrids.find(
          (grid) => grid.dataset.tableGridKind === "editor",
        );
        const previewWidth = Number.parseInt(
          previewGrid?.style.getPropertyValue("--gm-table-content-width")
            || "300",
          10,
        );
        const editorWidth = Number.parseInt(
          editorGrid?.style.getPropertyValue("--gm-table-content-width")
            || "300",
          10,
        );
        // Keep each view aligned with the table it actually displays.  The
        // editor is wider because it includes its row-action column.
        const automaticCardWidth = Math.max(1, previewWidth + 2);
        const automaticEditorWidth = Math.max(1, editorWidth + 2);
        tableCard.dataset.automaticCardWidth = String(automaticCardWidth);
        tableCard.dataset.automaticEditorWidth = String(automaticEditorWidth);
        tableCard.style.setProperty(
          "--gm-table-card-width",
          `${automaticCardWidth}px`,
        );
        tableCard.style.setProperty(
          "--gm-table-editor-width",
          `${automaticEditorWidth}px`,
        );
      }
      tableCard.closest(".gm-data-tables")?.dispatchEvent(
        new Event("gm-refresh-dock"),
      );
    };

    columnWidthInputs.forEach((input) => {
      input.addEventListener("input", applyColumnWidths);
    });
  });

  document.querySelectorAll(".gm-data-table__editor-content").forEach((editor) => {
    const cells = Array.from(
      editor.querySelectorAll("[data-table-editor-cell]"),
    ).sort((first, second) => (
      Number(first.dataset.rowIndex) - Number(second.dataset.rowIndex)
      || Number(first.dataset.columnIndex) - Number(second.dataset.columnIndex)
    ));
    if (cells.length === 0) {
      return;
    }

    const rowCount = Math.max(
      ...cells.map((cell) => Number(cell.dataset.rowIndex)),
    ) + 1;
    const columnCount = Math.max(
      ...cells.map((cell) => Number(cell.dataset.columnIndex)),
    ) + 1;
    const coordinateKey = (rowIndex, columnIndex) => (
      `${rowIndex}:${columnIndex}`
    );
    const boundedSpan = (input, available) => {
      const parsed = Number.parseInt(input?.value || "1", 10);
      const requested = Number.isFinite(parsed) ? parsed : 1;
      return Math.max(1, Math.min(requested, available, 20));
    };

    const applyLiveSpans = () => {
      const occupied = new Set();

      cells.forEach((cell) => {
        cell.hidden = false;
        cell.rowSpan = 1;
        cell.colSpan = 1;
        cell.classList.remove(
          "gm-data-table__cell--covered",
          "gm-data-table__cell--spanned",
        );
        delete cell.dataset.effectiveRowspan;
        delete cell.dataset.effectiveColspan;
      });

      cells.forEach((cell) => {
        const rowIndex = Number(cell.dataset.rowIndex);
        const columnIndex = Number(cell.dataset.columnIndex);
        const rowInput = cell.querySelector("[data-table-rowspan]");
        const columnInput = cell.querySelector("[data-table-colspan]");
        const availableRows = rowCount - rowIndex;
        const availableColumns = columnCount - columnIndex;
        if (rowInput) {
          rowInput.max = String(Math.min(availableRows, 20));
        }
        if (columnInput) {
          columnInput.max = String(Math.min(availableColumns, 20));
        }

        if (occupied.has(coordinateKey(rowIndex, columnIndex))) {
          cell.hidden = true;
          cell.classList.add("gm-data-table__cell--covered");
          return;
        }

        let rowSpan = boundedSpan(rowInput, availableRows);
        let columnSpan = boundedSpan(columnInput, availableColumns);
        const overlapsOccupiedCell = () => {
          for (
            let coveredRow = rowIndex;
            coveredRow < rowIndex + rowSpan;
            coveredRow += 1
          ) {
            for (
              let coveredColumn = columnIndex;
              coveredColumn < columnIndex + columnSpan;
              coveredColumn += 1
            ) {
              if (occupied.has(coordinateKey(coveredRow, coveredColumn))) {
                return true;
              }
            }
          }
          return false;
        };

        while (overlapsOccupiedCell()) {
          if (columnSpan > 1) {
            columnSpan -= 1;
          } else if (rowSpan > 1) {
            rowSpan -= 1;
          } else {
            break;
          }
        }

        cell.rowSpan = rowSpan;
        cell.colSpan = columnSpan;
        cell.classList.toggle(
          "gm-data-table__cell--spanned",
          rowSpan > 1 || columnSpan > 1,
        );
        cell.dataset.effectiveRowspan = String(rowSpan);
        cell.dataset.effectiveColspan = String(columnSpan);

        for (
          let coveredRow = rowIndex;
          coveredRow < rowIndex + rowSpan;
          coveredRow += 1
        ) {
          for (
            let coveredColumn = columnIndex;
            coveredColumn < columnIndex + columnSpan;
            coveredColumn += 1
          ) {
            occupied.add(coordinateKey(coveredRow, coveredColumn));
          }
        }
      });
    };

    const applyCellAlignment = (select) => {
      const cell = select.closest("[data-table-editor-cell]");
      if (!cell) {
        return;
      }
      const alignment = ["left", "center", "right"].includes(select.value)
        ? select.value
        : "left";
      cell.classList.remove(
        "gm-data-table__align--left",
        "gm-data-table__align--center",
        "gm-data-table__align--right",
      );
      cell.classList.add(`gm-data-table__align--${alignment}`);
      cell.dataset.cellAlignment = alignment;
    };

    editor.addEventListener("input", (event) => {
      if (
        event.target.matches("[data-table-rowspan], [data-table-colspan]")
      ) {
        applyLiveSpans();
      }
    });
    editor.addEventListener("change", (event) => {
      if (event.target.matches("[data-table-alignment]")) {
        applyCellAlignment(event.target);
        return;
      }
      if (
        !event.target.matches("[data-table-rowspan], [data-table-colspan]")
      ) {
        return;
      }
      const maximum = Number.parseInt(event.target.max || "20", 10);
      event.target.value = String(boundedSpan(event.target, maximum));
      applyLiveSpans();
    });
    editor.querySelectorAll("[data-table-alignment]").forEach(
      applyCellAlignment,
    );
    applyLiveSpans();
  });

  let floatingTableZIndex = 1150;
  document.querySelectorAll("[data-table-layout-url]").forEach((card) => {
    const container = card.closest("[data-card-reorder-url]");
    const header = card.querySelector(".gm-data-table__header");
    const detachButton = card.querySelector("[data-table-detach-toggle]");
    const layoutUrl = card.dataset.tableLayoutUrl;
    const csrfToken = container?.dataset.csrfToken;
    let activePointerId = null;
    let dragStartX = 0;
    let dragStartY = 0;
    let dragStartLeft = 0;
    let dragStartTop = 0;
    let freeDragMoved = false;

    if (!header || !detachButton || !layoutUrl || !csrfToken) {
      return;
    }

    const readPixel = (value) => {
      const parsed = Number.parseFloat(value);
      return Number.isFinite(parsed) ? parsed : 24;
    };
    const currentPosition = () => ({
      x: Math.round(readPixel(card.style.left)),
      y: Math.round(readPixel(card.style.top)),
    });
    const bringToFront = () => {
      floatingTableZIndex += 1;
      card.style.zIndex = String(floatingTableZIndex);
    };
    const applyFloatingHeightLimit = () => {
      const screenHeader = document.querySelector(".gm-screen__header");
      const inventoryPanel = inventoryArea?.querySelector(".sl-inventory");
      const headerRect = screenHeader?.getBoundingClientRect();
      const inventoryPanelRect = inventoryPanel?.getBoundingClientRect();
      const inventoryAreaRect = inventoryArea?.getBoundingClientRect();
      const inventoryBottom = inventoryPanelRect?.height
        ? inventoryPanelRect.bottom
        : inventoryAreaRect?.bottom;
      if (!headerRect || !Number.isFinite(inventoryBottom)) {
        card.style.removeProperty("--gm-table-floating-max-height");
        return;
      }
      const availableHeight = Math.max(
        1,
        Math.floor(inventoryBottom - headerRect.bottom),
      );
      card.style.setProperty(
        "--gm-table-floating-max-height",
        `${availableHeight}px`,
      );
    };
    const clampFloatingPosition = (left, top) => {
      if (!card.classList.contains("gm-data-table--detached")) {
        return currentPosition();
      }
      applyFloatingHeightLimit();
      const margin = 8;
      const rect = card.getBoundingClientRect();
      const maxLeft = Math.max(margin, window.innerWidth - rect.width - margin);
      const maxTop = Math.max(margin, window.innerHeight - rect.height - margin);
      const x = Math.round(Math.min(Math.max(left, margin), maxLeft));
      const y = Math.round(Math.min(Math.max(top, margin), maxTop));
      card.style.left = `${x}px`;
      card.style.top = `${y}px`;
      return { x, y };
    };
    const persistLayout = async () => {
      const position = currentPosition();
      const body = new URLSearchParams({
        is_detached: card.classList.contains("gm-data-table--detached") ? "1" : "0",
        is_stacked: card.classList.contains("gm-data-table--stacked") ? "1" : "0",
        x: String(position.x),
        y: String(position.y),
        csrfmiddlewaretoken: csrfToken,
      });
      try {
        const response = await fetch(layoutUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-CSRFToken": csrfToken,
            "X-Requested-With": "XMLHttpRequest",
          },
          body: body.toString(),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
          throw new Error(result.error || "Tabellenlayout konnte nicht gespeichert werden.");
        }
      } catch (error) {
        window.alert("Die Position der Tabelle konnte nicht gespeichert werden.");
      }
    };

    detachButton.addEventListener("click", () => {
      const willDetach = !card.classList.contains("gm-data-table--detached");
      if (willDetach) {
        const dockedRect = card.getBoundingClientRect();
        card.classList.add("gm-data-table--detached");
        bringToFront();
        clampFloatingPosition(dockedRect.left, dockedRect.top);
      } else {
        card.classList.remove("gm-data-table--detached");
        card.style.removeProperty("z-index");
      }
      detachButton.setAttribute("aria-pressed", String(willDetach));
      detachButton.title = willDetach
        ? "Tabelle andocken"
        : "Tabelle loslösen";
      header.draggable = !willDetach;
      persistLayout();
    });

    header.addEventListener("pointerdown", (event) => {
      if (!card.classList.contains("gm-data-table--detached")) {
        return;
      }
      bringToFront();
      if (
        event.button !== 0
        || event.target.closest("button, input, select, textarea, label, a, [contenteditable='true']")
      ) {
        return;
      }
      const position = currentPosition();
      activePointerId = event.pointerId;
      dragStartX = event.clientX;
      dragStartY = event.clientY;
      dragStartLeft = position.x;
      dragStartTop = position.y;
      freeDragMoved = false;
      card.classList.add("is-free-dragging");
      header.setPointerCapture(event.pointerId);
      event.preventDefault();
    });

    header.addEventListener("pointermove", (event) => {
      if (event.pointerId !== activePointerId) {
        return;
      }
      const deltaX = event.clientX - dragStartX;
      const deltaY = event.clientY - dragStartY;
      freeDragMoved = (
        freeDragMoved
        || Math.abs(deltaX) > 2
        || Math.abs(deltaY) > 2
      );
      clampFloatingPosition(
        dragStartLeft + deltaX,
        dragStartTop + deltaY,
      );
      event.preventDefault();
    });

    const finishFreeDrag = (event) => {
      if (event.pointerId !== activePointerId) {
        return;
      }
      if (header.hasPointerCapture(event.pointerId)) {
        header.releasePointerCapture(event.pointerId);
      }
      activePointerId = null;
      card.classList.remove("is-free-dragging");
      if (freeDragMoved) {
        persistLayout();
      }
    };

    header.addEventListener("pointerup", finishFreeDrag);
    header.addEventListener("pointercancel", finishFreeDrag);
    window.addEventListener("resize", () => {
      if (!card.classList.contains("gm-data-table--detached")) {
        return;
      }
      const position = currentPosition();
      clampFloatingPosition(position.x, position.y);
    }, { passive: true });

    if (card.classList.contains("gm-data-table--detached")) {
      window.requestAnimationFrame(() => {
        bringToFront();
        const position = currentPosition();
        clampFloatingPosition(position.x, position.y);
      });
    }
  });

  document.querySelectorAll("[data-note-layout-url]").forEach((card) => {
    const container = card.closest("[data-card-reorder-url]");
    const header = card.querySelector(".gm-note-card__header");
    const status = card.querySelector("[data-note-status]");
    const widthButton = card.querySelector("[data-note-width-toggle]");
    const detachButton = card.querySelector("[data-note-detach-toggle]");
    const layoutUrl = card.dataset.noteLayoutUrl;
    const csrfToken = container?.dataset.csrfToken;
    let activePointerId = null;
    let dragStartX = 0;
    let dragStartY = 0;
    let dragStartLeft = 0;
    let dragStartTop = 0;
    let freeDragMoved = false;
    let layoutSaveVersion = 0;

    if (!widthButton && !detachButton) {
      return;
    }

    const readPixel = (value) => {
      const parsed = Number.parseFloat(value);
      return Number.isFinite(parsed) ? parsed : 24;
    };

    const currentPosition = () => ({
      x: Math.round(readPixel(card.style.left)),
      y: Math.round(readPixel(card.style.top)),
    });

    const setLayoutStatus = (text, state = "") => {
      if (!status) {
        return;
      }
      status.textContent = text;
      status.classList.toggle("is-saving", state === "saving");
      status.classList.toggle("is-error", state === "error");
    };

    const clampFloatingPosition = (left, top) => {
      if (!card.classList.contains("gm-note-card--detached")) {
        return currentPosition();
      }
      const margin = 8;
      const rect = card.getBoundingClientRect();
      const maxLeft = Math.max(margin, window.innerWidth - rect.width - margin);
      const maxTop = Math.max(margin, window.innerHeight - rect.height - margin);
      const x = Math.round(Math.min(Math.max(left, margin), maxLeft));
      const y = Math.round(Math.min(Math.max(top, margin), maxTop));
      card.style.left = `${x}px`;
      card.style.top = `${y}px`;
      return { x, y };
    };

    const persistLayout = async () => {
      if (!layoutUrl || !csrfToken) {
        return;
      }
      const version = ++layoutSaveVersion;
      const position = currentPosition();
      const body = new URLSearchParams({
        note_is_wide: card.classList.contains("gm-note-card--wide") ? "1" : "0",
        note_is_detached: card.classList.contains("gm-note-card--detached") ? "1" : "0",
        note_x: String(position.x),
        note_y: String(position.y),
        csrfmiddlewaretoken: csrfToken,
      });
      setLayoutStatus("Speichert ...", "saving");

      try {
        const response = await fetch(layoutUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-CSRFToken": csrfToken,
            "X-Requested-With": "XMLHttpRequest",
          },
          body: body.toString(),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
          throw new Error(result.error || "Notizlayout konnte nicht gespeichert werden.");
        }
        if (version === layoutSaveVersion) {
          setLayoutStatus("Gespeichert");
        }
      } catch (error) {
        if (version === layoutSaveVersion) {
          setLayoutStatus("Speicherfehler", "error");
        }
      }
    };

    widthButton?.addEventListener("click", () => {
      const isWide = !card.classList.contains("gm-note-card--wide");
      card.classList.toggle("gm-note-card--wide", isWide);
      widthButton.setAttribute("aria-pressed", String(isWide));
      if (card.classList.contains("gm-note-card--detached")) {
        const position = currentPosition();
        clampFloatingPosition(position.x, position.y);
      }
      persistLayout();
    });

    detachButton?.addEventListener("click", () => {
      const willDetach = !card.classList.contains("gm-note-card--detached");
      if (willDetach) {
        const dockedRect = card.getBoundingClientRect();
        card.classList.add("gm-note-card--detached");
        clampFloatingPosition(dockedRect.left, dockedRect.top);
      } else {
        card.classList.remove("gm-note-card--detached");
      }
      detachButton.setAttribute("aria-pressed", String(willDetach));
      detachButton.title = willDetach
        ? "Notizzettel andocken"
        : "Notizzettel loslösen";
      if (header) {
        header.draggable = !willDetach;
      }
      persistLayout();
    });

    header?.addEventListener("pointerdown", (event) => {
      if (
        !card.classList.contains("gm-note-card--detached")
        || event.button !== 0
        || event.target.closest("button, input, select, textarea, label, a, [contenteditable='true']")
      ) {
        return;
      }
      const position = currentPosition();
      activePointerId = event.pointerId;
      dragStartX = event.clientX;
      dragStartY = event.clientY;
      dragStartLeft = position.x;
      dragStartTop = position.y;
      freeDragMoved = false;
      card.classList.add("is-free-dragging");
      header.setPointerCapture(event.pointerId);
      event.preventDefault();
    });

    header?.addEventListener("pointermove", (event) => {
      if (event.pointerId !== activePointerId) {
        return;
      }
      const deltaX = event.clientX - dragStartX;
      const deltaY = event.clientY - dragStartY;
      freeDragMoved = freeDragMoved || Math.abs(deltaX) > 2 || Math.abs(deltaY) > 2;
      clampFloatingPosition(
        dragStartLeft + deltaX,
        dragStartTop + deltaY,
      );
      event.preventDefault();
    });

    const finishFreeDrag = (event) => {
      if (event.pointerId !== activePointerId) {
        return;
      }
      if (header.hasPointerCapture(event.pointerId)) {
        header.releasePointerCapture(event.pointerId);
      }
      activePointerId = null;
      card.classList.remove("is-free-dragging");
      if (freeDragMoved) {
        persistLayout();
      }
    };

    header?.addEventListener("pointerup", finishFreeDrag);
    header?.addEventListener("pointercancel", finishFreeDrag);
    window.addEventListener("resize", () => {
      if (!card.classList.contains("gm-note-card--detached")) {
        return;
      }
      const position = currentPosition();
      clampFloatingPosition(position.x, position.y);
    }, { passive: true });

    if (card.classList.contains("gm-note-card--detached")) {
      window.requestAnimationFrame(() => {
        const position = currentPosition();
        clampFloatingPosition(position.x, position.y);
      });
    }
  });

  document.querySelectorAll("[data-note-editor]").forEach((editor) => {
    const card = editor.closest(".gm-note-card");
    const container = editor.closest("[data-card-reorder-url]");
    const status = card?.querySelector("[data-note-status]");
    const saveUrl = editor.dataset.noteSaveUrl;
    const csrfToken = container?.dataset.csrfToken;
    let saveTimer = null;
    let saveVersion = 0;
    let lastSavedHTML = editor.innerHTML;
    let savedSelectionRange = null;

    const setStatus = (text, state = "") => {
      if (!status) {
        return;
      }
      status.textContent = text;
      status.classList.toggle("is-saving", state === "saving");
      status.classList.toggle("is-error", state === "error");
    };

    const saveNote = async (keepalive = false) => {
      window.clearTimeout(saveTimer);
      const noteHTML = editor.innerHTML;
      if (!saveUrl || !csrfToken || noteHTML === lastSavedHTML) {
        if (noteHTML === lastSavedHTML) {
          setStatus("Gespeichert");
        }
        return;
      }

      const version = ++saveVersion;
      const body = new URLSearchParams({
        note_html: noteHTML,
        csrfmiddlewaretoken: csrfToken,
      });
      setStatus("Speichert …", "saving");

      try {
        const response = await fetch(saveUrl, {
          method: "POST",
          credentials: "same-origin",
          keepalive,
          headers: {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-CSRFToken": csrfToken,
            "X-Requested-With": "XMLHttpRequest",
          },
          body: body.toString(),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
          throw new Error(result.error || "Notiz konnte nicht gespeichert werden.");
        }
        if (version === saveVersion) {
          lastSavedHTML = noteHTML;
          setStatus(
            editor.innerHTML === noteHTML ? "Gespeichert" : "Ungespeichert",
          );
        }
      } catch (error) {
        if (version === saveVersion) {
          setStatus("Speicherfehler", "error");
        }
      }
    };

    const scheduleSave = () => {
      setStatus("Ungespeichert");
      window.clearTimeout(saveTimer);
      saveTimer = window.setTimeout(() => saveNote(), 450);
    };

    const rememberSelection = () => {
      const selection = window.getSelection();
      if (
        !selection
        || selection.rangeCount === 0
        || !editor.contains(selection.anchorNode)
        || !editor.contains(selection.focusNode)
      ) {
        return;
      }
      savedSelectionRange = selection.getRangeAt(0).cloneRange();
    };

    const restoreSelection = () => {
      if (!savedSelectionRange) {
        return false;
      }
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(savedSelectionRange);
      return true;
    };

    const removeSelectedFormatting = () => {
      const selection = window.getSelection();
      if (!selection || selection.rangeCount === 0) {
        return;
      }

      let range = selection.getRangeAt(0);
      const anchorElement = (
        selection.anchorNode?.nodeType === Node.ELEMENT_NODE
          ? selection.anchorNode
          : selection.anchorNode?.parentElement
      );
      const selectedBlock = anchorElement?.closest(
        "p, h1, h2, h3, blockquote, li, div",
      );

      if (
        range.collapsed
        && selectedBlock
        && selectedBlock !== editor
        && editor.contains(selectedBlock)
      ) {
        range = document.createRange();
        range.selectNodeContents(selectedBlock);
        selection.removeAllRanges();
        selection.addRange(range);
      }

      const selectedList = anchorElement?.closest("ul, ol");
      if (selectedList && editor.contains(selectedList)) {
        document.execCommand(
          selectedList.tagName === "OL"
            ? "insertOrderedList"
            : "insertUnorderedList",
          false,
          null,
        );
      }
      document.execCommand("removeFormat", false, null);
      document.execCommand("unlink", false, null);
      document.execCommand("formatBlock", false, "p");
    };

    editor.addEventListener("input", scheduleSave);
    editor.addEventListener("blur", () => saveNote());
    editor.addEventListener("keyup", rememberSelection);
    editor.addEventListener("pointerup", rememberSelection);
    document.addEventListener("selectionchange", rememberSelection);
    window.addEventListener("pagehide", () => saveNote(true));

    card?.querySelectorAll("[data-note-command]").forEach((button) => {
      button.addEventListener("pointerdown", (event) => {
        rememberSelection();
        event.preventDefault();
      });
      button.addEventListener("click", () => {
        editor.focus();
        restoreSelection();
        if (button.dataset.noteCommand === "removeFormat") {
          removeSelectedFormatting();
        } else {
          document.execCommand(
            button.dataset.noteCommand,
            false,
            button.dataset.noteValue || null,
          );
        }
        rememberSelection();
        scheduleSave();
      });
    });
  });

  const setupCardReorder = (container) => {
    const isTableContainer = container.classList.contains("gm-data-tables");
    const cards = () => Array.from(
      container.querySelectorAll("[data-reorder-card][data-reorder-id]"),
    );
    cards()
      .sort((first, second) => (
        Number(first.dataset.sortPosition || 0)
        - Number(second.dataset.sortPosition || 0)
      ))
      .forEach((card) => container.append(card));

    const refreshDockedRows = () => {
      if (!isTableContainer) {
        return;
      }
      const dockedCards = cards().filter(
        (card) => !card.classList.contains("gm-data-table--detached"),
      );
      // Keep docked stack widths in place while measuring the next layout.
      // Clearing them first forces a visible shrink-and-grow cycle.
      cards()
        .filter((card) => card.classList.contains("gm-data-table--detached"))
        .forEach((card) => {
          card.classList.remove("gm-data-table--stack-group");
          card.style.removeProperty("--gm-dock-shared-card-width");
          card.style.removeProperty("--gm-dock-shared-table-width");
        });
      let column = 0;
      let currentGroup = [];
      const groups = [];
      dockedCards.forEach((card) => {
        const wantsStack = (
          card.classList.contains("gm-data-table--stacked")
          && card.classList.contains("gm-data-table")
          && !card.classList.contains("gm-note-card")
          && column > 0
          && currentGroup.length < 2
        );
        if (wantsStack) {
          card.style.gridColumn = String(column);
          card.style.gridRow = "2";
          currentGroup.push(card);
          return;
        }
        if (card.classList.contains("gm-data-table--stacked")) {
          card.classList.remove("gm-data-table--stacked");
        }
        column += 1;
        card.style.gridColumn = String(column);
        card.style.gridRow = "1";
        currentGroup = [card];
        groups.push(currentGroup);
      });
      groups.forEach((group) => {
        const sharedCardWidth = Math.max(
          ...group.map((card) => {
            const manualWidth = Number.parseInt(card.dataset.windowWidth || "", 10);
            if (Number.isFinite(manualWidth)) {
              return manualWidth;
            }
            const editorOpen = Boolean(
              card.querySelector(".gm-data-table__editor[open]"),
            );
            const automaticWidth = Number.parseInt(
              card.dataset[
                editorOpen ? "automaticEditorWidth" : "automaticCardWidth"
              ] || "",
              10,
            );
            if (Number.isFinite(automaticWidth)) {
              return automaticWidth;
            }
            const parsed = Number.parseFloat(window.getComputedStyle(card).width);
            return Number.isFinite(parsed) ? parsed : 320;
          }),
        );
        const sharedTableWidth = Math.max(1, sharedCardWidth - 2);
        group.forEach((card) => {
          const isStackedGroup = group.length > 1;
          card.classList.toggle("gm-data-table--stack-group", isStackedGroup);
          if (isStackedGroup) {
            card.style.setProperty(
              "--gm-dock-shared-card-width",
              `${sharedCardWidth}px`,
            );
            card.style.setProperty(
              "--gm-dock-shared-table-width",
              `${sharedTableWidth}px`,
            );
          } else {
            card.style.removeProperty("--gm-dock-shared-card-width");
            card.style.removeProperty("--gm-dock-shared-table-width");
          }
        });
      });
      const hasStackedRows = groups.some((group) => group.length > 1);
      if (hasStackedRows) {
        groups.forEach((group) => {
          if (group.length === 1) {
            group[0].style.gridRow = "1 / span 2";
          }
        });
      }
      container.style.setProperty(
        "--gm-dock-column-count",
        String(Math.max(1, column)),
      );
      container.classList.toggle(
        "gm-data-tables--has-stacked",
        dockedCards.some((card) => card.classList.contains("gm-data-table--stacked")),
      );
    };
    container.addEventListener("gm-refresh-dock", refreshDockedRows);
    container.querySelectorAll(".gm-data-table__editor").forEach((editor) => {
      editor.addEventListener("toggle", refreshDockedRows);
    });
    refreshDockedRows();

    const dragSurfaces = container.querySelectorAll("[data-drag-surface]");
    let draggedCard = null;
    let originalOrder = [];
    let originalStackStates = new Map();
    let dropAccepted = false;
    let dragBlocked = false;
    let stackDropTarget = null;
    let pendingDropTarget = null;
    let pendingDropAfter = false;
    let pendingDropStack = false;
    let pendingDropUnstack = false;

    const restoreOrder = (cardOrder) => {
      cardOrder.forEach((card) => container.append(card));
      refreshDockedRows();
    };

    const stackGroupFor = (card) => {
      const orderedCards = cards();
      const index = orderedCards.indexOf(card);
      if (index < 0) {
        return [];
      }
      let anchorIndex = index;
      while (
        anchorIndex > 0
        && orderedCards[anchorIndex].classList.contains("gm-data-table--stacked")
      ) {
        anchorIndex -= 1;
      }
      const group = [orderedCards[anchorIndex]];
      for (
        let nextIndex = anchorIndex + 1;
        nextIndex < orderedCards.length;
        nextIndex += 1
      ) {
        if (!orderedCards[nextIndex].classList.contains("gm-data-table--stacked")) {
          break;
        }
        group.push(orderedCards[nextIndex]);
      }
      return group;
    };

    const persistDockLayout = async (card) => {
      const csrfToken = container.dataset.csrfToken;
      const layoutUrl = card.dataset.tableLayoutUrl;
      if (!csrfToken || !layoutUrl || !card.classList.contains("gm-data-table")) {
        return;
      }
      const body = new URLSearchParams({
        is_detached: card.classList.contains("gm-data-table--detached") ? "1" : "0",
        is_stacked: card.classList.contains("gm-data-table--stacked") ? "1" : "0",
        csrfmiddlewaretoken: csrfToken,
      });
      try {
        const response = await fetch(layoutUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-CSRFToken": csrfToken,
            "X-Requested-With": "XMLHttpRequest",
          },
          body: body.toString(),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
          throw new Error(result.error || "Tabellenposition konnte nicht gespeichert werden.");
        }
      } catch (error) {
        window.alert("Die Tabellenposition konnte nicht gespeichert werden.");
      }
    };

    const persistOrder = async (fallbackOrder) => {
      const csrfToken = container.dataset.csrfToken;
      if (!csrfToken) {
        restoreOrder(fallbackOrder);
        return;
      }

      const body = new URLSearchParams();
      cards().forEach((card) => body.append("ordered_ids", card.dataset.reorderId));
      body.append("csrfmiddlewaretoken", csrfToken);
      container.classList.add("is-reorder-saving");

      try {
        const response = await fetch(container.dataset.cardReorderUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-CSRFToken": csrfToken,
            "X-Requested-With": "XMLHttpRequest",
          },
          body: body.toString(),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
          throw new Error(result.error || "Reihenfolge konnte nicht gespeichert werden.");
        }
      } catch (error) {
        restoreOrder(fallbackOrder);
        window.alert("Die Kartenreihenfolge konnte nicht gespeichert werden.");
      } finally {
        container.classList.remove("is-reorder-saving");
      }
    };

    dragSurfaces.forEach((surface) => {
      surface.addEventListener("pointerdown", (event) => {
        dragBlocked = Boolean(
          event.target.closest("button, input, select, textarea, label, a, [contenteditable='true']"),
        );
      });

      surface.addEventListener("dragstart", (event) => {
        if (dragBlocked || container.classList.contains("is-reorder-saving")) {
          event.preventDefault();
          return;
        }
        draggedCard = surface.closest("[data-reorder-card]");
        if (
          !draggedCard
          || draggedCard.classList.contains("gm-note-card--detached")
          || draggedCard.classList.contains("gm-data-table--detached")
          || !event.dataTransfer
        ) {
          draggedCard = null;
          event.preventDefault();
          return;
        }
        originalOrder = cards();
        originalStackStates = new Map(
          originalOrder.map((card) => [
            card,
            card.classList.contains("gm-data-table--stacked"),
          ]),
        );
        dropAccepted = false;
        pendingDropTarget = null;
        pendingDropAfter = false;
        pendingDropStack = false;
        pendingDropUnstack = false;
        draggedCard.classList.add("is-dragging");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", draggedCard.dataset.reorderId);
      });

      surface.addEventListener("dragend", () => {
        if (draggedCard && !dropAccepted) {
          restoreOrder(originalOrder);
          originalStackStates.forEach((isStacked, card) => {
            card.classList.toggle("gm-data-table--stacked", isStacked);
          });
          refreshDockedRows();
        }
        cards().forEach((card) => card.classList.remove("is-stack-drop-target"));
        draggedCard?.classList.remove("is-dragging");
        draggedCard = null;
        originalOrder = [];
        originalStackStates = new Map();
        dropAccepted = false;
        dragBlocked = false;
        stackDropTarget = null;
        pendingDropTarget = null;
        pendingDropAfter = false;
        pendingDropStack = false;
        pendingDropUnstack = false;
      });
    });

    container.addEventListener("dragover", (event) => {
      if (!draggedCard) {
        return;
      }
      event.preventDefault();
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = "move";
      }

      const containerRect = container.getBoundingClientRect();
      const edgeSize = 48;
      if (event.clientX < containerRect.left + edgeSize) {
        container.scrollLeft -= 18;
      } else if (event.clientX > containerRect.right - edgeSize) {
        container.scrollLeft += 18;
      }

      const targetCard = event.target.closest("[data-reorder-card]");
      if (!targetCard || targetCard === draggedCard) {
        if (isTableContainer) {
          pendingDropTarget = null;
          pendingDropAfter = false;
          pendingDropStack = false;
          pendingDropUnstack = draggedCard.classList.contains("gm-data-table");
          stackDropTarget = null;
          cards().forEach((card) => card.classList.remove("is-stack-drop-target"));
        }
        return;
      }
      const targetRect = targetCard.getBoundingClientRect();
      const canStack = (
        draggedCard.classList.contains("gm-data-table")
        && !draggedCard.classList.contains("gm-note-card")
        && targetCard.classList.contains("gm-data-table")
        && !targetCard.classList.contains("gm-note-card")
        && !targetCard.classList.contains("gm-data-table--detached")
        && event.clientY > targetRect.top + (targetRect.height * 0.58)
        && stackGroupFor(targetCard).length < 2
      );
      cards().forEach((card) => card.classList.remove("is-stack-drop-target"));
      stackDropTarget = canStack ? targetCard : null;
      if (isTableContainer) {
        pendingDropTarget = targetCard;
        pendingDropAfter = canStack || event.clientX > targetRect.left + (targetRect.width / 2);
        pendingDropStack = canStack;
        pendingDropUnstack = false;
        if (canStack) {
          targetCard.classList.add("is-stack-drop-target");
        }
        return;
      }
      if (canStack) {
        draggedCard.classList.add("gm-data-table--stacked");
        targetCard.classList.add("is-stack-drop-target");
      } else {
        draggedCard.classList.remove("gm-data-table--stacked");
      }
      const insertAfter = canStack || event.clientX > targetRect.left + (targetRect.width / 2);
      container.insertBefore(
        draggedCard,
        insertAfter ? targetCard.nextSibling : targetCard,
      );
      refreshDockedRows();
    });

    container.addEventListener("drop", (event) => {
      if (!draggedCard) {
        return;
      }
      event.preventDefault();
      if (isTableContainer) {
        if (!pendingDropTarget) {
          if (!pendingDropUnstack) {
            dropAccepted = false;
            return;
          }
          const orderedCards = cards();
          const draggedIndex = orderedCards.indexOf(draggedCard);
          draggedCard.classList.remove("gm-data-table--stacked");
          // If the dragged card was the upper card, also release the first
          // card that followed it in the same stack.
          const followingCard = orderedCards[draggedIndex + 1];
          if (
            followingCard
            && followingCard.classList.contains("gm-data-table--stacked")
          ) {
            followingCard.classList.remove("gm-data-table--stacked");
          }
          refreshDockedRows();
          window.requestAnimationFrame(refreshDockedRows);
        } else {
          draggedCard.classList.toggle("gm-data-table--stacked", pendingDropStack);
          container.insertBefore(
            draggedCard,
            pendingDropAfter ? pendingDropTarget.nextSibling : pendingDropTarget,
          );
          refreshDockedRows();
          window.requestAnimationFrame(refreshDockedRows);
        }
      }
      dropAccepted = true;
      const droppedCard = draggedCard;
      persistOrder([...originalOrder]);
      cards().forEach((card) => {
        if (
          originalStackStates.has(card)
          && originalStackStates.get(card)
            !== card.classList.contains("gm-data-table--stacked")
        ) {
          persistDockLayout(card);
        }
      });
      if (!originalStackStates.has(droppedCard)) {
        persistDockLayout(droppedCard);
      }
    });
  };

  document.querySelectorAll("[data-card-reorder-url]").forEach(setupCardReorder);
})();
