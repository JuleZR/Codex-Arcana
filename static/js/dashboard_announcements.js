import { renderJournalMarkdown } from './charsheet/journal_markdown.js';

const region = document.querySelector('.dashboard_announcements');
const editor = region?.querySelector('.announcement_editor');
const form = editor?.querySelector('[data-announcement-form]');

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

region?.querySelector('[data-announcement-open]')?.addEventListener('click', () => editor.showModal());
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
    const button = deleteForm.querySelector('button');
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
