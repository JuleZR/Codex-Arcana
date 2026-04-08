export function createChoiceModalController({ hiddenInputContainer, windowController = null }) {
  const learningForm = hiddenInputContainer?.closest("form") || null;
  const modalWindow = document.getElementById("learnChoiceWindow");
  const titleEl = document.getElementById("learnChoiceWindowTitle");
  const introEl = document.getElementById("learnChoiceWindowIntro");
  const decisionListEl = document.getElementById("learnChoiceDecisionList");
  const formEl = document.getElementById("learnChoiceForm");
  const hintEl = document.getElementById("learnChoiceHint");
  const confirmBtn = document.getElementById("learnChoiceConfirmBtn");
  const cancelBtn = document.getElementById("learnChoiceCancelBtn");
  if (
    !hiddenInputContainer
    || !modalWindow
    || !titleEl
    || !introEl
    || !decisionListEl
    || !formEl
    || !hintEl
    || !confirmBtn
  ) {
    return null;
  }

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

  const getSections = () => Array.from(decisionListEl.querySelectorAll("[data-choice-decision-id]"));
  const getDecisionInputs = (decisionId) => Array.from(hiddenInputContainer.querySelectorAll(`input[data-choice-decision-id="${decisionId}"]`));
  const clearDecisionInputs = (decisionId) => {
    getDecisionInputs(decisionId).forEach((input) => {
      input.remove();
    });
  };
  const setHint = (text = "") => {
    hintEl.textContent = text;
    hintEl.hidden = !text;
  };

  const normalizeSearchText = (value) => String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");

  const getInputType = (section) => section.dataset.choiceInputType || "options";
  const getDecisionId = (section) => section.dataset.choiceDecisionId || "";
  const getDecisionTitle = (section) => section.dataset.choiceTitle || "Ausstehende Entscheidung";
  const getSelectionGroupId = (section) => section.dataset.choiceSelectionGroup || "";
  const getSectionOptionInputs = (section) => Array.from(section.querySelectorAll("input[type='radio']"));
  const getSelectedOptionId = (section) => {
    const selected = section.querySelector("input[type='radio']:checked");
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

  const updateDecisionResolvedState = (section) => {
    if (!(section instanceof HTMLElement)) {
      return;
    }
    const inputType = getInputType(section);
    let resolved = false;
    if (inputType === "text") {
      const input = section.querySelector("[data-choice-text-input]");
      resolved = input instanceof HTMLInputElement
        ? Boolean(String(input.value || "").trim())
        : isSectionResolvedByHidden(section);
    } else if (inputType === "unsupported") {
      resolved = true;
    } else {
      resolved = Boolean(section.querySelector("input[type='radio']:checked")) || isSectionResolvedByHidden(section);
    }
    section.classList.toggle("is-resolved", resolved);
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
    inputs.forEach((hiddenInput) => {
      const optionId = hiddenInput.dataset.choiceOptionId || "";
      const match = section.querySelector(
        `input[type='radio'][data-choice-option-id="${optionId}"]`,
      );
      if (match instanceof HTMLInputElement) {
        match.checked = true;
      }
    });
    updateDecisionResolvedState(section);
  };

  const syncFormFromHiddenInputs = () => {
    getSections().forEach((section) => {
      syncSectionFromHidden(section);
    });
  };

  const updateGroupedOptionAvailability = () => {
    const groupedSelections = new Map();

    getSections().forEach((section) => {
      const selectionGroupId = getSelectionGroupId(section);
      if (!selectionGroupId || getInputType(section) !== "options") {
        return;
      }
      const optionId = getSelectedOptionId(section);
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
      const currentSelection = getSelectedOptionId(section);
      optionInputs.forEach((input) => {
        if (!(input instanceof HTMLInputElement)) {
          return;
        }
        const optionId = input.dataset.choiceOptionId || input.value || "";
        const shouldDisable = Boolean(optionId) && optionId !== currentSelection && selectedIds.has(optionId);
        input.disabled = shouldDisable;
        const label = input.closest(".learn_choice_option");
        if (label instanceof HTMLElement) {
          label.classList.toggle("is-disabled", shouldDisable);
          label.setAttribute("aria-disabled", shouldDisable ? "true" : "false");
        }
      });
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

  const renderPendingDecisions = () => {
    syncFormFromHiddenInputs();
    updateGroupedOptionAvailability();
    const pendingSections = [];
    getSections().forEach((section) => {
      const pending = isActionableSection(section) && !isSectionResolvedByHidden(section);
      section.hidden = !pending;
      if (pending) {
        pendingSections.push(section);
      }
    });

    if (pendingSections.length > 0) {
      pendingSections.forEach((section, index) => {
        section.open = index === 0;
      });
    }

    titleEl.textContent = pendingSections.length > 1 ? "Ausstehende Entscheidungen" : "Ausstehende Entscheidung";
    introEl.textContent = pendingSections.length > 1
      ? "Alle offenen Choices sind hier gebuendelt und koennen in einem gemeinsamen Fenster bearbeitet werden."
      : "Diese offene Choice wird als eigener Entscheidungsvorgang behandelt.";
    confirmBtn.disabled = pendingSections.length === 0;
    setHint("");
    return pendingSections;
  };

  const collectPendingValues = (pendingSections) => {
    const results = [];
    const missing = [];
    const groupedSelections = new Map();

    for (const section of pendingSections) {
      const inputType = getInputType(section);
      const title = getDecisionTitle(section);
      const decisionId = getDecisionId(section);
      const selectionGroupId = getSelectionGroupId(section);

      if (inputType === "text") {
        const input = section.querySelector("[data-choice-text-input]");
        const value = input instanceof HTMLInputElement ? String(input.value || "").trim() : "";
        if (!value) {
          missing.push(title);
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

      const selectedInput = section.querySelector("input[type='radio']:checked");
      if (!(selectedInput instanceof HTMLInputElement)) {
        missing.push(title);
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

    if (missing.length) {
      return {
        ok: false,
        hint: `Bitte alle offenen Entscheidungen ausfuellen: ${missing.join(", ")}.`,
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

    pendingSections.forEach((section) => {
      clearDecisionInputs(getDecisionId(section));
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
    if (!stillPending.length) {
      if (!submitResolvedChoices()) {
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
    if (!(searchInput instanceof HTMLInputElement) || !options.length || !(emptyState instanceof HTMLElement)) {
      return;
    }

    const applyOptionFilter = () => {
      const needle = normalizeSearchText(String(searchInput.value || "").trim());
      let visibleCount = 0;
      options.forEach((entry) => {
        if (!(entry instanceof HTMLElement)) {
          return;
        }
        const haystack = normalizeSearchText(entry.dataset.choiceSearch || entry.textContent || "");
        const matches = !needle || haystack.includes(needle);
        entry.classList.toggle("is-filtered-out", !matches);
        if (matches) {
          visibleCount += 1;
        }
      });
      emptyState.hidden = visibleCount > 0;
    };

    searchInput.addEventListener("input", applyOptionFilter);
    searchInput.addEventListener("search", applyOptionFilter);
    searchInput.addEventListener("change", applyOptionFilter);
    applyOptionFilter();
  };

  getSections().forEach((section) => {
    bindSearchFilter(section);
    section.querySelectorAll("input[type='radio']").forEach((input) => {
      input.addEventListener("change", () => {
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
