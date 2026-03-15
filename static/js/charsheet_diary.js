document.addEventListener("DOMContentLoaded", () => {
  const diaryWindow = document.getElementById("diaryWindow");
  const diaryMeta = diaryWindow?.querySelector("[data-diary-list-url]");
  const counterEl = document.getElementById("diaryRollCounter");
  const hintEl = document.getElementById("diaryRollHint");
  const entryEl = document.getElementById("diaryRollEntry");
  const segmentEl = document.getElementById("diaryRollSegment");
  const inputEl = document.getElementById("diaryRollInput");
  const dateInputEl = document.getElementById("diaryRollDateInput");
  const dateDisplayEl = document.getElementById("diaryRollDateDisplay");
  const titleEl = document.getElementById("diaryRollEntryTitle");
  const stateEl = document.getElementById("diaryRollEntryState");
  const prevBtn = document.getElementById("diaryRollPrevBtn");
  const nextBtn = document.getElementById("diaryRollNextBtn");
  const modeBtn = document.getElementById("diaryRollModeBtn");
  const deleteBtn = document.getElementById("diaryRollDeleteBtn");

  if (
    !diaryWindow
    || !diaryMeta
    || !counterEl
    || !hintEl
    || !entryEl
    || !segmentEl
    || !inputEl
    || !dateInputEl
    || !dateDisplayEl
    || !titleEl
    || !stateEl
    || !prevBtn
    || !nextBtn
    || !modeBtn
    || !deleteBtn
  ) {
    return;
  }

  const listUrl = diaryMeta.dataset.diaryListUrl || "";
  const importUrl = diaryMeta.dataset.diaryImportUrl || "";
  const characterId = diaryMeta.dataset.characterId || diaryWindow.dataset.characterId || "";
  const legacyStorageKey = characterId ? `charsheet.diary.${characterId}` : "";
  const legacyPageStorageKey = characterId ? `charsheet.diary.page.${characterId}` : "";
  const saveDelayMs = 420;
  const fixIcon = `
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M5 13l4 4L19 7"></path>
      <path d="M7 4h10"></path>
    </svg>
  `;
  const editIcon = `
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M4 20h4l10-10-4-4L4 16v4z"></path>
      <path d="M13.8 6.2l4 4"></path>
    </svg>
  `;

  let entries = [];
  let currentIndex = 0;
  let lastRequestedIndex = 0;
  let saveTimer = null;
  let pendingSavePayload = null;
  let isLoading = false;
  let isProgrammaticUpdate = false;

  const getCsrfToken = () => {
    return document.cookie
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith("csrftoken="))
      ?.split("=")[1] || "";
  };

  const entryUrl = (entryId, action) => `${listUrl}${entryId}/${action}/`;
  const currentEntry = () => entries[currentIndex] || null;
  const isEmpty = (entry) => !String(entry?.text || "").trim();
  const isTailEntry = (entry) => Boolean(entry) && currentIndex === entries.length - 1;
  const isPlaceholderEntry = (entry) => Boolean(entry) && !entry.is_fixed && isEmpty(entry) && isTailEntry(entry);

  const formatHandwrittenDate = (rawValue) => {
    if (!rawValue) {
      return "";
    }
    const parsed = new Date(rawValue);
    if (Number.isNaN(parsed.getTime())) {
      return String(rawValue);
    }
    return parsed.toLocaleDateString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  };

  const setHint = (text, tone = "") => {
    hintEl.textContent = text;
    hintEl.dataset.tone = tone;
  };

  const setLoading = (loading) => {
    isLoading = loading;
    entryEl.classList.toggle("is-loading", loading);
    prevBtn.disabled = loading || currentIndex <= 0;
    nextBtn.disabled = loading || currentIndex >= entries.length - 1;
    deleteBtn.disabled = loading || !currentEntry();
    modeBtn.disabled = loading || !currentEntry();
  };

  const animateRoll = (direction) => {
    segmentEl.animate(
      [
        { opacity: 0.92, transform: "translateY(0) scale(1)" },
        { opacity: 0.26, transform: `translateY(${direction > 0 ? "-18%" : "18%"}) scale(0.985)` },
        { opacity: 1, transform: "translateY(0) scale(1)" },
      ],
      {
        duration: 320,
        easing: "cubic-bezier(0.33, 1, 0.68, 1)",
      },
    );
  };

  const renderEntry = () => {
    const entry = currentEntry();
    if (!entry) {
      entryEl.dataset.entryId = "";
      inputEl.value = "";
      counterEl.textContent = "Eintrag 0 / 0";
      titleEl.textContent = "Leere Rolle";
      stateEl.textContent = "Kein Eintrag";
      setHint("Noch keine Rolle geladen.");
      setLoading(false);
      return;
    }

    const placeholder = isPlaceholderEntry(entry);
    const editable = !entry.is_fixed;
    const entryNumber = Number(entry.order_index || 0) + 1;
    const totalEntries = entries.length;

    isProgrammaticUpdate = true;
    entryEl.dataset.entryId = String(entry.id);
    entryEl.classList.toggle("is-fixed", Boolean(entry.is_fixed));
    entryEl.classList.toggle("is-editing", editable && !placeholder);
    entryEl.classList.toggle("is-placeholder", placeholder);
    inputEl.value = entry.text || "";
    inputEl.readOnly = !editable;
    dateInputEl.value = entry.entry_date || (placeholder ? new Date().toISOString().slice(0, 10) : "");
    dateInputEl.disabled = Boolean(entry.entry_date) || entry.is_fixed || (!placeholder && !editable);
    dateDisplayEl.textContent = entry.is_fixed ? formatHandwrittenDate(entry.entry_date) : "";
    dateDisplayEl.hidden = !entry.is_fixed;
    dateInputEl.hidden = Boolean(entry.is_fixed);
    titleEl.textContent = placeholder ? "Neuer Eintrag" : `Eintrag ${entryNumber}`;
    stateEl.textContent = entry.is_fixed ? "Fixiert" : (placeholder ? "Neue Schreibflaeche" : "Bearbeitungsmodus");
    counterEl.textContent = `Eintrag ${entryNumber} / ${totalEntries}`;
    modeBtn.innerHTML = entry.is_fixed ? editIcon : fixIcon;
    modeBtn.title = entry.is_fixed ? "Eintrag bewusst bearbeiten" : "Eintrag fixieren";
    modeBtn.setAttribute("aria-label", modeBtn.title);
    setHint(
      placeholder ? "" : (entry.is_fixed ? "" : "Bearbeitungsmodus aktiv."),
      entry.is_fixed ? "fixed" : (placeholder ? "draft" : "editing"),
    );
    isProgrammaticUpdate = false;
    setLoading(false);
  };

  const applyPayload = (payload, preferredEntryId = null) => {
    if (!payload || !Array.isArray(payload.entries)) {
      return;
    }
    entries = payload.entries;
    const desiredId = preferredEntryId ?? payload.current_entry_id ?? currentEntry()?.id ?? null;
    const nextIndex = entries.findIndex((entry) => entry.id === desiredId);
    currentIndex = nextIndex >= 0 ? nextIndex : Math.min(lastRequestedIndex, Math.max(0, entries.length - 1));
    renderEntry();
  };

  const request = async (url, options = {}) => {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      ...options,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(String(payload.error || "diary_request_failed"));
    }
    return payload;
  };

  const readLegacyEntries = () => {
    if (!legacyStorageKey) {
      return [];
    }
    try {
      const raw = window.localStorage.getItem(legacyStorageKey);
      const parsed = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(parsed)) {
        return [];
      }
      return parsed
        .filter((entry) => entry && typeof entry === "object")
        .map((entry) => ({
          text: String(entry.text || ""),
          createdAt: String(entry.createdAt || ""),
          isSaved: typeof entry.isSaved === "boolean" ? entry.isSaved : true,
        }))
        .filter((entry) => entry.text.trim());
    } catch (_error) {
      return [];
    }
  };

  const clearLegacyEntries = () => {
    if (!legacyStorageKey) {
      return;
    }
    try {
      window.localStorage.removeItem(legacyStorageKey);
      if (legacyPageStorageKey) {
        window.localStorage.removeItem(legacyPageStorageKey);
      }
    } catch (_error) {
      // no-op
    }
  };

  const payloadHasRealEntries = (payload) => {
    return Boolean(
      payload
      && Array.isArray(payload.entries)
      && payload.entries.some((entry) => entry.is_fixed || String(entry.text || "").trim()),
    );
  };

  const maybeImportLegacyEntries = async (payload) => {
    if (!importUrl || payloadHasRealEntries(payload)) {
      return payload;
    }
    const legacyEntries = readLegacyEntries();
    if (!legacyEntries.length) {
      return payload;
    }

    setHint("Alte Tagebucheintraege werden uebernommen...", "editing");
    try {
      const importedPayload = await request(importUrl, {
        method: "POST",
        body: JSON.stringify({ entries: legacyEntries }),
      });
      clearLegacyEntries();
      return importedPayload;
    } catch (_error) {
      setHint("Die alten Tagebucheintraege konnten nicht automatisch uebernommen werden.", "error");
      return payload;
    }
  };

  const loadEntries = async (preferredEntryId = null) => {
    setLoading(true);
    try {
      let payload = await request(listUrl, { method: "GET" });
      payload = await maybeImportLegacyEntries(payload);
      applyPayload(payload, preferredEntryId);
    } catch (_error) {
      setHint("Die Pergamentrolle konnte nicht geladen werden.", "error");
      setLoading(false);
    }
  };

  const saveDraft = async (payloadToSave) => {
    if (!payloadToSave) {
      return;
    }
    const payload = await request(entryUrl(payloadToSave.entryId, "save"), {
      method: "POST",
      body: JSON.stringify({
        text: payloadToSave.text,
        entry_date: payloadToSave.entryDate,
      }),
    });
    applyPayload(payload, payloadToSave.entryId);
  };

  const flushPendingSave = async () => {
    if (!pendingSavePayload) {
      return;
    }
    window.clearTimeout(saveTimer);
    const payloadToSave = pendingSavePayload;
    pendingSavePayload = null;
    await saveDraft(payloadToSave);
  };

  const queueSave = () => {
    if (isProgrammaticUpdate || isLoading) {
      return;
    }
    const entry = currentEntry();
    if (!entry || entry.is_fixed) {
      return;
    }
    pendingSavePayload = {
      entryId: entry.id,
      text: inputEl.value,
      entryDate: dateInputEl.value || "",
    };
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(() => {
      flushPendingSave().catch((_error) => {
        setHint("Der Entwurf konnte nicht gespeichert werden.", "error");
      });
    }, saveDelayMs);
  };

  const showEntryAt = async (targetIndex) => {
    if (targetIndex < 0 || targetIndex >= entries.length || targetIndex === currentIndex || isLoading) {
      return;
    }
    try {
      await flushPendingSave();
    } catch (_error) {
      setHint("Der aktuelle Entwurf konnte nicht gesichert werden.", "error");
      return;
    }
    const direction = targetIndex > currentIndex ? 1 : -1;
    lastRequestedIndex = targetIndex;
    currentIndex = targetIndex;
    animateRoll(direction);
    renderEntry();
  };

  const beginEditing = async () => {
    const entry = currentEntry();
    if (!entry || !entry.is_fixed) {
      return;
    }
    setLoading(true);
    try {
      const payload = await request(entryUrl(entry.id, "edit"), { method: "POST", body: "{}" });
      applyPayload(payload, entry.id);
      inputEl.focus();
    } catch (_error) {
      setHint("Der Eintrag konnte nicht entsiegelt werden.", "error");
      setLoading(false);
    }
  };

  const fixEntry = async () => {
    const entry = currentEntry();
    if (!entry || isLoading) {
      return;
    }
    if (!String(inputEl.value || "").trim()) {
      setHint("Leere Eintraege koennen nicht fixiert werden.", "error");
      return;
    }
    setLoading(true);
    try {
      const payload = await request(entryUrl(entry.id, "fix"), {
        method: "POST",
        body: JSON.stringify({
          text: inputEl.value,
          entry_date: dateInputEl.value || "",
        }),
      });
      applyPayload(payload, entry.id);
    } catch (_error) {
      setHint("Der Eintrag konnte nicht fixiert werden.", "error");
      setLoading(false);
    }
  };

  const deleteEntry = async () => {
    const entry = currentEntry();
    if (!entry || isLoading) {
      return;
    }
    setLoading(true);
    try {
      const payload = await request(entryUrl(entry.id, "delete"), { method: "POST", body: "{}" });
      applyPayload(payload);
    } catch (_error) {
      setHint("Der Eintrag konnte nicht geloescht werden.", "error");
      setLoading(false);
    }
  };

  prevBtn.addEventListener("click", async () => {
    await showEntryAt(currentIndex - 1);
  });

  nextBtn.addEventListener("click", async () => {
    await showEntryAt(currentIndex + 1);
  });

  modeBtn.addEventListener("click", () => {
    const entry = currentEntry();
    if (!entry) {
      return;
    }
    if (entry.is_fixed) {
      beginEditing();
      return;
    }
    fixEntry();
  });

  deleteBtn.addEventListener("click", () => {
    deleteEntry();
  });

  inputEl.addEventListener("input", () => {
    queueSave();
  });

  dateInputEl.addEventListener("change", () => {
    queueSave();
  });

  loadEntries();
});
