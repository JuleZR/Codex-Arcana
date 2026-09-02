(function () {
  if (window.__itemSemanticEffectAdminV3Loaded) {
    return;
  }
  window.__itemSemanticEffectAdminV3Loaded = true;

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
    if (!select._itemSemanticAllOptions) {
      select._itemSemanticAllOptions = Array.prototype.map.call(select.options, function (option) {
        return { value: option.value, text: option.text };
      });
    }
    return select._itemSemanticAllOptions;
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

    var semanticOperators = {
      rule_flag: ["set_flag", "unset_flag"]
    };
    var isTextOnly = area.value === "text";
    var isWeaponRange = area.value === "weapon_range";
    var operator = root.querySelector('[name$="simple_operator"]');
    var scaleSource = root.querySelector('[name$="scale_source"]');
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

    setRowVisible(root, "simple_target", !isTextOnly);
    setRowVisible(root, "simple_operator", !isTextOnly);
    setRowVisible(root, "simple_weapon_category_filter", isWeaponRange);
    setRowVisible(root, "simple_weapon_type_filter", isWeaponRange);
    setRowVisible(root, "simple_weapon_type_contains_filter", isWeaponRange);
    setRowVisible(root, "simple_weapon_item_filter", isWeaponRange);
    setRowVisible(root, "rules_text", true);
    setRowVisible(root, "simple_value", !isTextOnly && !semanticOperators[area.value]);
    setRowVisible(root, "scale_divisor", !isTextOnly && scaleSource && scaleSource.value !== "");
    if (!isTextOnly) {
      syncSimpleTarget(root);
    }
  }

  function bind(root) {
    if (isEmptyTemplate(root)) {
      return;
    }
    var area = root.querySelector('[name$="effect_area"]');
    if (!area || area._itemSemanticEffectBoundV3) {
      return;
    }
    area._itemSemanticEffectBoundV3 = true;
    area.addEventListener("change", function () {
      syncEffectForm(root);
    });
    var scaleSource = root.querySelector('[name$="scale_source"]');
    if (scaleSource && !scaleSource._itemSemanticEffectBoundV3) {
      scaleSource._itemSemanticEffectBoundV3 = true;
      scaleSource.addEventListener("change", function () {
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
