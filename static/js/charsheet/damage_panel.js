import { readInt } from "./utils.js";

function formatModifier(value) {
  if (value > 0) {
    return `+${value}`;
  }
  return String(value);
}

export function initDamagePanel() {
  const form = document.querySelector(".damage_actions");
  const circleWrap = document.querySelector(".damage_circle_wrap");
  const actionInput = document.querySelector(".damage_action_input");
  const amountInput = document.querySelector(".damage_amount_input");
  const currentDamageEl = document.querySelector(".damage_current_value");
  const maxDamageEl = document.querySelector(".damage_max_circle");
  const woundPenaltyEl = document.querySelector(".wound_penalty_circle");
  const woundStageEl = document.querySelector(".wound_stage_text");
  if (
    !form
    || !circleWrap
    || !actionInput
    || !amountInput
    || !currentDamageEl
    || !maxDamageEl
    || !woundPenaltyEl
    || !woundStageEl
  ) {
    return;
  }

  const buttons = form.querySelectorAll(".damage_action_btn[data-action]");
  if (!buttons.length) {
    return;
  }

  const thresholdsScript = document.getElementById("wound-thresholds-data");
  let thresholdRows = [];
  if (thresholdsScript) {
    try {
      thresholdRows = JSON.parse(thresholdsScript.textContent || "[]");
    } catch (_error) {
      thresholdRows = [];
    }
  }

  let requestVersion = 0;
  let lastAppliedResponseVersion = 0;
  let requestQueue = Promise.resolve();
  let isFallbackSubmitting = false;
  let localDamage = readInt(currentDamageEl.textContent, 0);
  let glowTimeoutId = null;

  const triggerGlow = (action) => {
    circleWrap.classList.remove("effect-heal", "effect-damage");
    void circleWrap.offsetWidth;
    circleWrap.classList.add(action === "heal" ? "effect-heal" : "effect-damage");
    if (glowTimeoutId) {
      window.clearTimeout(glowTimeoutId);
    }
    glowTimeoutId = window.setTimeout(() => {
      circleWrap.classList.remove("effect-heal", "effect-damage");
      glowTimeoutId = null;
    }, 460);
  };

  const computeWoundInfo = (damage) => {
    if (!thresholdRows.length) {
      return { stage: "-", penaltyDisplay: "-" };
    }
    const sorted = [...thresholdRows].sort((a, b) => a.threshold - b.threshold);
    const first = sorted[0].threshold;
    const last = sorted[sorted.length - 1].threshold;

    if (damage < first) {
      return { stage: "-", penaltyDisplay: "-" };
    }
    if (damage > last) {
      return { stage: "Tod", penaltyDisplay: "0" };
    }

    let current = sorted[0];
    for (const row of sorted) {
      if (damage >= row.threshold) {
        current = row;
      } else {
        break;
      }
    }
    return {
      stage: current.stage || "-",
      penaltyDisplay: formatModifier(current.penalty ?? 0),
    };
  };

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.getAttribute("data-action");
      const amount = readInt(button.getAttribute("data-amount") || "1", 1);
      if (action !== "heal" && action !== "damage") {
        return;
      }

      actionInput.value = action;
      amountInput.value = String(amount);
      triggerGlow(action);

      localDamage = action === "damage" ? localDamage + amount : Math.max(0, localDamage - amount);
      currentDamageEl.textContent = String(localDamage);
      const optimisticWound = computeWoundInfo(localDamage);
      woundStageEl.textContent = optimisticWound.stage;
      woundPenaltyEl.textContent = optimisticWound.penaltyDisplay;

      const thisRequestVersion = requestVersion + 1;
      requestVersion = thisRequestVersion;
      const formData = new FormData(form);
      formData.set("ajax", "1");

      requestQueue = requestQueue.then(async () => {
        const response = await fetch(form.action, {
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
        localDamage = readInt(payload.current_damage, localDamage);
        currentDamageEl.textContent = String(localDamage);
        maxDamageEl.textContent = String(payload.current_damage_max ?? maxDamageEl.textContent);
        woundStageEl.textContent = String(payload.current_wound_stage ?? woundStageEl.textContent);
        woundPenaltyEl.textContent = String(payload.current_wound_penalty ?? woundPenaltyEl.textContent);
        woundPenaltyEl.classList.toggle("is-disabled", Boolean(payload.is_wound_penalty_ignored));
      }).catch((_error) => {
        if (!isFallbackSubmitting) {
          isFallbackSubmitting = true;
          form.submit();
        }
      });
    });
  });
}
