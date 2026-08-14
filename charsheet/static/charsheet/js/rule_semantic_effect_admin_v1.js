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

  function field(root, fieldName) {
    return root.querySelector('[name$="' + fieldName + '"]');
  }

  function fieldHasValue(root, fieldName) {
    var input = field(root, fieldName);
    if (!input) {
      return false;
    }
    if (input.type === "checkbox") {
      return input.checked;
    }
    if (input.tagName === "SELECT" && input.multiple) {
      return Array.prototype.some.call(input.options, function (option) {
        return option.selected;
      });
    }
    return String(input.value || "").trim() !== "";
  }

  function readAllOptions(select) {
    if (!select._ruleSemanticAllOptions) {
      select._ruleSemanticAllOptions = Array.prototype.map.call(select.options, function (option) {
        return { value: option.value, text: option.text };
      });
    }
    return select._ruleSemanticAllOptions;
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
    var prefix = area.value + ":";
    var options = readAllOptions(target).filter(function (option) {
      return option.value === "" || option.value.indexOf(prefix) === 0;
    });
    rebuildOptions(target, options, target.value);
  }

  function syncOperator(root) {
    var area = root.querySelector('[name$="effect_area"]');
    var operator = root.querySelector('[name$="simple_operator"]');
    if (!area || !operator) {
      return;
    }
    var allowed = area.value === "rule_flag"
      ? ["", "set_flag", "unset_flag"]
      : ["", "flat_add", "flat_sub", "multiply", "floor_divide", "override", "min_value", "max_value"];
    var options = readAllOptions(operator).filter(function (option) {
      return allowed.indexOf(option.value) !== -1;
    });
    rebuildOptions(operator, options, operator.value);
  }

  function syncScaling(root) {
    var area = field(root, "effect_area");
    var scaling = field(root, "simple_scaling");
    if (!area || !scaling) {
      return;
    }
    var allowedByArea = {
      rule_flag: [""],
      item: ["", "fame_total", "rune_crafter_level"],
      item_category: ["", "fame_total", "rune_crafter_level"],
      specialization: ["", "school_level", "skill_level", "skill_total"],
      skill: ["", "school_level", "trait_level", "fame_total", "rune_crafter_level"],
      skill_category: ["", "school_level", "trait_level", "fame_total", "rune_crafter_level"],
      weapon: ["", "school_level", "skill_level", "skill_total", "rune_crafter_level"],
      weapon_type: ["", "school_level", "skill_level", "skill_total", "rune_crafter_level"],
      damage_source: ["", "school_level", "skill_level", "skill_total", "rune_crafter_level"]
    };
    var allowed = allowedByArea[area.value] || ["", "school_level", "skill_level", "skill_total", "trait_level", "fame_total", "rune_crafter_level"];
    var options = readAllOptions(scaling).filter(function (option) {
      return allowed.indexOf(option.value) !== -1;
    });
    rebuildOptions(scaling, options, scaling.value);
  }

  function hasSelectableScaling(root) {
    var scaling = field(root, "simple_scaling");
    if (!scaling) {
      return false;
    }
    return Array.prototype.some.call(scaling.options, function (option) {
      return option.value !== "";
    });
  }

  function syncEffectForm(root) {
    if (isEmptyTemplate(root)) {
      return;
    }
    var area = root.querySelector('[name$="effect_area"]');
    if (!area) {
      return;
    }
    var isRuleFlag = area.value === "rule_flag";
    var scaling = field(root, "simple_scaling");
    var hasScaling = scaling && scaling.value !== "";
    var needsSchool = scaling && scaling.value === "school_level";
    var needsSkill = scaling && (scaling.value === "skill_level" || scaling.value === "skill_total");
    var hasChoiceBinding = fieldHasValue(root, "target_choice_definition") || fieldHasValue(root, "target_race_choice_definition");
    var hasMultiSkill = fieldHasValue(root, "target_skills");
    var hasCondition = fieldHasValue(root, "applies_during_character_creation")
      || fieldHasValue(root, "applies_in_combat")
      || fieldHasValue(root, "applies_outside_combat");
    var hasText = fieldHasValue(root, "notes") || fieldHasValue(root, "rules_text");

    syncSimpleTarget(root);
    syncOperator(root);
    syncScaling(root);

    setRowVisible(root, "simple_target", true);
    setRowVisible(root, "simple_operator", true);
    setRowVisible(root, "simple_value", !isRuleFlag);
    setRowVisible(root, "target_choice_definition", hasChoiceBinding);
    setRowVisible(root, "target_race_choice_definition", hasChoiceBinding);
    setRowVisible(root, "target_skills", hasMultiSkill);
    setRowVisible(root, "simple_scaling", hasScaling || hasSelectableScaling(root));
    setRowVisible(root, "simple_scale_school", needsSchool);
    setRowVisible(root, "simple_scale_skill", needsSkill);
    setRowVisible(root, "simple_scale_divisor", hasScaling);
    setRowVisible(root, "applies_during_character_creation", hasCondition);
    setRowVisible(root, "applies_in_combat", hasCondition);
    setRowVisible(root, "applies_outside_combat", hasCondition);
    setRowVisible(root, "notes", hasText);
    setRowVisible(root, "rules_text", hasText && fieldHasValue(root, "rules_text"));
  }

  function bind(root) {
    if (!root || isEmptyTemplate(root)) {
      return;
    }
    var area = root.querySelector('[name$="effect_area"]');
    if (!area || area._ruleSemanticEffectBoundV1) {
      return;
    }
    area._ruleSemanticEffectBoundV1 = true;
    area.addEventListener("change", function () {
      syncEffectForm(root);
    });
    var scaling = root.querySelector('[name$="simple_scaling"]');
    if (scaling) {
      scaling.addEventListener("change", function () {
        syncEffectForm(root);
      });
    }
    syncEffectForm(root);
  }

  function bindAll() {
    var rows = document.querySelectorAll(".inline-related:not(.empty-form)");
    Array.prototype.forEach.call(rows, bind);
    if (!rows.length) {
      var area = document.querySelector('form [name$="effect_area"]:not([name*="__prefix__"])');
      if (area) {
        bind(area.closest("form"));
      }
    }
  }

  document.addEventListener("DOMContentLoaded", bindAll);
  document.addEventListener("formset:added", function (event) {
    bind(event.target);
  });
})();
