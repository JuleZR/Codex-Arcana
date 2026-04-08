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
      return { stage: "-", penaltyDisplay: "-", isIgnored: false };
    }
    const sorted = [...thresholdRows].sort((a, b) => a.threshold - b.threshold);
    const first = Number(sorted[0].threshold || 0);
    const last = Number(sorted[sorted.length - 1].threshold || 0);

    if (damage < first) {
      return { stage: "-", penaltyDisplay: "-", isIgnored: false };
    }
    if (damage > last) {
      return { stage: "Tod", penaltyDisplay: "0", isIgnored: false };
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
      isIgnored: false,
    };
  }

  function applyWoundState(stage, penaltyDisplay, isIgnored = false) {
    const normalizedStage = String(stage || "-").trim() || "-";
    woundStageEl.textContent = composeStageLabel(stage, penaltyDisplay, isIgnored);
    woundStageEl.dataset.stage = normalizedStage;
    woundPenaltyEl.textContent = penaltyDisplay;
    woundStageEl.classList.toggle("is-disabled", Boolean(isIgnored));
    woundPenaltyEl.classList.toggle("is-disabled", Boolean(isIgnored));
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

      actionInput.value = action;
      amountInput.value = String(amount);

      const previousDamage = localDamage;
      localDamage = action === "damage"
        ? localDamage + amount
        : Math.max(0, localDamage - amount);

      currentDamageEl.textContent = String(localDamage);
      const optimisticWound = computeWoundInfo(localDamage);
      applyWoundState(optimisticWound.stage, optimisticWound.penaltyDisplay, optimisticWound.isIgnored);
      renderNeedle(localDamage, { animate: true, fromValue: previousDamage });
      window.sessionStorage.setItem(storageKey, String(localDamage));

      const thisRequestVersion = requestVersion + 1;
      requestVersion = thisRequestVersion;
      const formData = new FormData(form);
      formData.set("ajax", "1");

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
        localDamage = readInt(payload.current_damage, localDamage);
        currentDamageEl.textContent = String(localDamage);
        gauge.dataset.damageMax = String(readInt(payload.current_damage_max, readInt(gauge.dataset.damageMax || "1", 1)));
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
      }).catch((_error) => {
        localDamage = previousDamage;
        currentDamageEl.textContent = String(localDamage);
        const rollbackWound = computeWoundInfo(localDamage);
        applyWoundState(rollbackWound.stage, rollbackWound.penaltyDisplay, rollbackWound.isIgnored);
        renderNeedle(localDamage, { animate: true, fromValue: readInt(gauge.dataset.damageValue || localDamage, localDamage) });
        window.sessionStorage.setItem(storageKey, String(localDamage));
      });
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

      arcaneActionInput.value = action;
      arcaneAmountInput.value = String(amount);

      const maxArcane = readInt(arcaneMeter.dataset.arcaneMax || "0", 0);
      const previousArcane = localArcane;
      localArcane = action === "restore"
        ? Math.min(maxArcane, localArcane + amount)
        : Math.max(0, localArcane - amount);
      renderArcaneMeter(localArcane, maxArcane);

      const thisRequestVersion = arcaneRequestVersion + 1;
      arcaneRequestVersion = thisRequestVersion;
      const formData = new FormData(arcaneForm);
      formData.set("ajax", "1");

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
        localArcane = readInt(payload.current_arcane_power, localArcane);
        renderArcaneMeter(localArcane, readInt(payload.current_arcane_power_max, maxArcane));
      }).catch((_error) => {
        localArcane = previousArcane;
        renderArcaneMeter(localArcane, maxArcane);
      });
    });
  });
}
