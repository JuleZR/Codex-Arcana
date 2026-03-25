export function createChoiceModalController({ decisions = [], hiddenInputContainer, windowController = null }) {
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

  const getCurrentSelection = (decision) => {
    const inputs = getDecisionInputs(decision.decision_id);
    if (!inputs.length) {
      return { optionId: "", text: "" };
    }
    if (decision.input_type === "text") {
      return { optionId: "", text: inputs[0].value || "" };
    }
    const selectedInput = inputs[0];
    const selectedOption = decision.options.find(
      (option) => option.submit_name === selectedInput.name && String(option.submit_value) === String(selectedInput.value),
    );
    return {
      optionId: selectedOption?.id || selectedInput.dataset.choiceOptionId || "",
      text: "",
    };
  };

  const getTakenOptionIds = (selectionGroupId, ignoredDecisionIds = []) => {
    if (!selectionGroupId) {
      return new Set();
    }
    const ignored = new Set(ignoredDecisionIds);
    const taken = new Set();
    hiddenInputContainer.querySelectorAll(`input[data-choice-selection-group="${selectionGroupId}"]`).forEach((input) => {
      if (ignored.has(input.dataset.choiceDecisionId || "")) {
        return;
      }
      if (input.dataset.choiceOptionId) {
        taken.add(input.dataset.choiceOptionId);
      }
    });
    return taken;
  };

  const normalizeSearchText = (value) => String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");

  const isDecisionResolved = (decision) => {
    if (decision.input_type === "unsupported") {
      return false;
    }
    const selection = getCurrentSelection(decision);
    if (decision.input_type === "text") {
      return Boolean(String(selection.text || "").trim());
    }
    return Boolean(selection.optionId);
  };

  const getPendingDecisions = () => decisions.filter((decision) => !isDecisionResolved(decision));
  const hasPendingChoices = () => getPendingDecisions().length > 0;
  const emitPendingChange = () => {
    document.dispatchEvent(new CustomEvent("learn:choices-updated", {
      detail: { pendingCount: getPendingDecisions().length },
    }));
  };

  const appendHiddenInput = ({ decision, option = null, value = "" }) => {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = option ? option.submit_name : decision.text_submit_name;
    input.value = option ? option.submit_value : value;
    input.dataset.choiceDecisionId = decision.decision_id;
    input.dataset.choiceSelectionGroup = decision.selection_group_id || "";
    if (option) {
      input.dataset.choiceOptionId = option.id;
    }
    hiddenInputContainer.appendChild(input);
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

    Array.from(hiddenInputContainer.querySelectorAll('input[data-choice-decision-id]')).forEach((input) => {
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

  const buildOptionLabel = (decision, option, selectedOptionId, takenOptionIds) => {
    const label = document.createElement("label");
    label.className = "learn_choice_option";
    label.dataset.choiceSearch = normalizeSearchText([
      option.label || "",
      option.meta || "",
      option.description || "",
    ].join(" "));

    const input = document.createElement("input");
    input.type = "radio";
    input.name = `learnChoiceSelection-${decision.decision_id}`;
    input.value = option.id;
    input.checked = selectedOptionId === option.id;

    const takenElsewhere = takenOptionIds.has(option.id) && selectedOptionId !== option.id;
    if (takenElsewhere) {
      input.disabled = true;
      label.classList.add("is-disabled");
    }

    const body = document.createElement("span");
    const title = document.createElement("span");
    title.className = "learn_choice_option_title";
    title.textContent = option.label;
    body.appendChild(title);

    if (option.meta) {
      const meta = document.createElement("span");
      meta.className = "learn_choice_option_meta";
      meta.textContent = option.meta;
      body.appendChild(meta);
    }

    if (option.description) {
      const description = document.createElement("span");
      description.className = "learn_choice_option_description";
      description.textContent = option.description;
      body.appendChild(description);
    }

    label.appendChild(input);
    label.appendChild(body);
    return label;
  };

  const isDecisionResolvedInSection = (section, decision) => {
    if (!(section instanceof HTMLElement)) {
      return isDecisionResolved(decision);
    }
    if (decision.input_type === "unsupported") {
      return false;
    }
    if (decision.input_type === "text") {
      const input = section.querySelector(`#learnChoiceText-${decision.decision_id}`);
      if (input instanceof HTMLInputElement) {
        return Boolean(String(input.value || "").trim());
      }
      return isDecisionResolved(decision);
    }
    const selectedInput = section.querySelector(`input[name="learnChoiceSelection-${decision.decision_id}"]:checked`);
    if (selectedInput instanceof HTMLInputElement) {
      return true;
    }
    return isDecisionResolved(decision);
  };

  const updateDecisionResolvedState = (section, decision) => {
    if (!(section instanceof HTMLElement)) {
      return;
    }
    section.classList.toggle("is-resolved", isDecisionResolvedInSection(section, decision));
  };

  const buildDecisionSection = (decision, pendingDecisionIds, index) => {
    const section = document.createElement("details");
    section.className = "learn_choice_decision";
    section.dataset.choiceDecisionId = decision.decision_id;
    section.open = index === 0;

    const toggle = document.createElement("summary");
    toggle.className = "learn_choice_decision_toggle";

    const toggleText = document.createElement("div");
    toggleText.className = "learn_choice_decision_toggle_text";

    const title = document.createElement("span");
    title.className = "learn_choice_decision_title";
    title.textContent = decision.title || "Ausstehende Entscheidung";
    toggleText.appendChild(title);

    const summary = document.createElement("span");
    summary.className = "learn_choice_decision_summary";
    summary.textContent = decision.summary || decision.prompt || "Auswahl treffen";
    toggleText.appendChild(summary);

    toggle.appendChild(toggleText);
    section.appendChild(toggle);

    const body = document.createElement("div");
    body.className = "learn_choice_decision_body";

    if (decision.description) {
      const description = document.createElement("p");
      description.className = "learn_choice_decision_description";
      description.textContent = decision.description;
      body.appendChild(description);
    }

    const prompt = document.createElement("p");
    prompt.className = "learn_choice_decision_prompt";
    prompt.textContent = decision.prompt || "Auswahl treffen";
    body.appendChild(prompt);

    if (decision.input_type === "unsupported") {
      section.classList.add("is-unsupported");
      const note = document.createElement("p");
      note.className = "learn_choice_decision_note";
      note.textContent = decision.description || "Dieser Auswahltyp ist derzeit im Lernmenue noch nicht direkt belegbar.";
      body.appendChild(note);
      section.appendChild(body);
      return section;
    }

    const selection = getCurrentSelection(decision);
    const takenOptionIds = getTakenOptionIds(decision.selection_group_id || "", pendingDecisionIds);

    if (decision.input_type === "text") {
      const wrap = document.createElement("div");
      wrap.className = "learn_choice_text_wrap";
      const label = document.createElement("label");
      label.className = "learn_choice_text_label";
      label.htmlFor = `learnChoiceText-${decision.decision_id}`;
      label.textContent = "Eintrag";
      wrap.appendChild(label);

      const input = document.createElement("input");
      input.type = "text";
      input.id = `learnChoiceText-${decision.decision_id}`;
      input.className = "learn_inline_text learn_choice_text_input";
      input.autocomplete = "off";
      input.placeholder = decision.text_placeholder || "Eintrag";
      input.value = selection.text || "";
      input.addEventListener("input", () => {
        updateDecisionResolvedState(section, decision);
      });
      wrap.appendChild(input);
      body.appendChild(wrap);
      section.appendChild(body);
      updateDecisionResolvedState(section, decision);
      return section;
    }

    let searchInput = null;
    if (decision.options.length > 5) {
      searchInput = document.createElement("input");
      searchInput.type = "search";
      searchInput.className = "learn_inline_text learn_choice_search_input";
      searchInput.autocomplete = "off";
      searchInput.placeholder = "Auswahl durchsuchen";
      searchInput.setAttribute("aria-label", `${decision.title || "Auswahl"} durchsuchen`);
      body.appendChild(searchInput);
    }

    const options = document.createElement("fieldset");
    options.className = "learn_choice_options";
    decision.options.forEach((option) => {
      options.appendChild(buildOptionLabel(decision, option, selection.optionId, takenOptionIds));
    });
    const optionEntries = Array.from(options.querySelectorAll(".learn_choice_option"));
    const emptyState = document.createElement("p");
    emptyState.className = "learn_choice_search_empty";
    emptyState.textContent = "Keine passende Option gefunden.";
    emptyState.hidden = true;

    if (searchInput instanceof HTMLInputElement) {
      const applyOptionFilter = () => {
        const needle = normalizeSearchText(String(searchInput.value || "").trim());
        let visibleCount = 0;
        optionEntries.forEach((entry) => {
          if (!(entry instanceof HTMLElement)) {
            return;
          }
          const haystack = entry.dataset.choiceSearch || "";
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
    }

    options.addEventListener("change", () => {
      updateDecisionResolvedState(section, decision);
    });
    body.appendChild(options);
    body.appendChild(emptyState);
    section.appendChild(body);
    updateDecisionResolvedState(section, decision);
    return section;
  };

  const renderPendingDecisions = () => {
    const pendingDecisions = getPendingDecisions();
    const pendingDecisionIds = pendingDecisions.map((decision) => decision.decision_id);
    titleEl.textContent = pendingDecisions.length > 1 ? "Ausstehende Entscheidungen" : "Ausstehende Entscheidung";
    introEl.textContent = pendingDecisions.length > 1
      ? "Alle offenen Choices sind hier gebuendelt und koennen in einem gemeinsamen Fenster bearbeitet werden."
      : "Diese offene Choice wird als eigener Entscheidungsvorgang behandelt.";
    decisionListEl.replaceChildren();
    setHint("");

    pendingDecisions.forEach((decision, index) => {
      decisionListEl.appendChild(buildDecisionSection(decision, pendingDecisionIds, index));
    });

    confirmBtn.disabled = pendingDecisions.length === 0;
    return pendingDecisions;
  };

  const collectPendingValues = (pendingDecisions) => {
    const results = [];
    const missing = [];
    const groupedSelections = new Map();

    for (const decision of pendingDecisions) {
      if (decision.input_type === "unsupported") {
        continue;
      }

      if (decision.input_type === "text") {
        const input = formEl.querySelector(`#learnChoiceText-${decision.decision_id}`);
        const value = input instanceof HTMLInputElement ? String(input.value || "").trim() : "";
        if (!value) {
          missing.push(decision.title || "Ausstehende Entscheidung");
          continue;
        }
        results.push({ decision, value });
        continue;
      }

      const selectedInput = formEl.querySelector(`input[name="learnChoiceSelection-${decision.decision_id}"]:checked`);
      if (!(selectedInput instanceof HTMLInputElement)) {
        missing.push(decision.title || "Ausstehende Entscheidung");
        continue;
      }

      const option = decision.options.find((entry) => entry.id === selectedInput.value);
      if (!option) {
        missing.push(decision.title || "Ausstehende Entscheidung");
        continue;
      }

      if (decision.selection_group_id) {
        const existing = groupedSelections.get(decision.selection_group_id) || new Set();
        if (existing.has(option.id)) {
          return {
            ok: false,
            hint: "Dieselbe Option kann in einer gemeinsamen Choice-Gruppe nicht mehrfach gleichzeitig gewaehlt werden.",
          };
        }
        existing.add(option.id);
        groupedSelections.set(decision.selection_group_id, existing);
      }

      results.push({ decision, option });
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
    const pendingDecisions = getPendingDecisions();
    const collected = collectPendingValues(pendingDecisions);
    if (!collected.ok) {
      setHint(collected.hint || "Bitte alle offenen Entscheidungen ausfuellen.");
      return false;
    }

    pendingDecisions.forEach((decision) => {
      clearDecisionInputs(decision.decision_id);
    });

    collected.results.forEach((entry) => {
      if (entry.option) {
        appendHiddenInput({ decision: entry.decision, option: entry.option });
        return;
      }
      appendHiddenInput({ decision: entry.decision, value: entry.value || "" });
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
    const pendingDecisions = renderPendingDecisions();
    if (!pendingDecisions.length) {
      closeModal();
      return false;
    }
    openModal();
    return true;
  };

  formEl.addEventListener("submit", (event) => {
    event.preventDefault();
    applyPendingDecisions();
  });

  cancelBtn?.addEventListener("click", () => {
    closeModal();
  });

  emitPendingChange();

  return {
    emitPendingChange,
    getPendingDecisions,
    hasPendingChoices,
    openDecision: openPendingChoices,
    openNextPendingChoice: openPendingChoices,
    openPendingChoices,
  };
}




