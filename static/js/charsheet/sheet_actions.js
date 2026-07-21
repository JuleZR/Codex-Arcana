import { applySheetPartials } from "./partial_updates.js";

function flashSheetFeedback(level) {
  const normalized = level === "error" ? "error" : "success";
  document.body.classList.remove("sheet-feedback--success", "sheet-feedback--error");
  void document.body.offsetWidth;
  document.body.classList.add(`sheet-feedback--${normalized}`);
  window.setTimeout(() => {
    document.body.classList.remove(`sheet-feedback--${normalized}`);
  }, 1700);
}

function updateLearningFormFromPayload(payload) {
  const html = String(payload?.learningPanelHtml || "").trim();
  if (!html) {
    return false;
  }
  const currentForm = document.getElementById("learnForm");
  if (!(currentForm instanceof HTMLFormElement)) {
    return false;
  }
  const template = document.createElement("template");
  template.innerHTML = html;
  const nextForm = template.content.querySelector("#learnForm");
  if (!(nextForm instanceof HTMLFormElement)) {
    return false;
  }
  currentForm.replaceWith(nextForm);
  document.dispatchEvent(new CustomEvent("charsheet:partials-applied", {
    detail: { targets: ["learnForm"] },
  }));
  return true;
}

export function initSheetActions() {
  if (document.body.dataset.sheetActionsBound === "1") {
    return;
  }
  document.body.dataset.sheetActionsBound = "1";

  const searchParams = new URLSearchParams(window.location.search);
  if (
    window.top === window.self &&
    searchParams.get("print") === "1" &&
    document.body.dataset.printTriggered !== "1"
  ) {
    document.body.dataset.printTriggered = "1";
    window.setTimeout(() => {
      window.print();
    }, 250);
  }

  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.hasAttribute("data-sheet-action")) {
      return;
    }

    event.preventDefault();

    // A slow response must not turn a double click into two mutations. This is
    // especially important for destructive actions whose second request would
    // otherwise fall through to the browser and display a 404 page.
    if (form.dataset.sheetActionPending === "1") {
      return;
    }
    form.dataset.sheetActionPending = "1";

    let submitter = null;
    let submitterWasDisabled = false;
    let nativeFallbackStarted = false;

    try {
      submitter = event.submitter instanceof HTMLElement ? event.submitter : null;
      const formData = new FormData(form);
      if (
        submitter instanceof HTMLButtonElement ||
        submitter instanceof HTMLInputElement
      ) {
        const submitterName = submitter.getAttribute("name");
        if (submitterName) {
          formData.append(submitterName, submitter.value);
        }
        submitterWasDisabled = submitter.disabled;
        submitter.disabled = true;
      }
      const response = await fetch(form.action, {
        method: form.method || "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        credentials: "same-origin",
      });
      if (!response.ok) {
        throw new Error("sheet action failed");
      }
      const payload = await response.json();
      if (!payload?.ok) {
        if (form.hasAttribute("data-ajax-only")) {
          form.dispatchEvent(new CustomEvent("sheet:action-failed", { bubbles: true, detail: payload }));
          return;
        }
        throw new Error("sheet action invalid");
      }
      applySheetPartials(payload);
      updateLearningFormFromPayload(payload);
      if (payload?.learningFeedback?.level) {
        flashSheetFeedback(String(payload.learningFeedback.level));
      }
      if (form.hasAttribute("data-ajax-only")) {
        form.dispatchEvent(new CustomEvent("sheet:action-success", { bubbles: true, detail: payload }));
      }
      if (form.hasAttribute("data-reset-after-success")) {
        form.reset();
      }
    } catch (_error) {
      if (form.hasAttribute("data-ajax-only")) {
        form.dispatchEvent(new CustomEvent("sheet:action-failed", { bubbles: true, detail: null }));
        return;
      }
      nativeFallbackStarted = true;
      form.submit();
    } finally {
      if (!nativeFallbackStarted) {
        delete form.dataset.sheetActionPending;
        if (
          (submitter instanceof HTMLButtonElement || submitter instanceof HTMLInputElement) &&
          submitter.isConnected
        ) {
          submitter.disabled = submitterWasDisabled;
        }
      }
    }
  });
}


