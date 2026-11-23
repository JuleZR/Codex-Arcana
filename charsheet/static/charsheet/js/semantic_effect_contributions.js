(function () {
  "use strict";
  if (window.__semanticContributionsLoaded) return;
  window.__semanticContributionsLoaded = true;

  function field(root, name) {
    return root.querySelector('[name$="-' + name + '"], [name="' + name + '"]');
  }

  function show(root, name, visible) {
    var box = root.querySelector('.fieldBox.field-' + name) || root.querySelector('.field-' + name);
    if (!box) return;
    box.hidden = !visible;
    box.style.display = visible ? '' : 'none';
    var row = box.closest('.form-row');
    if (row && row !== box) {
      var anyVisible = Array.from(row.querySelectorAll('.fieldBox')).some(function (item) { return !item.hidden; });
      row.hidden = !anyVisible;
      row.style.display = anyVisible ? '' : 'none';
    }
  }

  function sync(root) {
    var area = field(root, 'effect_area');
    var applicable = area && area.value === 'derived_stat';
    var contributions = root.querySelectorAll('[name$="-calculation_contributions"], [name="calculation_contributions"]');
    var selected = false;
    contributions.forEach(function (input) {
      input.disabled = !applicable;
      selected = selected || input.checked;
    });
    var operation = field(root, 'contribution_operation');
    if (!operation) return;
    operation.disabled = !applicable || !selected;
    show(root, 'calculation_contributions', applicable);
    show(root, 'contribution_operation', applicable && selected);
    if (applicable) {
      var custom = selected && operation.value !== '';
      var ignore = custom && ['ignore', 'ignore_positive', 'ignore_negative'].includes(operation.value);
      show(root, 'simple_operator', !custom);
      show(root, 'simple_value', !ignore);
    }
  }

  function bind(root) {
    root.querySelectorAll('[name$="-contribution_operation"], [name="contribution_operation"]').forEach(function (input) {
      if (input.name.includes('__prefix__') || input.dataset.contributionBound) return;
      input.dataset.contributionBound = '1';
      var form = input.closest('.inline-related') || input.closest('form');
      form.addEventListener('change', function () { sync(form); });
      queueMicrotask(function () { sync(form); });
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { bind(document); });
  else bind(document);
  document.addEventListener('formset:added', function (event) { bind(event.target); });
}());
