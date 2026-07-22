import { applySheetPartials } from "./partial_updates.js";

export function initDamagePanel() {
  const form = document.querySelector(".damage_actions");
  const arcaneForm = document.querySelector(".arcane_actions");
  const gauge = document.querySelector(".damage_gauge");
  const arcaneMeter = document.querySelector(".arcane_meter");
  const needleArms = [...document.querySelectorAll(".damage_gauge_needle_arm")];
  const actionInput = document.querySelector(".damage_action_input");
  const amountInput = document.querySelector(".damage_amount_input");
  const damageTypeInput = document.querySelector(".damage_type_input");
  const damageTypeSwitch = document.querySelector(".damage_type_switch");
  const arcaneActionInput = document.querySelector(".arcane_action_input");
  const arcaneAmountInput = document.querySelector(".arcane_amount_input");
  const currentDamageEl = document.querySelector(".damage_readout_current");
  const stunDamageValueEl = document.querySelector("[data-stun-damage-value]");
  const lethalDamageValueEl = document.querySelector("[data-lethal-damage-value]");
  const currentArcaneEl = document.querySelector(".arcane_meter_current");
  const arcaneFillEl = document.querySelector(".arcane_meter_fill");
  const woundPenaltyEl = document.querySelector(".damage_penalty_value");
  const woundStageEl = document.querySelector(".damage_stage_value");
  if (!form || !gauge || !needleArms.length || !actionInput || !amountInput || !damageTypeInput || !damageTypeSwitch || !currentDamageEl || !woundPenaltyEl || !woundStageEl) {
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
  let requestQueue = Promise.resolve();
  let arcaneRequestVersion = 0;
  let lastAppliedArcaneResponseVersion = 0;
  let arcaneRequestQueue = Promise.resolve();
  let localStunDamage = readInt(gauge.dataset.stunDamage, 0);
  let localLethalDamage = readInt(gauge.dataset.lethalDamage, 0);
  let localDamage = localStunDamage + localLethalDamage;
  let localArcane = readInt(arcaneMeter?.dataset.arcaneCurrent || currentArcaneEl?.textContent, 0);
  let pendingDamageOperations = [];
  let damageFlushTimer = null;
  let damageDependentRefreshTimer = null;
  let damageDependentRefreshInFlight = false;
  let damageRequestInFlight = false;
  let confirmedStunDamage = localStunDamage;
  let confirmedLethalDamage = localLethalDamage;
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
    const isTerminalStage = new Set(["Außer Gefecht", "Ausser Gefecht", "Koma", "Tod"]).has(normalizedStage);
    woundPenaltyIgnored = Boolean(isIgnored);
    woundStageEl.textContent = composeStageLabel(stage, penaltyDisplay, isIgnored);
    woundStageEl.dataset.stage = normalizedStage;
    woundPenaltyEl.textContent = penaltyDisplay;
    woundStageEl.classList.toggle("is-disabled", woundPenaltyIgnored && !isTerminalStage);
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

  function renderNeedles(stunDamage, lethalDamage, options = {}) {
    const { animate = false } = options;
    const maxValue = Math.max(1, readInt(gauge.dataset.damageMax || "1", 1));
    const totalDamage = stunDamage + lethalDamage;
    gauge.classList.toggle("is-animating", animate);
    gauge.style.setProperty("--stun-needle-angle", `${computeRotation(stunDamage, maxValue)}deg`);
    gauge.style.setProperty("--lethal-needle-angle", `${computeRotation(lethalDamage, maxValue)}deg`);
    gauge.style.setProperty("--total-needle-angle", `${computeRotation(totalDamage, maxValue)}deg`);
    gauge.dataset.stunDamage = String(stunDamage);
    gauge.dataset.lethalDamage = String(lethalDamage);
    gauge.dataset.damageValue = String(totalDamage);
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

  function syncDamageDisplay(options = {}) {
    const { animate = true } = options;
    localDamage = localStunDamage + localLethalDamage;
    currentDamageEl.textContent = String(localDamage);
    if (stunDamageValueEl) {
      stunDamageValueEl.textContent = String(localStunDamage);
    }
    if (lethalDamageValueEl) {
      lethalDamageValueEl.textContent = String(localLethalDamage);
    }
    gauge.setAttribute("aria-label", `Schaden: ${localStunDamage} Betäubung, ${localLethalDamage} tödlich, ${localDamage} wirksam`);
    const optimisticWound = computeWoundInfo(localDamage);
    applyWoundState(optimisticWound.stage, optimisticWound.penaltyDisplay, optimisticWound.isIgnored);
    renderNeedles(localStunDamage, localLethalDamage, { animate });
    window.sessionStorage.setItem(storageKey, String(localDamage));
  }

  function applyDamageOperation(state, operation) {
    const amount = Math.max(0, readInt(operation.amount, 0));
    const maxDamage = Math.max(1, readInt(gauge.dataset.damageMax || "1", 1));
    let stun = Math.max(0, readInt(state.stun, 0));
    let lethal = Math.max(0, readInt(state.lethal, 0));

    if (operation.damageType === "G") {
      let combinedState = { stun, lethal };
      for (let index = 0; index < amount; index += 1) {
        combinedState = applyDamageOperation(combinedState, { ...operation, damageType: "B", amount: 1 });
        combinedState = applyDamageOperation(combinedState, { ...operation, damageType: "T", amount: 1 });
      }
      return combinedState;
    }
    if (operation.damageType === "T") {
      lethal = operation.action === "damage" ? lethal + amount : Math.max(0, lethal - amount);
    } else if (operation.action === "heal") {
      stun = Math.max(0, stun - amount);
    } else if (operation.action === "damage") {
      const availableTotal = Math.max(0, maxDamage - (stun + lethal));
      const fill = Math.min(amount, availableTotal);
      stun += fill;
      const overflowSteps = amount - fill;
      const converted = Math.min(overflowSteps, stun);
      stun -= converted;
      lethal += overflowSteps;
    }
    return { stun, lethal };
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
    if (damageRequestInFlight || pendingDamageOperations.length) {
      scheduleDamageDependentRefresh();
      return;
    }

    damageDependentRefreshInFlight = true;
    actionInput.value = "";
    amountInput.value = "1";
    damageTypeInput.value = damageTypeSwitch.dataset.damageType || "B";

    const formData = new FormData(form);
    formData.set("ajax", "1");
    formData.set("partials", "1");

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
      const serverStunDamage = readInt(payload.current_stun_damage, localStunDamage);
      const serverLethalDamage = readInt(payload.current_lethal_damage, localLethalDamage);
      if (damageRequestInFlight || pendingDamageOperations.length || serverStunDamage !== localStunDamage || serverLethalDamage !== localLethalDamage) {
        scheduleDamageDependentRefresh();
        return;
      }

      confirmedStunDamage = serverStunDamage;
      confirmedLethalDamage = serverLethalDamage;
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
    if (damageRequestInFlight || !pendingDamageOperations.length) {
      return requestQueue;
    }

    const operations = pendingDamageOperations.splice(0);
    const groupedOperations = [];
    operations.forEach((operation) => {
      const previous = groupedOperations[groupedOperations.length - 1];
      if (previous && previous.damageType === operation.damageType && previous.action === operation.action) {
        previous.amount += operation.amount;
      } else {
        groupedOperations.push({ ...operation });
      }
    });
    const unsentOperations = groupedOperations.map((operation) => ({ ...operation }));
    damageRequestInFlight = true;

    requestQueue = requestQueue.then(async () => {
      let lastPayload = null;
      while (unsentOperations.length) {
        const operation = unsentOperations[0];
        actionInput.value = operation.action;
        amountInput.value = String(operation.amount);
        damageTypeInput.value = operation.damageType;
        const formData = new FormData(form);
        formData.set("ajax", "1");
        formData.set("partials", "0");
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
        lastPayload = await response.json();
        confirmedStunDamage = readInt(lastPayload.current_stun_damage, confirmedStunDamage);
        confirmedLethalDamage = readInt(lastPayload.current_lethal_damage, confirmedLethalDamage);
        gauge.dataset.damageMax = String(readInt(lastPayload.current_damage_max, readInt(gauge.dataset.damageMax || "1", 1)));
        unsentOperations.shift();
      }

      if (!pendingDamageOperations.length) {
        localStunDamage = confirmedStunDamage;
        localLethalDamage = confirmedLethalDamage;
        syncDamageDisplay({ animate: true });
        if (lastPayload) {
          applyWoundState(
            String(lastPayload.current_wound_stage ?? "-"),
            String(lastPayload.current_wound_penalty ?? "-"),
            Boolean(lastPayload.is_wound_penalty_ignored),
          );
        }
      }
    }).catch((_error) => {
      pendingDamageOperations = [...unsentOperations, ...pendingDamageOperations];
      let replayed = { stun: confirmedStunDamage, lethal: confirmedLethalDamage };
      pendingDamageOperations.forEach((operation) => {
        replayed = applyDamageOperation(replayed, operation);
      });
      localStunDamage = replayed.stun;
      localLethalDamage = replayed.lethal;
      syncDamageDisplay({ animate: false });
    }).finally(() => {
      damageRequestInFlight = false;
      if (pendingDamageOperations.length) {
        scheduleDamageFlush();
      } else {
        scheduleDamageDependentRefresh();
      }
    });
    return requestQueue;
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
  renderNeedles(localStunDamage, localLethalDamage, {
    animate: previousValue !== null && readInt(previousValue, initialValue) !== initialValue,
  });
  window.sessionStorage.setItem(storageKey, String(initialValue));
  renderArcaneMeter(localArcane, readInt(arcaneMeter?.dataset.arcaneMax || "0", 0), { animate: false });

  const damageTypeStorageKey = `charsheet.damageType.${gauge.dataset.characterId || "default"}`;
  function selectDamageType(damageType, persist = true) {
    const selectedType = ["B", "G", "T"].includes(damageType) ? damageType : "B";
    const typeLabels = {
      B: "Betäubungsschaden",
      G: "Betäubungs- und tödlicher Schaden",
      T: "Tödlicher Schaden",
    };
    const typeLabel = typeLabels[selectedType];
    damageTypeSwitch.dataset.damageType = selectedType;
    damageTypeSwitch.setAttribute("aria-label", `Schadensauswahl: ${typeLabel}`);
    damageTypeInput.value = selectedType;
    document.querySelectorAll("#sheetDamagePanel .damage_step_btn[data-action]").forEach((button) => {
      if (button.classList.contains("arcane_step_btn")) {
        return;
      }
      button.setAttribute("aria-label", `${typeLabel} ${button.dataset.action === "damage" ? "erhöhen" : "verringern"}`);
    });
    if (persist) {
      window.localStorage.setItem(damageTypeStorageKey, selectedType);
    }
  }

  let storedDamageType = "B";
  try {
    storedDamageType = window.localStorage.getItem(damageTypeStorageKey) || "B";
  } catch (_error) {
    // Keep the default selection when browser storage is unavailable.
  }
  selectDamageType(storedDamageType, false);
  damageTypeSwitch.addEventListener("click", (event) => {
    const types = ["B", "G", "T"];
    if (event.detail === 0) {
      const currentIndex = types.indexOf(damageTypeSwitch.dataset.damageType || "B");
      selectDamageType(types[(currentIndex + 1) % types.length]);
      return;
    }
    const bounds = damageTypeSwitch.getBoundingClientRect();
    const segmentIndex = Math.max(0, Math.min(2, Math.floor(((event.clientX - bounds.left) / bounds.width) * 3)));
    selectDamageType(types[segmentIndex]);
  });

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

      const operation = {
        damageType: ["B", "G", "T"].includes(damageTypeSwitch.dataset.damageType)
          ? damageTypeSwitch.dataset.damageType
          : "B",
        action,
        amount,
      };
      const nextDamage = applyDamageOperation(
        { stun: localStunDamage, lethal: localLethalDamage },
        operation,
      );
      localStunDamage = nextDamage.stun;
      localLethalDamage = nextDamage.lethal;
      pendingDamageOperations.push(operation);
      syncDamageDisplay({ animate: true });
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
