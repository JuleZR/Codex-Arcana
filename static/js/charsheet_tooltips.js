document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("rightSidebar");
  const launcher = document.getElementById("rightSidebarLauncher");
  const closeBtn = document.getElementById("rightSidebarClose");
  const paydayTrigger = document.getElementById("paydayTrigger");
  const shopScaleTrigger = document.getElementById("shopScaleTrigger");
  const learnMenuTrigger = document.getElementById("learnMenuTrigger");
  const xpGainTrigger = document.getElementById("xpGainTrigger");
  const shopAddItemBtn = document.getElementById("shopAddItemBtn");
  const paydayWindow = document.getElementById("paydayWindow");
  const paydayWindowClose = document.getElementById("paydayWindowClose");
  const paydayWindowHandle = document.getElementById("paydayWindowHandle");
  const xpWindow = document.getElementById("xpWindow");
  const xpWindowClose = document.getElementById("xpWindowClose");
  const xpWindowHandle = document.getElementById("xpWindowHandle");
  const shopWindow = document.getElementById("shopWindow");
  const shopWindowClose = document.getElementById("shopWindowClose");
  const shopWindowHandle = document.getElementById("shopWindowHandle");
  const shopItemWindow = document.getElementById("shopItemWindow");
  const shopItemWindowClose = document.getElementById("shopItemWindowClose");
  const shopItemWindowHandle = document.getElementById("shopItemWindowHandle");
  const shopItemCancelBtn = document.getElementById("shopItemCancelBtn");
  const learnWindow = document.getElementById("learnWindow");
  const learnWindowClose = document.getElementById("learnWindowClose");
  const learnWindowHandle = document.getElementById("learnWindowHandle");
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

  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
  const placeWindow = (win, left, top) => {
    const rect = win.getBoundingClientRect();
    const maxLeft = Math.max(12, window.innerWidth - rect.width - 12);
    const maxTop = Math.max(12, window.innerHeight - rect.height - 12);
    win.style.left = `${clamp(left, 12, maxLeft)}px`;
    win.style.top = `${clamp(top, 12, maxTop)}px`;
  };

  const setupFloatingWindow = (trigger, win, close, handle, startTop, storageKey) => {
    if (!trigger || !win || !close || !handle) {
      return;
    }

    const loadState = () => {
      try {
        const raw = window.localStorage.getItem(storageKey);
        return raw ? JSON.parse(raw) : null;
      } catch (_error) {
        return null;
      }
    };
    const saveState = (state) => {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(state));
      } catch (_error) {
        // no-op
      }
    };
    const readWindowState = () => {
      const left = Number.parseFloat(win.style.left || "");
      const top = Number.parseFloat(win.style.top || "");
      return {
        isOpen: win.classList.contains("is-open"),
        left: Number.isFinite(left) ? left : null,
        top: Number.isFinite(top) ? top : null,
      };
    };

    let dragPointerId = null;
    let dragOffsetX = 0;
    let dragOffsetY = 0;

    const persistedState = loadState();
    if (persistedState && Number.isFinite(persistedState.left) && Number.isFinite(persistedState.top)) {
      placeWindow(win, persistedState.left, persistedState.top);
    }
    if (persistedState && persistedState.isOpen) {
      win.classList.add("is-open");
      win.setAttribute("aria-hidden", "false");
    }

    trigger.addEventListener("click", () => {
      win.classList.add("is-open");
      win.setAttribute("aria-hidden", "false");
      const rect = win.getBoundingClientRect();
      const saved = loadState();
      if (saved && Number.isFinite(saved.left) && Number.isFinite(saved.top)) {
        placeWindow(win, saved.left, saved.top);
      } else {
        const startLeft = window.innerWidth - rect.width - 176;
        placeWindow(win, startLeft, startTop);
      }
      saveState(readWindowState());
    });

    close.addEventListener("click", () => {
      win.classList.remove("is-open");
      win.setAttribute("aria-hidden", "true");
      saveState(readWindowState());
    });
    close.addEventListener("pointerdown", (event) => {
      event.stopPropagation();
    });

    handle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) {
        return;
      }
      const rect = win.getBoundingClientRect();
      dragPointerId = event.pointerId;
      dragOffsetX = event.clientX - rect.left;
      dragOffsetY = event.clientY - rect.top;
      handle.setPointerCapture(event.pointerId);
      win.classList.add("is-dragging");
    });

    handle.addEventListener("pointermove", (event) => {
      if (dragPointerId !== event.pointerId) {
        return;
      }
      placeWindow(win, event.clientX - dragOffsetX, event.clientY - dragOffsetY);
      saveState(readWindowState());
    });

    const stopDragging = (event) => {
      if (dragPointerId !== event.pointerId) {
        return;
      }
      win.classList.remove("is-dragging");
      try {
        handle.releasePointerCapture(event.pointerId);
      } catch (_error) {
        // no-op
      }
      dragPointerId = null;
      saveState(readWindowState());
    };
    handle.addEventListener("pointerup", stopDragging);
    handle.addEventListener("pointercancel", stopDragging);
  };

  setupFloatingWindow(paydayTrigger, paydayWindow, paydayWindowClose, paydayWindowHandle, 118, "charsheet.paydayWindow");
  setupFloatingWindow(xpGainTrigger, xpWindow, xpWindowClose, xpWindowHandle, 174, "charsheet.xpWindow");
  setupFloatingWindow(shopScaleTrigger, shopWindow, shopWindowClose, shopWindowHandle, 92, "charsheet.shopWindow");
  setupFloatingWindow(shopAddItemBtn, shopItemWindow, shopItemWindowClose, shopItemWindowHandle, 128, "charsheet.shopItemWindow");
  setupFloatingWindow(learnMenuTrigger, learnWindow, learnWindowClose, learnWindowHandle, 138, "charsheet.learnWindow");

  if (shopItemCancelBtn && shopItemWindow) {
    shopItemCancelBtn.addEventListener("click", () => {
      shopItemWindow.classList.remove("is-open");
      shopItemWindow.setAttribute("aria-hidden", "true");
      try {
        const left = Number.parseFloat(shopItemWindow.style.left || "");
        const top = Number.parseFloat(shopItemWindow.style.top || "");
        window.localStorage.setItem("charsheet.shopItemWindow", JSON.stringify({
          isOpen: false,
          left: Number.isFinite(left) ? left : null,
          top: Number.isFinite(top) ? top : null,
        }));
      } catch (_error) {
        // no-op
      }
    });
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const typeSelect = document.getElementById("shopItemTypeSelect");
  const armorFields = document.getElementById("shopItemArmorFields");
  const weaponFields = document.getElementById("shopItemWeaponFields");
  if (!typeSelect || !armorFields || !weaponFields) {
    return;
  }

  const armorInput = armorFields.querySelector("input[name='armor_rs_total']");
  const stackableRow = document.getElementById("shopItemStackableRow");
  const stackableInput = document.getElementById("shopItemStackableInput");
  const armorModeInputs = armorFields.querySelectorAll("input[name='armor_mode']");
  const armorTotalFields = document.getElementById("shopArmorTotalFields");
  const armorZoneFields = document.getElementById("shopArmorZoneFields");
  const armorZoneInputs = armorFields.querySelectorAll(
    "input[name='armor_rs_head'], input[name='armor_rs_torso'], input[name='armor_rs_arm_left'], input[name='armor_rs_arm_right'], input[name='armor_rs_leg_left'], input[name='armor_rs_leg_right']"
  );
  const weaponDamageInput = weaponFields.querySelector("input[name='weapon_damage']");
  const weaponDamageSourceSelect = weaponFields.querySelector("select[name='weapon_damage_source']");
  const weaponMinStInput = weaponFields.querySelector("input[name='weapon_min_st']");

  const syncArmorModeFields = () => {
    if (!armorTotalFields || !armorZoneFields) {
      return;
    }
    const selectedModeInput = armorFields.querySelector("input[name='armor_mode']:checked");
    const mode = selectedModeInput ? selectedModeInput.value : "total";
    const totalMode = mode === "total";

    armorTotalFields.hidden = !totalMode;
    armorZoneFields.hidden = totalMode;
    if (armorInput) {
      armorInput.required = totalMode;
    }
    armorZoneInputs.forEach((input) => {
      input.required = !totalMode;
    });
  };

  const syncItemTypeFields = () => {
    const value = String(typeSelect.value || "");
    const isArmor = value === "armor";
    const isWeapon = value === "weapon";

    armorFields.hidden = !isArmor;
    weaponFields.hidden = !isWeapon;

    if (armorInput) {
      armorInput.required = isArmor;
    }
    if (weaponDamageInput) {
      weaponDamageInput.required = isWeapon;
    }
    if (weaponDamageSourceSelect) {
      weaponDamageSourceSelect.required = isWeapon;
    }
    if (weaponMinStInput) {
      weaponMinStInput.required = isWeapon;
    }

    if (stackableRow && stackableInput) {
      const lockStackableOff = isArmor || isWeapon;
      stackableRow.hidden = lockStackableOff;
      stackableInput.disabled = lockStackableOff;
      if (lockStackableOff) {
        stackableInput.checked = false;
      }
    }

    if (isArmor) {
      syncArmorModeFields();
    } else {
      if (armorTotalFields) {
        armorTotalFields.hidden = false;
      }
      if (armorZoneFields) {
        armorZoneFields.hidden = true;
      }
      if (armorInput) {
        armorInput.required = false;
      }
      armorZoneInputs.forEach((input) => {
        input.required = false;
      });
    }
  };

  armorModeInputs.forEach((input) => {
    input.addEventListener("change", syncArmorModeFields);
  });
  typeSelect.addEventListener("change", syncItemTypeFields);
  syncItemTypeFields();
});

