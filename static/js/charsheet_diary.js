import { initBookViewer } from "./charsheet/book_viewer.js?v=20260917e";
import { journalTitle, renderJournalMarkdown } from "./charsheet/journal_markdown.js?v=20260917a";

document.addEventListener("DOMContentLoaded", () => {
  const diaryWindow = document.getElementById("diaryWindow");
  const diaryMeta = diaryWindow?.querySelector("[data-diary-list-url]");
  const hintEl = document.getElementById("diaryRollHint");
  const entryEl = document.getElementById("diaryRollEntry");
  const segmentEl = document.getElementById("diaryRollSegment");
  const inputEl = document.getElementById("diaryRollInput");
  const dateInputEl = document.getElementById("diaryRollDateInput");
  const dateDisplayEl = document.getElementById("diaryRollDateDisplay");
  const titleEl = document.getElementById("diaryRollEntryTitle");
  const modeBtn = document.getElementById("diaryRollModeBtn");
  const deleteBtn = document.getElementById("diaryRollDeleteBtn");
  const contentsEl = document.getElementById("diaryContents");
  const previewEl = document.getElementById("diaryMarkdownPreview");
  const previewBtn = document.getElementById("diaryPreviewBtn");
  const markdownHelpEl = document.getElementById("diaryMarkdownHelp");
  const markdownHelpBtn = document.getElementById("diaryMarkdownHelpBtn");
  const markdownHelpClose = document.getElementById("diaryMarkdownHelpClose");
  const coverEl = document.getElementById("diaryCover");
  const indexEl = document.getElementById("diaryIndex");
  const backEl = document.getElementById("diaryBackCover");
  const editorHost = document.getElementById("diaryEditorHost");
  const editorDone = document.getElementById("diaryEditorDone");

  if (
    !diaryWindow
    || !diaryMeta
    || !hintEl
    || !entryEl
    || !segmentEl
    || !inputEl
    || !dateInputEl
    || !dateDisplayEl
    || !titleEl
    || !modeBtn
    || !deleteBtn
    || !contentsEl
    || !previewEl
    || !previewBtn
    || !markdownHelpEl
    || !markdownHelpBtn
    || !markdownHelpClose
    || !coverEl
    || !indexEl
    || !backEl
    || !editorHost
    || !editorDone
  ) {
    return;
  }

  const listUrl = diaryMeta.dataset.diaryListUrl || "";
  const importUrl = diaryMeta.dataset.diaryImportUrl || "";
  const readOnlyMode = diaryMeta.dataset.readOnly === "1";
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
  const contentsIcon = `
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M5 5.5h5.5A2.5 2.5 0 0 1 13 8v11a2.5 2.5 0 0 0-2.5-2.5H5z"></path>
      <path d="M19 5.5h-3"></path>
      <path d="M19 9.5h-3"></path>
      <path d="M19 13.5h-3"></path>
    </svg>
  `;
  const previewIcon = `
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6z"></path>
      <circle cx="12" cy="12" r="2.5"></circle>
    </svg>
  `;
  const readIcon = `
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M4 5.5h6A2.5 2.5 0 0 1 12.5 8v11A2.5 2.5 0 0 0 10 16.5H4z"></path>
      <path d="M20 5.5h-5A2.5 2.5 0 0 0 12.5 8v11a2.5 2.5 0 0 1 2.5-2.5h5z"></path>
    </svg>
  `;
  const deleteIcon = `
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M5 7h14"></path>
      <path d="M9 7V4h6v3"></path>
      <path d="M7 7l1 13h8l1-13"></path>
      <path d="M10 11v5M14 11v5"></path>
    </svg>
  `;
  const infoIcon = `
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="9"></circle>
      <path d="M12 10.5v6"></path>
      <path d="M12 7.5h.01"></path>
    </svg>
  `;

  markdownHelpBtn.innerHTML = infoIcon;
  editorDone.innerHTML = readIcon;
  editorDone.title = "Zur Leseansicht";
  editorDone.setAttribute("aria-label", editorDone.title);
  deleteBtn.innerHTML = deleteIcon;

  let entries = [];
  let currentIndex = 0;
  let lastRequestedIndex = 0;
  let saveTimer = null;
  let pendingSavePayload = null;
  let activeSave = null;
  let isLoading = false;
  let isProgrammaticUpdate = false;
  let previewMode = false;
  let isTurning = false;
  let editingIndex = null;
  let renderedPages = [];

  const closeMarkdownHelp = () => {
    markdownHelpEl.hidden = true;
    markdownHelpBtn.setAttribute("aria-expanded", "false");
    markdownHelpBtn.title = "Markdown-Hilfe";
    markdownHelpBtn.setAttribute("aria-label", "Markdown-Hilfe anzeigen");
  };
  closeMarkdownHelp();

  const renderPreview = () => {
    const showPreview = previewMode || inputEl.readOnly;
    previewEl.innerHTML = renderJournalMarkdown(inputEl.value);
    previewEl.hidden = !showPreview;
    inputEl.hidden = showPreview;
    previewBtn.hidden = inputEl.readOnly;
    previewBtn.innerHTML = showPreview ? editIcon : previewIcon;
    previewBtn.title = showPreview ? "Weiterschreiben" : "Vorschau anzeigen";
    previewBtn.setAttribute("aria-label", previewBtn.title);
    previewBtn.setAttribute("aria-pressed", String(showPreview));
  };

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
    deleteBtn.disabled = readOnlyMode || loading || !currentEntry();
    modeBtn.disabled = readOnlyMode || loading || !currentEntry();
  };

  const resetPage = () => {
    closeMarkdownHelp();
    inputEl.scrollTop = 0;
    previewEl.scrollTop = 0;
    previewMode = false;
  };

  const renderEntry = () => {
    const entry = currentEntry();
    contentsEl.replaceChildren();
    entries.forEach((item, index) => {
      const heading = journalTitle(item.text);
      const label = `${index + 1}. ${item.entry_date || "Neuer Eintrag"}${heading ? ` – ${heading}` : ""}`;
      const row = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.setAttribute("aria-current", index === currentIndex ? "page" : "false");
      button.setAttribute("data-book-page-target", String(index + 2));
      row.append(button);
      contentsEl.append(row);
    });
    if (!entry) {
      entryEl.dataset.entryId = "";
      inputEl.value = "";
      inputEl.readOnly = true;
      renderPreview();
      dateInputEl.disabled = true;
      dateInputEl.value = "";
      dateDisplayEl.textContent = "";
      titleEl.textContent = "Leeres Tagebuch";
      setHint("Noch keine Einträge.");
      setLoading(false);
      return;
    }

    const placeholder = isPlaceholderEntry(entry);
    const editable = !readOnlyMode && !entry.is_fixed;
    const entryNumber = Number(entry.order_index || 0) + 1;
    isProgrammaticUpdate = true;
    entryEl.dataset.entryId = String(entry.id);
    entryEl.classList.toggle("is-fixed", Boolean(entry.is_fixed));
    entryEl.classList.toggle("is-editing", editable && !placeholder);
    entryEl.classList.toggle("is-placeholder", placeholder);
    inputEl.value = entry.text || "";
    inputEl.readOnly = !editable;
    renderPreview();
    dateInputEl.value = entry.entry_date || (placeholder ? new Date().toISOString().slice(0, 10) : "");
    dateInputEl.disabled = readOnlyMode || !editable;
    dateDisplayEl.textContent = entry.is_fixed ? formatHandwrittenDate(entry.entry_date) : "";
    dateDisplayEl.hidden = !entry.is_fixed;
    dateInputEl.hidden = Boolean(entry.is_fixed);
    titleEl.textContent = journalTitle(entry.text) || (placeholder ? "Neuer Eintrag" : `Eintrag ${entryNumber}`);
    modeBtn.innerHTML = entry.is_fixed ? editIcon : fixIcon;
    modeBtn.title = readOnlyMode ? "Leseansicht" : (entry.is_fixed ? "Eintrag bewusst bearbeiten" : "Eintrag fixieren");
    modeBtn.setAttribute("aria-label", modeBtn.title);
    setHint("", entry.is_fixed ? "fixed" : (placeholder ? "draft" : "editing"));
    isProgrammaticUpdate = false;
    setLoading(false);
  };

  const applyPayload = (payload, preferredEntryId = null, updateBook = true) => {
    if (!payload || !Array.isArray(payload.entries)) {
      return;
    }
    entries = payload.entries;
    const desiredId = preferredEntryId ?? payload.current_entry_id ?? currentEntry()?.id ?? null;
    const nextIndex = entries.findIndex((entry) => entry.id === desiredId);
    currentIndex = nextIndex >= 0 ? nextIndex : Math.min(lastRequestedIndex, Math.max(0, entries.length - 1));
    renderEntry();
    if (updateBook) renderBookPages();
  };

  const attachEditor = () => {
    const page = renderedPages[editingIndex];
    if (!page) return;
    renderedPages.forEach((renderedPage) => renderedPage.classList.remove("is-editing-page"));
    page.classList.add("is-editing-page");
    page.append(entryEl);
    entryEl.hidden = false;
  };

  const renderBookPages = () => {
    const pages = entries.map((entry, index) => {
      const page = document.createElement("article");
      page.className = "book_page journal-book__page";
      page.setAttribute("data-book-page-index", String(index + 2));
      const layout = document.createElement("div");
      layout.className = "journal-book__page-layout";
      const toc = document.createElement("button");
      toc.type = "button";
      toc.className = "journal-book__page-action journal-book__page-action--contents";
      toc.innerHTML = contentsIcon;
      toc.title = "Zurück zum Inhaltsverzeichnis";
      toc.setAttribute("aria-label", toc.title);
      toc.setAttribute("data-book-page-target", "1");
      const date = document.createElement("p");
      date.className = "journal-book__entry-date";
      date.textContent = entry.entry_date || "Neuer Eintrag";
      const content = document.createElement("div");
      content.className = "journal-book__markdown";
      content.innerHTML = renderJournalMarkdown(entry.text);
      layout.append(toc, date, content);
      if (!readOnlyMode) {
        const edit = document.createElement("button");
        edit.type = "button";
        edit.className = "journal-book__page-action journal-book__page-action--edit";
        edit.innerHTML = editIcon;
        edit.title = entry.text ? "Eintrag bearbeiten" : "Eintrag schreiben";
        edit.setAttribute("aria-label", edit.title);
        edit.addEventListener("click", async (event) => {
          event.stopPropagation();
          await showEntryAt(index);
          if (currentIndex !== index) return;
          if (currentEntry()?.is_fixed) await beginEditing();
          if (currentEntry()?.is_fixed) return;
          editingIndex = index;
          attachEditor();
          inputEl.focus();
        });
        layout.append(edit);
      }
      const number = document.createElement("span");
      number.className = "book_page__number";
      number.textContent = String(index + 2);
      page.append(layout, number);
      return page;
    });
    if (!pages.length) {
      const emptyPage = document.createElement("article");
      emptyPage.className = "book_page";
      emptyPage.textContent = "Noch keine Einträge.";
      pages.push(emptyPage);
    }
    renderedPages = pages;
    bookViewer.updatePages([coverEl, indexEl, ...pages, backEl]);
    if (editingIndex !== null) attachEditor();
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
    if (readOnlyMode || !importUrl || payloadHasRealEntries(payload)) {
      return payload;
    }
    const legacyEntries = readLegacyEntries();
    if (!legacyEntries.length) {
      return payload;
    }

    setHint("Alte Tagebucheintr\u00e4ge werden \u00fcbernommen...", "editing");
    try {
      const importedPayload = await request(importUrl, {
        method: "POST",
        body: JSON.stringify({ entries: legacyEntries }),
      });
      clearLegacyEntries();
      return importedPayload;
    } catch (_error) {
      setHint("Die alten Tagebucheintr\u00e4ge konnten nicht automatisch \u00fcbernommen werden.", "error");
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
      setHint("Das Tagebuch konnte nicht geladen werden.", "error");
      setLoading(false);
    }
  };

  const saveDraft = async (payloadToSave) => {
    if (readOnlyMode || !payloadToSave) {
      return;
    }
    const payload = await request(entryUrl(payloadToSave.entryId, "save"), {
      method: "POST",
      body: JSON.stringify({
        text: payloadToSave.text,
        entry_date: payloadToSave.entryDate,
      }),
    });
    // Do not replace text typed while this request was in flight.
    if (!pendingSavePayload) applyPayload(payload, payloadToSave.entryId, editingIndex === null);
  };

  const flushPendingSave = async () => {
    if (activeSave) await activeSave;
    if (!pendingSavePayload) {
      return;
    }
    window.clearTimeout(saveTimer);
    const payloadToSave = pendingSavePayload;
    pendingSavePayload = null;
    activeSave = saveDraft(payloadToSave);
    try {
      await activeSave;
    } catch (error) {
      pendingSavePayload ||= payloadToSave;
      throw error;
    } finally {
      activeSave = null;
    }
    if (pendingSavePayload) await flushPendingSave();
  };

  const queueSave = () => {
    if (readOnlyMode || isProgrammaticUpdate || isLoading) {
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
    if (targetIndex < 0 || targetIndex >= entries.length || targetIndex === currentIndex || isLoading || isTurning) {
      return;
    }
    isTurning = true;
    try {
      await flushPendingSave();
      lastRequestedIndex = targetIndex;
      currentIndex = targetIndex;
      resetPage();
      renderEntry();
    } catch (_error) {
      setHint("Der aktuelle Entwurf konnte nicht gesichert werden.", "error");
    } finally {
      isTurning = false;
    }
  };

  const beginEditing = async () => {
    const entry = currentEntry();
    if (!entry || !entry.is_fixed) {
      return;
    }
    setLoading(true);
    try {
      const payload = await request(entryUrl(entry.id, "edit"), { method: "POST", body: "{}" });
      previewMode = false;
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
      setHint("Leere Eintr\u00e4ge k\u00f6nnen nicht fixiert werden.", "error");
      return;
    }
    setLoading(true);
    try {
      await flushPendingSave();
      const payload = await request(entryUrl(entry.id, "fix"), {
        method: "POST",
        body: JSON.stringify({
          text: inputEl.value,
          entry_date: dateInputEl.value || "",
        }),
      });
      editingIndex = null;
      entryEl.hidden = true;
      editorHost.append(entryEl);
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
      await flushPendingSave();
      const payload = await request(entryUrl(entry.id, "delete"), { method: "POST", body: "{}" });
      editingIndex = null;
      entryEl.hidden = true;
      editorHost.append(entryEl);
      applyPayload(payload);
    } catch (_error) {
      setHint("Der Eintrag konnte nicht gel\u00f6scht werden.", "error");
      setLoading(false);
    }
  };

  modeBtn.addEventListener("click", () => {
    if (readOnlyMode) {
      return;
    }
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
    if (readOnlyMode) {
      return;
    }
    deleteEntry();
  });

  inputEl.addEventListener("input", () => {
    if (readOnlyMode) {
      return;
    }
    queueSave();
  });

  dateInputEl.addEventListener("change", () => {
    if (readOnlyMode) {
      return;
    }
    queueSave();
  });

  previewBtn.addEventListener("click", () => {
    previewMode = !previewMode;
    renderPreview();
    if (!previewMode) inputEl.focus();
  });
  markdownHelpBtn.addEventListener("click", () => {
    const willOpen = markdownHelpEl.hidden;
    markdownHelpEl.hidden = !willOpen;
    markdownHelpBtn.setAttribute("aria-expanded", String(willOpen));
    markdownHelpBtn.title = willOpen ? "Markdown-Hilfe schließen" : "Markdown-Hilfe";
    markdownHelpBtn.setAttribute(
      "aria-label",
      willOpen ? "Markdown-Hilfe schließen" : "Markdown-Hilfe anzeigen",
    );
  });
  markdownHelpClose.addEventListener("click", () => {
    closeMarkdownHelp();
    markdownHelpBtn.focus();
  });
  const finishEditing = async () => {
    if (isTurning) return false;
    try {
      await flushPendingSave();
      closeMarkdownHelp();
      editingIndex = null;
      entryEl.hidden = true;
      editorHost.append(entryEl);
      renderBookPages();
      return true;
    } catch (_error) {
      setHint("Der Entwurf konnte nicht gespeichert werden. Bitte erneut versuchen.", "error");
      return false;
    }
  };
  editorDone.addEventListener("click", finishEditing);
  ["mousedown", "touchstart", "touchmove"].forEach((eventName) => {
    entryEl.addEventListener(eventName, (event) => event.stopPropagation());
  });
  const bookViewer = initBookViewer(diaryWindow, {
    startClosed: true,
    beforeOpen: () => initialLoad,
    beforeClose: finishEditing,
  });
  const initialLoad = loadEntries();
});
