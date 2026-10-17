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
  let submitting = false;
  const confirmedIds = new Set();
  const lockedInputs = new Map();
  const previousBtn = modalWindow.querySelector("[data-choice-previous]");

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
  const getVisibleSections = () => getSections().filter(
    (section) => !isSavedSection(section),
  );
  const getNavItems = () => Array.from(navListEl.querySelectorAll("[data-choice-nav-id]"));
  const getDecisionId = (section) => section.dataset.choiceDecisionId || "";
  const getDecisionInputs = (decisionId) => Array.from(hiddenInputContainer.querySelectorAll(`input[data-choice-decision-id="${decisionId}"]`));
  const getSelectionGroupId = (section) => section.dataset.choiceSelectionGroup || "";
  const allowsDuplicateSelections = (section) => section.dataset.choiceAllowDuplicates === "1";
  const getInputType = (section) => section.dataset.choiceInputType || "options";
  const getDecisionTitle = (section) => section.dataset.choiceTitle || "Offene Wahl";
  const getSectionOptionInputs = (section) => Array.from(section.querySelectorAll("input[type='radio']:not([data-choice-side-option])"));
  const getNavItemByDecisionId = (decisionId) => navListEl.querySelector(`[data-choice-nav-id="${decisionId}"]`);
  const getPanelSummaryEl = (section) => section.querySelector("[data-choice-panel-summary]");
  const getPanelStateEl = (section) => section.querySelector("[data-choice-panel-state]");
  const unlockInputs = () => {
    lockedInputs.forEach((disabled, input) => { input.disabled = disabled; });
    lockedInputs.clear();
  };

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

  const getSelectedRadio = (section) => section.querySelector("input[type='radio']:checked:not([data-choice-side-option])");
  const getSelectedSideRadio = (section) => section.querySelector("input[data-choice-side-option]:checked");
  const getSpecificationInput = (selected) => selected?.closest(".learn_choice_option")
    ?.querySelector("[data-choice-specification-input]");
  const getSelectedOptionId = (section) => {
    const selected = getSelectedRadio(section);
    if (!(selected instanceof HTMLInputElement)) {
      return "";
    }
    return selected.dataset.choiceOptionId || selected.value || "";
  };

  const isSavedSection = (section) => section.dataset.choiceSaved === "1"
    || confirmedIds.has(getDecisionId(section));
  const isActionableSection = (section) => !isSavedSection(section)
    && getInputType(section) !== "unsupported";
  const isSectionResolvedByHidden = (section) => {
    const inputs = getDecisionInputs(getDecisionId(section));
    if (!inputs.length) {
      return false;
    }
    if (getInputType(section) === "text") {
      return Boolean(String(inputs[0].value || "").trim());
    }
    const mainInput = inputs.find((input) => input.dataset.choiceSideOption !== "1"
      && input.dataset.choiceSpecification !== "1");
    const selected = getSectionOptionInputs(section).find(
      (input) => input.dataset.choiceOptionId === mainInput?.dataset.choiceOptionId,
    );
    const specificationInput = getSpecificationInput(selected);
    if (specificationInput && !inputs.some(
      (input) => input.name === specificationInput.dataset.choiceSubmitName && input.value.trim(),
    )) {
      return false;
    }
    return !section.querySelector("[data-choice-side-option]")
      || (inputs.some((input) => input.dataset.choiceSideOption === "1")
        && inputs.some((input) => input.dataset.choiceSideOption !== "1"));
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
    const specificationInput = getSpecificationInput(getSelectedRadio(section));
    if (specificationInput && !specificationInput.value.trim()) {
      return false;
    }
    if (section.querySelector("[data-choice-side-option]")) {
      return Boolean(getSelectedRadio(section) && getSelectedSideRadio(section))
        || isSectionResolvedByHidden(section);
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
    let weaponLabel = title?.textContent?.trim() || selected.value || "";
    const specification = getSpecificationInput(selected)?.value.trim();
    if (specification) {
      weaponLabel = `${weaponLabel.replace(/\[Specification\]/g, "").replace(/[:\s]+$/, "")}: ${specification}`;
    }
    const side = getSelectedSideRadio(section);
    if (!side) {
      return weaponLabel;
    }
    const sideLabel = side.closest(".learn_choice_option")?.querySelector(".learn_choice_option_title")?.textContent?.trim();
    return sideLabel ? `${sideLabel}, ${weaponLabel}` : weaponLabel;
  };

  const updateDecisionResolvedState = (section) => {
    if (!(section instanceof HTMLElement)) {
      return;
    }
    if (section.dataset.choiceSaved === "1") return;
    const selected = getSelectedRadio(section);
    section.querySelectorAll("[data-choice-specification-wrap]").forEach((wrap) => {
      wrap.hidden = wrap.closest(".learn_choice_option") !== selected?.closest(".learn_choice_option");
    });
    const resolved = isSavedSection(section);
    const selectedLocally = isSectionResolved(section);
    const navItem = getNavItemByDecisionId(getDecisionId(section));
    const stateText = resolved ? "✓ Gespeichert" : selectedLocally ? "! Vorgemerkt" : "! Offen";
    const summaryText = getSelectionLabel(section) || "Noch keine Auswahl";

    section.classList.toggle("is-resolved", resolved);
    section.classList.toggle("is-pending", !resolved);
    section.classList.toggle("is-staged", !resolved && selectedLocally);

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
      navItem.classList.toggle("is-pending", !resolved);
      navItem.classList.toggle("is-staged", !resolved && selectedLocally);
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
    sideOption = false,
    specificationOption = false,
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
    if (sideOption) {
      input.dataset.choiceSideOption = "1";
    }
    if (specificationOption) {
      input.dataset.choiceSpecification = "1";
    }
    hiddenInputContainer.appendChild(input);
  };

  const syncSectionFromHidden = (section) => {
    if (section.dataset.choiceSaved === "1") return;
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
    section.querySelectorAll("[data-choice-specification-input]").forEach((input) => {
      input.value = inputs.find((hidden) => hidden.name === input.dataset.choiceSubmitName)?.value || "";
    });
    inputs.forEach((hiddenInput) => {
      if (hiddenInput.dataset.choiceSpecification === "1") {
        return;
      }
      const optionId = hiddenInput.dataset.choiceOptionId || "";
      const selector = hiddenInput.dataset.choiceSideOption === "1"
        ? `input[data-choice-side-option][data-choice-option-id="${optionId}"]`
        : `input[type='radio']:not([data-choice-side-option])[data-choice-option-id="${optionId}"]`;
      const match = section.querySelector(selector);
      if (match instanceof HTMLInputElement) {
        match.checked = true;
        if (hiddenInput.dataset.choiceSideOption !== "1") {
          restoredOptionId = optionId;
        }
      }
    });
    if (!getSelectedSideRadio(section)) {
      const defaultSide = section.querySelector('input[data-choice-side-option][value="maneuver"]');
      if (defaultSide instanceof HTMLInputElement) {
        defaultSide.checked = true;
      }
    }
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
      if (allowsDuplicateSelections(section)) {
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
      if (allowsDuplicateSelections(section)) {
        optionInputs.forEach((input) => {
          if (!(input instanceof HTMLInputElement)) {
            return;
          }
          input.disabled = false;
          const label = input.closest(".learn_choice_option");
          if (label instanceof HTMLElement) {
            label.classList.remove("is-disabled", "is-group-hidden");
            label.setAttribute("aria-disabled", "false");
            label.style.display = "";
          }
        });
        refreshSearchFilter(section);
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
    const visibleSections = getVisibleSections();
    activeDecisionId = visibleSections.some((section) => getDecisionId(section) === decisionId)
      ? decisionId
      : (visibleSections[0] ? getDecisionId(visibleSections[0]) : "");
    getSections().forEach((section) => {
      const active = getDecisionId(section) === activeDecisionId;
      section.hidden = !active;
      section.classList.toggle("is-active", active);
    });
    getNavItems().forEach((item) => {
      const active = item.getAttribute("data-choice-nav-id") === activeDecisionId;
      item.classList.toggle("is-active", active);
      item.setAttribute("aria-pressed", active ? "true" : "false");
      item.setAttribute("aria-current", active ? "step" : "false");
      if (active && focusNav) {
        item.focus();
      }
    });
    const sections = getSections();
    getNavItems().forEach((item) => {
      const section = sections.find((entry) => getDecisionId(entry) === item.dataset.choiceNavId);
      item.hidden = Boolean(section && isSavedSection(section));
    });
    if (previousBtn) previousBtn.disabled = visibleSections.findIndex(
      (section) => getDecisionId(section) === activeDecisionId,
    ) <= 0;
  };

  const getPendingSections = () => getSections().filter(
    (section) => isActionableSection(section),
  );
  const hasPendingChoices = () => getPendingSections().length > 0;
  const emitPendingChange = () => {
    const sections = getSections();
    const saved = sections.filter(isSavedSection).length;
    const label = modalWindow.querySelector("[data-choice-progress-label]");
    const progress = modalWindow.querySelector("[data-choice-progress]");
    if (label) label.textContent = `${saved} / ${sections.length}`;
    if (progress) {
      progress.max = Math.max(1, sections.length);
      progress.value = saved;
    }
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
    tempForm.setAttribute("data-sheet-action", "");
    tempForm.setAttribute("data-ajax-only", "");

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
    const onFailure = () => {
      unlockInputs();
      submitting = false;
      confirmBtn.disabled = false;
      setHint("Die Auswahl wurde nicht gespeichert. Bitte erneut übernehmen.");
      tempForm.remove();
    };
    tempForm.addEventListener("sheet:action-success", (event) => {
      if (event.detail?.learningFeedback?.level === "error" || event.detail?.ok !== true) {
        onFailure();
        return;
      }
      // A successful action may replace the entire learning partial. Its server
      // context is authoritative; never paint a rejected/still-open choice green.
      const currentPanels = document.getElementById("learnChoicePanelList");
      unlockInputs();
      if (currentPanels === panelListEl) {
        getSections().forEach((section) => {
          if (isSectionResolvedByHidden(section)) {
            confirmedIds.add(getDecisionId(section));
            section.querySelectorAll("input").forEach((input) => { input.disabled = true; });
            updateDecisionResolvedState(section);
          }
        });
        emitPendingChange();
        setActiveDecision(activeDecisionId);
        if (!getVisibleSections().length) closeModal();
        setHint("Auswahl gespeichert.");
      }
      submitting = false;
      confirmBtn.disabled = !hasPendingChoices();
      tempForm.remove();
    }, { once: true });
    tempForm.addEventListener("sheet:action-failed", onFailure, { once: true });
    const submitEvent = typeof SubmitEvent === "function"
      ? new SubmitEvent("submit", {
          bubbles: true,
          cancelable: true,
        })
      : new Event("submit", {
          bubbles: true,
          cancelable: true,
        });
    tempForm.dispatchEvent(submitEvent);
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
      const pending = isActionableSection(section);
      section.classList.toggle("is-pending", pending);
      if (pending) {
        pendingSections.push(section);
      }
      updateDecisionResolvedState(section);
    });

    setActiveDecision(chooseBestActiveSection(pendingSections));

    titleEl.textContent = "Wege der Entscheidung";
    if (introEl instanceof HTMLElement) {
      introEl.textContent = pendingSections.length > 1
        ? "Links siehst du alle offenen Entscheidungen. Rechts bearbeitest du die jeweils ausgewaehlte Entscheidung direkt."
        : "Links steht die offene Entscheidung, rechts kannst du die Auswahl direkt festlegen.";
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
      const sideInput = section.querySelector("[data-choice-side-option]")
        ? getSelectedSideRadio(section)
        : null;
      if (selectedInput && !sideInput && section.querySelector("[data-choice-side-option]")) {
        return { ok: false, hint: "Bitte Startbonus und Waffentyp zusammen auswaehlen." };
      }
      if (!(selectedInput instanceof HTMLInputElement)) {
        continue;
      }

      const optionId = selectedInput.dataset.choiceOptionId || selectedInput.value;
      const specificationInput = getSpecificationInput(selectedInput);
      const specification = specificationInput?.value.trim() || "";
      if (specificationInput && (!specification || specification === "*")) {
        setActiveDecision(decisionId);
        specificationInput.focus();
        return { ok: false, hint: "Bitte eine konkrete Spezifikation angeben." };
      }
      const selectionKey = specificationInput
        ? `${selectedInput.dataset.choiceSubmitValue}:${specification.toLowerCase()}`
        : optionId;
      if (selectionGroupId && !allowsDuplicateSelections(section)) {
        const existing = groupedSelections.get(selectionGroupId) || new Set();
        if (existing.has(selectionKey)) {
          return {
            ok: false,
            hint: "Dieselbe Option kann in einer gemeinsamen Choice-Gruppe nicht mehrfach gleichzeitig gewaehlt werden.",
          };
        }
        existing.add(selectionKey);
        groupedSelections.set(selectionGroupId, existing);
      }

      results.push({
        decisionId,
        selectionGroupId,
        optionId,
        submitName: selectedInput.dataset.choiceSubmitName || "",
        submitValue: selectedInput.dataset.choiceSubmitValue || selectedInput.value,
      });
      if (specificationInput) {
        results.push({
          decisionId,
          specificationOption: true,
          submitName: specificationInput.dataset.choiceSubmitName,
          submitValue: specification,
        });
      }
      if (sideInput instanceof HTMLInputElement) {
        results.push({
          decisionId,
          selectionGroupId: "",
          optionId: sideInput.dataset.choiceOptionId || sideInput.value,
          sideOption: true,
          submitName: sideInput.dataset.choiceSubmitName || "",
          submitValue: sideInput.dataset.choiceSubmitValue || sideInput.value,
        });
      }
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
    if (submitting) return false;
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
        sideOption: entry.sideOption || false,
        specificationOption: entry.specificationOption || false,
        submitName: entry.submitName,
        submitValue: entry.submitValue,
      });
    });

    submitting = true;
    panelListEl.querySelectorAll("input, select").forEach((input) => {
      lockedInputs.set(input, input.disabled);
      input.disabled = true;
    });
    confirmBtn.disabled = true;
    setHint("Auswahl wird gespeichert …");
    if (!submitResolvedChoices()) {
      unlockInputs();
      submitting = false;
      confirmBtn.disabled = false;
      setHint("Auswahl ist vorgemerkt. Bitte im Lernmenü übernehmen.");
    }
    return true;
  };

  const openPendingChoices = () => {
    if (!submitting) renderPendingDecisions();
    if (!getVisibleSections().length) {
      closeModal();
      return false;
    }
    openModal();
    return true;
  };

  const bindSearchFilter = (section) => {
    const searchInput = section.querySelector("[data-choice-search-input]");
    const gradeFilter = section.querySelector("[data-choice-grade-filter]");
    const options = Array.from(section.querySelectorAll(".learn_choice_options .learn_choice_option"));
    const emptyState = section.querySelector("[data-choice-empty-state]");
    if (!options.length || !(emptyState instanceof HTMLElement)) {
      return;
    }

    const applyOptionFilter = () => {
      const needle = searchInput instanceof HTMLInputElement
        ? normalizeSearchText(String(searchInput.value || "").trim())
        : "";
      const selectedGrade = gradeFilter instanceof HTMLSelectElement
        ? String(gradeFilter.value || "").trim()
        : "";
      let visibleCount = 0;
      options.forEach((entry) => {
        if (!(entry instanceof HTMLElement)) {
          return;
        }
        const hiddenByGroup = entry.classList.contains("is-group-hidden");
        const haystack = normalizeSearchText(entry.dataset.choiceSearch || entry.textContent || "");
        const matchesText = !needle || haystack.includes(needle);
        const matchesGrade = !selectedGrade || String(entry.dataset.choiceGrade || "") === selectedGrade;
        const shouldHide = hiddenByGroup || !matchesText || !matchesGrade;
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
    if (gradeFilter instanceof HTMLSelectElement) {
      gradeFilter.addEventListener("change", applyOptionFilter);
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

  previousBtn?.addEventListener("click", () => {
    const sections = getVisibleSections();
    const index = sections.findIndex((section) => getDecisionId(section) === activeDecisionId);
    if (index > 0) setActiveDecision(getDecisionId(sections[index - 1]), { focusNav: true });
  });

  getSections().forEach((section) => {
    bindSearchFilter(section);
    section.querySelectorAll("input[type='radio']").forEach((input) => {
      input.addEventListener("change", () => {
        // Keep the explicit tracker in sync immediately so that
        // updateGroupedOptionAvailability works even after section is hidden.
        const decisionId = getDecisionId(section);
        const optionId = input.dataset.choiceOptionId || input.value || "";
        if (optionId && !input.hasAttribute("data-choice-side-option")) {
          selectionTracker.set(decisionId, optionId);
        } else if (!input.hasAttribute("data-choice-side-option")) {
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
    section.querySelectorAll("[data-choice-specification-input]").forEach((input) => {
      input.addEventListener("input", () => updateDecisionResolvedState(section));
    });
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
