import { applySheetPartials } from "./partial_updates.js";
import { getCsrfToken } from "./utils.js";

function updateJsonScript(scriptId, value) {
  const script = document.getElementById(scriptId);
  if (script) {
    script.textContent = JSON.stringify(value ?? null);
  }
}

function enforceReadOnlyControls() {
  if (document.body?.dataset.readOnly !== "1") {
    return;
  }
  document.querySelectorAll("form button, form input, form textarea, form select").forEach((control) => {
    if (
      !control.closest("[data-card-hand]")
      && !control.matches("[data-school-group-toggle]")
      && !control.matches("[data-temporary-attribute-control]")
    ) {
      control.disabled = true;
    }
  });
  document.querySelectorAll("button, input[type='button'], input[type='submit']").forEach((control) => {
    if (
      !control.closest("[data-card-hand]")
      && control.getAttribute("role") !== "tab"
      && !control.matches("[data-school-group-toggle]")
      && !control.matches("[data-temporary-attribute-control]")
    ) {
      control.disabled = true;
      control.setAttribute("aria-disabled", "true");
    }
  });
  document.querySelectorAll("[data-temporary-attribute-control]").forEach((control) => {
    control.disabled = false;
    control.removeAttribute("aria-disabled");
  });
  document.querySelectorAll("[data-drag-handle]").forEach((handle) => {
    handle.draggable = false;
    handle.removeAttribute("tabindex");
    handle.setAttribute("aria-disabled", "true");
  });
}

function formatModifier(value) {
  return value > 0 ? `+${value}` : String(value);
}

function applyOptimisticAttributeAdjustment(row, nextAdjustment) {
  const previousAdjustment = Number.parseInt(row.dataset.temporaryAdjustment || "0", 10) || 0;
  const valueCell = row.querySelector("[data-attribute-value]");
  const modifierCell = row.querySelector(".mod-badge");
  if (valueCell instanceof HTMLElement) {
    const previousValue = Number.parseInt(valueCell.textContent || "0", 10) || 0;
    const nextValue = previousValue + nextAdjustment - previousAdjustment;
    valueCell.textContent = String(nextValue);
    if (modifierCell instanceof HTMLElement) {
      modifierCell.textContent = formatModifier(nextValue - 5);
    }
  }
  row.dataset.temporaryAdjustment = String(nextAdjustment);
  row.classList.toggle("is-temporary-positive", nextAdjustment > 0);
  row.classList.toggle("is-temporary-negative", nextAdjustment < 0);
}

async function submitTemporaryAttributeOperation(
  url,
  shortName,
  operation,
  amount,
  row,
  fallbackAdjustment,
  requestedAdjustment,
  requestKey,
  latestDesiredAdjustments,
) {
  row?.classList.add("is-temporary-pending");
  try {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ attribute: shortName, operation, amount }),
    });
    const payload = await response.json();
    if (!response.ok || !payload?.ok) {
      throw new Error("temporary attribute update failed");
    }
    if (latestDesiredAdjustments.get(requestKey) !== requestedAdjustment) {
      return;
    }
    updateJsonScript("wound-thresholds-data", payload.woundThresholdRows || []);
    updateJsonScript("battle-calculator-data", payload.battleCalculatorPayload || {});
    applySheetPartials(payload);
    document.dispatchEvent(new Event("charsheet:battle-calculator-data-updated"));
    enforceReadOnlyControls();
    if (latestDesiredAdjustments.get(requestKey) === requestedAdjustment) {
      latestDesiredAdjustments.delete(requestKey);
    }
  } catch (error) {
    if (
      row?.isConnected
      && latestDesiredAdjustments.get(requestKey) === requestedAdjustment
    ) {
      applyOptimisticAttributeAdjustment(row, fallbackAdjustment);
      latestDesiredAdjustments.delete(requestKey);
    }
    throw error;
  } finally {
    if (
      row?.isConnected
      && !latestDesiredAdjustments.has(requestKey)
    ) {
      row.classList.remove("is-temporary-pending");
    }
  }
}

export function initTemporaryAttributes() {
  if (document.body.dataset.temporaryAttributesBound === "1") {
    enforceReadOnlyControls();
    return;
  }
  document.body.dataset.temporaryAttributesBound = "1";
  let requestQueue = Promise.resolve();
  const pendingOperations = new Map();
  const latestDesiredAdjustments = new Map();

  function flushPendingOperation(key) {
    const pending = pendingOperations.get(key);
    if (!pending) {
      return;
    }
    pendingOperations.delete(key);
    const delta = pending.targetAdjustment - pending.baseAdjustment;
    if (delta === 0) {
      latestDesiredAdjustments.delete(key);
      pending.row?.classList.remove("is-temporary-pending");
      return;
    }
    const operation = pending.targetAdjustment === 0
      ? "reset"
      : delta > 0 ? "increment" : "decrement";
    const amount = operation === "reset" ? 1 : Math.abs(delta);
    requestQueue = requestQueue
      .catch(() => undefined)
      .then(() => submitTemporaryAttributeOperation(
        pending.url,
        pending.shortName,
        operation,
        amount,
        pending.row,
        pending.baseAdjustment,
        pending.targetAdjustment,
        key,
        latestDesiredAdjustments,
      ));
  }

  document.addEventListener("click", (event) => {
    const control = event.target instanceof Element
      ? event.target.closest("[data-temporary-attribute-control]")
      : null;
    if (!(control instanceof HTMLButtonElement)) {
      return;
    }
    const row = control.closest("[data-attribute-short-name]");
    const panel = control.closest("[data-temporary-attribute-panel]");
    if (!(row instanceof HTMLElement) || !(panel instanceof HTMLElement)) {
      return;
    }
    const url = String(panel.dataset.updateUrl || "").trim();
    const shortName = String(row.dataset.attributeShortName || "").trim();
    const operation = String(control.dataset.operation || "").trim();
    if (!url || !shortName || !operation) {
      return;
    }
    const currentAdjustment = Number.parseInt(row.dataset.temporaryAdjustment || "0", 10) || 0;
    if (operation === "reset" && currentAdjustment === 0) {
      return;
    }
    event.preventDefault();
    const key = `${url}:${shortName}`;
    const pending = pendingOperations.get(key) || {
      url,
      shortName,
      row,
      baseAdjustment: currentAdjustment,
      targetAdjustment: currentAdjustment,
      timer: 0,
    };
    window.clearTimeout(pending.timer);
    if (operation === "increment") {
      pending.targetAdjustment += 1;
    } else if (operation === "decrement") {
      pending.targetAdjustment -= 1;
    } else {
      pending.targetAdjustment = 0;
    }
    pending.row = row;
    pendingOperations.set(key, pending);
    latestDesiredAdjustments.set(key, pending.targetAdjustment);
    applyOptimisticAttributeAdjustment(row, pending.targetAdjustment);
    row.classList.add("is-temporary-pending");
    pending.timer = window.setTimeout(() => flushPendingOperation(key), 90);
  });

  document.addEventListener("charsheet:partials-applied", enforceReadOnlyControls);
  enforceReadOnlyControls();
}
