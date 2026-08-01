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

  function readAllAreaOptions(select) {
    if (!select._daemonicAllAreaOptions) {
      select._daemonicAllAreaOptions = Array.prototype.map.call(select.options, function (option) {
        return { value: option.value, text: option.text };
      });
    }
    return select._daemonicAllAreaOptions;
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

  function syncApplicationScope(root) {
    var scope = root.querySelector('[name$="application_scope"]');
    var area = root.querySelector('[name$="effect_area"]');
    if (!scope || !area) {
      return;
    }
    var creatureOnlyAreas = {
      special_skill: true,
      choice_attack_damage: true,
      attack_type_damage: true
    };
    var options = readAllAreaOptions(area);
    if (scope.value !== "creature") {
      options = options.filter(function (option) {
        return !creatureOnlyAreas[option.value];
      });
    }
    rebuildOptions(area, options, area.value);
  }

  function syncEffectForm(root) {
    if (isEmptyTemplate(root)) {
      return;
    }
    var area = root.querySelector('[name$="effect_area"]');
    if (!area) {
      return;
    }
    syncApplicationScope(root);
    var isChoice = area.value === "choice" || area.value === "choice_attack_damage";
    var isDisallowSchools = area.value === "disallow_schools";
    var isMovementExclusion = area.value === "movement_exclusion";
    var semanticOperators = {
      rule_flag: ["set_flag", "unset_flag"],
      capability: ["grant_capability", "remove_capability"],
      disallow_schools: ["remove_capability"],
      movement_exclusion: ["unset_flag"]
    };
    var operator = root.querySelector('[name$="simple_operator"]');
    if (operator) {
      var allowed = semanticOperators[area.value];
      var operatorOptions = readAllOptions(operator);
      if (allowed) {
        operatorOptions = operatorOptions.filter(function (option) {
          return option.value === "" || allowed.indexOf(option.value) !== -1;
        });
      } else {
        operatorOptions = operatorOptions.filter(function (option) {
          return ["", "flat_add", "flat_sub", "multiply", "floor_divide", "override", "min_value", "max_value"].indexOf(option.value) !== -1;
        });
      }
      rebuildOptions(operator, operatorOptions, operator.value);
    }
    var isSemanticBoolean = Boolean(semanticOperators[area.value]);
    setRowVisible(root, "simple_target", !isChoice && !isDisallowSchools);
    setRowVisible(root, "target_schools", isDisallowSchools);
    setRowVisible(root, "target_choice_definition", isChoice);
    setRowVisible(root, "simple_operator", !isDisallowSchools && !isMovementExclusion);
    setRowVisible(root, "simple_value", !isSemanticBoolean && !isDisallowSchools);
    if (!isChoice && !isDisallowSchools) {
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
    var scope = root.querySelector('[name$="application_scope"]');
    if (scope) {
      scope.addEventListener("change", function () {
        syncEffectForm(root);
      });
    }
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
