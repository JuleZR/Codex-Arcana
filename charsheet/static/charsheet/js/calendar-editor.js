(() => {
  function initialize() {
    const root = document.querySelector('[data-calendar-editor]');
    if (!root) return;
    const form = root.closest('form');
    const field = name => document.getElementById(`id_${name}`);
    const mode = field('calendar_mode');
    if (!mode) {
      root.dataset.readonly = 'true';
      root.querySelector('[data-editor-preview]').textContent = 'Kalenderdefinition zur Ansicht. Änderungen benötigen Bearbeitungsrechte.';
      return;
    }
    const source = field('calendar_definition');
    const preview = root.querySelector('[data-editor-preview]');
    const summary = document.querySelector('[data-calendar-summary]');
    const monthRows = root.querySelector('[data-month-rows]');
    const ruleRows = root.querySelector('[data-rule-rows]');
    const read = (row, name) => row.querySelector(`[name$="-${name}"]`);
    let snapshot = JSON.parse(document.getElementById('calendar-snapshot').textContent);
    let controller, sourceController, timer;
    let state = {months: [], reference_months: []};
    let adjustments = [];
    function onChange(element, callback) {
      if (window.django?.jQuery) window.django.jQuery(element).on('change', callback);
      else element.addEventListener('change', callback);
    }
    function add(container, template, management, values = {}, nested = false) {
      const index = Number(management.value);
      const placeholder = nested ? '__exception__' : '__prefix__';
      const wrapper = document.createElement('div');
      wrapper.innerHTML = template.innerHTML.replaceAll(placeholder, String(index));
      const row = wrapper.firstElementChild;
      container.append(row);
      management.value = index + 1;
      for (const [name, value] of Object.entries(values)) {
        const input = read(row, name);
        if (input) input.value = value ?? '';
      }
      return row;
    }
    function addMonth(values = {}) {
      return add(monthRows, root.querySelector('[data-month-template]'),
        field('calendar_months-TOTAL_FORMS'), values);
    }
    function addRule(values = {}) {
      const row = add(ruleRows, root.querySelector('[data-rule-template]'),
        field('calendar_rules-TOTAL_FORMS'), values);
      for (const exception of values.exceptions || []) addException(row, exception);
      return row;
    }
    function addException(row, values = {}) {
      return add(row.querySelector('[data-exception-rows]'),
        row.querySelector('[data-exception-template]'),
        row.querySelector('[name$="-exceptions-TOTAL_FORMS"]'), values, true);
    }
    function options(select, entries, previous, allowBlank = false) {
      select.replaceChildren(...(allowBlank ? [new Option('Bitte auswählen', '')] : []),
        ...entries.map(entry => new Option(entry.label, String(entry.value))));
      const value = String(previous ?? '');
      if ([...select.options].some(option => option.value === value)) select.value = value;
      else select.value = allowBlank ? '' : (select.options[0]?.value || '');
    }
    function updateMonths() {
      const months = [...monthRows.children].map((row, index) => ({
        key: String(index), name: read(row, 'name').value.trim(),
        position: Number(read(row, 'sort_order').value), days: Number(read(row, 'days').value),
        deleted: read(row, 'DELETE').checked,
      })).filter(row => !row.deleted && row.name && row.days > 0)
        .sort((a, b) => a.position - b.position);
      root.querySelector('[data-month-total]').textContent =
        `${months.length} Monate · ${months.reduce((total, row) => total + row.days, 0)} reguläre Tage`;
      for (const row of ruleRows.children) {
        const select = read(row, 'month');
        options(select, months.map(month => ({value: month.key, label: month.name})), select.value, true);
      }
      return months;
    }
    function sharing() {
      const others = snapshot.systems.filter(system => String(system.id) !== root.dataset.systemId);
      root.querySelector('[data-calendar-shared]').textContent = mode.value === 'new' ? '' :
        (others.length ? `Weitere Zeitrechnungen dieser Definition: ${others.map(system => system.name).join(', ')}. ` : '') +
        (mode.value === 'edit' ? 'Änderungen gelten für alle Zeitrechnungen dieser Definition; gespeicherte absolute Charaktertage bleiben erhalten.' :
          mode.value === 'copy' ? 'Eine eigene Definition wird angelegt; die Vorlage bleibt erhalten.' : 'Die ausgewählte Definition wird verwendet.');
      const row = field('confirm_shared_calendar').closest('.form-row');
      row.hidden = mode.value !== 'edit' || !others.length;
      field('confirm_shared_calendar').required = mode.value === 'edit' && Boolean(others.length);
    }
    function referenceVisibility() {
      const visible = Boolean(field('reference_system').value);
      document.querySelector('.calendar-reference-date').hidden = !visible;
      for (const part of ['year', 'month', 'day']) {
        field(`reference_${part}`).required = visible;
        field(`reference_${part}`).disabled = !visible;
      }
    }
    function dateText(prefix) {
      const month = field(`${prefix}_month`);
      if (!month.value || !field(`${prefix}_day`).value || field(`${prefix}_year`).value === '') return 'Datum unvollständig';
      return `${field(`${prefix}_day`).value}. ${month.selectedOptions[0]?.textContent} ${field(`${prefix}_year`).value}`;
    }
    function describe() {
      const text = field('reference_system').value ?
        `${dateText('anchor')} (${field('name').value || 'eigene Zeitrechnung'}) entspricht ${dateText('reference')} (${state.reference_name || 'Bezugszeitrechnung'}). Beide Daten bezeichnen denselben absoluten Tag.` :
        `${dateText('anchor')} ist der Ausgangspunkt dieser Zeitrechnung und entspricht dem absoluten Tag 0.`;
      preview.textContent = `${text} Das ausgewählte eigene Jahr hat ${state.days || '…'} Tage. ${state.notice || ''} ${adjustments.join(' ')}`;
      if (summary) summary.textContent = text;
    }
    function dates(prefix, months) {
      const month = field(`${prefix}_month`);
      const old = month.selectedOptions[0]?.dataset.key;
      const matching = old ? months.find(row => String(row.id) === old) : null;
      if (old && !matching && months.length) adjustments.push('Der bisherige Monat ist nicht mehr verfügbar; bitte die Datumsauswahl prüfen.');
      const previous = matching?.number ?? month.value;
      options(month, months.map(row => ({label: row.name, value: row.number})), previous);
      for (const option of month.options) option.dataset.key = String(months.find(row => String(row.number) === option.value)?.id);
      days(prefix, months);
    }
    function days(prefix, months) {
      const day = field(`${prefix}_day`);
      const length = months.find(row => String(row.number) === field(`${prefix}_month`).value)?.days || 0;
      const previous = Math.min(Number(day.value) || 1, length);
      if (Number(day.value) > length && length) adjustments.push(`Der gewählte Tag existiert hier nicht mehr und wurde auf ${length} begrenzt.`);
      options(day, Array.from({length}, (_, index) => ({label: index + 1, value: index + 1})), previous);
    }
    async function refresh() {
      controller?.abort();
      controller = new AbortController();
      referenceVisibility();
      try {
        const response = await fetch(root.dataset.previewUrl, {method: 'POST',
          credentials: 'same-origin', body: new FormData(form), signal: controller.signal});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error);
        state = data;
        adjustments = [];
        dates('anchor', data.months);
        if (field('reference_system').value) dates('reference', data.reference_months);
        form.dispatchEvent(new CustomEvent('calendar-layout-preview', {detail: data.months}));
        describe();
      } catch (error) {
        if (error.name !== 'AbortError') {
          preview.textContent = error.message;
          if (summary) summary.textContent = error.message;
        }
      }
    }
    function schedule() { clearTimeout(timer); timer = setTimeout(refresh, 180); }
    function editable() {
      root.dataset.readonly = String(mode.value === 'existing');
      for (const input of root.querySelectorAll('input:not([type="hidden"]), select, button')) input.disabled = mode.value === 'existing';
      source.required = mode.value !== 'new';
      sharing(); updateMonths(); referenceVisibility(); schedule();
    }
    function populate(data, fresh = false) {
      snapshot = data;
      monthRows.replaceChildren(); ruleRows.replaceChildren();
      for (const group of ['calendar_months', 'calendar_rules']) {
        field(`${group}-TOTAL_FORMS`).value = 0;
        field(`${group}-INITIAL_FORMS`).value = 0;
      }
      for (const [key, value] of Object.entries(data.definition)) field(`definition-${key}`).value = value;
      for (const month of data.months) addMonth(month);
      // Populate the rule selectors before assigning their row keys.
      for (const rule of data.rules) {
        const row = addRule(rule);
        updateMonths(); read(row, 'month').value = rule.month;
        row.querySelector('[name$="-exceptions-INITIAL_FORMS"]').value = rule.exceptions.length;
      }
      field('calendar_months-INITIAL_FORMS').value = data.months.length;
      field('calendar_rules-INITIAL_FORMS').value = data.rules.length;
      if (fresh) for (let index = 1; index <= 12; index++) addMonth({sort_order: index});
      field('confirm_shared_calendar').checked = false;
      editable();
    }
    async function loadSource() {
      sourceController?.abort(); sourceController = new AbortController();
      if (!source.value) { editable(); return; }
      try {
        const url = new URL(root.dataset.dataUrl, location.origin);
        url.searchParams.set('calendar', source.value);
        const response = await fetch(url, {credentials: 'same-origin', signal: sourceController.signal});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error);
        populate(data);
      } catch (error) { if (error.name !== 'AbortError') preview.textContent = error.message; }
    }
    onChange(mode, () => {
      if (mode.value === 'new') populate({definition: {name: '', months_per_year: 12, days_per_year: ''}, months: [], rules: [], systems: []}, true);
      else loadSource();
    });
    onChange(source, loadSource);
    field('definition-months_per_year').addEventListener('change', () => {
      const count = Number(field('definition-months_per_year').value);
      if (mode.value === 'existing' || !Number.isInteger(count) || count < 1 || count > 1000) return;
      const active = [...monthRows.children].filter(row => !read(row, 'DELETE').checked);
      while (active.length < count) active.push(addMonth({sort_order: Number(field('calendar_months-TOTAL_FORMS').value) + 1}));
      for (let index = active.length - 1; index >= count; index--) {
        const row = active[index];
        if (!read(row, 'name').value && !read(row, 'days').value && !read(row, 'id').value) read(row, 'DELETE').checked = true;
      }
      updateMonths(); schedule();
    });
    onChange(field('reference_system'), () => { referenceVisibility(); schedule(); });
    root.addEventListener('click', event => {
      if (event.target.closest('[data-add-month]')) addMonth({sort_order: Number(field('calendar_months-TOTAL_FORMS').value) + 1});
      else if (event.target.closest('[data-add-rule]')) addRule();
      else if (event.target.closest('[data-add-exception]')) addException(event.target.closest('[data-rule-row]'));
      else return;
      updateMonths(); schedule();
    });
    form.addEventListener('input', () => { updateMonths(); schedule(); });
    form.addEventListener('change', () => { updateMonths(); schedule(); });
    for (const prefix of ['anchor', 'reference']) onChange(field(`${prefix}_month`), () => {
      days(prefix, prefix === 'anchor' ? state.months : state.reference_months); describe();
    });
    editable();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, {once: true});
  else initialize();
})();
