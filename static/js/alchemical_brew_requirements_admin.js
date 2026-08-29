(() => {
  "use strict";

  const parseJson = (value, fallback = []) => {
    try {
      const parsed = JSON.parse(value || "[]");
      return Array.isArray(parsed) ? parsed : fallback;
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

      return {
        target: target ? target.value : "",
        level: level
          ? Number.parseInt(level.value || "0", 10)
          : 0,
      };
    });

    input.value = JSON.stringify(requirements);
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

    targetSelect.dataset.brewRequirementTarget = "1";
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
    levelInput.dataset.brewRequirementLevel = "1";
    levelInput.style.width = "90px";

    const removeButton =
      document.createElement("button");

    removeButton.type = "button";
    removeButton.className = "button";
    removeButton.textContent = "Entfernen";
    removeButton.dataset.brewRequirementRemove = "1";

    if (requirement) {
      targetSelect.value =
        requirement.target || "";

      if (requirement.level) {
        levelInput.value =
          requirement.level;
      }
    }

    row.appendChild(targetSelect);
    row.appendChild(levelInput);
    row.appendChild(removeButton);

    list.appendChild(row);

    syncEditor(editor);
  };

  const initializeEditor = (input) => {
    const container = getContainer(input);

    if (!container) {
      return;
    }

    /*
     * Nicht nur auf ein data-initialized-Flag verlassen.
     * Django kann Inline-DOM klonen.
     */
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

  /*
   * Event Delegation:
   * Die Listener sitzen am document und nicht an den
   * von Django möglicherweise geklonten Buttons.
   */
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
      if (
        !event.target.matches(
          "[data-brew-requirement-target]",
        )
      ) {
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

  document.addEventListener(
    "input",
    (event) => {
      if (
        !event.target.matches(
          "[data-brew-requirement-level]",
        )
      ) {
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