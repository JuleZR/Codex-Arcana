(() => {
  const root = document.querySelector('[data-character-date]');
  if (!root) return;
  const picker = root.querySelector('form');
  const open = root.querySelector('[data-date-open]');
  const face = root.querySelector('.character-date-display');
  const system = root.querySelector('[data-date-system]');
  const year = root.querySelector('[data-date-year]');
  const month = root.querySelector('[data-date-month]');
  const directDay = root.querySelector('[data-date-day]');
  const days = root.querySelector('[data-date-days]');
  const apply = root.querySelector('[data-date-apply]');
  const error = root.querySelector('[data-date-error]');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let current = null;
  let preview = null;
  let busy = false;
  let visible = true;

  const primary = root.querySelector('[data-date-primary]');
  const dateTexts = root.querySelectorAll(
    '[data-date-primary], [data-date-secondary], [data-date-season], [data-date-title], [data-date-picker-season], [data-date-saved]'
  );
  function placePicker() {
    if (picker.hidden) return;
    picker.style.top = '';
    const box = picker.getBoundingClientRect();
    if (box.bottom > window.innerHeight - 8) {
      const top = Math.max(8, window.innerHeight - box.height - 8);
      picker.style.top = `${top - root.getBoundingClientRect().top}px`;
    }
  }
  function fitDateText() {
    for (const text of dateTexts) {
      text.style.fontSize = '';
      const available = text.clientWidth;
      if (available && text.scrollWidth > available) {
        const size = parseFloat(getComputedStyle(text).fontSize);
        text.style.fontSize = `${size * available / text.scrollWidth * .98}px`;
      }
    }
    placePicker();
  }
  window.addEventListener('resize', fitDateText, {passive: true});
  if ('ResizeObserver' in window) {
    const observer = new ResizeObserver(fitDateText);
    observer.observe(open);
    observer.observe(picker);
  }
  document.fonts?.ready.then(fitDateText);

  const page = document.querySelector('.book-spread .page');
  function alignWithPage() {
    if (!page || window.innerWidth <= 1180) return;
    root.style.setProperty('--calendar-top', `${Math.max(0, page.getBoundingClientRect().top)}px`);
    placePicker();
  }
  if (page) {
    window.addEventListener('resize', alignWithPage, {passive: true});
    window.addEventListener('scroll', alignWithPage, {passive: true});
    page.closest('.book-spread')?.addEventListener('scroll', alignWithPage, {passive: true});
    if ('ResizeObserver' in window) new ResizeObserver(alignWithPage).observe(page);
    alignWithPage();
  }

  // A fixed pool, animated by CSS; no frame loop or particle timer.
  for (const host of root.querySelectorAll('[data-date-atmosphere]')) {
    for (const effect of ['spring', 'summer', 'autumn', 'winter']) {
      const layer = document.createElement('div');
      layer.className = 'calendar-particles';
      layer.dataset.effect = effect;
      const particleCount = effect === 'summer' ? 0 : 6;
      for (let index = 0; index < particleCount; index++) {
        const particle = document.createElement('i');
        particle.style.setProperty('--i', index);
        if (effect === 'spring' && (index === 1 || index === 4)) {
          particle.classList.add('calendar-cherry-blossom');
        }
        layer.append(particle);
      }
      host.append(layer);
    }
  }
  function pauseEffects() {
    root.classList.toggle('is-paused', document.hidden || !visible);
  }
  document.addEventListener('visibilitychange', pauseEffects);
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(entries => {
      visible = entries[0].isIntersecting;
      pauseEffects();
    }).observe(root);
  }
  pauseEffects();
  for (const artifact of root.querySelectorAll('.calendar-artifact')) {
    artifact.addEventListener('pointermove', event => {
      if (reduced.matches || document.hidden) return;
      const box = artifact.getBoundingClientRect();
      artifact.style.setProperty('--pointer-x', `${event.clientX - box.left}px`);
      artifact.style.setProperty('--pointer-y', `${event.clientY - box.top}px`);
    }, {passive: true});
  }
  function theme(artifact, season) {
    artifact.dataset.season = season?.style || 'neutral';
  }
  function display(data) {
    const changed = current && data.current &&
      (current.absolute_day !== data.current.absolute_day || current.system !== data.current.system);
    current = data.current;
    primary.textContent = current?.date_text || 'Zeitensiegel';
    root.querySelector('[data-date-secondary]').textContent = current ?
      current.abbreviation : 'Kein Kalender verfügbar';
    root.querySelector('[data-date-season]').textContent = current?.season?.name || '';
    open.setAttribute('aria-label', current ? `${current.label} – Kalender öffnen` : 'Kalender öffnen');
    open.disabled = !current;
    root.querySelectorAll('[data-date-step]').forEach(button => { button.disabled = !current; });
    theme(face, current?.season);
    fitDateText();
    if (changed && !reduced.matches) {
      open.classList.add('is-date-changing');
    }
  }
  open.addEventListener('animationend', () => open.classList.remove('is-date-changing'));

  function render(data) {
    preview = data.preview;
    year.value = preview.year;
    month.replaceChildren(...preview.months.map(entry => {
      const option = new Option(entry.name, entry.number);
      option.selected = entry.number === preview.month;
      return option;
    }));
    const entry = preview.months[preview.month - 1];
    directDay.max = entry.days;
    directDay.value = preview.day;
    root.querySelector('[data-date-title]').textContent = preview.date_text;
    root.querySelector('[data-date-picker-season]').textContent = preview.season?.name || 'Arkaner Kalender';
    root.querySelector('[data-date-saved]').textContent =
      preview.saved_date ? `Gespeichert: ${preview.saved_date.label}` : '';
    theme(picker, preview.season);
    days.replaceChildren();
    for (let day = 1; day <= entry.days; day++) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = day;
      button.setAttribute('aria-label', `${day}. ${entry.name}`);
      button.setAttribute('aria-pressed', String(day === preview.day));
      const saved = preview.saved_date;
      if (saved && saved.year === preview.year && saved.month === preview.month && saved.day === day) {
        button.setAttribute('aria-current', 'date');
        button.setAttribute('aria-label', `${day}. ${entry.name} – gespeichertes Datum`);
      }
      button.addEventListener('click', () => loadPreview({
        system: system.value, year: year.value, month: month.value, day,
      }, day));
      days.append(button);
    }
    apply.disabled = false;
    fitDateText();
  }
  async function request(params = null, body = null) {
    if (busy) return null;
    busy = true;
    error.textContent = '';
    root.setAttribute('aria-busy', 'true');
    try {
      const url = new URL(root.dataset.url, location.origin);
      if (params) url.search = new URLSearchParams(params);
      const response = await fetch(url, {
        method: body ? 'POST' : 'GET', credentials: 'same-origin',
        headers: body ? {
          'Content-Type': 'application/json',
          'X-CSRFToken': root.querySelector('[name=csrfmiddlewaretoken]').value,
        } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Datum konnte nicht geladen werden.');
      return data;
    } catch (exception) {
      error.textContent = exception.message;
      return null;
    } finally {
      busy = false;
      root.removeAttribute('aria-busy');
    }
  }
  async function loadPreview(params, focusDay = null) {
    if (busy) return;
    apply.disabled = true;
    const data = await request(params);
    if (data) {
      render(data);
      if (focusDay) days.querySelector('[aria-pressed="true"]')?.focus();
    }
  }
  function close(restoreFocus = true) {
    picker.hidden = true;
    open.setAttribute('aria-expanded', 'false');
    if (restoreFocus) open.focus();
  }
  open.addEventListener('click', async () => {
    if (busy || !current) return;
    if (!picker.hidden) return close();
    picker.hidden = false;
    open.setAttribute('aria-expanded', 'true');
    apply.disabled = true;
    system.value = current.system;
    await loadPreview({system: current.system});
    year.focus();
  });
  root.querySelector('[data-date-close]').addEventListener('click', () => close());
  root.querySelector('[data-date-cancel]').addEventListener('click', () => close());
  root.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !picker.hidden) { event.preventDefault(); close(); }
  });
  document.addEventListener('click', event => {
    if (!picker.hidden && !root.contains(event.target)) close(false);
  });
  system.addEventListener('change', () => {
    if (preview || current) loadPreview({
      system: system.value, absolute: (preview || current).absolute_day,
    });
  });
  year.addEventListener('change', () => {
    if (year.reportValidity()) loadPreview({
      system: system.value, year: year.value, month: month.value || 1,
      day: preview?.day || 1,
    });
  });
  for (const input of [year, directDay]) {
    input.addEventListener('input', () => { apply.disabled = true; });
  }
  directDay.addEventListener('change', () => {
    if (directDay.reportValidity() && year.reportValidity()) loadPreview({
      system: system.value, year: year.value, month: month.value, day: directDay.value,
    });
  });
  month.addEventListener('change', () => loadPreview({
    system: system.value, year: year.value, month: month.value, day: preview?.day || 1,
  }));
  root.querySelectorAll('[data-date-year-step]').forEach(button => {
    button.addEventListener('click', () => {
      if (!year.reportValidity()) return;
      loadPreview({system: system.value,
        year: String(BigInt(year.value) + BigInt(button.dataset.dateYearStep)),
        month: month.value || 1, day: preview?.day || 1});
    });
  });
  root.querySelectorAll('[data-date-month-step]').forEach(button => {
    button.addEventListener('click', () => {
      if (!preview || !year.reportValidity()) return;
      let next = preview.month + Number(button.dataset.dateMonthStep);
      let nextYear = BigInt(year.value);
      if (next < 1) { next = preview.months.length; nextYear--; }
      if (next > preview.months.length) { next = 1; nextYear++; }
      loadPreview({system: system.value, year: String(nextYear), month: next, day: preview.day});
    });
  });
  root.querySelectorAll('[data-date-step]').forEach(button => {
    button.addEventListener('click', async () => {
      const data = await request(null, {action: 'step', delta: Number(button.dataset.dateStep)});
      if (data) { display(data); close(false); }
    });
  });
  picker.addEventListener('submit', async event => {
    event.preventDefault();
    if (!preview || apply.disabled || !picker.reportValidity()) return;
    const data = await request(null, {action: 'set', system: preview.system,
      year: preview.year, month: preview.month, day: preview.day});
    if (data) { display(data); close(); }
  });
  (async () => {
    let data = await request();
    if (!data) return;
    system.replaceChildren(...data.systems.map(entry => new Option(entry.name, entry.id)));
    if (!data.current && data.systems.length) {
      data = await request(null, {action: 'initialize'});
      if (!data) return;
    }
    display(data);
    if (!data.systems.length) error.textContent = 'Es ist noch kein gültiger Kalender eingerichtet.';
  })();
})();
