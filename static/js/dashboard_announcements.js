import { renderJournalMarkdown } from './charsheet/journal_markdown.js';

const region = document.querySelector('.dashboard_announcements');
const editor = region?.querySelector('.announcement_editor');
const form = editor?.querySelector('[data-announcement-form]');
const createUrl = form?.action;
const reader = region ? document.createElement('dialog') : null;
let activeToggle;

if (reader) {
  reader.id = 'announcement-reader';
  reader.className = 'announcement_reader';
  reader.setAttribute('aria-labelledby', 'announcement-reader-title');
  reader.innerHTML = '<header class="announcement_reader_header">'
    + '<h2 id="announcement-reader-title">Nachricht</h2>'
    + '<button type="button" class="announcement_icon" aria-label="Schließen" title="Schließen">&times;</button>'
    + '</header><div class="announcement_reader_body"></div>';
  document.body.appendChild(reader);
  const closeReader = () => {
    reader.close();
    activeToggle?.setAttribute('aria-expanded', 'false');
    activeToggle?.focus();
  };
  reader.querySelector('button').addEventListener('click', closeReader);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && reader.open && !editor?.open) {
      event.preventDefault();
      closeReader();
    }
  });
  const header = reader.querySelector('header');
  let drag;
  const moveReader = (left, top) => {
    reader.style.margin = '0';
    reader.style.left = `${Math.max(12, Math.min(left, window.innerWidth - reader.offsetWidth - 12))}px`;
    reader.style.top = `${Math.max(12, Math.min(top, window.innerHeight - reader.offsetHeight - 12))}px`;
  };
  header.addEventListener('pointerdown', (event) => {
    if (event.button !== 0 || event.target.closest('button')) return;
    const rect = reader.getBoundingClientRect();
    drag = { x: event.clientX - rect.left, y: event.clientY - rect.top };
    header.setPointerCapture(event.pointerId);
    moveReader(rect.left, rect.top);
    event.preventDefault();
  });
  header.addEventListener('pointermove', (event) => {
    if (drag) moveReader(event.clientX - drag.x, event.clientY - drag.y);
  });
  header.addEventListener('lostpointercapture', () => { drag = null; });
  header.addEventListener('pointerup', (event) => {
    if (header.hasPointerCapture(event.pointerId)) header.releasePointerCapture(event.pointerId);
  });
  window.addEventListener('resize', () => {
    if (!reader.open) return;
    const rect = reader.getBoundingClientRect();
    moveReader(rect.left, rect.top);
  });
}

region?.querySelectorAll('[data-announcement]').forEach((toast) => {
  const body = toast.querySelector('[data-announcement-body]');
  const preview = toast.querySelector('[data-announcement-preview]');
  body.innerHTML = renderJournalMarkdown(toast.querySelector('[data-announcement-source]').textContent);
  // Preserve safe Markdown formatting, including bold titles, when collapsed.
  preview.replaceChildren(...body.cloneNode(true).childNodes);
  const toggle = toast.querySelector('[data-announcement-toggle]');
  toggle.setAttribute('aria-controls', reader.id);
  toggle.setAttribute('aria-haspopup', 'dialog');
  toggle.addEventListener('click', () => {
    activeToggle?.setAttribute('aria-expanded', 'false');
    activeToggle = toggle;
    toggle.setAttribute('aria-expanded', 'true');
    reader.className = `announcement_reader ${Array.from(toast.classList).find((name) => name.startsWith('announcement--')) || ''}`;
    reader.querySelector('#announcement-reader-title').textContent =
      body.querySelector('h1, h2, h3, h4, h5, h6')?.textContent.trim() || 'Nachricht';
    reader.querySelector('.announcement_reader_body').replaceChildren(...body.cloneNode(true).childNodes);
    reader.style.removeProperty('left');
    reader.style.removeProperty('top');
    reader.style.removeProperty('margin');
    if (!reader.open) reader.show();
    reader.querySelector('button').focus();
  });
});

