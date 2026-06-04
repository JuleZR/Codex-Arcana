import { applySheetPartials } from "./partial_updates.js";

export function initDamagePanel() {
  const form = document.querySelector(".damage_actions");
  const arcaneForm = document.querySelector(".arcane_actions");
  const gauge = document.querySelector(".damage_gauge");
  const arcaneMeter = document.querySelector(".arcane_meter");
  const needleArm = document.querySelector(".damage_gauge_needle_arm");
  const actionInput = document.querySelector(".damage_action_input");
  const amountInput = document.querySelector(".damage_amount_input");
  const arcaneActionInput = document.querySelector(".arcane_action_input");
  const arcaneAmountInput = document.querySelector(".arcane_amount_input");
  const currentDamageEl = document.querySelector(".damage_readout_current");
  const currentArcaneEl = document.querySelector(".arcane_meter_current");
  const arcaneFillEl = document.querySelector(".arcane_meter_fill");
  const woundPenaltyEl = document.querySelector(".damage_penalty_value");
  const woundStageEl = document.querySelector(".damage_stage_value");
  if (!form || !gauge || !needleArm || !actionInput || !amountInput || !currentDamageEl || !woundPenaltyEl || !woundStageEl) {
    return;
  }
  if (form.dataset.damageBound === "1") {
    return;
  }
  form.dataset.damageBound = "1";
  form.dataset.damageManaged = "1";

  const requestUrl = form.getAttribute("action") || window.location.href;
  const arcaneRequestUrl = arcaneForm?.getAttribute("action") || window.location.href;
  const storageKey = "charsheet.damageGauge.value";
  const thresholdsScript = document.getElementById("wound-thresholds-data");
  let thresholdRows = [];
  let requestVersion = 0;
  let lastAppliedResponseVersion = 0;
  let requestQueue = Promise.resolve();
  let arcaneRequestVersion = 0;
  let lastAppliedArcaneResponseVersion = 0;
  let arcaneRequestQueue = Promise.resolve();
  let localDamage = readInt(gauge.dataset.damageValue || currentDamageEl.textContent, 0);
  let localArcane = readInt(arcaneMeter?.dataset.arcaneCurrent || currentArcaneEl?.textContent, 0);
  let pendingDamageDelta = 0;
  let damageFlushTimer = null;
  let damageDependentRefreshTimer = null;
  let damageDependentRefreshInFlight = false;
  let damageRequestInFlight = false;
  let confirmedDamage = localDamage;
  let pendingArcaneDelta = 0;
  let arcaneFlushTimer = null;
  let arcaneRequestInFlight = false;
  let confirmedArcane = localArcane;
  let woundPenaltyIgnored = woundStageEl.classList.contains("is-disabled") || woundPenaltyEl.classList.contains("is-disabled");

  window.__charsheetDamagePanel = {
    flushPendingDamageRequests: () => {
      window.clearTimeout(damageFlushTimer);
      flushDamageDelta();
      window.clearTimeout(damageDependentRefreshTimer);
      const dependentRefresh = refreshDamageDependents();
      window.clearTimeout(arcaneFlushTimer);
      flushArcaneDelta();
      return Promise.all([
        requestQueue.catch(() => undefined),
        dependentRefresh.catch(() => undefined),
        arcaneRequestQueue.catch(() => undefined),
      ]);
    },
  };

  if (thresholdsScript) {
    try {
      thresholdRows = JSON.parse(thresholdsScript.textContent || "[]");
    } catch (_error) {
      thresholdRows = [];
    }
  }

  function readInt(rawValue, fallback = 0) {
    const parsed = Number.parseInt(String(rawValue ?? "").trim(), 10);
    return Number.isNaN(parsed) ? fallback : parsed;
  }

  function formatModifier(value) {
    if (value > 0) {
      return `+${value}`;
    }
    return String(value);
  }

  function composeStageLabel(stage, penaltyDisplay, isIgnored = false) {
    const safeStage = String(stage || "-").trim();
    if (!safeStage || safeStage === "-") {
      return "";
    }
    return safeStage;
  }

  function computeWoundInfo(damage) {
    if (!thresholdRows.length) {
      return { stage: "-", penaltyDisplay: "-", isIgnored: woundPenaltyIgnored };
    }
    const sorted = [...thresholdRows].sort((a, b) => a.threshold - b.threshold);
    const first = Number(sorted[0].threshold || 0);
    const last = Number(sorted[sorted.length - 1].threshold || 0);

    if (damage < first) {
      return { stage: "-", penaltyDisplay: "-", isIgnored: woundPenaltyIgnored };
    }
    if (damage > last) {
      return { stage: "Tod", penaltyDisplay: "0", isIgnored: woundPenaltyIgnored };
    }

    let current = sorted[0];
    for (const row of sorted) {
      if (damage >= Number(row.threshold || 0)) {
        current = row;
      } else {
        break;
      }
    }

    return {
      stage: String(current.stage || "-"),
      penaltyDisplay: formatModifier(readInt(current.penalty, 0)),
      isIgnored: woundPenaltyIgnored,
    };
  }

  function applyWoundState(stage, penaltyDisplay, isIgnored = false) {
    const normalizedStage = String(stage || "-").trim() || "-";
    woundPenaltyIgnored = Boolean(isIgnored);
    woundStageEl.textContent = composeStageLabel(stage, penaltyDisplay, isIgnored);
    woundStageEl.dataset.stage = normalizedStage;
    woundPenaltyEl.textContent = penaltyDisplay;
    woundStageEl.classList.toggle("is-disabled", woundPenaltyIgnored);
    woundPenaltyEl.classList.toggle("is-disabled", woundPenaltyIgnored);
  }

  function computeRotation(value, maxValue) {
    const safeMax = Math.max(1, maxValue);
    const clamped = Math.max(0, Math.min(value, safeMax));
    const sortedThresholds = thresholdRows
      .map((row) => Number(row.threshold || 0))
      .filter((entry) => Number.isFinite(entry))
      .sort((a, b) => a - b);

    let adjusted = clamped;
    if (sortedThresholds.includes(clamped) && clamped < safeMax) {
      adjusted = clamped + 1;
    } else if (clamped > 0 && clamped < safeMax) {
      adjusted = clamped + 0.5;
    }

    adjusted = Math.max(0, Math.min(adjusted, safeMax));
    return 6 + (adjusted / safeMax) * 168;
  }

  function renderNeedle(value, options = {}) {
    const { animate = false, fromValue = null } = options;
    const maxValue = Math.max(1, readInt(gauge.dataset.damageMax || "1", 1));
    const clampedValue = Math.max(0, Math.min(value, maxValue));
    const nextRotation = computeRotation(clampedValue, maxValue);

    if (animate) {
      const sourceValue = fromValue === null
        ? readInt(gauge.dataset.damageValue || clampedValue, clampedValue)
        : fromValue;
      const startRotation = computeRotation(sourceValue, maxValue);
      gauge.classList.add("is-animating");
      gauge.style.setProperty("--needle-angle", `${startRotation}deg`);
      window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => {
          gauge.style.setProperty("--needle-angle", `${nextRotation}deg`);
        });
      });
    } else {
      gauge.classList.remove("is-animating");
      gauge.style.setProperty("--needle-angle", `${nextRotation}deg`);
    }

    gauge.dataset.damageValue = String(clampedValue);
  }

  function renderArcaneMeter(value, maxValue, options = {}) {
    if (!arcaneMeter || !arcaneFillEl) {
      return;
    }
    const { animate = true } = options;
    const safeMax = Math.max(0, readInt(maxValue ?? arcaneMeter.dataset.arcaneMax, 0));
    const clampedValue = Math.max(0, Math.min(readInt(value, 0), safeMax));
    const ratio = safeMax <= 0 ? 0 : (clampedValue / safeMax) * 100;

    if (!animate) {
      arcaneFillEl.style.transition = "none";
    }
    arcaneFillEl.style.width = `${ratio}%`;
    const arcaneValueNode = arcaneMeter.querySelector(".arcane_meter_value");
    if (arcaneValueNode) {
      arcaneValueNode.innerHTML = `<span class="arcane_meter_current">${clampedValue}</span>`;
    }
    arcaneMeter.dataset.arcaneCurrent = String(clampedValue);
    arcaneMeter.dataset.arcaneMax = String(safeMax);
    if (!animate) {
      window.requestAnimationFrame(() => {
        arcaneFillEl.style.transition = "";
      });
    }
  }

  function syncDamageDisplay(value, options = {}) {
    const { animate = true, fromValue = null } = options;
    currentDamageEl.textContent = String(value);
    const optimisticWound = computeWoundInfo(value);
    applyWoundState(optimisticWound.stage, optimisticWound.penaltyDisplay, optimisticWound.isIgnored);
    renderNeedle(value, { animate, fromValue });
    window.sessionStorage.setItem(storageKey, String(value));
  }

  function scheduleDamageFlush() {
    window.clearTimeout(damageFlushTimer);
    damageFlushTimer = window.setTimeout(flushDamageDelta, 160);
  }

  function scheduleDamageDependentRefresh(delay = 650) {
    window.clearTimeout(damageDependentRefreshTimer);
    damageDependentRefreshTimer = window.setTimeout(refreshDamageDependents, delay);
  }

  async function refreshDamageDependents() {
    if (damageDependentRefreshInFlight) {
      scheduleDamageDependentRefresh();
      return;
    }
    if (damageRequestInFlight || pendingDamageDelta !== 0) {
      scheduleDamageDependentRefresh();
      return;
    }

    const refreshDamage = localDamage;
    damageDependentRefreshInFlight = true;
    actionInput.value = "set";
    amountInput.value = "1";

    const formData = new FormData(form);
    formData.set("ajax", "1");
    formData.set("partials", "1");
    formData.set("current_damage", String(refreshDamage));

    try {
      const response = await fetch(requestUrl, {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        credentials: "same-origin",
      });
      if (!response.ok) {
        throw new Error("damage dependent refresh failed");
      }
      const payload = await response.json();
      const serverDamage = readInt(payload.current_damage, refreshDamage);
      if (damageRequestInFlight || pendingDamageDelta !== 0 || serverDamage !== localDamage) {
        scheduleDamageDependentRefresh();
        return;
      }

      confirmedDamage = serverDamage;
      gauge.dataset.damageMax = String(readInt(payload.current_damage_max, readInt(gauge.dataset.damageMax || "1", 1)));
      applyWoundState(
        String(payload.current_wound_stage ?? "-"),
        String(payload.current_wound_penalty ?? "-"),
        Boolean(payload.is_wound_penalty_ignored),
      );
      if (Array.isArray(payload.partials) && payload.partials.length) {
        applySheetPartials(payload);
      }
    } catch (_error) {
      scheduleDamageDependentRefresh(1200);
    } finally {
      damageDependentRefreshInFlight = false;
    }
  }

  function flushDamageDelta() {
    if (damageRequestInFlight || pendingDamageDelta === 0) {
      return;
    }

    const targetDamage = localDamage;
    pendingDamageDelta = 0;
    damageRequestInFlight = true;

    const thisRequestVersion = requestVersion + 1;
    requestVersion = thisRequestVersion;
    actionInput.value = "set";
    amountInput.value = "1";

    const formData = new FormData(form);
    formData.set("ajax", "1");
    formData.set("partials", "0");
    formData.set("current_damage", String(targetDamage));

    requestQueue = requestQueue.then(async () => {
      const response = await fetch(requestUrl, {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        credentials: "same-origin",
      });
      if (!response.ok) {
        throw new Error("damage update failed");
      }

      const payload = await response.json();
      if (thisRequestVersion < lastAppliedResponseVersion) {
        return;
      }
      lastAppliedResponseVersion = thisRequestVersion;

      const previousServerDamage = localDamage;
      confirmedDamage = readInt(payload.current_damage, targetDamage);
      gauge.dataset.damageMax = String(readInt(payload.current_damage_max, readInt(gauge.dataset.damageMax || "1", 1)));

      if (pendingDamageDelta === 0) {
        localDamage = confirmedDamage;
        currentDamageEl.textContent = String(localDamage);
        applyWoundState(
          String(payload.current_wound_stage ?? "-"),
          String(payload.current_wound_penalty ?? "-"),
          Boolean(payload.is_wound_penalty_ignored),
        );
        if (Array.isArray(payload.partials) && payload.partials.length) {
          applySheetPartials(payload);
        }
        renderNeedle(localDamage, { animate: true, fromValue: previousServerDamage });
        window.sessionStorage.setItem(storageKey, String(localDamage));
      } else {
        localDamage = Math.max(0, localDamage);
        syncDamageDisplay(localDamage, { animate: false });
      }
    }).catch((_error) => {
      pendingDamageDelta = localDamage - confirmedDamage;
      syncDamageDisplay(localDamage, { animate: false });
    }).finally(() => {
      damageRequestInFlight = false;
      if (pendingDamageDelta !== 0) {
        scheduleDamageFlush();
      } else {
        scheduleDamageDependentRefresh();
      }
    });
  }

  function scheduleArcaneFlush() {
    window.clearTimeout(arcaneFlushTimer);
    arcaneFlushTimer = window.setTimeout(flushArcaneDelta, 160);
  }

  function flushArcaneDelta() {
    if (arcaneRequestInFlight || pendingArcaneDelta === 0 || !arcaneForm) {
      return;
    }

    const targetArcane = localArcane;
    pendingArcaneDelta = 0;
    arcaneRequestInFlight = true;

    const thisRequestVersion = arcaneRequestVersion + 1;
    arcaneRequestVersion = thisRequestVersion;
    arcaneActionInput.value = "set";
    arcaneAmountInput.value = "1";

    const formData = new FormData(arcaneForm);
    formData.set("ajax", "1");
    formData.set("current_arcane_power", String(targetArcane));

    arcaneRequestQueue = arcaneRequestQueue.then(async () => {
      const response = await fetch(arcaneRequestUrl, {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        credentials: "same-origin",
      });
      if (!response.ok) {
        throw new Error("arcane update failed");
      }

      const payload = await response.json();
      if (thisRequestVersion < lastAppliedArcaneResponseVersion) {
        return;
      }
      lastAppliedArcaneResponseVersion = thisRequestVersion;
      const maxArcane = readInt(payload.current_arcane_power_max, readInt(arcaneMeter?.dataset.arcaneMax || "0", 0));
      confirmedArcane = readInt(payload.current_arcane_power, targetArcane);
      localArcane = pendingArcaneDelta === 0
        ? confirmedArcane
        : Math.max(0, Math.min(maxArcane, localArcane));
      renderArcaneMeter(localArcane, maxArcane);
    }).catch((_error) => {
      const maxArcane = readInt(arcaneMeter?.dataset.arcaneMax || "0", 0);
      pendingArcaneDelta = localArcane - confirmedArcane;
      renderArcaneMeter(localArcane, maxArcane);
    }).finally(() => {
      arcaneRequestInFlight = false;
      if (pendingArcaneDelta !== 0) {
        scheduleArcaneFlush();
      }
    });
  }

  const initialValue = localDamage;
  const previousValue = window.sessionStorage.getItem(storageKey);
  if (previousValue !== null && readInt(previousValue, initialValue) !== initialValue) {
    renderNeedle(initialValue, { animate: true, fromValue: readInt(previousValue, initialValue) });
  } else {
    renderNeedle(initialValue);
  }
  window.sessionStorage.setItem(storageKey, String(initialValue));
  renderArcaneMeter(localArcane, readInt(arcaneMeter?.dataset.arcaneMax || "0", 0), { animate: false });

  document.querySelectorAll("#sheetDamagePanel .damage_step_btn[data-action]").forEach((button) => {
    if (button.classList.contains("arcane_step_btn")) {
      return;
    }
    button.addEventListener("click", () => {
      const action = button.getAttribute("data-action");
      const amount = readInt(button.getAttribute("data-amount") || "1", 1);
      if ((action !== "heal" && action !== "damage") || amount <= 0) {
        return;
      }

      const previousDamage = localDamage;
      const delta = action === "damage" ? amount : -amount;
      localDamage = Math.max(0, localDamage + delta);
      pendingDamageDelta += localDamage - previousDamage;
      syncDamageDisplay(localDamage, { animate: true, fromValue: previousDamage });
      scheduleDamageFlush();
      scheduleDamageDependentRefresh();
    });
  });

  if (!arcaneForm || !arcaneMeter || !arcaneActionInput || !arcaneAmountInput || !arcaneFillEl) {
    return;
  }
  if (arcaneForm.dataset.arcaneBound === "1") {
    return;
  }
  arcaneForm.dataset.arcaneBound = "1";

  document.querySelectorAll("#sheetDamagePanel .arcane_step_btn[data-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.getAttribute("data-action");
      const amount = readInt(button.getAttribute("data-amount") || "1", 1);
      if ((action !== "spend" && action !== "restore") || amount <= 0) {
        return;
      }

      const maxArcane = readInt(arcaneMeter.dataset.arcaneMax || "0", 0);
      const previousArcane = localArcane;
      const delta = action === "restore" ? amount : -amount;
      localArcane = Math.max(0, Math.min(maxArcane, localArcane + delta));
      pendingArcaneDelta += localArcane - previousArcane;
      renderArcaneMeter(localArcane, maxArcane);
      scheduleArcaneFlush();
    });
  });
}
