import { applySheetPartials } from "./partial_updates.js";

const VISIBLE_INTERVAL_MS = 2500;
const HIDDEN_INTERVAL_MS = 12000;

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
  syncPendingChoiceNoticesFromDom();
  document.dispatchEvent(new CustomEvent("charsheet:partials-applied", {
    detail: { targets: ["learnForm", "learnChoiceWindow"] },
  }));
  return true;
}

function syncPendingChoiceNoticesFromDom() {
  const hasPendingChoices = Array.from(
    document.querySelectorAll("#learnChoicePanelList [data-choice-decision-id]"),
  ).some((section) => {
    if (!(section instanceof HTMLElement)) {
      return false;
    }
    return (section.dataset.choiceInputType || "options") !== "unsupported";
  });
  document.querySelectorAll("[data-pending-choice-notice]").forEach((notice) => {
    if (!(notice instanceof HTMLElement)) {
      return;
    }
    notice.hidden = !hasPendingChoices;
    notice.style.display = hasPendingChoices ? "" : "none";
  });
}

export function initExternalSheetRefresh() {
  const body = document.body;
  if (!body || body.dataset.readOnly === "1") {
    return;
  }
  const url = String(body.dataset.externalRefreshUrl || "").trim();
  if (!url) {
    return;
  }

  let signature = String(body.dataset.externalRefreshSignature || "").trim();
  let openItemTransferCount = Math.max(
    0,
    Number.parseInt(String(body.dataset.openItemTransferCount || "0"), 10) || 0,
  );
  let notificationAudio = null;
  let timerId = 0;
  let inFlight = false;
  let queuedRefresh = null;

  const getNotificationAudio = () => {
    const soundUrl = String(body.dataset.itemTransferNotificationSound || "").trim();
    if (!soundUrl) {
      return null;
    }
    if (!notificationAudio) {
      notificationAudio = new Audio(soundUrl);
      notificationAudio.preload = "auto";
      notificationAudio.volume = 0.75;
    }
    return notificationAudio;
  };

  const primeNotificationAudio = () => {
    try {
      const audio = getNotificationAudio();
      if (!audio) {
        return;
      }
      audio.muted = true;
      const playPromise = audio.play();
      if (playPromise && typeof playPromise.catch === "function") {
        playPromise
          .then(() => {
            audio.pause();
            audio.currentTime = 0;
            audio.muted = false;
          })
          .catch(() => {
            audio.muted = false;
          });
      } else {
        audio.muted = false;
      }
    } catch (_error) {
      // Browsers may block audio until the first user gesture.
    }
  };

  const playItemTransferNotification = () => {
    try {
      const audio = getNotificationAudio();
      if (!audio) {
        return;
      }
      audio.muted = false;
      audio.currentTime = 0;
      const playPromise = audio.play();
      if (playPromise && typeof playPromise.catch === "function") {
        playPromise.catch(() => {});
      }
    } catch (_error) {
      // Browsers may still block audio depending on user settings.
    }
  };

  const syncItemTransferCount = (payload) => {
    if (!Object.prototype.hasOwnProperty.call(payload || {}, "openItemTransferCount")) {
      return;
    }
    const nextCount = Math.max(
      0,
      Number.parseInt(String(payload.openItemTransferCount || "0"), 10) || 0,
    );
    if (nextCount > openItemTransferCount) {
      playItemTransferNotification();
    }
    openItemTransferCount = nextCount;
    body.dataset.openItemTransferCount = String(nextCount);
  };

  const setItemTransferBaseline = (count) => {
    openItemTransferCount = Math.max(
      0,
      Number.parseInt(String(count || "0"), 10) || 0,
    );
    body.dataset.openItemTransferCount = String(openItemTransferCount);
  };

  const schedule = () => {
    window.clearTimeout(timerId);
    timerId = window.setTimeout(
      poll,
      document.hidden ? HIDDEN_INTERVAL_MS : VISIBLE_INTERVAL_MS,
    );
  };

  const poll = async ({ force = false, learning = false } = {}) => {
    if (inFlight) {
      if (force || learning) {
        queuedRefresh = {
          force: Boolean(force || queuedRefresh?.force),
          learning: Boolean(learning || queuedRefresh?.learning),
        };
      }
      schedule();
      return;
    }
    inFlight = true;
    try {
      const refreshUrl = new URL(url, window.location.origin);
      if (signature && !force) {
        refreshUrl.searchParams.set("signature", signature);
      }
      if (force) {
        refreshUrl.searchParams.set("force", "1");
      }
      if (learning) {
        refreshUrl.searchParams.set("learning", "1");
      }
      const response = await fetch(refreshUrl.toString(), {
        method: "GET",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        credentials: "same-origin",
      });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      if (!payload?.ok) {
        return;
      }
      signature = String(payload.signature || signature);
      body.dataset.externalRefreshSignature = signature;
      syncItemTransferCount(payload);
      if (payload.changed) {
        applySheetPartials(payload);
        updateLearningFormFromPayload(payload);
      }
    } catch (_error) {
      // The next scheduled poll will recover after transient network issues.
    } finally {
      inFlight = false;
      if (queuedRefresh) {
        const nextRefresh = queuedRefresh;
        queuedRefresh = null;
        window.setTimeout(() => poll(nextRefresh), 0);
      } else {
        schedule();
      }
    }
  };

  document.addEventListener("visibilitychange", schedule);
  document.addEventListener("charsheet:external-refresh-requested", (event) => {
    const detail = event instanceof CustomEvent ? event.detail : {};
    poll({
      force: Boolean(detail?.force),
      learning: Boolean(detail?.learning),
    });
  });
  document.addEventListener("charsheet:item-transfer-count-updated", (event) => {
    setItemTransferBaseline(event.detail?.count);
  });
  document.addEventListener("pointerdown", primeNotificationAudio, { once: true });
  document.addEventListener("keydown", primeNotificationAudio, { once: true });
  schedule();
}
