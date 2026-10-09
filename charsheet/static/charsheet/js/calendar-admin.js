(() => {
  const summary = document.querySelector('[data-calendar-summary]');
  if (!summary) return;
  const field = name => document.getElementById(`id_${name}`);
  const form = summary.closest('form');
  const selected = element => element?.selectedOptions[0]?.textContent || '';
  const debounce = callback => {
    let timer;
    return () => { clearTimeout(timer); timer = setTimeout(callback, 180); };
  };
  const status = (element, text) => { element.textContent = text; };
  // Django's related-object popups emit jQuery change events.
  function onChange(element, callback) {
    if (window.django?.jQuery) window.django.jQuery(element).on('change', callback);
    else element.addEventListener('change', callback);
  }
  async function navigation(params, signal) {
    const url = new URL(summary.dataset.navigationUrl, location.origin);
    url.search = new URLSearchParams(params);
    const response = await fetch(url, {credentials: 'same-origin', signal});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    return data;
  }
  function setOptions(select, entries, previous) {
    select.replaceChildren(...entries.map(entry => new Option(entry.label, entry.value)));
    if ([...select.options].some(option => option.value === String(previous))) select.value = previous;
  }

  if (field('months_per_year')) {
    function update() {
      const rows = [...document.querySelectorAll('#months-group tr.form-row')]
        .filter(row => !row.classList.contains('empty-form') &&
          !row.querySelector('[name$="-DELETE"]')?.checked &&
          [...row.querySelectorAll('input[name$="-name"], input[name$="-days"], input[name$="-sort_order"]')]
            .some(input => input.value !== ''));
      const days = rows.reduce((sum, row) => sum + (Number(row.querySelector('[name$="-days"]')?.value) || 0), 0);
      const expectedMonths = field('months_per_year').value || '…';
      const expectedDays = field('days_per_year').value || '…';
      const target = document.querySelector('[data-calendar-month-summary]');
      if (target) status(target, `${rows.length} von ${expectedMonths} Monaten angelegt – ${days} von ${expectedDays} Tagen zugeordnet`);
      const positions = rows.map(row => Number(row.querySelector('[name$="-sort_order"]')?.value));
      const duplicate = positions.length !== new Set(positions.filter(position => position > 0)).size;
      const validRows = rows.every(row => row.querySelector('[name$="-name"]')?.value.trim() &&
        ['days', 'sort_order'].every(name => {
          const value = Number(row.querySelector(`[name$="-${name}"]`)?.value);
          return Number.isInteger(value) && value > 0;
        }));
      const complete = rows.length === Number(expectedMonths) && days === Number(expectedDays) && !duplicate && validRows;
      target?.classList.toggle('is-incomplete', !complete);
      if (target && duplicate) target.append(document.createTextNode(' – Monatspositionen fehlen oder sind doppelt vergeben.'));
      if (target && !validRows) target.append(document.createTextNode(' – Bitte Monatsnamen und positive ganze Tageszahlen angeben.'));
      status(summary, `Dieser Kalender besteht aus ${expectedMonths} Monaten mit insgesamt ${expectedDays} regulären Tagen.`);
    }
    form.addEventListener('input', update);
    form.addEventListener('change', update);
    document.addEventListener('formset:added', update);
    document.addEventListener('formset:removed', update);
    const monthRows = document.querySelector('#months-group tbody');
    if (monthRows) new MutationObserver(update).observe(monthRows, {childList: true});
    update();
    return;
  }

  if (field('anchor_year')) {
    const referenceGroup = document.querySelector('.calendar-reference-date');
    const reference = field('reference_system');
    const calendar = field('calendar_definition');
    const states = {anchor: null, reference: null};
    const controllers = {};
    function dateText(prefix) {
      const month = field(`${prefix}_month`);
      if (!month.value || !field(`${prefix}_day`).value || field(`${prefix}_year`).value === '') return 'Datum noch unvollständig';
      return `${field(`${prefix}_day`).value}. ${selected(month)}, Jahr ${field(`${prefix}_year`).value}`;
    }
    function updateSummary() {
      referenceGroup.hidden = !reference.value;
      referenceGroup.querySelector('.description')?.remove();
      if (!reference.value) {
        status(summary, 'Diese Zeitrechnung bildet den Ausgangspunkt für alle weiteren Zeitrechnungen. '
          + 'Ihr festgelegtes Ausgangsdatum entspricht dem absoluten Tag 0. '
          + `Ausgangsdatum: ${dateText('anchor')}.`);
      } else {
        const description = document.createElement('div');
        description.className = 'description';
        description.textContent = `Bezugszeitrechnung: ${selected(reference)}. Beide Daten bezeichnen denselben absoluten Tag.`;
        referenceGroup.querySelector('h2')?.after(description);
        status(summary, `${dateText('anchor')} der ${field('name').value || 'eigenen Zeitrechnung'} entspricht `
          + `${dateText('reference')} in der ${states.reference?.system_name || selected(reference)}.`);
      }
      for (const part of ['year', 'month', 'day']) field(`reference_${part}`).required = Boolean(reference.value);
    }
    function updateDays(prefix) {
      const month = field(`${prefix}_month`);
      const day = field(`${prefix}_day`);
      const length = states[prefix]?.months.find(entry => String(entry.number) === month.value)?.days || 0;
      const previous = Math.min(Number(day.value) || 1, length);
      setOptions(day, Array.from({length}, (_, index) => ({label: index + 1, value: index + 1})), previous);
      updateSummary();
    }
    async function load(prefix) {
      controllers[prefix]?.abort();
      const controller = new AbortController();
      controllers[prefix] = controller;
      const source = prefix === 'anchor' ? calendar : reference;
      if (!source.value) { states[prefix] = null; updateSummary(); return; }
      const year = field(`${prefix}_year`).value;
      if (!/^-?\d+$/.test(year)) { updateSummary(); return; }
      try {
        const data = await navigation({[prefix === 'anchor' ? 'calendar' : 'system']: source.value, year}, controller.signal);
        states[prefix] = data;
        const month = field(`${prefix}_month`);
        setOptions(month, data.months.map(entry => ({label: entry.name, value: entry.number})), month.value);
        updateDays(prefix);
      } catch (error) {
        if (error.name !== 'AbortError') status(summary, error.message);
      }
    }
    for (const prefix of ['anchor', 'reference']) {
      field(`${prefix}_year`).addEventListener('input', debounce(() => load(prefix)));
      onChange(field(`${prefix}_month`), () => updateDays(prefix));
      field(`${prefix}_day`).addEventListener('change', updateSummary);
    }
    onChange(calendar, () => load('anchor'));
    onChange(reference, () => { updateSummary(); load('reference'); });
    field('name').addEventListener('input', updateSummary);
    updateSummary();
    load('anchor');
    load('reference');
    return;
  }

  if (field('added_days')) {
    const calendar = field('calendar');
    const month = field('month');
    const label = document.createElement('label');
    label.textContent = 'Schaltjahre ab Jahr';
    const start = document.createElement('input');
    start.type = 'text'; start.value = '0'; start.pattern = '-?[0-9]+';
    start.setAttribute('aria-label', 'Schaltjahre ab Jahr');
    label.append(start);
    const explanation = document.createElement('p');
    const preview = document.createElement('p');
    summary.replaceChildren(explanation, label, preview);
    let controller;
    async function update() {
      controller?.abort();
      controller = new AbortController();
      const exceptions = document.querySelector('#exceptions-group') ? [...document.querySelectorAll('#exceptions-group tr.form-row')]
        .filter(row => !row.classList.contains('empty-form') && !row.querySelector('[name$="-DELETE"]')?.checked &&
          row.querySelector('[name$="-period"]')?.value)
        .map(row => ({effect: row.querySelector('[name$="-effect"]').value,
          period: row.querySelector('[name$="-period"]').value,
          offset: row.querySelector('[name$="-offset"]').value || '0'}))
        : JSON.parse(summary.dataset.savedExceptions || '[]');
      try {
        const response = await fetch(summary.dataset.leapPreviewUrl, {
          method: 'POST', credentials: 'same-origin', signal: controller.signal,
          headers: {'Content-Type': 'application/json',
            'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value},
          body: JSON.stringify({calendar: calendar.value, month: month.value,
            period: field('period').value, added_days: field('added_days').value,
            offset: field('offset').value || '0', start: start.value, exceptions}),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error);
        status(explanation, `${data.summary} ${data.exception_summaries.join(' ')} ${data.notice}`);
        status(preview, `Schaltjahre ab Jahr ${data.start}: ${data.years.join(', ') || 'keine'}.`
          + (data.limited ? ' Vorschau auf die nächsten 128 Termine der Grundregel begrenzt.' : ''));
      } catch (error) {
        if (error.name !== 'AbortError') { status(explanation, error.message); status(preview, ''); }
      }
    }
    let monthController;
    async function loadMonths() {
      monthController?.abort(); monthController = new AbortController();
      const addLink = document.getElementById('add_id_month');
      if (addLink) {
        const url = new URL(addLink.href, location.origin);
        url.searchParams.set('calendar', calendar.value);
        addLink.href = url.href;
      }
      if (!calendar.value) { month.replaceChildren(new Option('Zuerst Kalender auswählen', '')); return; }
      try {
        const data = await navigation({calendar: calendar.value, year: start.value || '0'}, monthController.signal);
        setOptions(month, data.months.map(entry => ({label: entry.name, value: entry.id})), month.value);
        update();
      } catch (error) {
        if (error.name !== 'AbortError') status(explanation, error.message);
      }
    }
    const refresh = debounce(update);
    form.addEventListener('input', refresh);
    form.addEventListener('change', refresh);
    document.addEventListener('formset:added', refresh);
    document.addEventListener('formset:removed', refresh);
    onChange(calendar, loadMonths);
    onChange(month, update);
    const advanced = field('offset').closest('details');
    if (advanced && Number(field('offset').value)) advanced.open = true;
    loadMonths();
  }
})();
