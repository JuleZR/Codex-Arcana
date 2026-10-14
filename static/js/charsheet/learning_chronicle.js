import { escapeHtml, readInt } from "./utils.js?v=20260622a";
import { renderTooltipMarkup } from "./tooltip.js?v=20261014c";

// Presentation only: the cart controller owns costs, limits and submitted fields.
export function initLearningChronicle(form, cartBody, controller) {
  const inspector = form.querySelector("#learnInspector");
  const drawer = form.querySelector("#learnPlanDrawer");
  if (!inspector || !drawer || form.dataset.chronicleBound === "1") return;
  form.dataset.chronicleBound = "1";
  const sources = Array.from(form.querySelectorAll("[data-learn-source]"));
  const rows = () => Array.from(cartBody.querySelectorAll("[data-learn-cart-item]"));
  let selected = null;
  let selectedRow = null;
  let proxies = [];
  let lastTotals = {};
  let activeCategory = "";
  const rankKinds = new Set(["attr", "trait", "skill", "skill-cs", "lang", "school", "magic-aspect", "vampire-power"]);
  const groupName = (group) => group?.querySelector(".learn_group_heading > span, summary > span")?.textContent || "";
  const knownKinds = new Set(["trait", "skill", "skill-cs", "lang", "school", "lesson", "magic-aspect", "vampire-power", "vampire-trait"]);
  const rowFor = (source) => rows().find((row) => row.learningSource === source
    || (source.dataset.key && row.dataset.key === source.dataset.key));

  sources.forEach((source) => {
    if (source.dataset.kind === "attr") {
      source.dataset.name = source.dataset.name.replace(/\s+\([^()]*\)$/, "");
      source.cells[0].textContent = source.dataset.name;
      source.setAttribute("aria-label", `${source.dataset.name} steigern`);
    }
    source.classList.remove("tooltip_target");
    source.querySelectorAll(".tooltip_target").forEach((target) => target.classList.remove("tooltip_target"));
    source.querySelectorAll("[data-shop-tooltip-info]").forEach((button) => button.remove());
    const group = source.closest("[data-learn-group]");
    source.dataset.groupName = groupName(group);
    source.dataset.groupKey = group?.dataset.collapseKey || "";
  });
  form.querySelectorAll("[data-tab-panel]").forEach((panel) => {
    const known = sources.filter((source) => panel.contains(source) && (
      (knownKinds.has(source.dataset.kind) && readInt(source.dataset.base, 0) > 0)
      || ["advanced-remove", "vampire-power-remove", "vampire-buyoff"].includes(source.dataset.kind)
      || (source.dataset.kind === "advanced-weapon" && source.dataset.new === "0")
    ));
    if (!known.length) return;
    const section = document.createElement("section");
    section.className = "learn_known_options shop_group";
    section.setAttribute("data-learn-known", "");
    section.innerHTML = '<header class="learn_group_heading"><span>Bereits erlernt</span><span class="shop_group_count"></span></header><table class="shop_table"><tbody></tbody></table>';
    const body = section.querySelector("tbody");
    known.forEach((source) => body.append(source));
    panel.prepend(section);
  });
  sources.forEach((source) => {
    const nameCell = source.cells[0];
    const metaCell = source.cells[1];
    if (!nameCell || !metaCell) return;
    const name = document.createElement("span");
    name.className = "learn_offer_name";
    while (nameCell.firstChild) name.append(nameCell.firstChild);
    if (source.dataset.kind === "school") {
      let level = readInt(source.dataset.base, 0);
      let roman = "";
      for (const [value, numeral] of [[1000, "M"], [900, "CM"], [500, "D"], [400, "CD"], [100, "C"], [90, "XC"], [50, "L"], [40, "XL"], [10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"]]) {
        while (level >= value) { roman += numeral; level -= value; }
      }
      if (roman) name.append(` ${roman}`);
    }
    const heading = document.createElement("div");
    heading.className = "learn_offer_heading";
    const cost = document.createElement("strong");
    cost.className = "learn_offer_cost";
    cost.textContent = controller.getOfferCost(source);
    cost.dataset.offerCost = cost.textContent;
    heading.append(name, cost);
    nameCell.append(heading);
    metaCell.querySelectorAll(".learn_meta_inline__item").forEach((item) => {
      if (["Lvl", "EP"].includes(item.querySelector(".learn_meta_label")?.textContent.trim())) item.hidden = true;
    });
    const spellCost = metaCell.querySelector("[data-learn-spell-offer-cost]");
    if (spellCost) spellCost.hidden = true;
    if (rankKinds.has(source.dataset.kind) || source.dataset.kind === "lesson"
      || (!metaCell.querySelector(".learn_meta_inline, [data-advanced-weapon-bonus]") && source.dataset.kind !== "magic-spell")) metaCell.replaceChildren();
    const footer = document.createElement("td");
    footer.className = "learn_offer_footer";
    const label = document.createElement("span");
    label.textContent = source.getAttribute("aria-disabled") === "true" ? "✦ Erlernt" : "✦ Lernangebot";
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Details";
    button.setAttribute("aria-label", `Details zu ${source.dataset.name || "Lernoption"}`);
    footer.append(label, button);
    source.append(footer);
    source.removeAttribute("tabindex");
    source.removeAttribute("role");
  });

  const renderRanks = () => {
    sources.forEach((source) => {
      const row = rowFor(source);
      source.classList.toggle("is-planned", Boolean(row));
      source.classList.toggle("is-selected", source === selected);
      const cost = source.querySelector(".learn_offer_cost");
      if (cost) {
        cost.textContent = row?.querySelector("[data-learn-cost]")?.textContent
          || (source.dataset.kind === "magic-spell" ? controller.getOfferCost(source) : cost.dataset.offerCost);
      }
      if (!rankKinds.has(source.dataset.kind)) return;
      const base = readInt(source.dataset.base, 0);
      const max = readInt(source.dataset.max, 0);
      if (max < 1 || max > 30) return;
      let track = source.querySelector(".learn_rank_track");
      if (!track) {
        track = document.createElement("span");
        track.className = `learn_rank_track${source.dataset.kind === "school" ? " learn_rank_track--path" : ""}`;
        source.cells[1].append(track);
      }
      const delta = readInt(row?.querySelector("[data-learn-value]")?.value, 0);
      const target = base + delta;
      const freeLanguage = source.dataset.kind === "lang" && (
        row?.querySelector("[data-learn-lang-free]")?.checked
        || readInt(source.dataset.min, 0) > 0
      );
      const paidLevel = readInt(source.dataset.paidBase, base);
      track.setAttribute("aria-label", `Aktuell ${base}, geplant ${target}, Maximum ${max}`);
      track.innerHTML = Array.from({ length: max }, (_, index) => {
        const level = index + 1;
        const state = level <= Math.min(base, target) ? "owned"
          : level <= target ? "next" : level <= base ? "removed" : "";
        const free = freeLanguage && level > paidLevel && level <= Math.min(3, target);
        return `<span class="learn_rank ${state}${free ? " free" : ""}"${free ? ' title="Kostenlose Sprachstufe (INT-Mod)"' : ""} aria-hidden="true"></span>`;
      }).join("");
      if (source.dataset.kind === "lang") {
        const owned = source.dataset.write === "1";
        const planned = row?.querySelector("[data-learn-lang-write]")?.checked ?? owned;
        const state = owned && planned ? "owned" : planned ? "next" : owned ? "removed" : "";
        const label = `Lesen & Schreiben: ${planned ? "vorhanden" : "nicht vorhanden"}`;
        track.setAttribute("aria-label", `${track.getAttribute("aria-label")}, ${label}`);
        track.insertAdjacentHTML("beforeend", `<span class="learn_rank learn_rank--literacy ${state}" title="${label}" aria-hidden="true"></span>`);
      }
    });
  };

  const renderInspector = () => {
    if (!selected) {
      inspector.innerHTML = '<p class="learn_inspector_placeholder">Wähle eine Lernoption, um ihre Entwicklung zu planen.</p>';
      return;
    }
    if (!selectedRow?.isConnected) selectedRow = selected.dataset.kind === "skill-new-spec" ? null : rowFor(selected) || null;
    const active = inspector.contains(document.activeElement) ? document.activeElement : null;
    const activeProxy = active?.dataset.chronicleProxy;
    const caret = active instanceof HTMLInputElement && active.type === "text" ? active.selectionStart : null;
    const scroll = inspector.scrollTop;
    const name = selected.dataset.name || "Lernoption";
    let description = (selected.dataset.tooltipEffect || selected.dataset.tooltip || "")
      .replace(/\[\[SOURCESYMBOL:[\s\S]*?\]\]/g, "").trim();
    const attributeChart = description.match(/\[\[SPELLATTR:[^\]\r\n]*\]\]/)?.[0] || "";
    if (attributeChart) {
      description = description.replace(attributeChart, "").replace("**Prägende Eigenschaften**", "").trim();
    }
    const row = selectedRow;
    const categoryTab = document.getElementById(selected.closest("[data-tab-panel]")?.getAttribute("aria-labelledby"));
    const optionSymbol = selected.querySelector(".learn_option_symbol, .learn_spell_symbol");
    const hasOptionSymbol = optionSymbol && (optionSymbol.querySelector("img") || !["", "?", "*"].includes(optionSymbol.textContent.trim()));
    const categoryIcon = hasOptionSymbol ? optionSymbol.innerHTML : categoryTab?.querySelector(".learn_tabs__icon")?.innerHTML || "✧";
    const selectedGroup = selected.dataset.groupName || "";
    const blocked = selected.getAttribute("aria-disabled") === "true" || selected.dataset.careerAvailable === "0";
    const addButton = `<button type="button" data-chronicle-add ${blocked ? "disabled" : ""}>${blocked ? escapeHtml(selected.dataset.lockedReason || "Bereits erlernt") : "Im Plan vormerken"}</button>`;
    const removeButton = '<button type="button" data-chronicle-remove>Aus Plan entfernen</button>';
    const facts = [];
    if (selected.dataset.ownerName) facts.push(["Quelle", selected.dataset.ownerName]);
    if (selected.dataset.gradeLabel) facts.push(["Zaubergrad", selected.dataset.gradeLabel]);
    if (selected.dataset.mother === "1") facts.push(["Sprache", "Muttersprache"]);
    if (selected.dataset.weakness) facts.push(["Schwäche", selected.dataset.weakness]);
    if (row?.dataset.kind === "magic-spell") {
      facts.push(["Abrechnung", row.dataset.slotSourceKey
        ? `${row.dataset.slotSourceName} · ${row.querySelector("[data-learn-spell-source-label]")?.textContent || "Gebundener Slot"}`
        : "Zusatzzauber · EP"]);
    }
    inspector.innerHTML = `<div class="learn_inspector_seal" aria-hidden="true">${categoryIcon}</div><h3>${escapeHtml(name)}</h3>
      <div class="learn_inspector_group">${row ? removeButton : addButton}</div>
      <div class="learn_inspector_controls learn_inspector_controls--attribute"></div>
      ${!row && selected.dataset.kind === "skill-new-spec" ? '<label class="learn_spec_name">Neue Spezialisierung<input type="text" id="learnNewSpecification" maxlength="255" placeholder="Bezeichnung eingeben"></label>' : ""}
      ${attributeChart ? `<div class="learn_inspector_attributes">${renderTooltipMarkup(`**Prägende Eigenschaften**\n${attributeChart}`)}</div>` : ""}
      ${selectedGroup && selected.dataset.kind !== "attr" ? `<p class="learn_inspector_group">${escapeHtml(selectedGroup)}</p>` : ""}
      ${description ? `<div class="learn_inspector_description">${renderTooltipMarkup(description)}</div>` : ""}
      <dl class="learn_inspector_facts">${facts.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl>
      ${selected.dataset.requirementsMet === "0" ? '<p class="learn_inspector_note">Voraussetzungen aktuell nicht erfüllt. Der Lernabschluss prüft auch die Änderungen im Entwicklungsplan.</p>' : ""}`;
    proxies = [];
    if (row) {
      const controls = inspector.querySelector(".learn_inspector_controls");
      Array.from(row.cells).slice(0, 2).reverse().forEach((cell) => {
        const copy = document.createElement("div");
        copy.innerHTML = cell.innerHTML;
        copy.querySelectorAll(".learn_trait_spec_label").forEach((label) => label.remove());
        const language = copy.querySelector(".learn_lang_name_wrap");
        if (language) {
          language.querySelectorAll(":scope > span").forEach((label) => label.remove());
          const writing = language.querySelector(".learn_lang_write");
          if (writing) {
            Array.from(writing.childNodes).filter((node) => node.nodeType === 3).forEach((node) => node.remove());
            writing.append(" Lesen & Schreiben");
          }
        }
        const originals = Array.from(cell.querySelectorAll("input, select, textarea, button"));
        Array.from(copy.querySelectorAll("input, select, textarea, button")).forEach((proxy, index) => {
          const original = originals[index];
          if (proxy.type === "hidden") { proxy.remove(); return; }
          proxy.removeAttribute("name");
          proxy.removeAttribute("id");
          proxy.removeAttribute("required");
          proxy.dataset.chronicleProxy = String(proxies.length);
          proxies.push(original);
          if ("value" in original) proxy.value = original.value;
          if ("checked" in original) proxy.checked = original.checked;
          proxy.disabled = original.disabled;
          if (proxy.hasAttribute("data-learn-value")) proxy.setAttribute("aria-label", rankKinds.has(selected.dataset.kind) ? "Stufenänderung" : "Anzahl");
          if (proxy.hasAttribute("data-learn-step-dec")) proxy.disabled = Number(row.querySelector("[data-learn-value]").value) <= Number(row.querySelector("[data-learn-value]").min);
          if (proxy.hasAttribute("data-learn-step-inc")) {
            const value = row.querySelector("[data-learn-value]");
            proxy.disabled = Boolean(value.max) && Number(value.value) >= Number(value.max);
          }
        });
        controls.append(copy);
      });
    }
    inspector.scrollTop = scroll;
    if (activeProxy !== undefined) {
      const next = inspector.querySelector(`[data-chronicle-proxy="${activeProxy}"]`);
      next?.focus({ preventScroll: true });
      if (caret !== null && next instanceof HTMLInputElement && next.type === "text") next.setSelectionRange(caret, caret);
    }
  };

  const renderSection = () => {
    const tab = form.querySelector('[role="tab"][aria-selected="true"]');
    const panel = document.getElementById(tab?.getAttribute("aria-controls"));
    const category = panel?.id || "";
    const categoryChanged = category !== activeCategory;
    if (categoryChanged) {
      activeCategory = category;
      const filter = form.querySelector("#learnGroupFilter");
      if (filter) {
        filter.hidden = ["learn-panel-attributes", "learn-panel-magic"].includes(category);
        filter.innerHTML = '<option value="">Alle Gruppen</option>' + Array.from(panel?.querySelectorAll("[data-learn-group]") || [])
          .map((group) => `<option value="${escapeHtml(group.dataset.collapseKey || "")}">${escapeHtml(groupName(group) || "Gruppe")}</option>`).join("");
      }
    }
    form.querySelectorAll("[data-learn-magic-source-filter-menu], [data-learn-magic-grade-filter-menu]")
      .forEach((menu) => { menu.hidden = category !== "learn-panel-magic"; });
    const visible = panel ? Array.from(panel.querySelectorAll("[data-learn-source]")).filter((source) => !source.hidden) : [];
    const title = tab?.querySelector(".learn_tabs__label")?.textContent || "Lernoptionen";
    form.querySelector("#learnSectionTitle").textContent = title;
    const eyebrow = form.querySelector("#learnSectionEyebrow");
    if (eyebrow) eyebrow.textContent = `Die Chronik · ${title}`;
    const intro = form.querySelector("#learnSectionIntro");
    if (intro) intro.textContent = ({
      "learn-panel-attributes": "Die Grundlagen deiner Entwicklung.",
      "learn-panel-traits": "Talente und Bürden.",
      "learn-panel-skills": "Wissen und Fertigkeit.",
      "learn-panel-languages": "Die Worte der Völker.",
      "learn-panel-schools": "Kampfkunst und Magie.",
      "learn-panel-advanced": "Die höheren Wege deiner Ausbildung.",
      "learn-panel-lessons": "Besondere Techniken und ihre Voraussetzungen.",
      "learn-panel-brews": "Rezepte für deinen Almanach.",
      "learn-panel-magic": "Die arkanen und göttlichen Künste.",
      "learn-panel-vampire": "Die Kräfte des Blutes.",
    })[category] || "Plane deine nächsten Lernschritte.";
    form.querySelector("#learnSectionCount").textContent = `${visible.length} Einträge`;
    form.querySelector("[data-learn-catalog-empty]").hidden = visible.length > 0;
    panel?.querySelectorAll("[data-learn-known]").forEach((section) => {
      const count = Array.from(section.querySelectorAll("[data-learn-source]")).filter((source) => !source.hidden).length;
      section.hidden = count === 0;
      section.querySelector(".shop_group_count").textContent = String(count);
    });
    if (selected && selected.closest("[data-tab-panel]") !== panel) {
      selected = null;
      selectedRow = null;
      renderInspector();
      renderRanks();
    }
    if (categoryChanged) form.dispatchEvent(new CustomEvent("learn:category-updated"));
  };

  const renderPlan = (totals = lastTotals) => {
    lastTotals = totals;
    const count = rows().length;
    drawer.classList.toggle("has-plan", count > 0);
    const badge = form.querySelector("#learnPlanCount");
    badge.hidden = count === 0;
    badge.textContent = String(count);
    badge.setAttribute("aria-label", `${count} Lernschritte vorgemerkt`);
    form.querySelector("#learnPlanSummary").textContent = count
      ? `${count} Lernschritte · ${totals.spent || 0} EP` : "Noch keine Lernschritte vorgemerkt";
    const ep = form.querySelector("[data-learn-top-ep]");
    ep.textContent = document.getElementById("learnBudgetValue").textContent;
    for (const [selector, value] of [["[data-learn-top-slots]", totals.spellSlotRemaining], ["[data-learn-top-brews]", totals.brewSlotRemaining]]) {
      const field = form.querySelector(selector);
      if (field) { field.textContent = `${value || 0} frei`; field.classList.toggle("is-negative", value < 0); }
    }
    const languageResource = form.querySelector("[data-learn-top-languages-resource]");
    if (languageResource) {
      const remaining = totals.freeLanguageRemaining ?? readInt(document.getElementById("learnBudgetPanel")?.getAttribute("data-free-language-budget"), 0);
      languageResource.hidden = remaining <= 0;
      languageResource.querySelector("[data-learn-top-languages]").textContent = `${Math.max(0, remaining)} frei`;
    }
    renderRanks();
    renderInspector();
    renderSection();
  };

  form.addEventListener("learn:select-source", (event) => {
    selected = event.detail;
    selectedRow = selected.dataset.kind === "skill-new-spec" ? null : rowFor(selected) || null;
    renderRanks();
    renderInspector();
  });
  form.addEventListener("learn:plan-updated", (event) => renderPlan(event.detail));
  form.addEventListener("learn:filters-updated", renderSection);
  form.querySelectorAll('[role="tab"]').forEach((tab) => tab.addEventListener("click", () => queueMicrotask(renderSection)));
  const tabs = form.querySelector(".learn_tabs__list");
  new MutationObserver(renderSection).observe(tabs, { subtree: true, attributes: true, attributeFilter: ["aria-selected"] });
  inspector.addEventListener("click", (event) => {
    const proxy = event.target.closest("[data-chronicle-proxy]");
    if (proxy instanceof HTMLButtonElement) { proxies[Number(proxy.dataset.chronicleProxy)]?.click(); return; }
    if (event.target.closest("[data-chronicle-add]")) {
      const spec = inspector.querySelector("#learnNewSpecification");
      if (spec && !spec.value.trim()) {
        spec.required = true;
        spec.reportValidity();
        spec.required = false;
        return;
      }
      selectedRow = controller.addFromSource(selected, spec?.value.trim() || "") || null;
      renderInspector();
    }
    if (event.target.closest("[data-chronicle-remove]")) selectedRow?.querySelector("[data-learn-remove]")?.click();
  });
  for (const type of ["input", "change"]) {
    inspector.addEventListener(type, (event) => {
      const proxy = event.target.closest("[data-chronicle-proxy]");
      if (!proxy || proxy instanceof HTMLButtonElement) return;
      const original = proxies[Number(proxy.dataset.chronicleProxy)];
      if (!original) return;
      original.value = proxy.value;
      if ("checked" in original) original.checked = proxy.checked;
      original.dispatchEvent(new Event(type, { bubbles: true }));
      controller.refreshTotals();
    });
  }
  cartBody.addEventListener("click", (event) => {
    if (event.target.closest("button, input, select, label")) return;
    const row = event.target.closest("[data-learn-cart-item]");
    if (row?.learningSource) { selected = row.learningSource; selectedRow = row; renderRanks(); renderInspector(); }
  });
  cartBody.addEventListener("input", () => controller.refreshTotals());
  cartBody.addEventListener("change", () => controller.refreshTotals());
  form.querySelector("#learnDiscardBtn").addEventListener("click", () => { controller.clearCart(); drawer.open = false; });
  form.addEventListener("invalid", (event) => {
    if (cartBody.contains(event.target)) drawer.open = true;
  }, true);
  controller.refreshTotals();
}
