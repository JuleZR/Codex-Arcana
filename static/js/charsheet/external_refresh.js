import { applySheetPartials } from "./partial_updates.js";

const VISIBLE_INTERVAL_MS = 2500;
const HIDDEN_INTERVAL_MS = 12000;

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
  let timerId = 0;
  let inFlight = false;

  const schedule = () => {
    window.clearTimeout(timerId);
    timerId = window.setTimeout(
      poll,
      document.hidden ? HIDDEN_INTERVAL_MS : VISIBLE_INTERVAL_MS,
    );
  };

  const poll = async () => {
    if (inFlight) {
      schedule();
      return;
    }
    inFlight = true;
    try {
      const refreshUrl = new URL(url, window.location.origin);
      if (signature) {
        refreshUrl.searchParams.set("signature", signature);
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
      if (payload.changed) {
        applySheetPartials(payload);
      }
    } catch (_error) {
      // The next scheduled poll will recover after transient network issues.
    } finally {
      inFlight = false;
      schedule();
    }
  };

  document.addEventListener("visibilitychange", schedule);
  schedule();
}
