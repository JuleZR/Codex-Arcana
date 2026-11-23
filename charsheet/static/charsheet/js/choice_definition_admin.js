(function () {
  "use strict";
  if (window.__choiceDefinitionAdminLoaded) return;
  window.__choiceDefinitionAdminLoaded = true;

  function field(root, name) {
    return root.querySelector('[name$="-' + name + '"], [name="' + name + '"]');
  }

  function show(root, name, visible) {
    var box = root.querySelector('.fieldBox.field-' + name) || root.querySelector('.field-' + name);
    if (!box) return;
    box.hidden = !visible;
    box.style.display = visible ? "" : "none";
    box.querySelectorAll('input, select, textarea, button').forEach(function (input) {
      if (!visible && !input.disabled) {
        input.disabled = true;
        input.dataset.choiceDisabled = '1';
      } else if (visible && input.dataset.choiceDisabled) {
        input.disabled = false;
        delete input.dataset.choiceDisabled;
      }
    });
    var row = box.closest('.form-row');
    if (row && row !== box) {
      var anyVisible = Array.from(row.querySelectorAll('.fieldBox')).some(function (item) {
        return !item.hidden;
      });
      row.hidden = !anyVisible;
      row.style.display = anyVisible ? "" : "none";
    }
  }

  function sync(root) {
    var target = field(root, 'target_kind');
    var kinds = [target.value];
    var additional = field(root, 'additional_target_kinds');
    if (additional) {
      kinds = kinds.concat(Array.from(additional.selectedOptions, function (option) { return option.value; }));
    }
    var filters = {
      allowed_attribute: ['attribute'], allowed_attributes: ['attribute'],
      allowed_skill_category: ['skill'], allowed_skill_categories: ['skill'],
      allowed_skills: ['skill'], allowed_creature_special_skills: ['skill'],
      allow_all_creature_special_skills: ['skill'], allowed_skill_family: ['skill'],
      allowed_derived_stat: ['derived_stat'], allowed_resource: ['resource'],
      allowed_proficiency_group: ['proficiency_group'],
      allowed_organization_types: ['entity'], uses_nobility_ranks: ['entity']
    };
    Object.keys(filters).forEach(function (name) {
      show(root, name, filters[name].some(function (kind) { return kinds.includes(kind); }));
    });
    show(root, 'additional_target_kinds', !['text', 'entity'].includes(target.value));
    show(root, 'max_levels_by_target', !['text', 'entity'].includes(target.value));
    root.querySelectorAll('[data-target-limits] select option').forEach(function (option) {
      var visible = !option.value || kinds.includes(option.value.split(':')[0]);
      // Preserve existing limits while the target type is being edited.
      option.hidden = !visible && !option.selected;
      option.disabled = !visible && !option.selected;
    });
  }

  function bind(root) {
    root.querySelectorAll('[name$="-target_kind"], [name="target_kind"]').forEach(function (target) {
      if (target.name.includes('__prefix__') || target.dataset.choiceBound) return;
      target.dataset.choiceBound = '1';
      var form = target.closest('tr.form-row, .inline-related') || target.closest('form');
      form.addEventListener('change', function () { sync(form); });
      form.addEventListener('click', function (event) {
        var limits = event.target.closest('[data-target-limits]');
        if (!limits) return;
        if (event.target.matches('[data-add-limit]')) {
          var row = limits.querySelector('[data-limit-row]').cloneNode(true);
          row.querySelectorAll('input, select').forEach(function (input) {
            input.value = '';
            input.removeAttribute('id');
          });
          limits.insertBefore(row, event.target);
          sync(form);
        }
        if (event.target.matches('[data-remove-limit]')) {
          var removed = event.target.closest('[data-limit-row]');
          if (limits.querySelectorAll('[data-limit-row]').length > 1) removed.remove();
          else removed.querySelectorAll('input, select').forEach(function (input) { input.value = ''; });
        }
      });
      sync(form);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { bind(document); });
  else bind(document);
  document.addEventListener('formset:added', function (event) { bind(event.target); });
}());
