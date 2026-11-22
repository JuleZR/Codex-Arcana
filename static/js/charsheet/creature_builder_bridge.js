let activeWorkshop = null;
let bound = false;

export function initCreatureBuilder() {
  if (bound) return;
  bound = true;
  document.addEventListener("click", (event) => {
    const trigger = event.target instanceof Element
      ? event.target.closest("[data-creature-builder-url]") : null;
    if (!trigger) return;
    event.preventDefault();
    event.stopPropagation();
    if (activeWorkshop) return;
    const choice = trigger.closest(".creature-creation-controls");
    const assignmentForm = choice?.querySelector("form.creature-creation-card__form");
    const select = assignmentForm?.querySelector("select[name='creature_id']");
    const dialog = document.createElement("dialog");
    dialog.className = "payday-window sheet-window sheet-window--editor-modal sl-workshop-window creature-builder-dialog is-open";
    dialog.setAttribute("aria-label", "Kreaturenbaukasten");
    const frame = document.createElement("iframe");
    const url = new URL(trigger.dataset.creatureBuilderUrl, window.location.origin);
    if (url.origin !== window.location.origin) return;
    url.searchParams.set("embedded", "1");
    const instanceId = trigger.closest("[data-creature-builder-instance]")?.dataset.creatureBuilderInstance;
    if (instanceId) url.searchParams.set("instance", instanceId);
    if (assignmentForm?.querySelector("input[name='is_kraftbestie']")?.checked) {
      url.searchParams.set("kraftbestie", "1");
    }
    if (select?.selectedOptions[0]?.dataset.creatureTypeId) {
      url.searchParams.set("type", select.selectedOptions[0].dataset.creatureTypeId);
    }
    frame.src = url.href;
    frame.title = "Kreaturenbaukasten";
    const header = document.createElement("header");
    header.className = "payday-window__titlebar sheet-window__header workshop_header market_header";
    const emblem = document.createElement("span");
    emblem.className = "market_emblem";
    emblem.setAttribute("aria-hidden", "true");
    emblem.textContent = "✦";
    const heading = document.createElement("div");
    heading.className = "sheet-window__heading market_heading";
    const eyebrow = document.createElement("span");
    eyebrow.className = "market_guild";
    eyebrow.textContent = "Codex Arcana · Kreaturen";
    const title = document.createElement("h3");
    title.className = "sheet-window__title market_title";
    title.textContent = "Kreatur erschaffen / bearbeiten";
    const subtitle = document.createElement("p");
    subtitle.className = "market_subtitle";
    subtitle.textContent = "Kompendium · 17 Erschaffungsschritte";
    heading.append(eyebrow, title, subtitle);
    const actions = document.createElement("div");
    actions.className = "sheet-window__actions";
    const close = document.createElement("button");
    close.type = "button";
    close.className = "payday-window__close sheet-window__close";
    close.setAttribute("aria-label", "Fenster schließen");
    close.textContent = "×";
    close.addEventListener("click", () => dialog.close());
    actions.append(close);
    header.append(emblem, heading, actions);
    const body = document.createElement("div");
    body.className = "sheet-window__body";
    body.append(frame);
    dialog.append(header, body);
    document.body.append(dialog);
    activeWorkshop = { dialog, frame, trigger, assignmentForm, select };
    dialog.addEventListener("close", () => {
      activeWorkshop = null;
      dialog.remove();
      trigger.focus();
    }, { once: true });
    dialog.showModal();
  }, true);

  window.addEventListener("message", (event) => {
    const workshop = activeWorkshop;
    if (!workshop || event.origin !== window.location.origin
        || event.source !== workshop.frame.contentWindow || event.data?.creatureBuilder !== true) return;
    if (event.data.cancelled) {
      workshop.dialog.close();
      return;
    }
    if (!event.data.saved || !Number.isSafeInteger(event.data.id)) return;
    if (workshop.assignmentForm && workshop.select) {
      const option = new Option(event.data.instanceName || event.data.name, String(event.data.id), true, true);
      option.dataset.creatureTypeId = String(event.data.typeId || "");
      workshop.select.add(option);
      workshop.select.value = String(event.data.id);
      let instanceName = workshop.assignmentForm.querySelector("input[name='custom_name']");
      if (!instanceName) {
        instanceName = document.createElement("input");
        instanceName.type = "hidden";
        instanceName.name = "custom_name";
        workshop.assignmentForm.append(instanceName);
      }
      instanceName.value = event.data.instanceName || "";
      workshop.select.dispatchEvent(new Event("change", { bubbles: true }));
      workshop.dialog.close();
      workshop.assignmentForm.requestSubmit();
    } else {
      // The template is already assigned; reload its canonical card data.
      workshop.dialog.close();
      window.location.reload();
    }
  });
}
