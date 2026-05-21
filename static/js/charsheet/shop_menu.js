import { escapeHtml, getCsrfToken, readInt, saveJsonStorage } from "./utils.js";

export function initShopMenu() {
  const filterInput = document.getElementById("shopFilterInput");
  const shopList = document.querySelector(".shop_list_scroll");
  const cartWrapper = document.querySelector(".shop_cart_wrapper");
  const cartBody = document.getElementById("shopCartBody");
  const subtotalEl = document.getElementById("shopCartSubtotal");
  const finalEl = document.getElementById("shopCartFinal");
  const finalLabelEl = document.getElementById("shopCartFinalLabel");
  const balanceEl = document.getElementById("shopCartBalance");
  const discountRow = document.querySelector(".shop_cart_discount_row");
  const discountInput = document.getElementById("shopDiscountInput");
  const discountDecBtn = document.getElementById("shopDiscountDec");
  const discountIncBtn = document.getElementById("shopDiscountInc");
  const actionBtn = document.getElementById("shopActionBtn");
  const addItemBtn = document.getElementById("shopAddItemBtn");
  const buyModeBtn = document.getElementById("shop-tab-buy");
  const sellModeBtn = document.getElementById("shop-tab-sell");
  const listTitle = document.getElementById("shopListTitle");
  const cartTitle = document.getElementById("shopCartTitle");
  const modePanels = Array.from(document.querySelectorAll("[data-shop-mode-panel]"));
  if (
    !filterInput
    || !shopList
    || !cartWrapper
    || !cartBody
    || !subtotalEl
    || !finalEl
    || !finalLabelEl
    || !balanceEl
    || !discountInput
    || !discountDecBtn
    || !discountIncBtn
    || !actionBtn
    || !buyModeBtn
    || !sellModeBtn
    || !listTitle
    || !cartTitle
    || !modePanels.length
  ) {
    return;
  }

  const QUALITY_ORDER = ["wretched", "very_poor", "poor", "common", "fine", "excellent", "legendary"];
  const QUALITY_LABELS = {
    wretched: "Extrem schlecht",
    very_poor: "Sehr schlecht",
    poor: "Schlecht",
    common: "Normal",
    fine: "Gut",
    excellent: "Exzellent",
    legendary: "Legendaer",
  };
  const QUALITY_COLORS = {
    wretched: "#DD2828",
    very_poor: "#7A7A7A",
    poor: "#000000",
    common: "#33CC33",
    fine: "#0000FF",
    excellent: "#CC00CC",
    legendary: "#FF9933",
  };
  const QUALITY_PRICE_MODS = {
    wretched: 0.25,
    very_poor: 0.5,
    poor: 0.75,
    common: 1,
    fine: 2,
    excellent: 5,
    legendary: 20,
  };

  let baseBalance = readInt(cartWrapper.getAttribute("data-shop-balance") || "0", 0);
  const buyUrl = String(cartWrapper.getAttribute("data-buy-url") || "");
  const sellUrl = String(cartWrapper.getAttribute("data-sell-url") || "");
  const tradeUrl = String(cartWrapper.getAttribute("data-trade-url") || "");
  const cart = new Map();
  let cartCounter = 0;
  let currentMode = "buy";

  const readOptionalInt = (value) => {
    const parsed = Number.parseInt(String(value ?? "").trim(), 10);
    return Number.isNaN(parsed) ? null : parsed;
  };
  const fmtNumber = (value) => Number(value || 0).toLocaleString("de-DE");
  const fmtKs = (value) => `${fmtNumber(value)} KS`;
  const normalizeQuality = (quality) => {
    const normalized = String(quality || "common");
    return QUALITY_ORDER.includes(normalized) ? normalized : "common";
  };
  const shiftQuality = (quality, delta) => {
    const index = QUALITY_ORDER.indexOf(normalizeQuality(quality));
    const nextIndex = Math.min(Math.max(index + delta, 0), QUALITY_ORDER.length - 1);
    return QUALITY_ORDER[nextIndex];
  };
  const isQualityAdjustableType = (itemType) => itemType === "weapon" || itemType === "armor" || itemType === "shield";
  const qualityBadge = (quality) => {
    const normalized = normalizeQuality(quality);
    const label = QUALITY_LABELS[normalized] || QUALITY_LABELS.common;
    const color = QUALITY_COLORS[normalized] || QUALITY_COLORS.common;
    return `<span class="shop_quality_value shop_quality_dot" style="--quality-color: ${color};" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}">&#11044;</span>`;
  };
  const createEntryKey = () => {
    cartCounter += 1;
    return `cart-${cartCounter}`;
  };
  const syncModeFromTabs = () => {
    currentMode = sellModeBtn.getAttribute("aria-selected") === "true" ? "sell" : "buy";
  };
  const currentPanel = () => modePanels.find((panel) => panel.getAttribute("data-shop-mode-panel") === currentMode) || null;
  const currentGroups = () => Array.from(currentPanel()?.querySelectorAll("[data-shop-group]") || []);
  const cartHasBuyEntries = () => Array.from(cart.values()).some((entry) => entry.mode === "buy");
  const cartHasSellEntries = () => Array.from(cart.values()).some((entry) => entry.mode === "sell");
  const syncModeUi = () => {
    const isSellMode = currentMode === "sell";
    buyModeBtn.classList.toggle("is-active", !isSellMode);
    buyModeBtn.setAttribute("aria-pressed", isSellMode ? "false" : "true");
    sellModeBtn.classList.toggle("is-active", isSellMode);
    sellModeBtn.setAttribute("aria-pressed", isSellMode ? "true" : "false");
    modePanels.forEach((panel) => {
      panel.hidden = panel.getAttribute("data-shop-mode-panel") !== currentMode;
    });
    if (addItemBtn instanceof HTMLElement) {
      addItemBtn.hidden = isSellMode;
    }
    if (discountRow instanceof HTMLElement) {
      discountRow.hidden = !cartHasBuyEntries();
    }
    listTitle.textContent = isSellMode ? "Verkaufbare Gegenstaende" : "Kaufbare Gegenstaende";
    cartTitle.textContent = "Handelskorb";
    finalLabelEl.textContent = "Saldo";
    actionBtn.textContent = "Handeln";
  };
  const unitPriceForEntry = (entry) => {
    if (entry.mode === "sell") {
      return Math.max(0, readInt(entry.unitPrice, 0));
    }
    const mod = QUALITY_PRICE_MODS[normalizeQuality(entry.quality)] ?? 1;
    return Math.max(0, Math.round(entry.basePrice * mod));
  };
  const parseRowPayload = (row) => {
    const mode = String(row.getAttribute("data-shop-mode") || "buy");
    if (mode === "sell") {
      return {
        mode,
        characterItemId: row.getAttribute("data-character-item-id") || "",
        name: row.getAttribute("data-shop-name") || "",
        itemType: row.getAttribute("data-shop-item-type") || "misc",
        stackable: row.getAttribute("data-shop-stackable") === "1",
        availableQty: readInt(row.getAttribute("data-shop-available-qty"), 1),
        quality: normalizeQuality(row.getAttribute("data-shop-quality") || "common"),
        unitPrice: readInt(row.getAttribute("data-shop-unit-price"), 0),
      };
    }
    return {
      mode,
      id: row.getAttribute("data-shop-id") || "",
      name: row.getAttribute("data-shop-name") || "",
      itemType: row.getAttribute("data-shop-item-type") || "misc",
      stackable: row.getAttribute("data-shop-stackable") === "1",
      basePrice: readInt(row.getAttribute("data-shop-base-price"), 0),
      quality: normalizeQuality(row.getAttribute("data-shop-quality") || "common"),
      stats: {
        damageDiceAmount: readOptionalInt(row.getAttribute("data-shop-damage-dice-amount")),
        damageDiceFaces: readOptionalInt(row.getAttribute("data-shop-damage-dice-faces")),
        damageFlatBonus: readOptionalInt(row.getAttribute("data-shop-damage-flat-bonus")),
        h2DiceAmount: readOptionalInt(row.getAttribute("data-shop-h2-dice-amount")),
        h2DiceFaces: readOptionalInt(row.getAttribute("data-shop-h2-dice-faces")),
        h2FlatBonus: readOptionalInt(row.getAttribute("data-shop-h2-flat-bonus")),
        armorRs: readOptionalInt(row.getAttribute("data-shop-armor-rs")),
        armorBel: readOptionalInt(row.getAttribute("data-shop-armor-bel")),
        shieldRs: readOptionalInt(row.getAttribute("data-shop-shield-rs")),
        shieldBel: readOptionalInt(row.getAttribute("data-shop-shield-bel")),
      },
    };
  };
  const applyFilter = () => {
    const query = String(filterInput.value || "").trim().toLowerCase();
    currentGroups().forEach((group) => {
      const rows = group.querySelectorAll("[data-shop-item]");
      let hasMatch = false;
      rows.forEach((row) => {
        const haystack = String(row.getAttribute("data-shop-search") || "").toLowerCase();
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
  const render = () => {
    let subtotal = 0;
    const rows = [];
    cart.forEach((entry, cartKey) => {
      const unitPrice = unitPriceForEntry(entry);
      const lineTotal = unitPrice * entry.qty;
      subtotal += lineTotal;
      const qualityIndex = QUALITY_ORDER.indexOf(normalizeQuality(entry.quality));
      const qualityAdjustable = entry.mode === "buy" && isQualityAdjustableType(entry.itemType);
      const disableDown = !qualityAdjustable || qualityIndex <= 0 ? "disabled" : "";
      const disableUp = !qualityAdjustable || qualityIndex >= QUALITY_ORDER.length - 1 ? "disabled" : "";
      const qualityControls = qualityAdjustable
        ? `<div class="shop_quality_stepper">
            <button type="button" class="shop_step_btn" data-cart-quality-dec aria-label="Qualitaet senken" ${disableDown}>&#9660;</button>
            ${qualityBadge(entry.quality)}
            <button type="button" class="shop_step_btn" data-cart-quality-inc aria-label="Qualitaet erhoehen" ${disableUp}>&#9650;</button>
          </div>`
        : entry.mode === "sell"
          ? qualityBadge(entry.quality)
          : "";
      const qtyMax = entry.mode === "sell" ? Math.max(1, readInt(entry.availableQty, 1)) : null;
      const qtyControls = entry.stackable
        ? `<div class="shop_qty_stepper">
            <button type="button" class="shop_step_btn" data-cart-qty-dec aria-label="Menge verringern">-</button>
            <input type="text" class="shop_cart_qty_input" value="${entry.qty}" data-cart-qty inputmode="numeric" aria-label="Menge"${qtyMax ? ` max="${qtyMax}"` : ""}>
            <button type="button" class="shop_step_btn" data-cart-qty-inc aria-label="Menge erhoehen">+</button>
          </div>`
        : `<span class="shop_cart_qty_fixed">1</span>`;
      rows.push(`
        <tr data-cart-key="${cartKey}">
          <td>${escapeHtml(entry.name)}</td>
          <td>${qualityControls}</td>
          <td>${qtyControls}</td>
          <td>${fmtKs(unitPrice)}</td>
          <td>${fmtKs(lineTotal)}</td>
          <td><button type="button" class="shop_cart_remove_btn" data-cart-remove>x</button></td>
        </tr>
      `);
    });

    cartBody.innerHTML = rows.length
      ? rows.join("")
      : `<tr class="shop_cart_empty_row"><td colspan="6">${currentMode === "sell" ? "Noch keine Gegenstaende zum Verkauf ausgewaehlt." : "Noch keine Gegenstaende ausgewaehlt."}</td></tr>`;

    const discountPercent = cartHasBuyEntries()
      ? Math.min(100, Math.max(-100, readInt(discountInput.value, 0)))
      : 0;
    if (cartHasBuyEntries() && readInt(discountInput.value, 0) !== discountPercent) {
      discountInput.value = String(discountPercent);
    }
    const buySubtotal = Array.from(cart.values())
      .filter((entry) => entry.mode === "buy")
      .reduce((sum, entry) => sum + (unitPriceForEntry(entry) * entry.qty), 0);
    const sellSubtotal = Array.from(cart.values())
      .filter((entry) => entry.mode === "sell")
      .reduce((sum, entry) => sum + (unitPriceForEntry(entry) * entry.qty), 0);
    const discountedBuyTotal = Math.max(0, Math.round(buySubtotal * (100 - discountPercent) / 100));
    const finalValue = discountedBuyTotal - sellSubtotal;
    const simulatedBalance = baseBalance - finalValue;

    subtotalEl.textContent = fmtKs(subtotal);
    finalEl.textContent = fmtKs(finalValue);
    balanceEl.textContent = fmtKs(simulatedBalance);
    balanceEl.classList.toggle("is-negative", simulatedBalance < 0);
  };
  const switchMode = (nextMode) => {
    if (nextMode !== "buy" && nextMode !== "sell") {
      return;
    }
    currentMode = nextMode;
    syncModeUi();
    applyFilter();
    render();
  };
  const closeShopWindow = () => {
    document.getElementById("shopWindow")?.classList.remove("is-open");
    document.getElementById("shopWindow")?.setAttribute("aria-hidden", "true");
    saveJsonStorage("charsheet.shopWindow", {
      isOpen: false,
      left: null,
      top: null,
    });
  };

  filterInput.addEventListener("input", applyFilter);
  [buyModeBtn, sellModeBtn].forEach((tabBtn) => {
    tabBtn.addEventListener("click", () => {
      syncModeFromTabs();
      switchMode(currentMode);
    });
    tabBtn.addEventListener("keydown", (event) => {
      if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) {
        return;
      }
      window.requestAnimationFrame(() => {
        syncModeFromTabs();
        switchMode(currentMode);
      });
    });
  });

  shopList.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement) || !target.hasAttribute("data-shop-pick")) {
      return;
    }
    const row = target.closest("[data-shop-item]");
    if (!(row instanceof HTMLElement)) {
      return;
    }

    const payload = parseRowPayload(row);
    if (payload.mode === "sell") {
      if (!payload.characterItemId || !payload.name || payload.unitPrice < 0) {
        return;
      }
      for (const entry of cart.values()) {
        if (entry.characterItemId === payload.characterItemId) {
          if (entry.stackable) {
            entry.qty = Math.min(entry.availableQty, entry.qty + 1);
          }
          render();
          return;
        }
      }
      cart.set(createEntryKey(), { ...payload, qty: 1 });
      render();
      return;
    }

    if (!payload.id || !payload.name || payload.basePrice < 0) {
      return;
    }
    let merged = false;
    if (payload.stackable) {
      for (const entry of cart.values()) {
        if (entry.id === payload.id && normalizeQuality(entry.quality) === normalizeQuality(payload.quality)) {
          entry.qty += 1;
          merged = true;
          break;
        }
      }
    }
    if (!merged) {
      cart.set(createEntryKey(), { ...payload, qty: 1 });
    }
    render();
  });

  cartBody.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const row = target.closest("[data-cart-key]");
    if (!(row instanceof HTMLElement)) {
      return;
    }
    const cartKey = row.getAttribute("data-cart-key") || "";
    const entry = cart.get(cartKey);
    if (!entry) {
      return;
    }

    if (target.hasAttribute("data-cart-qty-dec") || target.hasAttribute("data-cart-qty-inc")) {
      if (!entry.stackable) {
        return;
      }
      const delta = target.hasAttribute("data-cart-qty-inc") ? 1 : -1;
      const maxQty = entry.mode === "sell" ? Math.max(1, readInt(entry.availableQty, 1)) : Number.MAX_SAFE_INTEGER;
      entry.qty = Math.min(maxQty, Math.max(1, entry.qty + delta));
      render();
      return;
    }

    if (target.hasAttribute("data-cart-quality-dec") || target.hasAttribute("data-cart-quality-inc")) {
      if (entry.mode !== "buy" || !isQualityAdjustableType(entry.itemType)) {
        return;
      }
      const delta = target.hasAttribute("data-cart-quality-inc") ? 1 : -1;
      const nextQuality = shiftQuality(entry.quality, delta);
      if (nextQuality === entry.quality) {
        return;
      }
      entry.quality = nextQuality;
      if (entry.stackable) {
        for (const [otherKey, otherEntry] of cart.entries()) {
          if (otherKey === cartKey) {
            continue;
          }
          if (otherEntry.id === entry.id && normalizeQuality(otherEntry.quality) === normalizeQuality(entry.quality)) {
            otherEntry.qty += entry.qty;
            cart.delete(cartKey);
            break;
          }
        }
      }
      render();
      return;
    }

    if (target.hasAttribute("data-cart-remove")) {
      cart.delete(cartKey);
      render();
    }
  });

  cartBody.addEventListener("input", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || !target.hasAttribute("data-cart-qty")) {
      return;
    }
    const row = target.closest("[data-cart-key]");
    if (!(row instanceof HTMLElement)) {
      return;
    }
    const cartKey = row.getAttribute("data-cart-key") || "";
    const entry = cart.get(cartKey);
    if (!entry || !entry.stackable) {
      return;
    }
    const maxQty = entry.mode === "sell" ? Math.max(1, readInt(entry.availableQty, 1)) : Number.MAX_SAFE_INTEGER;
    entry.qty = Math.min(maxQty, Math.max(1, readInt(target.value, 1)));
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

  actionBtn.addEventListener("click", async () => {
    const url = tradeUrl || (cartHasSellEntries() && !cartHasBuyEntries() ? sellUrl : buyUrl);
    if (!url || !cart.size) {
      return;
    }

    const payload = {
      buy_items: Array.from(cart.values())
        .filter((entry) => entry.mode === "buy")
        .map((entry) => ({
          id: entry.id,
          qty: entry.stackable ? entry.qty : 1,
          quality: normalizeQuality(entry.quality),
        })),
      sell_items: Array.from(cart.values())
        .filter((entry) => entry.mode === "sell")
        .map((entry) => ({
          character_item_id: entry.characterItemId,
          qty: entry.stackable ? entry.qty : 1,
        })),
      discount: readInt(discountInput.value, 0),
    };

    try {
      const response = await fetch(url, {
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
      if (data?.ok) {
        closeShopWindow();
        window.location.reload();
        return;
      }
      if (data?.error === "insufficient_funds") {
        balanceEl.classList.remove("is-fail-flash");
        void balanceEl.offsetWidth;
        balanceEl.classList.add("is-fail-flash");
      }
    } catch (_error) {
      // no-op
    }
  });

  syncModeFromTabs();
  syncModeUi();
  applyFilter();
  render();
}
