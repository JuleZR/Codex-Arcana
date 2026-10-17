import { escapeHtml, getCsrfToken, initPersistentDetails, readInt } from "./utils.js?v=20261013-market-details";
import { applySheetPartials } from "./partial_updates.js";
import { animateMoneyBalance } from "./money_animation.js?v=20261013-sidebar-money";

export function initShopMenu() {
  const shopWindow = document.getElementById("shopWindow");
  if (shopWindow instanceof HTMLElement && shopWindow.dataset.shopMenuBound === "1") {
    return;
  }
  const filterInput = document.getElementById("shopFilterInput");
  const shopList = document.querySelector(".market_catalog");
  const cartWrapper = document.querySelector(".market_cart");
  const cartBody = document.getElementById("shopCartBody");
  const subtotalEl = document.getElementById("shopCartSubtotal");
  const finalEl = document.getElementById("shopCartFinal");
  const finalLabelEl = document.getElementById("shopCartFinalLabel");
  const balanceEl = document.getElementById("shopCartBalance");
  const discountInput = document.getElementById("shopDiscountInput");
  const discountDecBtn = document.getElementById("shopDiscountDec");
  const discountIncBtn = document.getElementById("shopDiscountInc");
  const resaleInput = document.getElementById("shopResaleInput");
  const resaleDecBtn = document.getElementById("shopResaleDec");
  const resaleIncBtn = document.getElementById("shopResaleInc");
  const actionBtn = document.getElementById("shopActionBtn");
  const addItemBtn = document.getElementById("shopAddItemBtn");
  const buyModeBtn = document.getElementById("shop-tab-buy");
  const sellModeBtn = document.getElementById("shop-tab-sell");
  const listTitle = document.getElementById("shopListTitle");
  const cartTitle = document.getElementById("shopCartTitle");
  let modePanels = Array.from(document.querySelectorAll("[data-shop-mode-panel]"));
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
    || !resaleInput
    || !resaleDecBtn
    || !resaleIncBtn
    || !actionBtn
    || !buyModeBtn
    || !sellModeBtn
    || !listTitle
    || !cartTitle
    || !modePanels.length
  ) {
    return;
  }
  if (shopWindow instanceof HTMLElement) {
    shopWindow.dataset.shopMenuBound = "1";
  }

  const readQualityChoices = () => {
    const script = document.getElementById("shopQualityChoices");
    if (!script) {
      return [];
    }
    try {
      const parsed = JSON.parse(script.textContent || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch (_error) {
      return [];
    }
  };
  const qualityChoices = readQualityChoices();
  const QUALITY_ORDER = qualityChoices.map((quality) => String(quality.value || ""));
  const defaultQuality = qualityChoices.find((quality) => quality.is_default)?.value || QUALITY_ORDER[0] || "";
  const QUALITY_LABELS = Object.fromEntries(qualityChoices.map((quality) => [String(quality.value), String(quality.label)]));
  const QUALITY_COLORS = Object.fromEntries(qualityChoices.map((quality) => [String(quality.value), String(quality.color)]));

  let baseBalance = readInt(cartWrapper.getAttribute("data-shop-balance") || "0", 0);
  const buyUrl = String(cartWrapper.getAttribute("data-buy-url") || "");
  const sellUrl = String(cartWrapper.getAttribute("data-sell-url") || "");
  const tradeUrl = String(cartWrapper.getAttribute("data-trade-url") || "");
  const cart = new Map();
  let cartCounter = 0;
  let currentMode = "buy";
  let transactionPending = false;
  let lastResalePercent = null;
  const headerBalance = document.getElementById("shopHeaderBalance");
  const statusEl = document.getElementById("shopStatus");
  const groupDisclosureState = initPersistentDetails(
    "#shopWindow [data-shop-group]",
    "codexArcana.shop.categoryDisclosure.v1",
  );
  let sellGroupDisclosureState = groupDisclosureState;

  const readOptionalInt = (value) => {
    const parsed = Number.parseInt(String(value ?? "").trim(), 10);
    return Number.isNaN(parsed) ? null : parsed;
  };
  const fmtNumber = (value) => Number(value || 0).toLocaleString("de-DE");
  const fmtKs = (value) => `${fmtNumber(value)} KS`;
  const normalizeQuality = (quality) => {
    const normalized = String(quality || defaultQuality);
    return QUALITY_ORDER.includes(normalized) ? normalized : defaultQuality;
  };
  const shiftQuality = (quality, delta) => {
    const index = QUALITY_ORDER.indexOf(normalizeQuality(quality));
    const nextIndex = Math.min(Math.max(index + delta, 0), QUALITY_ORDER.length - 1);
    return QUALITY_ORDER[nextIndex];
  };
  const qualityBadge = (quality) => {
    const normalized = normalizeQuality(quality);
    const label = QUALITY_LABELS[normalized] || "Qualität unbekannt";
    const rawColor = QUALITY_COLORS[normalized] || "";
    const color = /^#[0-9a-f]{6}$/i.test(rawColor) ? rawColor : "#777777";
    return `<span class="market_quality_dot" style="--quality-color: ${color};" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}">&#11044;</span>`;
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
  const syncActionSeal = () => {
    actionBtn.innerHTML = '<span aria-hidden="true">✦</span><span>Handel abschließen</span><span aria-hidden="true">→</span>';
  };
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
    listTitle.textContent = isSellMode ? "Besitzwaren" : "Handelswaren";
    cartTitle.textContent = "Deine Auswahl";
    finalLabelEl.textContent = "Handelssaldo";
    syncActionSeal();
  };
  syncActionSeal();
  const readResalePercent = () => Math.min(100, Math.max(0, readInt(resaleInput.value, 50)));
  const unitPriceForEntry = (entry) => {
    if (entry.mode === "sell") {
      return Math.max(0, Math.round(readInt(entry.unitPrice, 0) * readResalePercent() / 100));
    }
    return Math.max(0, readInt(entry.qualityPrices[normalizeQuality(entry.quality)]?.price, entry.defaultPrice));
  };
  const parseRowPayload = (row) => {
    const mode = String(row.getAttribute("data-shop-mode") || "buy");
    if (mode === "sell") {
      return {
        mode,
        characterItemId: row.getAttribute("data-character-item-id") || "",
        name: row.getAttribute("data-shop-name") || "",
        itemType: row.getAttribute("data-shop-item-type") || "misc",
        showsQuality: row.getAttribute("data-shop-shows-quality") === "1",
        stackable: row.getAttribute("data-shop-stackable") === "1",
        availableQty: readInt(row.getAttribute("data-shop-available-qty"), 1),
        quality: normalizeQuality(row.getAttribute("data-shop-quality")),
        unitPrice: readInt(row.getAttribute("data-shop-unit-price"), 0),
      };
    }
    return {
      mode,
      id: row.getAttribute("data-shop-id") || "",
      name: row.getAttribute("data-shop-name") || "",
      itemType: row.getAttribute("data-shop-item-type") || "misc",
      showsQuality: row.getAttribute("data-shop-shows-quality") === "1",
      stackable: row.getAttribute("data-shop-stackable") === "1",
      basePrice: readInt(row.getAttribute("data-shop-base-price"), 0),
      defaultPrice: readInt(row.getAttribute("data-shop-default-price"), 0),
      qualityPrices: JSON.parse(row.querySelector('script[type="application/json"]')?.textContent || "{}"),
      quality: normalizeQuality(row.getAttribute("data-shop-quality")),
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
    let matchCount = 0;
    currentGroups().forEach((group) => {
      const rows = group.querySelectorAll("[data-shop-item]");
      let count = 0;
      rows.forEach((row) => {
        const haystack = String(row.getAttribute("data-shop-search") || "").toLowerCase();
        const isMatch = !query || haystack.includes(query);
        if (row.hidden === isMatch) row.hidden = !isMatch;
        if (isMatch) {
          count += 1;
        }
      });
      const counter = group.querySelector(".market_group_count");
      if (counter) counter.textContent = String(count);
      if (!group.parentElement?.closest("[data-shop-group]")) {
        matchCount += count;
      }
      group.hidden = count === 0;
      if (query && count) {
        group.open = true;
      } else if (!query) {
        (currentMode === "sell" ? sellGroupDisclosureState : groupDisclosureState).restore(group);
      }
    });
    const counter = document.getElementById("shopItemCount");
    if (counter) counter.textContent = `${fmtNumber(matchCount)} Artikel`;
  };
  const render = () => {
    const rows = [];
    cart.forEach((entry, cartKey) => {
      const unitPrice = unitPriceForEntry(entry);
      const lineTotal = unitPrice * entry.qty;
      const qualityIndex = QUALITY_ORDER.indexOf(normalizeQuality(entry.quality));
      const qualityAdjustable = entry.mode === "buy" && entry.showsQuality;
      const disableDown = !qualityAdjustable || qualityIndex <= 0 ? "disabled" : "";
      const disableUp = !qualityAdjustable || qualityIndex >= QUALITY_ORDER.length - 1 ? "disabled" : "";
      const qualityControls = qualityAdjustable
        ? `<div class="market_quality_stepper">
            <button type="button" data-cart-quality-inc aria-label="Qualität erhöhen" ${disableUp}>&#9650;</button>
            ${qualityBadge(entry.qualityPrices[entry.quality]?.quality || entry.quality)}
            <button type="button" data-cart-quality-dec aria-label="Qualität senken" ${disableDown}>&#9660;</button>
          </div>`
        : entry.mode === "sell" && entry.showsQuality
          ? qualityBadge(entry.quality)
          : "";
      const qtyMax = entry.mode === "sell" ? Math.max(1, readInt(entry.availableQty, 1)) : null;
      const qtyControls = entry.stackable
        ? `<div class="market_qty_stepper">
            <button type="button" data-cart-qty-dec aria-label="Menge verringern" ${entry.qty <= 1 ? "disabled" : ""}>−</button>
            <input type="text" class="market_qty_input" value="${entry.qty}" data-cart-qty inputmode="numeric" aria-label="Menge"${qtyMax ? ` max="${qtyMax}"` : ""}>
            <button type="button" data-cart-qty-inc aria-label="Menge erhöhen" ${qtyMax && entry.qty >= qtyMax ? "disabled" : ""}>+</button>
          </div>`
        : `<span>1 Stück</span>`;
      const shownQuality = entry.qualityPrices?.[entry.quality]?.quality || entry.quality;
      const qualityLabel = entry.showsQuality
        ? ` · ${escapeHtml(QUALITY_LABELS[shownQuality] || "")}` : "";
      rows.push(`
        <tr data-cart-key="${cartKey}">
          <td class="market_cart_main">
            ${entry.showsQuality ? `<div class="market_cart_quality">${qualityControls}</div>` : ""}
            <div class="market_cart_description">
              <div class="market_cart_name"><span>${escapeHtml(entry.name)}</span><button type="button" class="market_remove" data-cart-remove aria-label="Gegenstand entfernen">×</button></div>
              <small>${entry.mode === "sell" ? "Verkaufen" : "Kaufen"}${qualityLabel} · ${fmtKs(unitPrice)} / Stück</small>
            </div>
          </td>
          <td class="market_cart_qty">${qtyControls}</td>
          <td class="market_cart_total">${fmtKs(lineTotal)}</td>
        </tr>
      `);
    });

    cartBody.innerHTML = rows.length
      ? rows.join("")
      : '<tr class="market_cart_empty"><td colspan="3">Noch keine Gegenstände ausgewählt.<br>Wähle eine Ware aus dem Verzeichnis.</td></tr>';
    const cartCount = document.getElementById("shopCartCount");
    if (cartCount) cartCount.textContent = fmtNumber(cart.size);

    const discountPercent = cartHasBuyEntries()
      ? Math.min(100, Math.max(0, readInt(discountInput.value, 0)))
      : 0;
    if (cartHasBuyEntries() && readInt(discountInput.value, 0) !== discountPercent) {
      discountInput.value = String(discountPercent);
    }
    const resalePercent = readResalePercent();
    if (readInt(resaleInput.value, 50) !== resalePercent) {
      resaleInput.value = String(resalePercent);
    }
    if (lastResalePercent !== resalePercent) document.querySelectorAll('[data-shop-item][data-shop-mode="sell"]').forEach((row) => {
      const priceCell = row.querySelector(".shop_item_price");
      if (priceCell) {
        const effectivePrice = readInt(row.getAttribute("data-shop-unit-price"), 0);
        priceCell.textContent = fmtKs(Math.round(effectivePrice * resalePercent / 100));
      }
    });
    lastResalePercent = resalePercent;
    const buySubtotal = Array.from(cart.values())
      .filter((entry) => entry.mode === "buy")
      .reduce((sum, entry) => sum + (unitPriceForEntry(entry) * entry.qty), 0);
    const sellSubtotal = Array.from(cart.values())
      .filter((entry) => entry.mode === "sell")
      .reduce((sum, entry) => sum + (unitPriceForEntry(entry) * entry.qty), 0);
    const numerator = buySubtotal * (100 - discountPercent);
    const quotient = Math.floor(numerator / 100);
    const remainder = numerator % 100;
    const discountedBuyTotal = quotient + (remainder > 50 || (remainder === 50 && quotient % 2) ? 1 : 0);
    const finalValue = discountedBuyTotal - sellSubtotal;
    const simulatedBalance = baseBalance - finalValue;

    subtotalEl.textContent = fmtKs(buySubtotal);
    document.getElementById("shopSellSubtotal").textContent = fmtKs(Array.from(cart.values())
      .filter((entry) => entry.mode === "sell")
      .reduce((sum, entry) => sum + entry.unitPrice * entry.qty, 0));
    document.getElementById("shopDiscountAmount").textContent = `−${fmtKs(buySubtotal - discountedBuyTotal)}`;
    document.getElementById("shopResaleAmount").textContent = `+${fmtKs(sellSubtotal)}`;
    finalEl.textContent = fmtKs(finalValue);
    balanceEl.textContent = fmtKs(simulatedBalance);
    balanceEl.classList.toggle("is-negative", simulatedBalance < 0);
    actionBtn.disabled = transactionPending || !cart.size;
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
  const setAllGroups = (open) => {
    const state = currentMode === "sell" ? sellGroupDisclosureState : groupDisclosureState;
    currentGroups().forEach((group) => { if (!group.hidden) state.set(group, open); });
  };
  document.getElementById("shopExpandAll")?.addEventListener("click", () => setAllGroups(true));
  document.getElementById("shopCollapseAll")?.addEventListener("click", () => setAllGroups(false));

  filterInput.addEventListener("input", applyFilter);
  [buyModeBtn, sellModeBtn].forEach((tabBtn) => {
    tabBtn.addEventListener("click", () => {
      syncModeFromTabs();
      switchMode(currentMode);
    });
    tabBtn.addEventListener("keydown", (event) => {
      if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
        return;
      }
      window.requestAnimationFrame(() => {
        syncModeFromTabs();
        switchMode(currentMode);
      });
    });
  });

  shopList.addEventListener("click", (event) => {
    if (transactionPending) return;
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
    if (transactionPending) return;
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
      if (entry.mode !== "buy" || !entry.showsQuality) {
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
    if (transactionPending) return;
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
    const rawValue = target.value;
    const selectionStart = target.selectionStart;
    const selectionEnd = target.selectionEnd;
    render();
    const replacement = cartBody.querySelector(`[data-cart-key="${cartKey}"] [data-cart-qty]`);
    if (replacement && !rawValue) replacement.value = "";
    replacement?.focus();
    replacement?.setSelectionRange(selectionStart, selectionEnd);
  });

  document.addEventListener("charsheet:partials-applied", (event) => {
    if (transactionPending) return;
    const targets = event.detail?.targets || [];
    if (targets.includes("shop-panel-sell")) {
      modePanels = Array.from(document.querySelectorAll("[data-shop-mode-panel]"));
      sellGroupDisclosureState = initPersistentDetails(
        "#shop-panel-sell [data-shop-group]",
        "codexArcana.shop.categoryDisclosure.v1",
      );
      lastResalePercent = null;
      syncModeUi();
      applyFilter();
    }
    if (targets.includes("sheetWalletPanel")) {
      const value = document.querySelector("#sheetWalletPanel .wallet_total__value");
      if (value) {
        baseBalance = readInt(value.textContent.replace(/[^\d-]/g, ""), baseBalance);
        cartWrapper.setAttribute("data-shop-balance", String(baseBalance));
        if (headerBalance) headerBalance.textContent = fmtKs(baseBalance);
      }
    }
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
  resaleInput.addEventListener("input", render);
  resaleDecBtn.addEventListener("click", () => {
    resaleInput.value = String(Math.max(0, readInt(resaleInput.value, 50) - 5));
    render();
  });
  resaleIncBtn.addEventListener("click", () => {
    resaleInput.value = String(Math.min(100, readInt(resaleInput.value, 50) + 5));
    render();
  });

  actionBtn.addEventListener("click", async () => {
    const url = tradeUrl || (cartHasSellEntries() && !cartHasBuyEntries() ? sellUrl : buyUrl);
    if (!url || !cart.size || actionBtn.disabled) {
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
      discount: Math.min(100, Math.max(0, readInt(discountInput.value, 0))),
      resale_percent: readResalePercent(),
    };

    transactionPending = true;
    actionBtn.disabled = true;
    [discountInput, discountDecBtn, discountIncBtn, resaleInput, resaleDecBtn, resaleIncBtn]
      .forEach((control) => { control.disabled = true; });
    if (statusEl) statusEl.textContent = "Handel wird gebucht …";
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
      if (response.ok && data?.ok) {
        const previousBalance = baseBalance;
        baseBalance = readInt(data.new_money, baseBalance);
        cartWrapper.setAttribute("data-shop-balance", String(baseBalance));
        cart.clear();
        if (data.signature) {
          document.body.dataset.externalRefreshSignature = String(data.signature);
        }
        applySheetPartials(data);
        lastResalePercent = null;
        modePanels = Array.from(document.querySelectorAll("[data-shop-mode-panel]"));
        sellGroupDisclosureState = initPersistentDetails(
          "#shop-panel-sell [data-shop-group]",
          "codexArcana.shop.categoryDisclosure.v1",
        );
        syncModeUi();
        applyFilter();
        render();
        await animateMoneyBalance(previousBalance, baseBalance);
        if (statusEl) statusEl.textContent = "Handel abgeschlossen.";
        return;
      }
      if (data?.error === "insufficient_funds") {
        balanceEl.classList.remove("is-fail-flash");
        void balanceEl.offsetWidth;
        balanceEl.classList.add("is-fail-flash");
      }
      if (statusEl) statusEl.textContent = data?.error === "insufficient_funds"
        ? "Der Kassenbestand reicht für diesen Handel nicht aus."
        : "Der Handel konnte nicht abgeschlossen werden. Bitte prüfe die ausgewählten Gegenstände.";
    } catch (_error) {
      if (statusEl) statusEl.textContent = "Der Handel konnte nicht bestätigt werden. Bitte prüfe deinen Kassenbestand, bevor du erneut handelst.";
    } finally {
      transactionPending = false;
      actionBtn.disabled = !cart.size;
      [discountInput, discountDecBtn, discountIncBtn, resaleInput, resaleDecBtn, resaleIncBtn]
        .forEach((control) => { control.disabled = false; });
    }
  });

  syncModeFromTabs();
  syncModeUi();
  applyFilter();
  render();
  if (headerBalance) headerBalance.textContent = fmtKs(baseBalance);
}