// Expire locally too, without polling the server or keeping a timer per toast.
let expiryTimer;
function expireAnnouncements() {
  clearTimeout(expiryTimer);
  let next = Infinity;
  region?.querySelectorAll('[data-expires]').forEach((toast) => {
    const remaining = Date.parse(toast.dataset.expires) - Date.now();
    if (remaining <= 0) toast.remove();
    else next = Math.min(next, remaining);
  });
  if (Number.isFinite(next)) expiryTimer = setTimeout(expireAnnouncements, Math.min(next + 50, 2147483647));
}
expireAnnouncements();
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) expireAnnouncements();
});

function openAnnouncementEditor(editButton = null) {
  form.reset();
  form.action = editButton ? editButton.dataset.editAnnouncement : createUrl;
  editor.querySelector('[data-announcement-error]').hidden = true;
  editor.querySelector('#announcement-editor-title').textContent = editButton
    ? 'Nachricht bearbeiten' : 'Nachricht erstellen';
  form.querySelector('[type="submit"]').textContent = editButton
    ? 'Speichern' : 'Für alle veröffentlichen';
  if (editButton) {
    const toast = editButton.closest('[data-announcement]');
    form.elements.kind.value = editButton.dataset.kind;
    form.elements.text.value = toast.querySelector('[data-announcement-source]').textContent;
    if (toast.dataset.expires) {
      const expiry = new Date(toast.dataset.expires);
      const localTime = new Date(expiry.getTime() - expiry.getTimezoneOffset() * 60000);
      form.elements.expires_at.value = localTime.toISOString().slice(0, 19);
    }
  }
  updatePreview();
  editor.showModal();
}

region?.querySelector('[data-announcement-open]')?.addEventListener('click', () => openAnnouncementEditor());
region?.querySelectorAll('[data-edit-announcement]').forEach((button) => {
  button.addEventListener('click', () => openAnnouncementEditor(button));
});
editor?.querySelector('[data-announcement-close]')?.addEventListener('click', () => editor.close());

function updatePreview() {
  const live = editor.querySelector('[data-announcement-live]');
  live.className = `announcement announcement_live announcement--${form.elements.kind.value}`;
  const icons = { update: '🆕', warning: '⚠️', critical: '🚨' };
  live.innerHTML = `<span class="announcement_kind" aria-hidden="true">${icons[form.elements.kind.value]}</span>`
    + renderJournalMarkdown(form.elements.text.value);
}
form?.addEventListener('input', updatePreview);

async function submitForm(target, data) {
  const response = await fetch(target.action, {
    method: 'POST', body: data, credentials: 'same-origin',
    headers: { 'X-CSRFToken': data.get('csrfmiddlewaretoken') },
  });
  if (!response.ok) {
    const result = await response.json().catch(() => null);
    throw new Error(result?.errors
      ? Object.values(result.errors).flat().join(' ')
      : 'Die Nachricht konnte nicht gespeichert oder gelöscht werden. Bitte erneut versuchen.');
  }
}

form?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const error = editor.querySelector('[data-announcement-error]');
  const button = form.querySelector('[type="submit"]');
  error.hidden = true;
  button.disabled = true;
  try {
    const data = new FormData(form);
    const localExpiry = data.get('expires_at');
    if (localExpiry) data.set('expires_at', new Date(localExpiry).toISOString());
    await submitForm(form, data);
    window.location.reload();
  } catch (failure) {
    error.textContent = failure.message;
    error.hidden = false;
    button.disabled = false;
  }
});

region?.querySelectorAll('[data-delete-announcement]').forEach((deleteForm) => {
  deleteForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = deleteForm.querySelector('[type="submit"]');
    button.disabled = true;
    try {
      await submitForm(deleteForm, new FormData(deleteForm));
      deleteForm.closest('[data-announcement]').remove();
    } catch (failure) {
      button.disabled = false;
      window.alert(failure.message);
    }
  });
});
