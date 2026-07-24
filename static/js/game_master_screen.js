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
    const options = Array.from(
      results?.querySelectorAll("button[data-creature-ref]") || [],
    );
    const empty = results?.querySelector("[data-creature-search-empty]");
    if (!query || !selectedId || !results) {
      return;
    }

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
    document.addEventListener("click", (event) => {
      if (!picker.contains(event.target)) {
        results.hidden = true;
      }
    });
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

  document.querySelectorAll(".gm-table-picker").forEach((picker) => {
    const reopenKey = `gm-table-picker-open:${window.location.pathname}`;
    try {
      if (window.sessionStorage.getItem(reopenKey) === "1") {
        picker.open = true;
        window.sessionStorage.removeItem(reopenKey);
      }
    } catch (error) {
      // The picker also works when browser storage is unavailable.
    }

    picker.querySelectorAll("form").forEach((form) => {
      form.addEventListener("submit", () => {
        try {
          window.sessionStorage.setItem(reopenKey, "1");
        } catch (error) {
          // A blocked storage API must not block the form submission.
        }
      });
    });

    const showForm = picker.querySelector("[data-table-picker-show]");
    const select = picker.querySelector("[data-table-picker-select]");
    const submit = picker.querySelector("[data-table-picker-submit]");

    if (!showForm || !select || !submit) {
      return;
    }

    const updateSelection = () => {
      const action = select.value;
      submit.disabled = !action;
      if (action) {
        showForm.action = action;
      } else {
        showForm.removeAttribute("action");
      }
    };

    select.addEventListener("change", updateSelection);
    showForm.addEventListener("submit", (event) => {
      if (!select.value) {
        event.preventDefault();
      }
    });
    updateSelection();
  });

  document.querySelectorAll(".gm-data-table__editor").forEach((editor) => {
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
        || event.target.closest("button, input, select, textarea, a, [contenteditable='true']")
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
    const cards = () => Array.from(
      container.querySelectorAll("[data-reorder-card][data-reorder-id]"),
    );
    cards()
      .sort((first, second) => (
        Number(first.dataset.sortPosition || 0)
        - Number(second.dataset.sortPosition || 0)
      ))
      .forEach((card) => container.append(card));

    const dragSurfaces = container.querySelectorAll("[data-drag-surface]");
    let draggedCard = null;
    let originalOrder = [];
    let dropAccepted = false;
    let dragBlocked = false;

    const restoreOrder = (cardOrder) => {
      cardOrder.forEach((card) => container.append(card));
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
          event.target.closest("button, input, select, textarea, a, [contenteditable='true']"),
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
          || !event.dataTransfer
        ) {
          draggedCard = null;
          event.preventDefault();
          return;
        }
        originalOrder = cards();
        dropAccepted = false;
        draggedCard.classList.add("is-dragging");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", draggedCard.dataset.reorderId);
      });

      surface.addEventListener("dragend", () => {
        if (draggedCard && !dropAccepted) {
          restoreOrder(originalOrder);
        }
        draggedCard?.classList.remove("is-dragging");
        draggedCard = null;
        originalOrder = [];
        dropAccepted = false;
        dragBlocked = false;
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
        return;
      }
      const targetRect = targetCard.getBoundingClientRect();
      const insertAfter = event.clientX > targetRect.left + (targetRect.width / 2);
      container.insertBefore(
        draggedCard,
        insertAfter ? targetCard.nextSibling : targetCard,
      );
    });

    container.addEventListener("drop", (event) => {
      if (!draggedCard) {
        return;
      }
      event.preventDefault();
      dropAccepted = true;
      persistOrder([...originalOrder]);
    });
  };

  document.querySelectorAll("[data-card-reorder-url]").forEach(setupCardReorder);
})();
