document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("rightSidebar");
  const launcher = document.getElementById("rightSidebarLauncher");
  const closeBtn = document.getElementById("rightSidebarClose");
  const paydayTrigger = document.getElementById("paydayTrigger");
  const paydayWindow = document.getElementById("paydayWindow");
  const paydayWindowClose = document.getElementById("paydayWindowClose");
  const paydayWindowHandle = document.getElementById("paydayWindowHandle");
  if (!sidebar || !launcher || !closeBtn) {
    return;
  }

  const setOpenState = (isOpen) => {
    sidebar.classList.toggle("is-open", isOpen);
    launcher.setAttribute("aria-expanded", String(isOpen));
    launcher.classList.toggle("is-open", isOpen);
  };

  launcher.addEventListener("click", () => {
    setOpenState(true);
  });
  closeBtn.addEventListener("click", () => {
    setOpenState(false);
  });

  if (!paydayTrigger || !paydayWindow || !paydayWindowClose || !paydayWindowHandle) {
    return;
  }

  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
  const placePaydayWindow = (left, top) => {
    const rect = paydayWindow.getBoundingClientRect();
    const maxLeft = Math.max(12, window.innerWidth - rect.width - 12);
    const maxTop = Math.max(12, window.innerHeight - rect.height - 12);
    paydayWindow.style.left = `${clamp(left, 12, maxLeft)}px`;
    paydayWindow.style.top = `${clamp(top, 12, maxTop)}px`;
  };

  let dragPointerId = null;
  let dragOffsetX = 0;
  let dragOffsetY = 0;

  paydayTrigger.addEventListener("click", () => {
    paydayWindow.classList.add("is-open");
    paydayWindow.setAttribute("aria-hidden", "false");
    const rect = paydayWindow.getBoundingClientRect();
    const startLeft = window.innerWidth - rect.width - 176;
    const startTop = 118;
    placePaydayWindow(startLeft, startTop);
  });

  paydayWindowClose.addEventListener("click", () => {
    paydayWindow.classList.remove("is-open");
    paydayWindow.setAttribute("aria-hidden", "true");
  });
  paydayWindowClose.addEventListener("pointerdown", (event) => {
    event.stopPropagation();
  });

  paydayWindowHandle.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) {
      return;
    }
    const rect = paydayWindow.getBoundingClientRect();
    dragPointerId = event.pointerId;
    dragOffsetX = event.clientX - rect.left;
    dragOffsetY = event.clientY - rect.top;
    paydayWindowHandle.setPointerCapture(event.pointerId);
    paydayWindow.classList.add("is-dragging");
  });

  paydayWindowHandle.addEventListener("pointermove", (event) => {
    if (dragPointerId !== event.pointerId) {
      return;
    }
    placePaydayWindow(event.clientX - dragOffsetX, event.clientY - dragOffsetY);
  });

  const stopDragging = (event) => {
    if (dragPointerId !== event.pointerId) {
      return;
    }
    paydayWindow.classList.remove("is-dragging");
    try {
      paydayWindowHandle.releasePointerCapture(event.pointerId);
    } catch (_error) {
      // no-op
    }
    dragPointerId = null;
  };
  paydayWindowHandle.addEventListener("pointerup", stopDragging);
  paydayWindowHandle.addEventListener("pointercancel", stopDragging);
});