document.addEventListener("DOMContentLoaded", () => {
  const filterInput = document.getElementById("shopFilterInput");
  const groups = document.querySelectorAll("[data-shop-group]");
  if (!filterInput || !groups.length) {
    return;
  }

  const applyFilter = () => {
    const query = (filterInput.value || "").trim().toLowerCase();
    groups.forEach((group) => {
      const rows = group.querySelectorAll("[data-shop-item]");
      let hasMatch = false;
      rows.forEach((row) => {
        const haystack = (row.getAttribute("data-shop-search") || "").toLowerCase();
        const isMatch = !query || haystack.includes(query);
        row.hidden = !isMatch;
        if (isMatch) {
          hasMatch = true;
        }
      });
      group.hidden = !hasMatch;
      if (query && hasMatch) {
        group.open = true;
      }
    });
  };

  filterInput.addEventListener("input", applyFilter);
  applyFilter();
});

document.addEventListener("DOMContentLoaded", () => {
  const shopList = document.querySelector(".shop_list_scroll");
  const cartWrapper = document.querySelector(".shop_cart_wrapper");
  const cartBody = document.getElementById("shopCartBody");
  const subtotalEl = document.getElementById("shopCartSubtotal");
  const finalEl = document.getElementById("shopCartFinal");
  const balanceEl = document.getElementById("shopCartBalance");
  const discountInput = document.getElementById("shopDiscountInput");
  const discountDecBtn = document.getElementById("shopDiscountDec");
  const discountIncBtn = document.getElementById("shopDiscountInc");
  const buyBtn = document.getElementById("shopBuyBtn");
  if (
    !shopList || !cartWrapper || !cartBody || !subtotalEl || !finalEl || !balanceEl ||
    !discountInput || !discountDecBtn || !discountIncBtn || !buyBtn
  ) {
    return;
  }

  const baseBalance = Number.parseInt(cartWrapper.getAttribute("data-shop-balance") || "0", 10) || 0;
  const buyUrl = String(cartWrapper.getAttribute("data-buy-url") || "");
  const cart = new Map();

  const readInt = (value, fallback = 0) => {
    const parsed = Number.parseInt(String(value ?? "").trim(), 10);
    return Number.isNaN(parsed) ? fallback : parsed;
  };
  const fmtNumber = (value) => Number(value || 0).toLocaleString("de-DE");
  const fmtKs = (value) => `${fmtNumber(value)} KS`;
  const getCsrfToken = () => {
    const cookie = document.cookie
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith("csrftoken="));
    return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
  };

  const render = () => {
    let subtotal = 0;
    const rows = [];
    cart.forEach((entry) => {
      const lineTotal = entry.price * entry.qty;
      subtotal += lineTotal;
      rows.push(`
        <tr data-cart-id="${entry.id}">
          <td>${entry.name}</td>
          <td>
            <div class="shop_qty_stepper">
              <button type="button" class="shop_step_btn" data-cart-qty-dec aria-label="Menge verringern">-</button>
              <input type="text" class="shop_cart_qty_input" value="${entry.qty}" data-cart-qty inputmode="numeric" aria-label="Menge">
              <button type="button" class="shop_step_btn" data-cart-qty-inc aria-label="Menge erhöhen">+</button>
            </div>
          </td>
          <td>${fmtKs(entry.price)}</td>
          <td>${fmtKs(lineTotal)}</td>
          <td><button type="button" class="shop_cart_remove_btn" data-cart-remove>×</button></td>
        </tr>
      `);
    });

    cartBody.innerHTML = rows.length
      ? rows.join("")
      : '<tr class="shop_cart_empty_row"><td colspan="5">Noch keine Items ausgewählt.</td></tr>';

    const discountPercent = Math.min(100, Math.max(0, readInt(discountInput.value, 0)));
    if (readInt(discountInput.value, 0) !== discountPercent) {
      discountInput.value = String(discountPercent);
    }
    const finalPrice = Math.max(0, Math.round(subtotal * (100 - discountPercent) / 100));
    const simulatedBalance = baseBalance - finalPrice;

    subtotalEl.textContent = fmtKs(subtotal);
    finalEl.textContent = fmtKs(finalPrice);
    balanceEl.textContent = fmtKs(simulatedBalance);
    balanceEl.classList.toggle("is-negative", simulatedBalance < 0);
  };

  shopList.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    if (!target.classList.contains("shop_pick_btn")) {
      return;
    }

    const row = target.closest("[data-shop-item]");
    if (!(row instanceof HTMLElement)) {
      return;
    }
    const id = row.getAttribute("data-shop-id") || "";
    const name = row.getAttribute("data-shop-name") || "";
    const price = readInt(row.getAttribute("data-shop-price"), 0);
    if (!id || !name || price < 0) {
      return;
    }

    const existing = cart.get(id);
    if (existing) {
      existing.qty += 1;
    } else {
      cart.set(id, { id, name, price, qty: 1 });
    }
    render();
  });

  cartBody.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    if (target.hasAttribute("data-cart-qty-dec") || target.hasAttribute("data-cart-qty-inc")) {
      const row = target.closest("[data-cart-id]");
      if (!(row instanceof HTMLElement)) {
        return;
      }
      const id = row.getAttribute("data-cart-id") || "";
      const entry = cart.get(id);
      if (!entry) {
        return;
      }
      const delta = target.hasAttribute("data-cart-qty-inc") ? 1 : -1;
      entry.qty = Math.max(1, entry.qty + delta);
      render();
      return;
    }
    if (!target.hasAttribute("data-cart-remove")) {
      return;
    }
    const row = target.closest("[data-cart-id]");
    if (!(row instanceof HTMLElement)) {
      return;
    }
    const id = row.getAttribute("data-cart-id") || "";
    if (!id) {
      return;
    }
    cart.delete(id);
    render();
  });

  cartBody.addEventListener("input", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || !target.hasAttribute("data-cart-qty")) {
      return;
    }
    const row = target.closest("[data-cart-id]");
    if (!(row instanceof HTMLElement)) {
      return;
    }
    const id = row.getAttribute("data-cart-id") || "";
    const entry = cart.get(id);
    if (!entry) {
      return;
    }
    entry.qty = Math.max(1, readInt(target.value, 1));
    render();
  });

  discountInput.addEventListener("input", render);
  discountDecBtn.addEventListener("click", () => {
    discountInput.value = String(Math.max(0, readInt(discountInput.value, 0) - 5));
    render();
  });
  discountIncBtn.addEventListener("click", () => {
    discountInput.value = String(Math.min(100, readInt(discountInput.value, 0) + 5));
    render();
  });

  buyBtn.addEventListener("click", async () => {
    if (!buyUrl || !cart.size) {
      return;
    }
    const items = Array.from(cart.values()).map((entry) => ({
      id: entry.id,
      qty: entry.qty,
    }));
    const payload = {
      items,
      discount: readInt(discountInput.value, 0),
    };

    try {
      const response = await fetch(buyUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (data && data.ok) {
        const shopWindow = document.getElementById("shopWindow");
        if (shopWindow) {
          shopWindow.classList.remove("is-open");
          shopWindow.setAttribute("aria-hidden", "true");
          try {
            const left = Number.parseFloat(shopWindow.style.left || "");
            const top = Number.parseFloat(shopWindow.style.top || "");
            window.localStorage.setItem("charsheet.shopWindow", JSON.stringify({
              isOpen: false,
              left: Number.isFinite(left) ? left : null,
              top: Number.isFinite(top) ? top : null,
            }));
          } catch (_error) {
            // no-op
          }
        }
        window.location.reload();
        return;
      }
      if (data && data.error === "insufficient_funds") {
        balanceEl.classList.remove("is-fail-flash");
        void balanceEl.offsetWidth;
        balanceEl.classList.add("is-fail-flash");
      }
    } catch (_error) {
      // no-op for now
    }
  });
  render();
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
