import { renderJournalMarkdown } from './charsheet/journal_markdown.js';

const region = document.querySelector('.dashboard_announcements');
const editor = region?.querySelector('.announcement_editor');
const form = editor?.querySelector('[data-announcement-form]');
const createUrl = form?.action;

region?.querySelectorAll('[data-announcement]').forEach((toast) => {
  const body = toast.querySelector('[data-announcement-body]');
  const preview = toast.querySelector('[data-announcement-preview]');
  body.innerHTML = renderJournalMarkdown(toast.querySelector('[data-announcement-source]').textContent);
  // Preserve safe Markdown formatting, including bold titles, when collapsed.
  preview.replaceChildren(...body.cloneNode(true).childNodes);
  const toggle = toast.querySelector('[data-announcement-toggle]');
  toggle.addEventListener('click', () => {
    const expanded = toggle.getAttribute('aria-expanded') !== 'true';
    toggle.setAttribute('aria-expanded', String(expanded));
    toggle.textContent = expanded ? 'Weniger anzeigen' : 'Mehr anzeigen';
    preview.hidden = expanded;
    body.hidden = !expanded;
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
