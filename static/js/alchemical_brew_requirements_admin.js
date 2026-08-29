(() => {
  "use strict";

  const parseJson = (value, fallback = []) => {
    try {
      const parsed = JSON.parse(value || "[]");
      return Array.isArray(parsed)
        ? parsed
        : fallback;
    } catch (_error) {
      return fallback;
    }
  };

  const createOption = (value, label) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    return option;
  };

  const createOptGroup = (label, options) => {
    const group = document.createElement("optgroup");
    group.label = label;

    options.forEach((entry) => {
      group.appendChild(
        createOption(
          entry.value,
          entry.label,
        ),
      );
    });

    return group;
  };

  const getContainer = (input) => (
    input.closest(".form-row")
    || input.parentElement
  );

  const getEditorInput = (editor) => {
    const container = editor.parentElement;

    if (!container) {
      return null;
    }

    return container.querySelector(
      ".alchemical-brew-requirements-data",
    );
  };

  const updateAlternativeUi = (row) => {
    const alternative = row.querySelector(
      "[data-brew-requirement-alternative]",
    );

    const group = row.querySelector(
      "[data-brew-requirement-group]",
    );

    if (!alternative || !group) {
      return;
    }

    group.disabled = !alternative.checked;
    group.style.display = alternative.checked
      ? ""
      : "none";
  };

  const syncEditor = (editor) => {
    const input = getEditorInput(editor);

    if (!input) {
      return;
    }

    const rows = Array.from(
      editor.querySelectorAll(
        "[data-brew-requirement-row]",
      ),
    );

    const requirements = rows.map((row) => {
      const target = row.querySelector(
        "[data-brew-requirement-target]",
      );

      const level = row.querySelector(
        "[data-brew-requirement-level]",
      );

      const alternative = row.querySelector(
        "[data-brew-requirement-alternative]",
      );

      const group = row.querySelector(
        "[data-brew-requirement-group]",
      );

      const isAlternative = Boolean(
        alternative && alternative.checked,
      );

      return {
        target: target
          ? target.value
          : "",

        level: level
          ? Number.parseInt(
              level.value || "0",
              10,
            )
          : 0,

        is_alternative: isAlternative,

        alternative_group: (
          isAlternative
          && group
          && group.value
        )
          ? Number.parseInt(
              group.value,
              10,
            )
          : null,
      };
    });

    input.value = JSON.stringify(
      requirements,
    );
  };

  const addRow = (
    editor,
    requirement = null,
  ) => {
    const input = getEditorInput(editor);

    if (!input) {
      return;
    }

    const skills = parseJson(
      input.dataset.skills,
    );

    const schools = parseJson(
      input.dataset.schools,
    );

    const aspects = parseJson(
      input.dataset.aspects,
    );

    const list = editor.querySelector(
      "[data-brew-requirements-list]",
    );

    if (!list) {
      return;
    }

    const row = document.createElement("div");

    row.dataset.brewRequirementRow = "1";

    row.style.display = "flex";
    row.style.gap = "8px";
    row.style.alignItems = "center";
    row.style.marginBottom = "8px";

    const targetSelect =
      document.createElement("select");

    targetSelect.dataset.brewRequirementTarget =
      "1";

    targetSelect.style.minWidth = "300px";

    targetSelect.appendChild(
      createOption(
        "",
        "---------",
      ),
    );

    targetSelect.appendChild(
      createOptGroup(
        "Fertigkeiten",
        skills,
      ),
    );

    targetSelect.appendChild(
      createOptGroup(
        "Arkane Schulen",
        schools,
      ),
    );

    targetSelect.appendChild(
      createOptGroup(
        "Aspekte",
        aspects,
      ),
    );

    const levelInput =
      document.createElement("input");

    levelInput.type = "number";
    levelInput.min = "1";
    levelInput.step = "1";

    levelInput.dataset.brewRequirementLevel =
      "1";

    levelInput.style.width = "90px";

    const alternativeLabel =
      document.createElement("label");

    alternativeLabel.style.display = "flex";
    alternativeLabel.style.alignItems = "center";
    alternativeLabel.style.gap = "4px";
    alternativeLabel.style.whiteSpace = "nowrap";

    const alternativeInput =
      document.createElement("input");

    alternativeInput.type = "checkbox";

    alternativeInput.dataset
      .brewRequirementAlternative = "1";

    const alternativeText =
      document.createElement("span");

    alternativeText.textContent = "ODER";

    alternativeLabel.appendChild(
      alternativeInput,
    );

    alternativeLabel.appendChild(
      alternativeText,
    );

    const groupInput =
      document.createElement("input");

    groupInput.type = "number";
    groupInput.min = "1";
    groupInput.step = "1";
    groupInput.placeholder = "Gruppe";

    groupInput.dataset.brewRequirementGroup =
      "1";

    groupInput.style.width = "90px";

    const removeButton =
      document.createElement("button");

    removeButton.type = "button";
    removeButton.className = "button";
    removeButton.textContent = "Entfernen";

    removeButton.dataset.brewRequirementRemove =
      "1";

    if (requirement) {
      targetSelect.value =
        requirement.target || "";

      if (requirement.level) {
        levelInput.value =
          requirement.level;
      }

      alternativeInput.checked = Boolean(
        requirement.is_alternative
        || (
          requirement.alternative_group
          !== null
          && requirement.alternative_group
          !== undefined
        )
      );

      if (requirement.alternative_group) {
        groupInput.value =
          requirement.alternative_group;
      }
    }

    row.appendChild(targetSelect);
    row.appendChild(levelInput);
    row.appendChild(alternativeLabel);
    row.appendChild(groupInput);
    row.appendChild(removeButton);

    list.appendChild(row);

    updateAlternativeUi(row);
    syncEditor(editor);
  };

  const initializeEditor = (input) => {
    const container = getContainer(input);

    if (!container) {
      return;
    }

    if (
      container.querySelector(
        ".alchemical-brew-requirements-editor",
      )
    ) {
      return;
    }

    const initialRequirements = parseJson(
      input.value,
    );

    const editor = document.createElement("div");

    editor.className =
      "alchemical-brew-requirements-editor";

    editor.style.marginTop = "8px";

    const list = document.createElement("div");
    list.dataset.brewRequirementsList = "1";

    const addButton =
      document.createElement("button");

    addButton.type = "button";
    addButton.className = "button";

    addButton.textContent =
      "+ Voraussetzung hinzufügen";

    addButton.dataset.brewRequirementAdd = "1";
    addButton.style.marginTop = "6px";

    editor.appendChild(list);
    editor.appendChild(addButton);

    container.appendChild(editor);

    initialRequirements.forEach(
      (requirement) => {
        addRow(
          editor,
          requirement,
        );
      },
    );
  };

  const initializeAllEditors = () => {
    document
      .querySelectorAll(
        ".alchemical-brew-requirements-data",
      )
      .forEach(initializeEditor);
  };

  document.addEventListener(
    "click",
    (event) => {
      const addButton = event.target.closest(
        "[data-brew-requirement-add]",
      );

      if (addButton) {
        event.preventDefault();

        const editor = addButton.closest(
          ".alchemical-brew-requirements-editor",
        );

        if (editor) {
          addRow(editor);
        }

        return;
      }

      const removeButton = event.target.closest(
        "[data-brew-requirement-remove]",
      );

      if (!removeButton) {
        return;
      }

      event.preventDefault();

      const editor = removeButton.closest(
        ".alchemical-brew-requirements-editor",
      );

      const row = removeButton.closest(
        "[data-brew-requirement-row]",
      );

      if (row) {
        row.remove();
      }

      if (editor) {
        syncEditor(editor);
      }
    },
  );

  document.addEventListener(
    "change",
    (event) => {
      const isTarget = event.target.matches(
        "[data-brew-requirement-target]",
      );

      const isAlternative = event.target.matches(
        "[data-brew-requirement-alternative]",
      );

      if (!isTarget && !isAlternative) {
        return;
      }

      const row = event.target.closest(
        "[data-brew-requirement-row]",
      );

      if (row && isAlternative) {
        updateAlternativeUi(row);
      }

      const editor = event.target.closest(
        ".alchemical-brew-requirements-editor",
      );

      if (editor) {
        syncEditor(editor);
      }
    },
  );

  document.addEventListener(
    "input",
    (event) => {
      const isLevel = event.target.matches(
        "[data-brew-requirement-level]",
      );

      const isGroup = event.target.matches(
        "[data-brew-requirement-group]",
      );

      if (!isLevel && !isGroup) {
        return;
      }

      const editor = event.target.closest(
        ".alchemical-brew-requirements-editor",
      );

      if (editor) {
        syncEditor(editor);
      }
    },
  );

  const start = () => {
    initializeAllEditors();

    const observer = new MutationObserver(
      () => {
        initializeAllEditors();
      },
    );

    observer.observe(
      document.body,
      {
        childList: true,
        subtree: true,
      },
    );
  };

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      start,
    );
  } else {
    start();
  }
})();