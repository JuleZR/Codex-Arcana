document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("rightSidebar");
  const launcher = document.getElementById("rightSidebarLauncher");
  const closeBtn = document.getElementById("rightSidebarClose");
  const paydayTrigger = document.getElementById("paydayTrigger");
  const shopScaleTrigger = document.getElementById("shopScaleTrigger");
  const learnMenuTrigger = document.getElementById("learnMenuTrigger");
  const charInfoEditTrigger = document.getElementById("charInfoEditTrigger");
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
  const charInfoWindow = document.getElementById("charInfoWindow");
  const charInfoWindowClose = document.getElementById("charInfoWindowClose");
  const charInfoWindowHandle = document.getElementById("charInfoWindowHandle");
  const charInfoCancelBtn = document.getElementById("charInfoCancelBtn");
  const charInfoForm = document.getElementById("charInfoForm");
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
  setupFloatingWindow(charInfoEditTrigger, charInfoWindow, charInfoWindowClose, charInfoWindowHandle, 132, "charsheet.charInfoWindow");

  if (learnWindow && learnWindow.getAttribute("data-force-close") === "1") {
    learnWindow.classList.remove("is-open");
    learnWindow.setAttribute("aria-hidden", "true");
    try {
      const left = Number.parseFloat(learnWindow.style.left || "");
      const top = Number.parseFloat(learnWindow.style.top || "");
      window.localStorage.setItem("charsheet.learnWindow", JSON.stringify({
        isOpen: false,
        left: Number.isFinite(left) ? left : null,
        top: Number.isFinite(top) ? top : null,
      }));
    } catch (_error) {
      // no-op
    }
  }

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

  if (charInfoCancelBtn && charInfoWindow) {
    charInfoCancelBtn.addEventListener("click", () => {
      charInfoWindow.classList.remove("is-open");
      charInfoWindow.setAttribute("aria-hidden", "true");
      try {
        const left = Number.parseFloat(charInfoWindow.style.left || "");
        const top = Number.parseFloat(charInfoWindow.style.top || "");
        window.localStorage.setItem("charsheet.charInfoWindow", JSON.stringify({
          isOpen: false,
          left: Number.isFinite(left) ? left : null,
          top: Number.isFinite(top) ? top : null,
        }));
      } catch (_error) {
        // no-op
      }
    });
  }

  if (charInfoForm) {
    charInfoForm.addEventListener("submit", () => {
      try {
        const left = Number.parseFloat(charInfoWindow?.style.left || "");
        const top = Number.parseFloat(charInfoWindow?.style.top || "");
        window.localStorage.setItem("charsheet.charInfoWindow", JSON.stringify({
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
  const fireflies = Array.from(document.querySelectorAll(".firefly-layer .firefly"));
  if (!fireflies.length) {
    return;
  }

  let seed = 948713;
  const rand = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  const randRange = (min, max) => min + (max - min) * rand();

  const styleId = "firefly-generated-keyframes";
  const existing = document.getElementById(styleId);
  if (existing) {
    existing.remove();
  }

  const keyframes = [];
  fireflies.forEach((firefly, index) => {
    const moveName = `firefly-move-${index + 1}`;
    const stepCount = Math.floor(randRange(16, 29));
    const frames = [];
    for (let step = 0; step <= stepCount; step += 1) {
      const percent = (step / stepCount) * 100;
      const x = randRange(-49, 49).toFixed(2);
      const y = randRange(-49, 49).toFixed(2);
      const scale = randRange(0.26, 1).toFixed(2);
      frames.push(
        `${percent.toFixed(6)}% { transform: translateX(${x}vw) translateY(${y}vh) scale(${scale}); }`
      );
    }
    keyframes.push(`@keyframes ${moveName} {\n${frames.join("\n")}\n}`);

    firefly.style.setProperty("--ff-move", moveName);
    firefly.style.setProperty("--ff-move-duration", `${Math.round(randRange(180, 320))}s`);
    firefly.style.setProperty("--ff-move-delay", `-${Math.round(randRange(0, 300))}s`);
    firefly.style.setProperty("--ff-drift-duration", `${randRange(9, 18).toFixed(3)}s`);
    firefly.style.setProperty("--ff-flash-duration", `${Math.round(randRange(5200, 10800))}ms`);
    firefly.style.setProperty("--ff-flash-delay", `${Math.round(randRange(0, 9000))}ms`);
  });

  const styleEl = document.createElement("style");
  styleEl.id = styleId;
  styleEl.textContent = keyframes.join("\n");
  document.head.appendChild(styleEl);
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
  const consumableRow = document.getElementById("shopItemConsumableRow");
  const consumableInput = document.getElementById("shopItemConsumableInput");
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
    const isMisc = value === "misc";

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

    if (consumableRow && consumableInput) {
      consumableRow.hidden = !isMisc;
      const allowConsumable = isMisc && !!(stackableInput && stackableInput.checked);
      consumableInput.disabled = !allowConsumable;
      if (!allowConsumable) {
        consumableInput.checked = false;
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
  if (stackableInput) {
    stackableInput.addEventListener("change", syncItemTypeFields);
  }
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

    const discountPercent = Math.min(100, Math.max(-100, readInt(discountInput.value, 0)));
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
    if (!target.hasAttribute("data-shop-pick")) {
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
    discountInput.value = String(Math.max(-100, readInt(discountInput.value, 0) - 5));
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
  const form = document.getElementById("learnForm");
  const cartBody = document.getElementById("learnCartBody");
  const budgetEl = document.getElementById("learnBudgetValue");
  const spentEl = document.getElementById("learnSpentValue");
  const remainingEl = document.getElementById("learnRemainingValue");
  const validationHint = document.getElementById("learnValidationHint");
  const applyBtn = document.getElementById("learnApplyBtn");
  const filterInput = document.getElementById("learnFilterInput");
  if (!form || !cartBody || !budgetEl || !spentEl || !remainingEl || !applyBtn) {
    return;
  }

  const budget = Number.parseInt(form.getAttribute("data-learn-budget") || "0", 10) || 0;

  const readInt = (value, fallback = 0) => {
    const parsed = Number.parseInt(String(value ?? "").trim(), 10);
    return Number.isNaN(parsed) ? fallback : parsed;
  };
  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
  const escapeHtml = (value) => String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

  const calcSkillCost = (level) => {
    if (level <= 5) {
      return Math.max(0, level);
    }
    return 5 + ((Math.max(0, level) - 5) * 2);
  };
  const calcLanguageCost = (level, write, mother) => {
    const base = mother ? 0 : Math.max(0, level);
    return base + (write ? 1 : 0);
  };
  const calcAttributeTotalCost = (targetLevel, maxValue) => {
    const level = Math.max(0, targetLevel);
    const threshold = maxValue - 2;
    if (level <= threshold) {
      return level * 10;
    }
    let cost = threshold * 10;
    for (let value = threshold + 1; value <= level; value += 1) {
      cost += 20;
    }
    return cost;
  };

  const getRows = () => Array.from(cartBody.querySelectorAll("[data-learn-cart-item]"));
  const ensureEmptyRow = () => {
    const emptyRow = cartBody.querySelector("[data-learn-empty-row]");
    if (emptyRow) {
      emptyRow.hidden = getRows().length > 0;
    }
  };

  const syncRow = (row) => {
    const kind = row.getAttribute("data-kind") || "";
    const valueInput = row.querySelector("[data-learn-value]");
    const costCell = row.querySelector("[data-learn-cost]");
    const infoEl = row.querySelector("[data-learn-level-info]");
    if (!(valueInput instanceof HTMLInputElement) || !costCell) {
      return { cost: 0, invalidWrite: false };
    }

    let value = readInt(valueInput.value, 0);
    let cost = 0;
    let invalidWrite = false;

    if (kind === "attr") {
      const base = readInt(row.getAttribute("data-base"), 0);
      const min = readInt(row.getAttribute("data-min"), 0);
      const max = readInt(row.getAttribute("data-max"), 0);
      const minAdd = Math.min(0, min - base);
      const maxAdd = Math.max(0, max - base);
      const hidden = row.querySelector("[data-learn-hidden]");
      value = clamp(value, minAdd, maxAdd);
      cost = calcAttributeTotalCost(base + value, max) - calcAttributeTotalCost(base, max);
      if (hidden instanceof HTMLInputElement) {
        hidden.value = String(value);
      }
      if (infoEl) {
        infoEl.textContent = `(${base + value})`;
      }
      valueInput.min = String(minAdd);
      valueInput.max = String(maxAdd);
    } else if (kind === "skill") {
      const base = readInt(row.getAttribute("data-base"), 0);
      const minAdd = -base;
      const maxAdd = Math.max(0, 10 - base);
      const hidden = row.querySelector("[data-learn-hidden]");
      value = clamp(value, minAdd, maxAdd);
      cost = calcSkillCost(base + value) - calcSkillCost(base);
      if (hidden instanceof HTMLInputElement) {
        hidden.value = String(value);
      }
      if (infoEl) {
        infoEl.textContent = `(${base + value})`;
      }
      valueInput.min = String(minAdd);
      valueInput.max = String(maxAdd);
    } else if (kind === "lang") {
      const base = readInt(row.getAttribute("data-base"), 0);
      const minAdd = -base;
      const max = readInt(row.getAttribute("data-max"), 0);
      const maxAdd = Math.max(0, max - base);
      const hidden = row.querySelector("[data-learn-hidden]");
      const writeHidden = row.querySelector("[data-learn-lang-write-hidden]");
      const writeInput = row.querySelector("[data-learn-lang-write]");
      const baseWrite = row.getAttribute("data-write") === "1";
      const mother = row.getAttribute("data-mother") === "1";
      let writeAdd = false;
      value = clamp(value, minAdd, maxAdd);
      if (writeInput instanceof HTMLInputElement) {
        if (baseWrite) {
          writeInput.checked = true;
          writeInput.disabled = true;
          writeAdd = false;
        } else {
          writeAdd = writeInput.checked;
        }
      }
      const write = baseWrite || writeAdd;
      invalidWrite = write && base + value < 1;
      cost = calcLanguageCost(base + value, write, mother) - calcLanguageCost(base, baseWrite, mother);
      if (hidden instanceof HTMLInputElement) {
        hidden.value = String(value);
      }
      if (writeHidden instanceof HTMLInputElement) {
        writeHidden.value = writeAdd ? "1" : "0";
      }
      if (infoEl) {
        infoEl.textContent = `(${base + value})`;
      }
      valueInput.min = String(minAdd);
      valueInput.max = String(maxAdd);
    } else if (kind === "school") {
      const base = readInt(row.getAttribute("data-base"), 0);
      const minAdd = -base;
      const max = readInt(row.getAttribute("data-max"), base);
      const maxAdd = Math.max(0, max - base);
      const hidden = row.querySelector("[data-learn-hidden]");
      value = clamp(value, minAdd, maxAdd);
      cost = value * 8;
      if (hidden instanceof HTMLInputElement) {
        hidden.value = String(value);
      }
      if (infoEl) {
        infoEl.textContent = `(${base + value})`;
      }
      valueInput.min = String(minAdd);
      valueInput.max = String(maxAdd);
    }

    valueInput.value = String(value);
    costCell.textContent = `${cost} EP`;
    return { cost, invalidWrite };
  };

  const refreshTotals = () => {
    let spent = 0;
    let invalidWrite = false;
    getRows().forEach((row) => {
      const result = syncRow(row);
      spent += result.cost;
      invalidWrite = invalidWrite || result.invalidWrite;
    });
    const remaining = budget - spent;
    budgetEl.textContent = `${budget} EP`;
    spentEl.textContent = `${spent} EP`;
    remainingEl.textContent = `${remaining} EP`;
    remainingEl.classList.toggle("is-negative", remaining < 0);
    const overBudget = remaining < 0;
    applyBtn.disabled = false;
    if (validationHint) {
      const messages = [];
      if (overBudget) {
        messages.push("Zu wenig EP für die ausgewählten Lernschritte.");
      }
      if (invalidWrite) {
        messages.push("Schreiben benötigt mindestens Sprachlevel 1.");
      }
      validationHint.hidden = messages.length === 0;
      validationHint.textContent = messages.join(" ");
    }
    return { overBudget, invalidWrite };
  };

  const bindRow = (row) => {
    const valueInput = row.querySelector("[data-learn-value]");
    const removeBtn = row.querySelector("[data-learn-remove]");
    const writeInput = row.querySelector("[data-learn-lang-write]");
    const decBtn = row.querySelector("[data-learn-step-dec]");
    const incBtn = row.querySelector("[data-learn-step-inc]");
    if (valueInput instanceof HTMLInputElement) {
      valueInput.addEventListener("input", refreshTotals);
      valueInput.addEventListener("change", refreshTotals);
    }
    if (valueInput instanceof HTMLInputElement && decBtn instanceof HTMLButtonElement) {
      decBtn.addEventListener("click", () => {
        const current = readInt(valueInput.value, 0);
        const min = readInt(valueInput.min, 0);
        const max = valueInput.max ? readInt(valueInput.max, Number.MAX_SAFE_INTEGER) : Number.MAX_SAFE_INTEGER;
        valueInput.value = String(clamp(current - 1, min, max));
        refreshTotals();
      });
    }
    if (valueInput instanceof HTMLInputElement && incBtn instanceof HTMLButtonElement) {
      incBtn.addEventListener("click", () => {
        const current = readInt(valueInput.value, 0);
        const min = readInt(valueInput.min, 0);
        const max = valueInput.max ? readInt(valueInput.max, Number.MAX_SAFE_INTEGER) : Number.MAX_SAFE_INTEGER;
        valueInput.value = String(clamp(current + 1, min, max));
        refreshTotals();
      });
    }
    if (writeInput instanceof HTMLInputElement) {
      writeInput.addEventListener("change", refreshTotals);
    }
    if (removeBtn instanceof HTMLButtonElement) {
      removeBtn.addEventListener("click", () => {
        row.remove();
        ensureEmptyRow();
        refreshTotals();
      });
    }
  };

  const createRowFromSource = (source) => {
    const kind = source.getAttribute("data-kind") || "";
    const key = source.getAttribute("data-key") || "";
    const name = source.getAttribute("data-name") || key;
    const safeName = escapeHtml(name);
    if (!kind || !key) {
      return null;
    }
    const row = document.createElement("tr");
    row.setAttribute("data-learn-cart-item", "");
    row.setAttribute("data-kind", kind);
    row.setAttribute("data-key", key);

    if (kind === "attr") {
      const shortName = source.getAttribute("data-short") || "";
      const base = readInt(source.getAttribute("data-base"), 0);
      const min = readInt(source.getAttribute("data-min"), 0);
      const max = readInt(source.getAttribute("data-max"), 0);
      const minAdd = Math.min(0, min - base);
      const maxAdd = Math.max(0, max - base);
      if (maxAdd < 1 && minAdd === 0) {
        return null;
      }
      row.setAttribute("data-base", String(base));
      row.setAttribute("data-min", String(min));
      row.setAttribute("data-max", String(max));
      const startAdd = maxAdd > 0 ? 1 : 0;
      row.innerHTML = `
        <td><span>${safeName}</span> <span data-learn-level-info>(${base + startAdd})</span><input type="hidden" name="learn_attr_add_${shortName}" value="${startAdd}" data-learn-hidden></td>
        <td>
          <div class="shop_qty_stepper">
            <button type="button" class="shop_step_btn" data-learn-step-dec aria-label="Wert verringern">-</button>
            <input class="shop_cart_qty_input" type="number" min="${minAdd}" max="${maxAdd}" value="${startAdd}" data-learn-value>
            <button type="button" class="shop_step_btn" data-learn-step-inc aria-label="Wert erhöhen">+</button>
          </div>
        </td>
        <td data-learn-cost>0 EP</td>
        <td><button type="button" class="shop_cart_remove_btn" data-learn-remove aria-label="Eintrag entfernen">×</button></td>
      `;
      return row;
    }

    if (kind === "skill") {
      const slug = source.getAttribute("data-slug") || "";
      const base = readInt(source.getAttribute("data-base"), 0);
      const minAdd = -base;
      const maxAdd = Math.max(0, 10 - base);
      if (maxAdd < 1 && minAdd === 0) {
        return null;
      }
      row.setAttribute("data-base", String(base));
      const startAdd = maxAdd > 0 ? 1 : 0;
      row.innerHTML = `
        <td><span>${safeName}</span> <span data-learn-level-info>(${base + startAdd})</span><input type="hidden" name="learn_skill_add_${slug}" value="${startAdd}" data-learn-hidden></td>
        <td>
          <div class="shop_qty_stepper">
            <button type="button" class="shop_step_btn" data-learn-step-dec aria-label="Wert verringern">-</button>
            <input class="shop_cart_qty_input" type="number" min="${minAdd}" max="${maxAdd}" value="${startAdd}" data-learn-value>
            <button type="button" class="shop_step_btn" data-learn-step-inc aria-label="Wert erhöhen">+</button>
          </div>
        </td>
        <td data-learn-cost>0 EP</td>
        <td><button type="button" class="shop_cart_remove_btn" data-learn-remove aria-label="Eintrag entfernen">×</button></td>
      `;
      return row;
    }

    if (kind === "lang") {
      const slug = source.getAttribute("data-slug") || "";
      const base = readInt(source.getAttribute("data-base"), 0);
      const minAdd = -base;
      const max = readInt(source.getAttribute("data-max"), 0);
      const maxAdd = Math.max(0, max - base);
      const baseWrite = source.getAttribute("data-write") === "1";
      const mother = source.getAttribute("data-mother") === "1";
      if (maxAdd < 1 && minAdd === 0 && baseWrite) {
        return null;
      }
      const startAdd = maxAdd > 0 ? 1 : 0;
      row.setAttribute("data-base", String(base));
      row.setAttribute("data-max", String(max));
      row.setAttribute("data-write", baseWrite ? "1" : "0");
      row.setAttribute("data-mother", mother ? "1" : "0");
      row.innerHTML = `
        <td>
          <span>${safeName}</span>
          <span data-learn-level-info>(${base + startAdd})</span>
          <input type="hidden" name="learn_lang_add_${slug}" value="${startAdd}" data-learn-hidden>
          <input type="hidden" name="learn_lang_write_${slug}" value="0" data-learn-lang-write-hidden>
        </td>
        <td>
          <div class="learn_lang_value_wrap">
            <label class="learn_lang_write"><input type="checkbox" data-learn-lang-write ${baseWrite ? "checked disabled" : ""}> Schreiben</label>
            <div class="shop_qty_stepper">
              <button type="button" class="shop_step_btn" data-learn-step-dec aria-label="Wert verringern">-</button>
              <input class="shop_cart_qty_input" type="number" min="${minAdd}" max="${maxAdd}" value="${startAdd}" data-learn-value>
              <button type="button" class="shop_step_btn" data-learn-step-inc aria-label="Wert erhöhen">+</button>
            </div>
          </div>
        </td>
        <td data-learn-cost>0 EP</td>
        <td><button type="button" class="shop_cart_remove_btn" data-learn-remove aria-label="Eintrag entfernen">×</button></td>
      `;
      return row;
    }

    if (kind === "school") {
      const schoolId = source.getAttribute("data-id") || "";
      const base = readInt(source.getAttribute("data-base"), 0);
      const minAdd = -base;
      const max = readInt(source.getAttribute("data-max"), base);
      const maxAdd = Math.max(0, max - base);
      if (maxAdd < 1 && minAdd === 0) {
        return null;
      }
      row.setAttribute("data-base", String(base));
      row.setAttribute("data-max", String(max));
      const startAdd = maxAdd > 0 ? 1 : 0;
      row.innerHTML = `
        <td><span>${safeName}</span> <span data-learn-level-info>(${base + startAdd})</span><input type="hidden" name="learn_school_add_${schoolId}" value="${startAdd}" data-learn-hidden></td>
        <td>
          <div class="shop_qty_stepper">
            <button type="button" class="shop_step_btn" data-learn-step-dec aria-label="Wert verringern">-</button>
            <input class="shop_cart_qty_input" type="number" min="${minAdd}" max="${maxAdd}" value="${startAdd}" data-learn-value>
            <button type="button" class="shop_step_btn" data-learn-step-inc aria-label="Wert erhöhen">+</button>
          </div>
        </td>
        <td data-learn-cost>0 EP</td>
        <td><button type="button" class="shop_cart_remove_btn" data-learn-remove aria-label="Eintrag entfernen">×</button></td>
      `;
      return row;
    }
    return null;
  };

  const addFromSource = (source) => {
    const key = source.getAttribute("data-key") || "";
    if (!key) {
      return;
    }
    const existing = cartBody.querySelector(`[data-learn-cart-item][data-key="${key}"]`);
    if (existing) {
      const input = existing.querySelector("[data-learn-value]");
      if (input instanceof HTMLInputElement) {
        input.focus();
      }
      return;
    }
    const row = createRowFromSource(source);
    if (!row) {
      return;
    }
    cartBody.appendChild(row);
    bindRow(row);
    ensureEmptyRow();
    refreshTotals();
  };

  Array.from(document.querySelectorAll("[data-learn-source]")).forEach((source) => {
    source.addEventListener("click", () => {
      addFromSource(source);
    });
    source.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        addFromSource(source);
      }
    });
  });

  if (filterInput instanceof HTMLInputElement) {
    filterInput.addEventListener("input", () => {
      const needle = String(filterInput.value || "").trim().toLowerCase();
      const rows = Array.from(document.querySelectorAll("[data-learn-source]"));
      rows.forEach((row) => {
        const haystack = String(row.getAttribute("data-learn-search") || "").toLowerCase();
        row.hidden = needle.length > 0 && !haystack.includes(needle);
      });
      Array.from(document.querySelectorAll("[data-learn-group]")).forEach((group) => {
        const visible = Array.from(group.querySelectorAll("tr")).some((row) => !row.hidden);
        group.hidden = !visible;
      });
    });
  }

  form.addEventListener("submit", (event) => {
    const state = refreshTotals();
    if (state.invalidWrite) {
      event.preventDefault();
      return;
    }
    if (state.overBudget) {
      event.preventDefault();
      remainingEl.classList.remove("is-fail-flash");
      void remainingEl.offsetWidth;
      remainingEl.classList.add("is-fail-flash");
    }
  });

  ensureEmptyRow();
  refreshTotals();
});

document.addEventListener("DOMContentLoaded", () => {
  const dbAnchors = document.querySelectorAll(".db_tooltip_anchor[data-db-tooltip]");
  dbAnchors.forEach((anchor) => {
    const text = anchor.getAttribute("data-db-tooltip") || "";
    if (!text.trim()) {
      return;
    }
    anchor.classList.add("tooltip_target");
    if (!anchor.getAttribute("data-tooltip")) {
      anchor.setAttribute("data-tooltip", text);
    }
    if (!anchor.getAttribute("data-tooltip-side")) {
      anchor.setAttribute("data-tooltip-side", "right");
    }
    // Disable legacy CSS-only tooltip so only floating tooltip is shown.
    anchor.removeAttribute("data-db-tooltip");
  });

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

  const escapeHtml = (value) => String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

  const parseTableRow = (line) => {
    const trimmed = String(line || "").trim();
    if (!trimmed.includes("|")) {
      return [];
    }
    const normalized = trimmed
      .replace(/^\|/, "")
      .replace(/\|$/, "");
    return normalized.split("|").map((part) => part.trim());
  };

  const isTableDividerRow = (row) =>
    row.length > 0 && row.every((cell) => /^:?-{2,}:?$/.test(cell));

  const renderTooltipMarkup = (rawText) => {
    const text = String(rawText || "").trim();
    if (!text) {
      return "";
    }
    const lines = text.split("\n");
    const chunks = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];
      if (!line.trim()) {
        i += 1;
        continue;
      }

      const header = parseTableRow(line);
      const divider = i + 1 < lines.length ? parseTableRow(lines[i + 1]) : [];
      if (
        header.length > 0 &&
        header.length === divider.length &&
        isTableDividerRow(divider)
      ) {
        let j = i + 2;
        const bodyRows = [];
        while (j < lines.length) {
          const row = parseTableRow(lines[j]);
          if (!row.length || row.length !== header.length) {
            break;
          }
          bodyRows.push(row);
          j += 1;
        }

        let tableHtml = "<table><thead><tr>";
        header.forEach((cell) => {
          tableHtml += `<th>${escapeHtml(cell)}</th>`;
        });
        tableHtml += "</tr></thead>";
        if (bodyRows.length) {
          tableHtml += "<tbody>";
          bodyRows.forEach((row) => {
            tableHtml += "<tr>";
            row.forEach((cell) => {
              tableHtml += `<td>${escapeHtml(cell)}</td>`;
            });
            tableHtml += "</tr>";
          });
          tableHtml += "</tbody>";
        }
        tableHtml += "</table>";
        chunks.push(tableHtml);
        i = j;
        continue;
      }

      const paragraphLines = [];
      let j = i;
      while (j < lines.length && lines[j].trim()) {
        paragraphLines.push(escapeHtml(lines[j]));
        j += 1;
      }
      chunks.push(`<p>${paragraphLines.join("<br>")}</p>`);
      i = j;
    }

    return chunks.join("");
  };

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
      const text = (target.getAttribute("data-tooltip") || "")
        .replace(/\r\n/g, "\n")
        .replace(/\\n/g, "\n");
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
        tooltip.innerHTML = renderTooltipMarkup(text);
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
  const menus = Array.from(document.querySelectorAll(".inv_menu"));
  if (!menus.length) {
    return;
  }

  const closeMenu = (menu) => {
    const trigger = menu.querySelector(".inv_menu_trigger");
    const panel = menu.querySelector(".inv_menu_panel");
    if (!(trigger instanceof HTMLButtonElement) || !(panel instanceof HTMLElement)) {
      return;
    }
    panel.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
  };

  const openMenu = (menu) => {
    menus.forEach((other) => {
      if (other !== menu) {
        closeMenu(other);
      }
    });
    const trigger = menu.querySelector(".inv_menu_trigger");
    const panel = menu.querySelector(".inv_menu_panel");
    if (!(trigger instanceof HTMLButtonElement) || !(panel instanceof HTMLElement)) {
      return;
    }
    panel.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
  };

  menus.forEach((menu) => {
    const trigger = menu.querySelector(".inv_menu_trigger");
    const panel = menu.querySelector(".inv_menu_panel");
    if (!(trigger instanceof HTMLButtonElement) || !(panel instanceof HTMLElement)) {
      return;
    }

    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (panel.hidden) {
        openMenu(menu);
      } else {
        closeMenu(menu);
      }
    });

    panel.addEventListener("click", (event) => {
      event.stopPropagation();
    });
  });

  document.addEventListener("click", () => {
    menus.forEach(closeMenu);
  });

  const removeButtons = Array.from(document.querySelectorAll("[data-require-shift-delete]"));
  removeButtons.forEach((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    button.addEventListener("click", (event) => {
      if (event.shiftKey) {
        return;
      }
      event.preventDefault();
      window.alert("Zum Entfernen bitte Shift gedrueckt halten und erneut klicken.");
    });
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
