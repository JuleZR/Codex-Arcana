export function createChoiceModalController({ hiddenInputContainer, windowController = null }) {
  const learningForm = hiddenInputContainer?.closest("form") || null;
  const modalWindow = document.getElementById("learnChoiceWindow");
  const titleEl = document.getElementById("learnChoiceWindowTitle");
  const introEl = document.getElementById("learnChoiceWindowIntro");
  const navListEl = document.getElementById("learnChoiceDecisionList");
  const panelListEl = document.getElementById("learnChoicePanelList");
  const formEl = document.getElementById("learnChoiceForm");
  const hintEl = document.getElementById("learnChoiceHint");
  const confirmBtn = document.getElementById("learnChoiceConfirmBtn");
  const cancelBtn = document.getElementById("learnChoiceCancelBtn");
  if (
    !hiddenInputContainer
    || !modalWindow
    || !titleEl
    || !navListEl
    || !panelListEl
    || !formEl
    || !hintEl
    || !confirmBtn
  ) {
    return null;
  }

  let activeDecisionId = "";

  // Explicit selection tracker — decisionId → optionId.
  // Stays up-to-date even when sections are hidden so that grouping
  // never relies on querying :checked inside display:none elements.
  const selectionTracker = new Map();

  const closeModal = () => {
    if (windowController) {
      windowController.close();
      return;
    }
    modalWindow.classList.remove("is-open");
    modalWindow.setAttribute("aria-hidden", "true");
  };

  const openModal = () => {
    if (windowController) {
      windowController.open();
      return;
    }
    modalWindow.classList.add("is-open");
    modalWindow.setAttribute("aria-hidden", "false");
  };

  const getSections = () => Array.from(panelListEl.querySelectorAll("[data-choice-decision-id]"));
  const getNavItems = () => Array.from(navListEl.querySelectorAll("[data-choice-nav-id]"));
  const getDecisionId = (section) => section.dataset.choiceDecisionId || "";
  const getDecisionInputs = (decisionId) => Array.from(hiddenInputContainer.querySelectorAll(`input[data-choice-decision-id="${decisionId}"]`));
  const getSelectionGroupId = (section) => section.dataset.choiceSelectionGroup || "";
  const getInputType = (section) => section.dataset.choiceInputType || "options";
  const getDecisionTitle = (section) => section.dataset.choiceTitle || "Ausstehende Entscheidung";
  const getSectionOptionInputs = (section) => Array.from(section.querySelectorAll("input[type='radio']"));
  const getNavItemByDecisionId = (decisionId) => navListEl.querySelector(`[data-choice-nav-id="${decisionId}"]`);
  const getPanelSummaryEl = (section) => section.querySelector("[data-choice-panel-summary]");
  const getPanelStateEl = (section) => section.querySelector("[data-choice-panel-state]");

  const clearDecisionInputs = (decisionId) => {
    getDecisionInputs(decisionId).forEach((input) => {
      input.remove();
    });
    selectionTracker.delete(decisionId);
  };

  const setHint = (text = "") => {
    hintEl.textContent = text;
    hintEl.hidden = !text;
  };

  const normalizeSearchText = (value) => String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");

  const getSelectedRadio = (section) => section.querySelector("input[type='radio']:checked");
  const getSelectedOptionId = (section) => {
    const selected = getSelectedRadio(section);
    if (!(selected instanceof HTMLInputElement)) {
      return "";
    }
    return selected.dataset.choiceOptionId || selected.value || "";
  };

  const isActionableSection = (section) => getInputType(section) !== "unsupported";
  const isSectionResolvedByHidden = (section) => {
    const inputs = getDecisionInputs(getDecisionId(section));
    if (!inputs.length) {
      return false;
    }
    if (getInputType(section) === "text") {
      return Boolean(String(inputs[0].value || "").trim());
    }
    return true;
  };

  const isSectionResolved = (section) => {
    const inputType = getInputType(section);
    if (inputType === "unsupported") {
      return false;
    }
    if (inputType === "text") {
      const input = section.querySelector("[data-choice-text-input]");
      return input instanceof HTMLInputElement
        ? Boolean(String(input.value || "").trim())
        : isSectionResolvedByHidden(section);
    }
    return Boolean(getSelectedRadio(section)) || isSectionResolvedByHidden(section);
  };

  const getSelectionLabel = (section) => {
    if (getInputType(section) === "text") {
      const input = section.querySelector("[data-choice-text-input]");
      const value = input instanceof HTMLInputElement ? String(input.value || "").trim() : "";
      return value || "";
    }
    const selected = getSelectedRadio(section);
    if (!(selected instanceof HTMLInputElement)) {
      return "";
    }
    const option = selected.closest(".learn_choice_option");
    const title = option?.querySelector(".learn_choice_option_title");
    return title?.textContent?.trim() || selected.value || "";
  };

  const updateDecisionResolvedState = (section) => {
    if (!(section instanceof HTMLElement)) {
      return;
    }
    const resolved = isSectionResolved(section);
    const actionable = isActionableSection(section);
    const navItem = getNavItemByDecisionId(getDecisionId(section));
    const stateText = !actionable
      ? "Info"
      : resolved
        ? "Ausgewaehlt"
        : "Offen";
    const summaryText = resolved
      ? (getSelectionLabel(section) || "Auswahl gespeichert")
      : "Noch nicht ausgewaehlt";

    section.classList.toggle("is-resolved", resolved);
    section.classList.toggle("is-pending", actionable && !resolved);

    const panelSummary = getPanelSummaryEl(section);
    if (panelSummary instanceof HTMLElement) {
      panelSummary.textContent = summaryText;
    }
    const panelState = getPanelStateEl(section);
    if (panelState instanceof HTMLElement) {
      panelState.textContent = stateText;
    }

    if (navItem instanceof HTMLElement) {
      navItem.classList.toggle("is-resolved", resolved);
      navItem.classList.toggle("is-pending", actionable && !resolved);
      const navSummary = navItem.querySelector("[data-choice-nav-summary]");
      const navState = navItem.querySelector("[data-choice-nav-state]");
      if (navSummary instanceof HTMLElement) {
        navSummary.textContent = summaryText;
      }
      if (navState instanceof HTMLElement) {
        navState.textContent = stateText;
      }
    }
  };

  const appendHiddenInput = ({
    decisionId,
    selectionGroupId = "",
    optionId = "",
    submitName,
    submitValue,
  }) => {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = submitName;
    input.value = submitValue;
    input.dataset.choiceDecisionId = decisionId;
    input.dataset.choiceSelectionGroup = selectionGroupId;
    if (optionId) {
      input.dataset.choiceOptionId = optionId;
    }
    hiddenInputContainer.appendChild(input);
  };

  const syncSectionFromHidden = (section) => {
    const decisionId = getDecisionId(section);
    const inputs = getDecisionInputs(decisionId);
    const inputType = getInputType(section);
    if (inputType === "text") {
      const input = section.querySelector("[data-choice-text-input]");
      if (input instanceof HTMLInputElement) {
        input.value = inputs.length ? inputs[0].value || "" : "";
      }
      updateDecisionResolvedState(section);
      return;
    }

    section.querySelectorAll("input[type='radio']").forEach((input) => {
      if (input instanceof HTMLInputElement) {
        input.checked = false;
      }
    });
    let restoredOptionId = "";
    inputs.forEach((hiddenInput) => {
      const optionId = hiddenInput.dataset.choiceOptionId || "";
      const match = section.querySelector(`input[type='radio'][data-choice-option-id="${optionId}"]`);
      if (match instanceof HTMLInputElement) {
        match.checked = true;
        restoredOptionId = optionId;
      }
    });
    if (restoredOptionId) {
      selectionTracker.set(decisionId, restoredOptionId);
    } else {
      selectionTracker.delete(decisionId);
    }
    updateDecisionResolvedState(section);
  };

  const syncFormFromHiddenInputs = () => {
    getSections().forEach((section) => {
      syncSectionFromHidden(section);
    });
  };

  const refreshSearchFilter = (section) => {
    if (typeof section.__applyChoiceFilter === "function") {
      section.__applyChoiceFilter();
    }
  };

  const updateGroupedOptionAvailability = () => {
    const groupedSelections = new Map();

    getSections().forEach((section) => {
      const selectionGroupId = getSelectionGroupId(section);
      if (!selectionGroupId || getInputType(section) !== "options") {
        return;
      }
      // Use the explicit tracker first (works even when section is hidden),
      // fall back to querying the checked radio.
      const decisionId = getDecisionId(section);
      const optionId = selectionTracker.get(decisionId) || getSelectedOptionId(section);
      if (!optionId) {
        return;
      }
      const selectedIds = groupedSelections.get(selectionGroupId) || new Set();
      selectedIds.add(optionId);
      groupedSelections.set(selectionGroupId, selectedIds);
    });

    getSections().forEach((section) => {
      const selectionGroupId = getSelectionGroupId(section);
      const optionInputs = getSectionOptionInputs(section);
      if (!selectionGroupId || !optionInputs.length) {
        return;
      }
      const selectedIds = groupedSelections.get(selectionGroupId) || new Set();
      const decisionId = getDecisionId(section);
      const currentSelection = selectionTracker.get(decisionId) || getSelectedOptionId(section);
      optionInputs.forEach((input) => {
        if (!(input instanceof HTMLInputElement)) {
          return;
        }
        const optionId = input.dataset.choiceOptionId || input.value || "";
        const shouldHide = Boolean(optionId) && optionId !== currentSelection && selectedIds.has(optionId);
        input.disabled = shouldHide;
        const label = input.closest(".learn_choice_option");
        if (label instanceof HTMLElement) {
          label.classList.toggle("is-disabled", shouldHide);
          label.classList.toggle("is-group-hidden", shouldHide);
          label.setAttribute("aria-disabled", shouldHide ? "true" : "false");
          // Force display via inline style to beat any CSS specificity conflict.
          label.style.display = shouldHide ? "none" : "";
        }
      });
      refreshSearchFilter(section);
    });
  };

  const setActiveDecision = (decisionId, { focusNav = false } = {}) => {
    activeDecisionId = decisionId || "";
    getSections().forEach((section) => {
      const active = getDecisionId(section) === activeDecisionId;
      section.hidden = !active;
      section.classList.toggle("is-active", active);
    });
    getNavItems().forEach((item) => {
      const active = item.getAttribute("data-choice-nav-id") === activeDecisionId;
      item.classList.toggle("is-active", active);
      item.setAttribute("aria-pressed", active ? "true" : "false");
      if (active && focusNav) {
        item.focus();
      }
    });
  };

  const getPendingSections = () => getSections().filter(
    (section) => isActionableSection(section) && !isSectionResolvedByHidden(section),
  );
  const hasPendingChoices = () => getPendingSections().length > 0;
  const emitPendingChange = () => {
    document.dispatchEvent(new CustomEvent("learn:choices-updated", {
      detail: { pendingCount: getPendingSections().length },
    }));
  };

  const submitResolvedChoices = () => {
    if (!(learningForm instanceof HTMLFormElement)) {
      return false;
    }
    const csrfInput = learningForm.querySelector('input[name="csrfmiddlewaretoken"]');
    if (!(csrfInput instanceof HTMLInputElement) || !csrfInput.value) {
      return false;
    }

    const tempForm = document.createElement("form");
    tempForm.method = "post";
    tempForm.action = learningForm.action;
    tempForm.hidden = true;

    const csrfClone = document.createElement("input");
    csrfClone.type = "hidden";
    csrfClone.name = csrfInput.name;
    csrfClone.value = csrfInput.value;
    tempForm.appendChild(csrfClone);

    Array.from(hiddenInputContainer.querySelectorAll("input[data-choice-decision-id]")).forEach((input) => {
      if (!(input instanceof HTMLInputElement) || !input.name) {
        return;
      }
      const clone = document.createElement("input");
      clone.type = "hidden";
      clone.name = input.name;
      clone.value = input.value;
      tempForm.appendChild(clone);
    });

    document.body.appendChild(tempForm);
    tempForm.submit();
    return true;
  };

  const chooseBestActiveSection = (pendingSections) => {
    const sections = getSections();
    const existing = sections.find((section) => getDecisionId(section) === activeDecisionId);
    if (existing) {
      return getDecisionId(existing);
    }
    if (pendingSections.length > 0) {
      return getDecisionId(pendingSections[0]);
    }
    if (sections.length > 0) {
      return getDecisionId(sections[0]);
    }
    return "";
  };

  const renderPendingDecisions = () => {
    syncFormFromHiddenInputs();
    updateGroupedOptionAvailability();
    const pendingSections = [];
    getSections().forEach((section) => {
      const pending = isActionableSection(section) && !isSectionResolvedByHidden(section);
      section.classList.toggle("is-pending", pending);
      if (pending) {
        pendingSections.push(section);
      }
      updateDecisionResolvedState(section);
    });

    setActiveDecision(chooseBestActiveSection(pendingSections));

    titleEl.textContent = pendingSections.length > 1 ? "Ausstehende Entscheidungen" : "Ausstehende Entscheidung";
    if (introEl instanceof HTMLElement) {
      introEl.textContent = pendingSections.length > 1
        ? "Links siehst du alle offenen Choices. Rechts bearbeitest du die jeweils ausgewaehlte Entscheidung direkt."
        : "Links steht die offene Choice, rechts kannst du die Auswahl direkt festlegen.";
    }
    confirmBtn.disabled = pendingSections.length === 0;
    setHint("");
    return pendingSections;
  };

  const collectPendingValues = (pendingSections) => {
    const results = [];
    const groupedSelections = new Map();

    for (const section of pendingSections) {
      const inputType = getInputType(section);
      const decisionId = getDecisionId(section);
      const selectionGroupId = getSelectionGroupId(section);

      if (inputType === "text") {
        const input = section.querySelector("[data-choice-text-input]");
        const value = input instanceof HTMLInputElement ? String(input.value || "").trim() : "";
        if (!value) {
          continue;
        }
        results.push({
          decisionId,
          selectionGroupId,
          submitName: input.dataset.choiceSubmitName || "",
          submitValue: value,
        });
        continue;
      }

      const selectedInput = getSelectedRadio(section);
      if (!(selectedInput instanceof HTMLInputElement)) {
        continue;
      }

      const optionId = selectedInput.dataset.choiceOptionId || selectedInput.value;
      if (selectionGroupId) {
        const existing = groupedSelections.get(selectionGroupId) || new Set();
        if (existing.has(optionId)) {
          return {
            ok: false,
            hint: "Dieselbe Option kann in einer gemeinsamen Choice-Gruppe nicht mehrfach gleichzeitig gewaehlt werden.",
          };
        }
        existing.add(optionId);
        groupedSelections.set(selectionGroupId, existing);
      }

      results.push({
        decisionId,
        selectionGroupId,
        optionId,
        submitName: selectedInput.dataset.choiceSubmitName || "",
        submitValue: selectedInput.dataset.choiceSubmitValue || selectedInput.value,
      });
    }

    if (!results.length) {
      return {
        ok: false,
        hint: "Bitte mindestens eine Entscheidung treffen.",
      };
    }

    return { ok: true, results };
  };

  const applyPendingDecisions = () => {
    const pendingSections = getPendingSections();
    const collected = collectPendingValues(pendingSections);
    if (!collected.ok) {
      setHint(collected.hint || "Bitte alle offenen Entscheidungen ausfuellen.");
      return false;
    }

    const resolvedIds = new Set(collected.results.map((entry) => entry.decisionId));
    pendingSections.forEach((section) => {
      if (resolvedIds.has(getDecisionId(section))) {
        clearDecisionInputs(getDecisionId(section));
      }
    });

    collected.results.forEach((entry) => {
      appendHiddenInput({
        decisionId: entry.decisionId,
        selectionGroupId: entry.selectionGroupId,
        optionId: entry.optionId || "",
        submitName: entry.submitName,
        submitValue: entry.submitValue,
      });
    });

    emitPendingChange();
    const stillPending = renderPendingDecisions();
    if (!submitResolvedChoices()) {
      if (!stillPending.length) {
        closeModal();
      }
    }
    return true;
  };

  const openPendingChoices = () => {
    const pendingSections = renderPendingDecisions();
    if (!pendingSections.length) {
      closeModal();
      return false;
    }
    openModal();
    return true;
  };

  const bindSearchFilter = (section) => {
    const searchInput = section.querySelector("[data-choice-search-input]");
    const options = Array.from(section.querySelectorAll(".learn_choice_option"));
    const emptyState = section.querySelector("[data-choice-empty-state]");
    if (!options.length || !(emptyState instanceof HTMLElement)) {
      return;
    }

    const applyOptionFilter = () => {
      const needle = searchInput instanceof HTMLInputElement
        ? normalizeSearchText(String(searchInput.value || "").trim())
        : "";
      let visibleCount = 0;
      options.forEach((entry) => {
        if (!(entry instanceof HTMLElement)) {
          return;
        }
        const hiddenByGroup = entry.classList.contains("is-group-hidden");
        const haystack = normalizeSearchText(entry.dataset.choiceSearch || entry.textContent || "");
        const matches = !needle || haystack.includes(needle);
        const shouldHide = hiddenByGroup || !matches;
        entry.classList.toggle("is-filtered-out", shouldHide);
        if (!shouldHide) {
          visibleCount += 1;
        }
      });
      emptyState.hidden = visibleCount > 0;
    };

    section.__applyChoiceFilter = applyOptionFilter;
    if (searchInput instanceof HTMLInputElement) {
      searchInput.addEventListener("input", applyOptionFilter);
      searchInput.addEventListener("search", applyOptionFilter);
      searchInput.addEventListener("change", applyOptionFilter);
    }
    applyOptionFilter();
  };

  getNavItems().forEach((item) => {
    item.addEventListener("click", () => {
      const decisionId = item.getAttribute("data-choice-nav-id") || "";
      if (decisionId) {
        setHint("");
        setActiveDecision(decisionId);
        updateGroupedOptionAvailability();
      }
    });
  });

  getSections().forEach((section) => {
    bindSearchFilter(section);
    section.querySelectorAll("input[type='radio']").forEach((input) => {
      input.addEventListener("change", () => {
        // Keep the explicit tracker in sync immediately so that
        // updateGroupedOptionAvailability works even after section is hidden.
        const decisionId = getDecisionId(section);
        const optionId = input.dataset.choiceOptionId || input.value || "";
        if (optionId) {
          selectionTracker.set(decisionId, optionId);
        } else {
          selectionTracker.delete(decisionId);
        }
        updateDecisionResolvedState(section);
        updateGroupedOptionAvailability();
      });
    });
    const textInput = section.querySelector("[data-choice-text-input]");
    if (textInput instanceof HTMLInputElement) {
      textInput.addEventListener("input", () => {
        updateDecisionResolvedState(section);
      });
    }
  });

  formEl.addEventListener("submit", (event) => {
    event.preventDefault();
    applyPendingDecisions();
  });

  cancelBtn?.addEventListener("click", () => {
    closeModal();
  });

  renderPendingDecisions();
  emitPendingChange();

  return {
    emitPendingChange,
    getPendingDecisions: getPendingSections,
    hasPendingChoices,
    openDecision: openPendingChoices,
    openNextPendingChoice: openPendingChoices,
    openPendingChoices,
  };
}
