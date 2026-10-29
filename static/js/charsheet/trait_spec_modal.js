import { createFloatingWindowController } from "./window_manager.js";

export function initTraitSpecModal() {
  const traitSpecWindow = document.getElementById("traitSpecWindow");
  const traitSpecWindowClose = document.getElementById("traitSpecWindowClose");
  const traitSpecWindowHandle = document.getElementById("traitSpecWindowHandle");
  const traitSpecWindowTitle = document.getElementById("traitSpecWindowTitle");
  const traitSpecCancelBtn = document.getElementById("traitSpecCancelBtn");
  const traitSpecForm = document.getElementById("traitSpecForm");
  const traitSpecInput = document.getElementById("id_trait_specification");
  const traitSpecOption = document.getElementById("id_specification_option");
  const freeRow = traitSpecForm?.querySelector("[data-trait-free-specification]");
  const controlledRow = traitSpecForm?.querySelector("[data-trait-controlled-specification]");
  if (
    !traitSpecWindow
    || !traitSpecWindowClose
    || !traitSpecWindowHandle
    || !traitSpecWindowTitle
    || !traitSpecForm
    || !traitSpecInput
    || !traitSpecOption
    || !freeRow
    || !controlledRow
  ) {
    return;
  }
  if (traitSpecWindow.dataset.modalBound === "1") {
    return;
  }
  traitSpecWindow.dataset.modalBound = "1";
  const organizationChoice = document.createElement("input");
  organizationChoice.type = "hidden";
  organizationChoice.name = "organization_choice";
  const organizationRank = document.createElement("input");
  organizationRank.type = "hidden";
  organizationRank.name = "organization_rank";
  traitSpecForm.append(organizationChoice, organizationRank);
  organizationChoice.disabled = true;
  organizationRank.disabled = true;
  const specificationMaxLength = traitSpecInput.maxLength;
  const nobilityEditor = traitSpecForm.querySelector("[data-nobility-editor]");
  const titleList = traitSpecForm.querySelector("[data-nobility-title-list]");
  const titleInput = traitSpecForm.querySelector('[name="nobility_titles"]');
  const addTitle = traitSpecForm.querySelector("[data-nobility-add]");
  let nobility = null;

  function syncTitles() {
    const rows = Array.from(titleList.children);
    titleInput.value = JSON.stringify(rows.map((row) => ({
      country_id: row.querySelector("select").value,
      specification: row.querySelector("[data-title-specification]").value,
      selected_rank: row.querySelector("[data-title-rank]").value,
    })));
    rows.forEach((row) => {
      row.querySelector("button[data-remove-title]").disabled = rows.length < 2;
    });
  }

  function appendTitle(title = {}) {
    const row = document.createElement("div");
    row.className = "nobility_title_row";
    const countryLabel = document.createElement("label");
    countryLabel.className = "shop_item_form_row skill_spec_form_row nobility_title_country";
    const label = document.createElement("span");
    label.textContent = "Titelland";
    const country = document.createElement("select");
    country.required = false;
    country.className = "dashboard_input";
    country.dataset.learnEntityChoice = "";
    country.append(new Option("Freitext", ""));
    nobility.countries.forEach((option) => {
      country.add(new Option(option.name, String(option.id)));
    });
    country.value = String(title.country_id || "");
    countryLabel.append(label, country);
    const rankLabel = document.createElement("label");
    rankLabel.className = "shop_item_form_row skill_spec_form_row nobility_title_rank";
    const rankText = document.createElement("span");
    rankText.textContent = "Rang";
    const rank = document.createElement("select");
    rank.dataset.titleRank = "";
    rank.className = "dashboard_input";
    rankLabel.append(rankText, rank);
    const updateRank = (preferred = "", retainSelection = false) => {
      const selected = nobility.countries.find(
        (option) => String(option.id) === country.value,
      );
      const ranks = selected?.rank_options || [];
      rank.replaceChildren();
      if (retainSelection && preferred && !ranks.includes(preferred)) {
        rank.add(new Option("Rang wählen", ""));
      }
      ranks.forEach((name) => rank.add(new Option(name, name)));
      if (!ranks.length) {
        rank.add(new Option(country.value ? "Kein gültiger Rang" : "", ""));
      }
      rank.disabled = !ranks.length;
      rank.required = Boolean(ranks.length);
      rank.value = ranks.includes(preferred) ? preferred
        : (retainSelection && preferred ? "" : (selected?.rank || ""));
      specificationText.textContent = country.value ? "Namenszusatz" : "Titel (Freitext)";
      specification.placeholder = country.value ? "z. B. von Vagoth" : "Eigener Adelstitel";
      specification.required = !country.value;
      syncTitles();
    };
    const specificationLabel = document.createElement("label");
    specificationLabel.className = "shop_item_form_row skill_spec_form_row nobility_title_specification";
    const specificationText = document.createElement("span");
    specificationText.textContent = "Namenszusatz";
    const specification = document.createElement("input");
    specification.type = "text";
    specification.className = "dashboard_input";
    specification.maxLength = specificationMaxLength;
    specification.dataset.titleSpecification = "";
    specification.value = title.specification || "";
    specification.placeholder = "z. B. von Vagoth";
    specificationLabel.append(specificationText, specification);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "shop_item_cancel_btn";
    remove.dataset.removeTitle = "";
    remove.textContent = "×";
    remove.title = "Titel entfernen";
    remove.setAttribute("aria-label", "Titel entfernen");
    remove.addEventListener("click", () => {
      row.remove();
      syncTitles();
    });
    country.addEventListener("change", () => updateRank());
    rank.addEventListener("change", syncTitles);
    specification.addEventListener("input", syncTitles);
    row.append(countryLabel, rankLabel, specificationLabel, remove);
    titleList.append(row);
    updateRank(title.selected_rank || title.rank || "", true);
  }

  addTitle?.addEventListener("click", () => appendTitle());

  const controller = createFloatingWindowController({
    windowEl: traitSpecWindow,
    closeButton: traitSpecWindowClose,
    handle: traitSpecWindowHandle,
    startTop: 168,
    startRightInset: 212,
    storageKey: "charsheet.traitSpecWindow",
    allowPersistedOpen: false,
  });
  if (!controller) {
    return;
  }

  document.addEventListener("click", (event) => {
    const bubbleTrigger = event.target instanceof Element
      ? event.target.closest("[data-organization-bubble-trigger]") : null;
    if (bubbleTrigger instanceof HTMLElement) {
      const bubble = document.getElementById(bubbleTrigger.getAttribute("popovertarget"));
      if (!(bubble instanceof HTMLElement)) return;
      event.preventDefault();
      if (bubble.matches(":popover-open")) {
        bubble.hidePopover();
        return;
      }
      bubble.showPopover();
      const rect = bubbleTrigger.getBoundingClientRect();
      const size = bubble.getBoundingClientRect();
      const left = Math.max(8, Math.min(rect.left, window.innerWidth - size.width - 8));
      const above = rect.bottom + size.height + 10 > window.innerHeight - 8;
      bubble.style.left = `${left}px`;
      bubble.style.top = `${Math.max(8, above ? rect.top - size.height - 10 : rect.bottom + 10)}px`;
      bubble.dataset.placement = above ? "above" : "below";
      bubble.style.setProperty("--arrow-left", `${Math.max(12, Math.min(size.width - 20, rect.left + rect.width / 2 - left))}px`);
      return;
    }
    const trigger = event.target instanceof Element ? event.target.closest("[data-trait-spec-trigger]") : null;
    if (!(trigger instanceof HTMLElement)) {
      return;
    }
    trigger.closest(".char_rank_bubble")?.hidePopover();
    const organization = trigger.closest("[data-organization-choice]");
    const source = organization || trigger;
    const field = organization ? trigger.dataset.organizationField : "";
    const connector = field === "organization_connector";
    const label = organization ? (connector ? "Verbindungswort" : "Rang") : "Spezifikation";
    traitSpecWindowTitle.textContent = `${source.dataset.traitName || "Trait"} bearbeiten`;
    traitSpecForm.action = source.dataset.action || "";
    organizationChoice.disabled = !organization;
    organizationChoice.value = organization?.dataset.organizationChoice || "";
    organizationRank.disabled = !connector;
    organizationRank.value = source.dataset.specificationOption || "";
    traitSpecInput.name = connector ? field : "specification";
    traitSpecOption.name = organization && !connector ? field : "specification_option";
    traitSpecInput.maxLength = connector ? 50 : specificationMaxLength;
    freeRow.querySelector("span").textContent = label;
    controlledRow.querySelector("span").textContent = label;
    traitSpecForm.querySelector(".skill_spec_hint").hidden = Boolean(organization);
    let options = [];
    try {
      options = connector ? [] : JSON.parse(source.dataset.specificationOptions || "[]");
    } catch (_error) {
      options = [];
    }
    const controlled = options.length > 0;
    freeRow.hidden = controlled;
    controlledRow.hidden = !controlled;
    traitSpecInput.disabled = controlled;
    traitSpecOption.disabled = !controlled;
    traitSpecInput.value = controlled ? "" : (trigger.dataset.specification || "");
    traitSpecOption.replaceChildren(new Option("---------", ""));
    options.forEach((option) => {
      traitSpecOption.add(new Option(option.name, String(option.id)));
    });
    traitSpecOption.value = source.dataset.specificationOption || "";
    nobility = null;
    if (!organization && source.dataset.nobilityEditor) {
      try {
        nobility = JSON.parse(source.dataset.nobilityEditor);
      } catch (_error) {
        nobility = null;
      }
    }
    if (nobilityEditor && titleList && titleInput) {
      traitSpecWindow.dataset.nobilityMode = nobility ? "1" : "0";
      nobilityEditor.hidden = !nobility;
      titleInput.disabled = !nobility;
      titleList.replaceChildren();
      if (nobility) {
        freeRow.hidden = true;
        controlledRow.hidden = true;
        traitSpecInput.disabled = true;
        traitSpecOption.disabled = true;
        traitSpecForm.querySelector(".skill_spec_hint").hidden = true;
        nobility.titles.forEach(appendTitle);
      }
    }
    controller.open();
    window.setTimeout(() => {
      const target = nobility ? titleList.querySelector("select")
        : (controlled ? traitSpecOption : traitSpecInput);
      target.focus();
      if (!nobility && !controlled) target.select();
    }, 0);
  });

  traitSpecCancelBtn?.addEventListener("click", () => {
    controller.close();
  });
  traitSpecForm.addEventListener("submit", () => {
    controller.close();
  });
}
