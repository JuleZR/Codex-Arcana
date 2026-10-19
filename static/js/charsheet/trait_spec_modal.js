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
    controller.open();
    window.setTimeout(() => {
      const target = controlled ? traitSpecOption : traitSpecInput;
      target.focus();
      if (!controlled) target.select();
    }, 0);
  });

  traitSpecCancelBtn?.addEventListener("click", () => {
    controller.close();
  });
  traitSpecForm.addEventListener("submit", () => {
    controller.close();
  });
}
