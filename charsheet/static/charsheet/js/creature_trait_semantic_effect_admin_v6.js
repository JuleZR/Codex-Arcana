(function () {
  function isEmptyTemplate(root) {
    return root && root.classList && root.classList.contains("empty-form");
  }

  function fieldRow(root, fieldName) {
    var classRow = root.querySelector(".field-" + fieldName);
    if (classRow) {
      return classRow;
    }
    var input = root.querySelector('[name$="' + fieldName + '"]');
    return input ? input.closest(".form-row, .fieldBox, div") : null;
  }

  function setRowVisible(root, fieldName, visible) {
    var row = fieldRow(root, fieldName);
    if (row) {
      row.hidden = !visible;
      row.style.display = visible ? "" : "none";
    }
  }

  function readAllOptions(select) {
    if (!select._creatureAllTargetOptions) {
      select._creatureAllTargetOptions = Array.prototype.map.call(select.options, function (option) {
        return { value: option.value, text: option.text };
      });
    }
    return select._creatureAllTargetOptions;
  }

  function rebuildOptions(select, options, currentValue) {
    while (select.options.length) {
      select.remove(0);
    }
    options.forEach(function (option) {
      var node = document.createElement("option");
      node.value = option.value;
      node.text = option.text;
      select.add(node);
    });
    select.value = options.some(function (option) { return option.value === currentValue; }) ? currentValue : "";
  }

  function syncSimpleTarget(root) {
    var area = root.querySelector('[name$="effect_area"]');
    var target = root.querySelector('[name$="simple_target"]');
    if (!area || !target) {
      return;
    }
    var visiblePrefix = area.value + ":";
    var filteredOptions = readAllOptions(target).filter(function (option) {
      return option.value === "" || option.value.indexOf(visiblePrefix) === 0;
    });
    rebuildOptions(target, filteredOptions, target.value);
  }

  function syncEffectForm(root) {
    if (isEmptyTemplate(root)) {
      return;
    }
    var area = root.querySelector('[name$="effect_area"]');
    if (!area) {
      return;
    }
    var isChoice = area.value === "choice";
    setRowVisible(root, "simple_target", !isChoice);
    setRowVisible(root, "target_choice_definition", isChoice);
    if (!isChoice) {
      syncSimpleTarget(root);
    }
  }

  function bind(root) {
    if (isEmptyTemplate(root)) {
      return;
    }
    var area = root.querySelector('[name$="effect_area"]');
    if (!area || area._creatureEffectBoundV6) {
      return;
    }
    area._creatureEffectBoundV6 = true;
    area.addEventListener("change", function () {
      syncEffectForm(root);
    });
    syncEffectForm(root);
  }

  function bindAll() {
    var inlineRows = document.querySelectorAll(".inline-related:not(.empty-form)");
    Array.prototype.forEach.call(inlineRows, bind);

    if (document.querySelector(".inline-related")) {
      return;
    }
    var standaloneArea = document.querySelector('form [name$="effect_area"]:not([name*="__prefix__"])');
    if (standaloneArea) {
      bind(standaloneArea.closest("form"));
    }
  }

  document.addEventListener("DOMContentLoaded", bindAll);
  document.addEventListener("formset:added", function (event) {
    bind(event.target);
  });
})();
