/* One renderer/editor for admin defaults, personal layouts and calendar faces. */
(() => {
  'use strict';
  const fields = {
    day: 'Tag', month_primary: 'Monat',
    month_alternative: 'Monat (alt.)', year: 'Jahr',
    system_primary: 'Zeitrechnung', system_alternative: 'Zeitrechnung (alt.)',
    season: 'Jahreszeit', text: 'Text',
  };
  const copy = value => JSON.parse(JSON.stringify(value));
  const renderFits = new WeakMap(), renderObservers = new WeakMap();
  const split = value => {
    const match = (value || '').match(/^\s*(.*?)\s*\[([^\[\]]*)\]\s*$/u);
    return match ? [match[1].trim(), match[2].trim()] : [value || '', ''];
  };
  function values(data) {
    const [month, alternative] = split(data.month_name);
    const [system, abbreviation] = split(data.abbreviation);
    return {day: String(data.day).padStart(2, '0'), year: String(data.year),
      month_primary: month, month_alternative: alternative,
      system_primary: system, system_alternative: abbreviation,
      season: data.season?.name || ''};
  }
  function render(host, layout, data, editing = null) {
    if (layout.version === 1) layout = normalize(layout).layout;
    host.classList.add('calendar-layout');
    const rows = [], dynamic = new Map();
    function build(node) {
      const group = node.type === 'group';
      const box = document.createElement('span');
      box.className = `calendar-layout-${group ? 'group' : 'element'}`;
      const style = node.style || {};
      box.dir = 'auto';
      box.dataset.color = style.color || 'inherit';
      box.style.fontSize = `${style.size || 14}px`;
      box.style.fontWeight = style.weight || 'normal';
      box.style.fontStyle = style.italic ? 'italic' : 'normal';
      box.style.textAlign = {start: 'start', center: 'center', end: 'end'}[style.align] || 'inherit';
      box.style.padding = `${style.padding || 0}px`;
      box.style.alignSelf = {start: 'flex-start', center: 'center', end: 'flex-end'}[style.align] || 'auto';
      if (style.width === 'fill') { box.style.width = '100%'; box.style.flexGrow = '1'; }
      if (group) {
        if (layout.version === 2 && node.direction === 'row') box.style.width = '100%';
        box.style.flexDirection = node.direction;
        box.style.gap = `${style.gap ?? 3}px`;
        box.style.flexWrap = layout.version === 2 || style.wrap === false ? 'nowrap' : 'wrap';
        box.style.alignItems = {start: 'flex-start', center: 'center', end: 'flex-end'}[style.align || 'center'];
        box.style.justifyContent = {start: 'flex-start', center: 'center', end: 'flex-end'}[style.align || 'center'];
        for (const child of node.children) {
          const childBox = build(child);
          // Keep punctuation beside the preceding value with automatic gaps.
          if (layout.version === 2 && Array.from(box.children).some(previous => !previous.hidden) &&
              child.field === 'text' && /^[.,:;!?]+$/.test(child.text || '')) {
            childBox.style.marginInlineStart = '-' + (style.gap ?? 3) + 'px';
          }
          box.append(childBox);
        }
        if (node.direction === 'row') rows.push(box);
        if (!editing && Array.from(box.children).every(child => child.hidden)) box.hidden = true;
      } else {
        if (style.size_mode === 'dynamic') dynamic.set(box, style.size || 14);
        if (layout.version === 2) {
          box.style.flexShrink = '0';
          box.style.maxWidth = 'none';
          box.style.whiteSpace = 'pre';
          box.style.overflowWrap = 'normal';
        }
        box.textContent = node.field === 'text' ? node.text || '' : data[node.field] || '';
        if (!box.textContent && !editing) box.hidden = true;
      }
      if (style.visible === false) {
        if (editing) box.classList.add('is-layout-hidden');
        else box.hidden = true;
      }
      if (editing) editing(box, node);
      return box;
    }
    host.replaceChildren(build(layout.root));
    const fit = () => {
      for (const [box, size] of dynamic) box.style.fontSize = `${size}px`;
      for (const row of rows) {
        if (!row.clientWidth) continue;
        const children = Array.from(row.children).filter(box => box.classList.contains('calendar-layout-element') &&
          !box.hidden && window.getComputedStyle(box).display !== 'none');
        const adjustable = children.filter(box => dynamic.has(box));
        if (!adjustable.length) continue;
        const style = window.getComputedStyle(row);
        const number = value => Number.parseFloat(value) || 0;
        const available = row.clientWidth - number(style.paddingLeft) - number(style.paddingRight);
        // Rectangles include the editor's 175% zoom; available width does not.
        const scale = row.getBoundingClientRect().width / row.offsetWidth || 1;
        const occupied = () => children.reduce((width, box) => {
          const css = window.getComputedStyle(box);
          return width + box.getBoundingClientRect().width / scale + number(css.marginLeft) + number(css.marginRight);
        }, Math.max(0, children.length - 1) * number(style.columnGap));
        if (occupied() <= available) continue;
        const apply = ratio => adjustable.forEach(box => { box.style.fontSize = `${Math.max(8, dynamic.get(box) * ratio)}px`; });
        let low = 0, high = 1;
        apply(low);
        if (occupied() <= available) {
          for (let i = 0; i < 10; i++) {
            const middle = (low + high) / 2; apply(middle);
            if (occupied() <= available - .5) low = middle; else high = middle;
          }
          apply(low);
        }
      }
    };
    renderFits.set(host, fit);
    if (!renderObservers.has(host) && window.ResizeObserver) {
      const observer = new window.ResizeObserver(() => renderFits.get(host)?.());
      observer.observe(host); renderObservers.set(host, observer);
    }
    fit();
    document.fonts?.ready.then(() => renderFits.get(host)?.());
  }
  function normalize(layout) {
    if (layout.version === 2) {
      const result = copy(layout);
      result.root.style ||= {};
      result.root.children.forEach(line => { line.style ||= {}; });
      while (result.root.children.length < 3) result.root.children.push(row());
      return {layout: result, notice: ''};
    }
    let flattened = false;
    function inherited(node, parent = {}) {
      const style = {...(node.style || {})};
      if (!style.color || style.color === 'inherit') style.color = parent.color || 'inherit';
      if (parent.visible === false) style.visible = false;
      return style;
    }
    function leaves(node, parent = {}) {
      const style = inherited(node, parent);
      if (node.type === 'element') return [{...copy(node), style}];
      if (node.direction === 'column' && node.children.length > 1) flattened = true;
      return node.children.flatMap(child => leaves(child, style));
    }
    function lines(node, parent = {}) {
      const style = inherited(node, parent);
      if (node.type === 'element') return [row([ {...copy(node), style} ], {align: parent.align || 'center'})];
      if (node.direction === 'column') return node.children.flatMap(child => lines(child, style));
      return [row(leaves(node, parent), {...style, align: style.align || parent.align || 'center', color: 'inherit', visible: true})];
    }
    const rows = lines(layout.root);
    const overflow = rows.length > 3;
    if (overflow) rows[2].children.push(...rows.slice(3).flatMap(line => line.children));
    const result = {version: 2, root: {type: 'group', direction: 'column',
      style: {...copy(layout.root.style || {}), color: 'inherit', visible: true}, children: rows.slice(0, 3)}};
    while (result.root.children.length < 3) result.root.children.push(row());
    const notice = (overflow ? 'Zusätzliche Zeilen werden im Entwurf in Zeile 3 zusammengeführt. ' : '') +
      (flattened ? 'Verschachtelte Zeilen werden in ihre übergeordnete Zeile übernommen. ' : '');
    return {layout: result, notice: notice +
      'Das bestehende Layout wurde als dreizeiliger Entwurf übernommen. Reihenfolge und Elementformatierung bleiben erhalten; bisherige Gruppenabstände und Ausrichtungen bitte prüfen. Das gespeicherte Original bleibt bis zum Speichern erhalten.'};
  }
  function row(children = [], style = {}) {
    return {type: 'group', direction: 'row', style: {align: 'center', gap: 4, ...style}, children};
  }
  function template(name) {
    const el = (field, size = 14, extra = {}) => ({type: 'element', field, style: {size, ...extra}});
    const dot = () => ({...el('text', 22), text: '.'});
    const date = [el('day', 22), dot(), el('month_primary', 22)];
    const year = [el('year', 16), el('system_primary', 16)];
    const extra = [el('month_alternative', 12, {italic: true, color: 'muted'}),
      {...el('text', 12, {color: 'muted'}), text: '·'}, el('season', 12, {color: 'accent'})];
    const rows = name === 'Klassisch' ? [row([...date, ...year]), row(extra), row()] :
      name === 'Zweizeilig' ? [row(date), row([...year, ...extra]), row()] :
        [row(date), row(year), row(extra)];
    return {version: 2, root: {type: 'group', direction: 'column',
      style: {align: 'center', gap: 3}, children: rows}};
  }
  function editor(host, initial, data, onChange = () => {}, longValues = null) {
    let converted = normalize(initial);
    let layout = converted.layout;
    let baseline = JSON.stringify(layout);
    let history = [copy(layout)], position = 0;
    let selected = null, activeRow = 0, dragged = null, target = null;
    let long = false, narrow = false, pendingTemplate = null;
    let pointer = null, suppressClick = false;
    const boxes = new Map(), rowBoxes = new Map();
    host.classList.add('calendar-layout-editor');
    host.replaceChildren();
    const make = (tag, className, parent) => {
      const element = document.createElement(tag); element.className = className;
      if (parent) parent.append(element); return element;
    };
    const button = (parent, text, action, label = text) => {
      const element = make('button', '', parent); element.type = 'button';
      element.textContent = text; element.setAttribute('aria-label', label); element.title = label;
      element.addEventListener('click', action); return element;
    };
    const toolbar = make('div', 'calendar-layout-toolbar', host);
    const undo = button(toolbar, '↶', () => restore(-1), 'Rückgängig');
    const redo = button(toolbar, '↷', () => restore(1), 'Wiederholen');
    const longButton = button(toolbar, 'Langer Monat', () => { long = !long; drawCanvas(); }, 'Längster Monatsname');
    const narrowButton = button(toolbar, 'Kompakt', () => { narrow = !narrow; drawCanvas(); }, 'Kompakte Breite');
    longButton.setAttribute('aria-pressed', 'false'); narrowButton.setAttribute('aria-pressed', 'false');
    const templates = make('select', 'calendar-layout-templates', toolbar);
    templates.setAttribute('aria-label', 'Layoutvorlage');
    templates.append(new Option('Vorlage …', ''));
    ['Klassisch', 'Zweizeilig', 'Dreizeilig'].forEach(name => templates.append(new Option(name, name)));
    templates.addEventListener('change', () => {
      const name = templates.value; if (!name) return;
      if (JSON.stringify(layout) !== baseline) {
        pendingTemplate = name; confirmation.hidden = false;
        tools.hidden = true; placeholder.hidden = true;
        confirmationText.textContent = 'Ungespeicherte Änderungen durch „' + name + '“ ersetzen?';
      } else applyTemplate(name);
      templates.value = '';
    });
    const confirmation = make('div', 'calendar-layout-confirmation', host); confirmation.hidden = true;
    const confirmationText = make('span', '', confirmation);
    button(confirmation, 'Vorlage übernehmen', () => {
      if (pendingTemplate) applyTemplate(pendingTemplate);
    });
    button(confirmation, 'Abbrechen', () => {
      pendingTemplate = null; confirmation.hidden = true; drawTools();
    });
    const palette = make('div', 'calendar-layout-palette', host);
    palette.setAttribute('aria-label', 'Elementpalette');
    Object.entries(fields).forEach(([field, name]) => {
      const tile = button(palette, name, event => {
        if (suppressClick) { suppressClick = false; return; }
        add(field, activeRow, layout.root.children[activeRow].children.length);
      });
      tile.dataset.layoutField = field;
      draggable(tile, () => ({field}));
    });
    const help = button(toolbar, '?', () => {},
      'Kacheln ziehen oder anklicken. Elemente anklicken und unten formatieren. Ohne Ziehen: Alt + Pfeiltasten oder „Mehr“. Rückgängig: Strg/⌘ + Z; Wiederholen: Strg/⌘ + Umschalt + Z.');
    const status = make('div', 'calendar-layout-status', host);
    const note = make('span', 'calendar-layout-notice', status);
    note.textContent = converted.notice ? 'Übernahme des bisherigen Layouts prüfen' : ''; note.title = converted.notice;
    note.setAttribute('role', 'status');
    const viewport = make('div', 'calendar-layout-viewport', host);
    const zoom = make('div', 'calendar-layout-zoom', viewport);
    const canvas = make('div', 'calendar-layout-preview calendar-artifact', zoom);
    const actual = make('div', '', canvas);
    canvas.tabIndex = -1;
    canvas.addEventListener('click', event => {
      if (!event.target.closest('.calendar-layout-element')) { selected = null; draw(); }
    });
    const toolsSlot = make('div', 'calendar-layout-tools-slot', host);
    toolsSlot.append(confirmation);
    const placeholder = make('span', 'calendar-layout-tools-placeholder', toolsSlot);
    placeholder.textContent = 'Element zum Bearbeiten anklicken';
    const tools = make('div', 'calendar-layout-context', toolsSlot); tools.hidden = true;
    tools.setAttribute('role', 'toolbar'); tools.setAttribute('aria-label', 'Element bearbeiten');
    const hint = make('span', 'calendar-layout-hint', status); hint.setAttribute('role', 'status');
    const marker = make('span', 'calendar-layout-insertion');
    marker.setAttribute('aria-hidden', 'true');
    function count() { return layout.root.children.reduce((sum, line) => sum + line.children.length, 0); }
    function record() {
      const snapshot = JSON.stringify(layout);
      if (snapshot === JSON.stringify(history[position])) return;
      history = history.slice(0, position + 1); history.push(copy(layout));
      if (history.length > 100) history.shift();
      position = history.length - 1; onChange(copy(layout)); updateHistory();
    }
    function updateHistory() { undo.disabled = position === 0; redo.disabled = position === history.length - 1; }
    function restore(delta) {
      if (position + delta < 0 || position + delta >= history.length) return;
      cancelDrag();
      position += delta; layout = copy(history[position]); selected = null;
      onChange(copy(layout)); draw();
    }
    function applyTemplate(name) {
      cancelDrag();
      layout = template(name); selected = null; activeRow = 0;
      pendingTemplate = null; confirmation.hidden = true; record(); draw();
    }
    function locate(node) {
      for (let i = 0; i < 3; i++) {
        const index = layout.root.children[i].children.indexOf(node);
        if (index >= 0) return {row: i, index};
      }
      return null;
    }
    function add(field, line, index) {
      if (count() >= 128) { hint.textContent = 'Maximal 128 Datumsbestandteile.'; return; }
      const node = {type: 'element', field, style: {size: 14},
        ...(field === 'text' ? {text: ' · '} : {})};
      layout.root.children[line].children.splice(index, 0, node);
      selected = node; activeRow = line; record(); draw(); boxes.get(node)?.focus();
    }
    function move(node, line, index) {
      const old = locate(node); if (!old) return;
      if (old.row === line && old.index < index) index--;
      if (old.row === line && old.index === index) return;
      layout.root.children[old.row].children.splice(old.index, 1);
      layout.root.children[line].children.splice(index, 0, node);
      selected = node; activeRow = line; record(); draw(); boxes.get(node)?.focus();
    }
    function clearDrop(end = true) {
      marker.remove(); target = null;
      if (end) host.classList.remove('is-dragging');
      for (const box of rowBoxes.values()) box.classList.remove('is-drop-target');
    }
    function indicate(box, x, y) {
      clearDrop(false);
      host.classList.add('is-dragging');
      const line = Number(box.dataset.layoutRow);
      const nodes = layout.root.children[line].children;
      const rtl = window.getComputedStyle(box).direction === 'rtl';
      let index = nodes.length;
      for (let i = 0; i < nodes.length; i++) {
        const rect = boxes.get(nodes[i]).getBoundingClientRect();
        const sameLine = y === undefined || (y >= rect.top && y <= rect.bottom);
        const before = rtl ? x > rect.left + rect.width / 2 : x < rect.left + rect.width / 2;
        if ((y !== undefined && y < rect.top) || (sameLine && before)) { index = i; break; }
      }
      target = {row: line, index}; box.classList.add('is-drop-target');
      box.insertBefore(marker, index < nodes.length ? boxes.get(nodes[index]) : null);
    }
    function drop() {
      if (!dragged || !target) return;
      const destination = {...target}; const source = dragged; clearDrop();
      if (source.node) move(source.node, destination.row, destination.index);
      else add(source.field, destination.row, destination.index);
      dragged = null;
    }
    function draggable(element, source) {
      // One pointer path for mouse, pen and touch; native HTML dragging would
      // take over the gesture and cancel pointermove/pointerup delivery.
      element.draggable = false;
      element.addEventListener('dragstart', event => event.preventDefault());
      element.addEventListener('pointerdown', event => {
        if ((event.button !== undefined && event.button !== 0) || element.disabled || host.inert) return;
        pointer = {id: event.pointerId, x: event.clientX, y: event.clientY,
          source: source(), element, active: false};
        element.setPointerCapture(event.pointerId);
      });
      element.addEventListener('pointermove', event => {
        if (!pointer || pointer.id !== event.pointerId) return;
        if (event.pointerType === 'mouse' && event.buttons !== undefined && !(event.buttons & 1)) {
          cancelDrag(); return;
        }
        if (!pointer.active && Math.hypot(event.clientX - pointer.x, event.clientY - pointer.y) < 8) return;
        pointer.active = true; dragged = pointer.source; event.preventDefault();
        host.classList.add('is-dragging'); element.classList.add('is-drag-source');
        const under = document.elementFromPoint(event.clientX, event.clientY)?.closest('[data-layout-row]');
        if (under && actual.contains(under)) indicate(under, event.clientX, event.clientY); else clearDrop(false);
      });
      element.addEventListener('pointerup', event => {
        if (!pointer || pointer.id !== event.pointerId) return;
        if (pointer.active) {
          event.preventDefault(); suppressClick = true; drop();
          setTimeout(() => { suppressClick = false; }, 0);
        }
        cancelDrag();
      });
      element.addEventListener('pointercancel', cancelDrag);
      element.addEventListener('lostpointercapture', () => { if (pointer?.element === element) cancelDrag(); });
    }
    function cancelDrag() {
      const gesture = pointer; pointer = null; dragged = null;
      gesture?.element.classList.remove('is-drag-source');
      if (gesture?.element.hasPointerCapture?.(gesture.id)) gesture.element.releasePointerCapture(gesture.id);
      clearDrop();
    }
    function drawCanvas() {
      boxes.clear(); rowBoxes.clear();
      const width = narrow ? 250 : data._width || 330;
      canvas.style.width = width + 'px'; zoom.style.width = (width * 1.75) + 'px';
      canvas.dataset.season = data._season || 'neutral';
      longButton.setAttribute('aria-pressed', String(long));
      narrowButton.setAttribute('aria-pressed', String(narrow));
      render(actual, layout, long && longValues ? longValues : data, (box, node) => {
        if (node.type === 'group' && node !== layout.root) {
          const i = layout.root.children.indexOf(node); box.dataset.layoutRow = i;
          rowBoxes.set(i, box); box.classList.add('calendar-layout-edit-row');
          box.setAttribute('aria-label', 'Zeile ' + (i + 1));
          box.addEventListener('click', event => {
            if (event.target === box) { event.stopPropagation(); selected = null; activeRow = i; draw(); }
          });
        } else if (node.type === 'element') {
          boxes.set(node, box);
          box.setAttribute('role', 'button'); box.tabIndex = 0;
          box.setAttribute('aria-label', fields[node.field] + ': ' + (box.textContent || 'Noch kein Wert'));
          box.setAttribute('aria-pressed', String(selected === node));
          if (!box.textContent) {
            box.textContent = fields[node.field]; box.classList.add('is-empty-value');
          }
          if (node === selected) box.classList.add('is-layout-selected');
          const select = event => {
            event.stopPropagation();
            if (suppressClick) { suppressClick = false; return; }
            selected = node; activeRow = locate(node).row; drawCanvas(); drawTools();
            boxes.get(node)?.focus();
          };
          box.addEventListener('click', select);
          box.addEventListener('keydown', event => {
            if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(event); }
          });
          draggable(box, () => ({node}));
        }
      });
      for (const [i, box] of rowBoxes) {
        const shown = long && longValues ? longValues : data;
        if (layout.root.children[i].children.every(node => node.style?.visible === false ||
          !(node.field === 'text' ? node.text : shown[node.field]))) box.classList.add('is-empty-row');
      }
      const crowded = Array.from(rowBoxes.values()).some(box => {
        const children = Array.from(box.children).filter(child => child.classList.contains('calendar-layout-element'));
        const height = Math.max(0, ...children.map(child => child.getBoundingClientRect().height));
        const padding = Number.parseFloat(box.style.padding || '0') * 2 * 1.75;
        return box.scrollWidth > box.clientWidth + 1 ||
          (children.length > 0 && box.getBoundingClientRect().height > height + padding + 3);
      });
      hint.textContent = crowded ? 'Die Zeile ist für diese Breite zu groß. Abstände oder Schriftgrößen verkleinern.' : '';
      hint.title = hint.textContent;
    }
    function style(key, value) {
      if (!selected) return;
      selected.style ||= {};
      if (value === '') delete selected.style[key]; else selected.style[key] = value;
      record(); drawCanvas();
    }
    function selectTool(title, key, choices, parent = tools) {
      const label = make('label', '', parent); label.textContent = title;
      const input = make('select', '', label); input.setAttribute('aria-label', title);
      choices.forEach(([value, name]) => input.append(new Option(name, value)));
      const value = selected.style?.[key] || (key === 'size_mode' ? 'fixed' : '');
      input.value = choices.some(([choice]) => choice === value) ? value : '';
      input.addEventListener('change', () => style(key, input.value)); return input;
    }
    function drawTools() {
      tools.replaceChildren(); tools.hidden = !selected || !confirmation.hidden;
      placeholder.hidden = Boolean(selected) || !confirmation.hidden; if (!selected) return;
      tools.setAttribute('aria-label', fields[selected.field] + ' bearbeiten');
      const sizeRow = make('span', 'calendar-layout-size', tools);
      const size = () => selected.style?.size || 14;
      const field = make('input', ''); field.type = 'number';
      field.min = 8; field.max = 40; field.step = 1; field.value = size();
      field.setAttribute('aria-label', 'Schriftgröße');
      const sizing = selectTool('Schriftgröße', 'size_mode', [['fixed', 'Fest'], ['dynamic', 'Dynamisch anpassen']], sizeRow);
      const updateSizeLabel = () => {
        field.setAttribute('aria-label', selected.style?.size_mode === 'dynamic' ? 'Maximale Schriftgröße' : 'Schriftgröße');
        field.title = selected.style?.size_mode === 'dynamic' ? 'Maximale Schriftgröße; passt sich bis 8 px an die Zeile an.' : 'Feste Schriftgröße';
      };
      updateSizeLabel(); sizing.addEventListener('change', updateSizeLabel);
      button(sizeRow, '−', () => { style('size', Math.max(8, size() - 1)); field.value = size(); }, 'Schrift verkleinern');
      sizeRow.append(field);
      button(sizeRow, '+', () => { style('size', Math.min(40, size() + 1)); field.value = size(); }, 'Schrift vergrößern');
      field.addEventListener('input', () => {
        if (field.value !== '' && field.reportValidity()) style('size', Number(field.value));
      });
      const bold = button(tools, 'Fett', () => {
        style('weight', selected.style?.weight === 'bold' ? 'normal' : 'bold');
        bold.setAttribute('aria-pressed', String(selected.style.weight === 'bold'));
      }); bold.setAttribute('aria-pressed', String(selected.style?.weight === 'bold'));
      const italic = button(tools, 'Kursiv', () => {
        style('italic', !selected.style?.italic);
        italic.setAttribute('aria-pressed', String(selected.style.italic));
      }); italic.setAttribute('aria-pressed', String(Boolean(selected.style?.italic)));
      selectTool('Farbe', 'color', [['', 'Standard'], ['primary', 'Haupttext'], ['accent', 'Akzent'], ['muted', 'Gedämpft']]);
      button(tools, '🗑', () => {
        const found = locate(selected); layout.root.children[found.row].children.splice(found.index, 1);
        selected = null; record(); draw();
      }, 'Element entfernen');
      const more = make('details', 'calendar-layout-more', tools);
      const summary = make('summary', '', more); summary.textContent = 'Mehr';
      const lineLabel = make('label', '', more); lineLabel.textContent = 'Zeile';
      const line = make('select', '', lineLabel); line.setAttribute('aria-label', 'Zeile des Elements');
      ['Erste', 'Zweite', 'Dritte'].forEach((name, i) => line.append(new Option(name, i)));
      line.value = activeRow;
      line.addEventListener('change', () => move(selected, Number(line.value), layout.root.children[Number(line.value)].children.length));
      const alignment = make('div', 'calendar-layout-line-align', more);
      [['start', 'Links'], ['center', 'Zentriert'], ['end', 'Rechts']].forEach(([value, name]) => {
        const b = button(alignment, name, () => {
          layout.root.children[activeRow].style.align = value; record(); drawCanvas();
          Array.from(alignment.children).forEach(option => option.setAttribute('aria-pressed', String(option === b)));
        }, 'Zeile: ' + name);
        b.setAttribute('aria-pressed', String((layout.root.children[activeRow].style.align || 'center') === value));
      });
      selectTool('Elementausrichtung', 'align', [['', 'Wie Zeile'], ['start', 'Links'], ['center', 'Zentriert'], ['end', 'Rechts']], more);
      selectTool('Breite', 'width', [['', 'Automatisch'], ['fill', 'Ausfüllen']], more);
      if (selected.field === 'text') {
        const label = make('label', 'calendar-layout-text', more); label.textContent = 'Text';
        const input = make('input', '', label); input.type = 'text'; input.maxLength = 200;
        input.value = selected.text || '';
        input.addEventListener('input', () => { selected.text = input.value; record(); drawCanvas(); });
      }
      const visibility = make('label', '', more);
      const visible = make('input', '', visibility); visible.type = 'checkbox';
      visible.checked = selected.style?.visible !== false; visibility.append(document.createTextNode('Sichtbar'));
      visible.addEventListener('change', () => style('visible', visible.checked));
      [['Innenabstand', 'padding', selected.style || {}], ['Zeilenabstand', 'gap', layout.root.style],
        ['Abstand in dieser Zeile', 'gap', layout.root.children[activeRow].style]].forEach(([name, key, object]) => {
        const label = make('label', '', more); label.textContent = name + ' (px)';
        const input = make('input', '', label); input.type = 'number'; input.min = 0; input.max = 24;
        input.step = 1; input.value = object[key] ?? (key === 'gap' ? 3 : 0);
        input.addEventListener('input', () => {
          if (input.value === '' || !input.reportValidity()) return;
          if (name === 'Innenabstand') { style(key, Number(input.value)); return; }
          object[key] = Number(input.value); record(); drawCanvas();
        });
      });
    }
    function draw() { updateHistory(); drawCanvas(); drawTools(); }
    host.addEventListener('keydown', event => {
      if (event.key === 'Escape' && selected) {
        event.preventDefault(); event.stopPropagation(); selected = null; draw(); canvas.focus(); return;
      }
      const editing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName);
      if (editing) return;
      if ((event.ctrlKey || event.metaKey) && !event.altKey) {
        const key = event.key.toLowerCase();
        if (key === 'z' || key === 'y') {
          event.preventDefault(); event.stopPropagation();
          restore(key === 'y' || event.shiftKey ? 1 : -1);
        }
      }
      if (event.altKey && selected && ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
        event.preventDefault(); event.stopPropagation();
        const found = locate(selected);
        if (event.key === 'ArrowLeft') move(selected, found.row, Math.max(0, found.index - 1));
        if (event.key === 'ArrowRight') move(selected, found.row, Math.min(layout.root.children[found.row].children.length, found.index + 2));
        if (event.key === 'ArrowUp' && found.row > 0) move(selected, found.row - 1, layout.root.children[found.row - 1].children.length);
        if (event.key === 'ArrowDown' && found.row < 2) move(selected, found.row + 1, layout.root.children[found.row + 1].children.length);
        boxes.get(selected)?.focus();
      }
    });
    draw();
    return {getLayout: () => copy(layout),
      setLayout(next) {
        cancelDrag();
        converted = normalize(next); layout = converted.layout; baseline = JSON.stringify(layout);
        history = [copy(layout)]; position = 0; selected = null;
        pendingTemplate = null; confirmation.hidden = true;
        note.textContent = converted.notice ? 'Übernahme des bisherigen Layouts prüfen' : ''; note.title = converted.notice;
        onChange(copy(layout)); draw();
      },
      setValues(next, longest = null) { data = next; longValues = longest; if (!pointer) drawCanvas(); },
      destroy() { cancelDrag(); renderObservers.get(actual)?.disconnect(); renderObservers.delete(actual); renderFits.delete(actual); }};
  }
  window.CalendarLayout = {render, editor, values, split, normalize, template};
  function initAdmin() {
    document.querySelectorAll('[data-calendar-layout-widget]').forEach(widget => {
      const hidden = widget.querySelector('input');
      const initial = JSON.parse(widget.querySelector('[data-layout-initial]').textContent);
      const fallback = JSON.parse(widget.querySelector('[data-layout-fallback]').textContent);
      const host = widget.querySelector('[data-layout-host]');
      const get = name => document.getElementById(`id_${name}`)?.value || '';
      const control = editor(host, initial || fallback, {}, layout => { hidden.value = JSON.stringify(layout); });
      let previewMonths = [];
      const refresh = () => {
        const monthSelect = document.getElementById('id_anchor_month');
        const selected = monthSelect?.selectedOptions[0];
        const data = {day: get('anchor_day') || '1', year: get('anchor_year') || '0',
          month_name: selected?.value ? selected.textContent : '', abbreviation: get('abbreviation')};
        const rows = Array.from(document.querySelectorAll('[data-month-row]')).filter(row =>
          !row.querySelector('[name$="-DELETE"]')?.checked);
        const months = rows.map(row => ({name: row.querySelector('[name$="-name"]')?.value || '',
          season: row.querySelector('[name$="-season"]')?.selectedOptions[0]?.textContent || ''}));
        const number = Number(get('anchor_month'));
        if (get('calendar_mode') !== 'existing' && months[number - 1]) data.month_name = months[number - 1].name;
        const month = months.find(row => row.name === data.month_name);
        data.season = {name: month?.season === '---------' ? '' : month?.season || ''};
        const calculated = previewMonths.find(row => row.number === number);
        if (calculated) data.season = calculated.season;
        const candidates = get('calendar_mode') === 'existing' && previewMonths.length ? previewMonths : months;
        const longest = candidates.reduce((a, b) => a.name.length >= b.name.length ? a : b, {name: data.month_name});
        control.setValues({...values(data), _season: data.season?.style}, values({...data, month_name: longest.name}));
      };
      document.querySelector('form')?.addEventListener('calendar-layout-preview', event => {
        previewMonths = event.detail; refresh();
      });
      document.querySelector('form')?.addEventListener('input', refresh);
      document.querySelector('form')?.addEventListener('change', refresh);
      const monthSelect = document.getElementById('id_anchor_month');
      if (monthSelect) new MutationObserver(refresh).observe(monthSelect, {childList: true});
      buttonOutside(widget, 'Globales Fallback verwenden', () => {
        control.setLayout(fallback); hidden.value = '';
      });
      refresh();
    });
  }
  function buttonOutside(parent, title, action) {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = title;
    button.addEventListener('click', action); parent.append(button);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initAdmin);
  else initAdmin();
})();
