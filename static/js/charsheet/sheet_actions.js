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
  const currentChoiceWindow = document.getElementById("learnChoiceWindow");
  const nextChoiceWindow = template.content.querySelector("#learnChoiceWindow");
  if (
    currentChoiceWindow instanceof HTMLElement
    && nextChoiceWindow instanceof HTMLElement
  ) {
    if (typeof currentChoiceWindow.__floatingWindowController?.destroy === "function") {
      currentChoiceWindow.__floatingWindowController.destroy();
    }
    currentChoiceWindow.replaceWith(nextChoiceWindow);
  }
  document.dispatchEvent(new CustomEvent("charsheet:partials-applied", {
    detail: { targets: ["learnForm", "learnChoiceWindow"] },
  }));
  return true;
}

function updateLearningBudgetFromPayload(payload) {
  if (Object.prototype.hasOwnProperty.call(payload || {}, "currentExperience")) {
    const currentExperience = Number.parseInt(String(payload.currentExperience), 10);
    if (Number.isFinite(currentExperience)) {
      const budgetPanel = document.getElementById("learnBudgetPanel");
      const budgetValue = document.getElementById("learnBudgetValue");
      const remainingValue = document.getElementById("learnRemainingValue");
      if (budgetPanel instanceof HTMLElement) {
        budgetPanel.dataset.learnBudget = String(currentExperience);
      }
      if (budgetValue) {
        budgetValue.textContent = `${currentExperience} EP`;
      }
      if (remainingValue) {
        remainingValue.textContent = `${currentExperience} EP`;
        remainingValue.classList.remove("is-negative");
      }
    }
  }

  const html = String(payload?.learningBudgetHtml || "").trim();
  if (!html) {
    return false;
  }
  const currentBudget = document.getElementById("learnBudgetPanel");
  if (!(currentBudget instanceof HTMLElement)) {
    return false;
  }
  const template = document.createElement("template");
  template.innerHTML = html;
  const nextBudget = template.content.querySelector("#learnBudgetPanel");
  if (!(nextBudget instanceof HTMLElement)) {
    return false;
  }
  currentBudget.replaceWith(nextBudget);
  document.dispatchEvent(new Event("learn:refresh-totals"));
  return true;
}

function updateCultistCorruptionFromPayload(payload) {
  if (!Object.prototype.hasOwnProperty.call(payload || {}, "cultistCorruptionLevel")) {
    return;
  }
  const parsedLevel = Number.parseInt(String(payload.cultistCorruptionLevel), 10);
  const level = Number.isFinite(parsedLevel) ? Math.min(10, Math.max(0, parsedLevel)) : 0;
  Array.from(document.body.classList).forEach((className) => {
    if (/^cultist-corruption--level-\d+$/.test(className)) {
      document.body.classList.remove(className);
    }
  });
  document.body.classList.toggle("has-cultist-corruption", level > 0);
  if (level > 0) {
    document.body.classList.add(`cultist-corruption--level-${level}`);
  }
  document.body.dataset.cultistCorruptionLevel = String(level);
}

function refreshDeferredSheetPartials(payload) {
  const url = String(payload?.deferredPartialsUrl || "").trim();
  if (!url) {
    return;
  }
  document.dispatchEvent(new CustomEvent("charsheet:external-refresh-requested", {
    detail: { force: true, learning: true },
  }));
}

function waitForPrintAssets() {
  const waits = [];
  if (document.readyState !== "complete") {
    waits.push(new Promise((resolve) => {
      window.addEventListener("load", resolve, { once: true });
    }));
  }
  if (document.fonts && typeof document.fonts.ready?.then === "function") {
    waits.push(document.fonts.ready.catch(() => {}));
  }
  document.querySelectorAll("img").forEach((image) => {
    if (image.complete) {
      return;
    }
    waits.push(new Promise((resolve) => {
      image.addEventListener("load", resolve, { once: true });
      image.addEventListener("error", resolve, { once: true });
    }));
  });
  return Promise.race([
    Promise.all(waits),
    new Promise((resolve) => {
      window.setTimeout(resolve, 2500);
    }),
  ]);
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
    window.setTimeout(async () => {
      await waitForPrintAssets();
      window.print();
    }, 500);
  }

  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.hasAttribute("data-sheet-action")) {
      return;
    }

    if (event.defaultPrevented) {
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
      if (Array.isArray(payload.partials) && payload.partials.length) {
        applySheetPartials(payload);
      }
      updateLearningBudgetFromPayload(payload);
      updateCultistCorruptionFromPayload(payload);
      updateLearningFormFromPayload(payload);
      if (payload?.learningFeedback?.level) {
        form.dispatchEvent(new CustomEvent("learn:applied", {
          detail: payload.learningFeedback,
        }));
        flashSheetFeedback(String(payload.learningFeedback.level));
      }
      if (Object.prototype.hasOwnProperty.call(payload, "openItemTransferCount")) {
        document.dispatchEvent(new CustomEvent("charsheet:item-transfer-count-updated", {
          detail: { count: payload.openItemTransferCount },
        }));
      }
      refreshDeferredSheetPartials(payload);
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


