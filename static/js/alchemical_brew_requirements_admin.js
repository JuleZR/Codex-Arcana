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

  const initializeEditor = (input) => {
    if (input.dataset.requirementsInitialized === "1") {
      return;
    }

    input.dataset.requirementsInitialized = "1";

    const skills = parseJson(
      input.dataset.skills,
    );
    const schools = parseJson(
      input.dataset.schools,
    );
    const initialRequirements = parseJson(
      input.value,
    );

    const editor = document.createElement("div");
    editor.className = "alchemical-brew-requirements-editor";

    editor.style.marginTop = "8px";

    const heading = document.createElement("div");
    heading.textContent = "Voraussetzungen";
    heading.style.fontWeight = "600";
    heading.style.marginBottom = "8px";

    const list = document.createElement("div");

    const addButton = document.createElement("button");
    addButton.type = "button";
    addButton.className = "button";
    addButton.textContent = "+ Voraussetzung hinzufügen";
    addButton.style.marginTop = "6px";

    editor.appendChild(list);
    editor.appendChild(addButton);

    const syncValue = () => {
      const rows = Array.from(
        list.querySelectorAll(
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

    const addRow = (requirement = null) => {
      const row = document.createElement("div");
      row.dataset.brewRequirementRow = "1";

      row.style.display = "flex";
      row.style.gap = "8px";
      row.style.alignItems = "center";
      row.style.marginBottom = "8px";

      const targetSelect = document.createElement("select");
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
          "Schulen",
          schools,
        ),
      );

      const levelInput = document.createElement("input");
      levelInput.type = "number";
      levelInput.min = "1";
      levelInput.step = "1";
      levelInput.dataset.brewRequirementLevel = "1";
      levelInput.style.width = "90px";

      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "button";
      removeButton.textContent = "Entfernen";

      if (requirement) {
        targetSelect.value = requirement.target || "";

        if (requirement.level) {
          levelInput.value = requirement.level;
        }
      }

      targetSelect.addEventListener(
        "change",
        syncValue,
      );

      levelInput.addEventListener(
        "input",
        syncValue,
      );

      removeButton.addEventListener(
        "click",
        () => {
          row.remove();
          syncValue();
        },
      );

      row.appendChild(targetSelect);
      row.appendChild(levelInput);
      row.appendChild(removeButton);

      list.appendChild(row);

      syncValue();
    };

    initialRequirements.forEach(
      (requirement) => {
        addRow(requirement);
      },
    );

    addButton.addEventListener(
      "click",
      () => {
        addRow();
      },
    );

    const container = (
      input.closest(".form-row")
      || input.parentElement
    );

    if (container) {
      container.appendChild(editor);
    } else {
      input.insertAdjacentElement(
        "afterend",
        editor,
      );
    }
  };

  const initializeAllEditors = () => {
    document
      .querySelectorAll(
        ".alchemical-brew-requirements-data",
      )
      .forEach(initializeEditor);
  };

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