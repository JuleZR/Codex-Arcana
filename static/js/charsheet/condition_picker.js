(function () {
  if (window.__magicConditionPickersLoaded) return;
  window.__magicConditionPickersLoaded = true;

  function initialize(picker) {
    if (picker.dataset.conditionPickerReady) return;
    const source = picker.querySelector("[data-condition-source]");
    const available = picker.querySelector("[data-condition-available]");
    const selected = picker.querySelector("[data-condition-selected]");
    const add = picker.querySelector("[data-condition-add]");
    const remove = picker.querySelector("[data-condition-remove]");
    const count = picker.querySelector("[data-condition-count]");
    const toggle = picker.querySelector("[data-condition-toggle]");
    const fields = picker.querySelector("[data-condition-fields]");
    if (!source || !available || !selected || !add || !remove) return;
    picker.dataset.conditionPickerReady = "1";
    let remembered = [];
    if (toggle) toggle.checked = source.selectedOptions.length > 0;

    function updateButtons() {
      add.disabled = !available.selectedOptions.length;
      remove.disabled = !selected.selectedOptions.length;
      if (count) count.textContent = `(${selected.options.length})`;
    }

    function sync() {
      available.replaceChildren();
      selected.replaceChildren();
      const groups = new Map();
      Array.from(source.options).forEach((option) => {
        const copy = option.cloneNode(true);
        copy.selected = false;
        const destination = option.selected ? selected : available;
        const group = option.dataset.conditionGroup;
        if (!group) {
          destination.appendChild(copy);
          return;
        }
        const key = `${option.selected}:${group}`;
        if (!groups.has(key)) {
          const optgroup = document.createElement("optgroup");
          optgroup.label = group;
          destination.appendChild(optgroup);
          groups.set(key, optgroup);
        }
        groups.get(key).appendChild(copy);
      });
      updateButtons();
      if (toggle && fields) {
        if (source.selectedOptions.length) toggle.checked = true;
        fields.hidden = !toggle.checked;
      }
    }

    function move(from, enabled) {
      const values = new Set(Array.from(from.selectedOptions, option => option.value));
      if (!values.size) return;
      Array.from(source.options).forEach((option) => {
        if (values.has(option.value)) option.selected = enabled;
      });
      source.dispatchEvent(new Event("change", { bubbles: true }));
    }

    add.addEventListener("click", () => move(available, true));
    remove.addEventListener("click", () => move(selected, false));
    [[available, true], [selected, false]].forEach(([list, enabled]) => {
      list.addEventListener("change", updateButtons);
      list.addEventListener("dblclick", () => move(list, enabled));
      list.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        move(list, enabled);
      });
    });
    source.addEventListener("change", sync);
    toggle?.addEventListener("change", () => {
      if (!toggle.checked) {
        remembered = Array.from(source.selectedOptions, option => option.value);
      }
      const values = new Set(remembered);
      Array.from(source.options).forEach(option => {
        option.selected = toggle.checked && values.has(option.value);
      });
      source.dispatchEvent(new Event("change", { bubbles: true }));
    });
    sync();
  }

  function initializeGroup(group) {
    if (group.dataset.effectGroupReady) return;
    const fields = group.querySelector("[data-effect-group-fields]");
    const number = group.querySelector("[data-effect-display-group]");
    const append = group.querySelector("[data-effect-display-group-append]");
    const row = group.closest("[data-magic-effect-row]");
    if (!fields || !number || !append || !row) return;
    group.dataset.effectGroupReady = "1";
    fields.hidden = !number.value && !append.checked;
    let remembered = number.value;
    append.addEventListener("change", () => {
      if (!append.checked) remembered = number.value;
      number.value = append.checked ? remembered : "";
      row.dataset.displayGroup = number.value;
      row.dataset.displayGroupAppend = append.checked ? "1" : "0";
      fields.hidden = !append.checked;
      number.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }

  function initializeFocus(editor) {
    if (editor.dataset.focusReady) return;
    const source = editor.querySelector("[data-focus-target-picker] [data-condition-source]");
    const value = editor.querySelector("[data-focus-bindings-value]");
    const list = editor.querySelector("[data-focus-bindings]");
    const template = editor.querySelector("[data-focus-binding-template]");
    if (!source || !value || !list || !template) return;
    editor.dataset.focusReady = "1";
    const catalog = JSON.parse(editor.dataset.focusOptions || "{}");

    function save() {
      const targets = [];
      list.querySelectorAll("[data-focus-binding]").forEach(pane => {
        const schoolId = pane.dataset.focusSchoolId;
        const picker = pane.querySelector("[data-condition-source]");
        const hasSelection = picker.selectedOptions.length > 0;
        const configuration = catalog[schoolId];
        const current = hasSelection ? "" : " (aktuelle Bindung)";
        pane.querySelector("legend").textContent = `${configuration.name} · ${configuration.label}${current}`;
        Array.from(picker.selectedOptions).forEach(option => {
          targets.push({
            school_id: Number(schoolId), kind: catalog[schoolId].kind,
            object_id: Number(option.value),
          });
        });
      });
      value.value = JSON.stringify(targets);
      value.dispatchEvent(new Event("input", { bubbles: true }));
    }

    function sync() {
      const saved = JSON.parse(value.value || "[]");
      const schoolIds = new Set(Array.from(source.selectedOptions, option => option.value));
      list.querySelectorAll("[data-focus-binding]").forEach(pane => {
        if (!schoolIds.has(pane.dataset.focusSchoolId)) {
          pane.remove();
        }
      });
      schoolIds.forEach(schoolId => {
        const configuration = catalog[schoolId];
        if (!configuration || list.querySelector(`[data-focus-school-id="${schoolId}"]`)) return;
        const pane = template.content.firstElementChild.cloneNode(true);
        pane.dataset.focusSchoolId = schoolId;
        pane.querySelector("legend").textContent = `${configuration.name} · ${configuration.label}`;
        const picker = pane.querySelector("[data-condition-source]");
        const selected = new Set(saved.filter(target =>
          String(target.school_id) === schoolId && target.kind === configuration.kind,
        ).map(target => String(target.object_id)));
        configuration.options.forEach(entry => {
          const option = document.createElement("option");
          option.value = String(entry.pk);
          option.textContent = entry.name;
          option.selected = selected.has(option.value);
          picker.appendChild(option);
        });
        list.appendChild(pane);
        pane.querySelectorAll("select").forEach(select => { select.disabled = source.disabled; });
        initialize(pane.querySelector("[data-condition-picker]"));
        picker.addEventListener("change", save);
      });
      save();
    }
    source.addEventListener("change", sync);
    sync();
  }

  function scan(root) {
    if (root.matches?.("[data-condition-picker]")) initialize(root);
    root.querySelectorAll?.("[data-condition-picker]").forEach(initialize);
    if (root.matches?.("[data-effect-group]")) initializeGroup(root);
    root.querySelectorAll?.("[data-effect-group]").forEach(initializeGroup);
    if (root.matches?.("[data-focus-editor]")) initializeFocus(root);
    root.querySelectorAll?.("[data-focus-editor]").forEach(initializeFocus);
  }

  window.initializeMagicConditionPickers = scan;
  scan(document);
  new MutationObserver((mutations) => {
    mutations.forEach(mutation => mutation.addedNodes.forEach(scan));
  }).observe(document.documentElement, { childList: true, subtree: true });
})();
