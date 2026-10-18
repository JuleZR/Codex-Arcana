(() => {
  const selector = 'select[data-learn-entity-choice], select[name^="adv_choice_"], select[name^="dis_choice_"]';
  const enhanced = new WeakSet();
  let nextId = 0;

  function enhance(select) {
    if (enhanced.has(select) || !HTMLElement.prototype.showPopover) return;
    enhanced.add(select);
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = `${select.className} searchable_choice_trigger`;
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    const label = select.getAttribute('aria-label')
      || select.closest('label')?.querySelector('span')?.textContent.trim()
      || 'Auswahl';
    const panel = document.createElement('div');
    panel.className = 'searchable_choice_panel';
    panel.setAttribute('popover', 'auto');
    panel.id = `searchable-choice-${++nextId}`;
    trigger.setAttribute('aria-controls', panel.id);
    const search = document.createElement('input');
    search.type = 'search';
    search.className = 'searchable_choice_search';
    search.placeholder = 'Suchen …';
    search.setAttribute('aria-label', `${label} durchsuchen`);
    const list = document.createElement('div');
    list.className = 'searchable_choice_list';
    list.setAttribute('role', 'listbox');
    list.setAttribute('aria-label', label);
    const empty = document.createElement('div');
    empty.className = 'searchable_choice_empty';
    empty.textContent = 'Keine Treffer';
    empty.setAttribute('role', 'status');
    panel.append(search, list, empty);
    select.after(trigger, panel);
    select.classList.add('searchable_choice_native');
    select.tabIndex = -1;

    const render = () => {
      const query = search.value.trim().toLocaleLowerCase('de');
      list.replaceChildren();
      Array.from(select.options).forEach((option) => {
        if (option.hidden || !option.textContent.toLocaleLowerCase('de').includes(query)) return;
        const entry = document.createElement('div');
        const disabled = option.disabled || Boolean(option.closest('optgroup')?.disabled);
        entry.setAttribute('role', 'option');
        entry.setAttribute('aria-selected', String(option.selected));
        entry.setAttribute('aria-disabled', String(disabled));
        entry.tabIndex = -1;
        entry.textContent = option.textContent.trim() || 'Bitte wählen';
        entry.addEventListener('click', (event) => {
          event.preventDefault();
          if (disabled) return;
          select.value = option.value;
          select.dispatchEvent(new Event('input', { bubbles: true }));
          select.dispatchEvent(new Event('change', { bubbles: true }));
          panel.hidePopover();
          trigger.focus();
        });
        list.append(entry);
      });
      empty.hidden = list.childElementCount > 0;
    };
    const sync = () => {
      trigger.disabled = select.disabled;
      const text = select.selectedOptions[0]?.textContent.trim() || 'Bitte wählen';
      trigger.textContent = text;
      trigger.setAttribute('aria-label', `${label}: ${text}`);
      if (select.disabled && panel.matches(':popover-open')) panel.hidePopover();
    };
    const open = () => {
      if (select.disabled) return;
      search.value = '';
      render();
      const rect = trigger.getBoundingClientRect();
      const width = Math.min(Math.max(rect.width, 280), window.innerWidth - 16);
      const below = window.innerHeight - rect.bottom - 8;
      const above = rect.top - 8;
      const upward = below < 220 && above > below;
      panel.style.width = `${width}px`;
      panel.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - width - 8))}px`;
      panel.style.maxHeight = `${Math.max(0, Math.min(380, upward ? above : below))}px`;
      panel.style.top = upward ? 'auto' : `${rect.bottom + 4}px`;
      panel.style.bottom = upward ? `${window.innerHeight - rect.top + 4}px` : 'auto';
      panel.showPopover();
      search.focus();
    };
    trigger.addEventListener('click', (event) => {
      event.preventDefault();
      if (panel.matches(':popover-open')) panel.hidePopover();
      else open();
    });
    panel.addEventListener('toggle', () => {
      trigger.setAttribute('aria-expanded', String(panel.matches(':popover-open')));
    });
    search.addEventListener('input', render);
    panel.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        panel.hidePopover();
        trigger.focus();
      } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        const options = Array.from(list.querySelectorAll('[role="option"][aria-disabled="false"]'));
        const index = options.indexOf(document.activeElement);
        const next = event.key === 'ArrowDown' ? index + 1 : (index < 0 ? options.length - 1 : index - 1);
        if (next < 0) search.focus();
        else options[Math.min(next, options.length - 1)]?.focus();
      } else if (event.key === 'Enter' && event.target === search) {
        event.preventDefault();
        list.querySelector('[role="option"][aria-disabled="false"]')?.click();
      } else if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('[role="option"]')) {
        event.preventDefault();
        event.target.click();
      }
    });
    select.addEventListener('change', sync);
    select.addEventListener('focus', open);
    select.addEventListener('invalid', (event) => {
      event.preventDefault();
      open();
    });
    select.form?.addEventListener('reset', () => setTimeout(sync, 0));
    new MutationObserver(() => {
      sync();
      if (panel.matches(':popover-open')) render();
    }).observe(select, { attributes: true, childList: true, subtree: true, characterData: true });
    sync();
  }

  const scan = (root) => {
    if (!(root instanceof Element || root instanceof Document)) return;
    if (root.matches?.(selector)) enhance(root);
    root.querySelectorAll(selector).forEach(enhance);
  };
  scan(document);
  new MutationObserver((records) => {
    records.forEach((record) => record.addedNodes.forEach(scan));
  }).observe(document.body, { childList: true, subtree: true });
})();