document.addEventListener("DOMContentLoaded", () => {
  const targets = document.querySelectorAll(".tooltip_target[data-tooltip]");
  if (!targets.length) {
    return;
  }

  const tooltip = document.createElement("div");
  tooltip.className = "floating-tooltip";
  document.body.appendChild(tooltip);
  const SHOW_DELAY_MS = 1100;
  const HIDE_HOLD_MS = 380;

  let activeTarget = null;
  let pendingTarget = null;
  let showTimeoutId = null;
  let hideTimeoutId = null;

  function clearShowTimer() {
    if (showTimeoutId) {
      window.clearTimeout(showTimeoutId);
      showTimeoutId = null;
    }
  }

  function scheduleHide() {
    if (hideTimeoutId) {
      window.clearTimeout(hideTimeoutId);
    }
    hideTimeoutId = window.setTimeout(() => {
      tooltip.classList.remove("is-visible");
      activeTarget = null;
      pendingTarget = null;
      hideTimeoutId = null;
    }, HIDE_HOLD_MS);
  }

  function positionTooltip(target) {
    const gap = 10;
    const viewportPadding = 8;
    const panel = target.closest(".p2_panel");
    const panelRect = (panel || target).getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    const preferredSide = target.getAttribute("data-tooltip-side") || "left";
    let left = preferredSide === "right"
      ? panelRect.right + gap
      : panelRect.left - tooltipRect.width - gap;

    if (left < viewportPadding || left + tooltipRect.width > window.innerWidth - viewportPadding) {
      left = panelRect.right + gap;
    }
    if (left + tooltipRect.width > window.innerWidth - viewportPadding) {
      left = panelRect.left - tooltipRect.width - gap;
    }

    let top = targetRect.top + (targetRect.height / 2) - (tooltipRect.height / 2);
    const maxTop = window.innerHeight - tooltipRect.height - viewportPadding;
    if (top > maxTop) {
      top = maxTop;
    }

    tooltip.style.left = `${Math.max(viewportPadding, left)}px`;
    tooltip.style.top = `${Math.max(viewportPadding, top)}px`;
  }

  targets.forEach((target) => {
    target.addEventListener("mouseenter", () => {
      const text = target.getAttribute("data-tooltip") || "";
      if (!text.trim()) {
        return;
      }

      if (hideTimeoutId) {
        window.clearTimeout(hideTimeoutId);
        hideTimeoutId = null;
      }
      clearShowTimer();
      if (activeTarget && activeTarget !== target) {
        tooltip.classList.remove("is-visible");
        activeTarget = null;
      }

      pendingTarget = target;
      showTimeoutId = window.setTimeout(() => {
        if (pendingTarget !== target) {
          return;
        }
        tooltip.textContent = text;
        activeTarget = target;
        tooltip.classList.add("is-visible");
        positionTooltip(target);
        showTimeoutId = null;
      }, SHOW_DELAY_MS);
    });

    target.addEventListener("mouseleave", () => {
      if (pendingTarget === target) {
        pendingTarget = null;
      }
      clearShowTimer();
      scheduleHide();
    });
  });

  window.addEventListener(
    "scroll",
    () => {
      if (activeTarget) {
        positionTooltip(activeTarget);
      }
    },
    true,
  );

  window.addEventListener("resize", () => {
    if (activeTarget) {
      positionTooltip(activeTarget);
    }
  });

  document.addEventListener("mouseleave", () => {
    clearShowTimer();
    scheduleHide();
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const walletTooltip = document.querySelector(".wallet_inline_tooltip");
  const walletCoins = document.querySelectorAll(".js-wallet-coin");
  if (!walletTooltip || !walletCoins.length) {
    return;
  }

  let hideTimeoutId = null;
  const show = () => {
    if (hideTimeoutId) {
      window.clearTimeout(hideTimeoutId);
      hideTimeoutId = null;
    }
    walletTooltip.classList.add("is-visible");
  };
  const hide = () => {
    if (hideTimeoutId) {
      window.clearTimeout(hideTimeoutId);
    }
    hideTimeoutId = window.setTimeout(() => {
      walletTooltip.classList.remove("is-visible");
      hideTimeoutId = null;
    }, 120);
  };

  walletCoins.forEach((coin) => {
    coin.addEventListener("mouseenter", show);
    coin.addEventListener("mouseleave", hide);
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector(".damage_actions");
  const circleWrap = document.querySelector(".damage_circle_wrap");
  const actionInput = document.querySelector(".damage_action_input");
  const amountInput = document.querySelector(".damage_amount_input");
  if (!form || !circleWrap || !actionInput || !amountInput) {
    return;
  }

  const buttons = form.querySelectorAll(".damage_action_btn[data-action]");
  if (!buttons.length) {
    return;
  }
  const currentDamageEl = document.querySelector(".damage_current_value");
  const maxDamageEl = document.querySelector(".damage_max_circle");
  const woundPenaltyEl = document.querySelector(".wound_penalty_circle");
  const woundStageEl = document.querySelector(".wound_stage_text");
  if (!currentDamageEl || !maxDamageEl || !woundPenaltyEl || !woundStageEl) {
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
  function triggerGlow(action) {
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
  }

  function readInt(text, fallback = 0) {
    const parsed = Number.parseInt(String(text ?? "").trim(), 10);
    return Number.isNaN(parsed) ? fallback : parsed;
  }

  function formatModifier(value) {
    if (value > 0) {
      return `+${value}`;
    }
    return String(value);
  }

  function computeWoundInfo(damage) {
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
  }

  buttons.forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.getAttribute("data-action");
      const amount = readInt(button.getAttribute("data-amount") || "1", 1);
      if (action !== "heal" && action !== "damage") {
        return;
      }

      actionInput.value = action;
      amountInput.value = String(amount);
      triggerGlow(action);

      // Optimistic UI update so value change feels immediate.
      localDamage = action === "damage"
        ? localDamage + amount
        : Math.max(0, localDamage - amount);
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
});
