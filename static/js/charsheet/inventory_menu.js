import { applySheetPartials } from "./partial_updates.js";
import { createFloatingWindowController } from "./window_manager.js";
import { createItemEffectPreview } from "./item_effect_preview.js?v=20261102-overlay-workshop4";

let divisionGroupId = 0;
const openOwnInventories = new Map();

function showOwnInventory(panel, containerId) {
  if (!(panel instanceof HTMLElement)) {
    return;
  }
  const sections = Array.from(panel.querySelectorAll("[data-own-inventory-panel]"));
  const selectedId = sections.some((section) => section.dataset.containerId === containerId)
    ? containerId : "";
  openOwnInventories.set(panel.dataset.inventoryCharacter, selectedId);
  sections.forEach((section) => {
    section.hidden = section.dataset.containerId !== selectedId;
  });
  panel.querySelectorAll("[data-own-inventory-toggle]").forEach((button) => {
    button.setAttribute("aria-expanded", button.dataset.containerId === selectedId ? "true" : "false");
  });
}

function restoreOwnInventory() {
  const panel = document.getElementById("sheetInventoryPanel");
  if (panel instanceof HTMLElement) {
    showOwnInventory(panel, openOwnInventories.get(panel.dataset.inventoryCharacter) || "");
  }
}

function syncOwnInventoryFields(section) {
  const enabled = section.querySelector("[name='own_inventory_enabled']");
  const breaksAt = section.querySelector("[name='own_inventory_breaks_at']");
  const values = section.querySelector("[data-own-inventory-values]");
  const breakLimit = section.querySelector("[data-own-inventory-break-limit]");
  if (values) values.hidden = !enabled?.checked;
  if (breakLimit) breakLimit.hidden = !breaksAt?.checked;
}

function loadOwnInventorySettings(form, payload) {
  ["own_inventory_enabled", "own_inventory_capacity_kg", "own_inventory_breaks_at", "own_inventory_breaks_at_kg", "own_inventory_allowed_size_classes"]
    .forEach((name) => {
      const field = form.querySelector(`[name='${name}']`);
      if (!field) return;
      if (field.multiple) {
        const allowed = Array.isArray(payload[name]) ? payload[name] : [];
        Array.from(field.options).forEach((option) => {
          option.selected = allowed.includes(option.value);
        });
        return;
      }
      if (field.type === "checkbox") field.checked = Boolean(payload[name]);
      else field.value = String(payload[name] ?? "");
    });
  form.querySelectorAll("[data-own-inventory-settings]").forEach(syncOwnInventoryFields);
}

function parseIdList(rawValue) {
  return String(rawValue || "")
    .split(",")
    .map((value) => Number.parseInt(value.trim(), 10))
    .filter((value) => Number.isInteger(value) && value > 0);
}

function parseJsonList(rawValue) {
  try {
    const parsed = JSON.parse(String(rawValue || "[]"));
    return Array.isArray(parsed) ? parsed : [];
  } catch (_error) {
    return [];
  }
}

function parseJsonObject(rawValue) {
  try {
    const parsed = JSON.parse(String(rawValue || "{}"));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch (_error) {
    return {};
  }
}

function parseCpSteps(rawValue) {
  const seen = new Set();
  return String(rawValue || "")
    .split(/[^0-9]+/)
    .map((value) => Number.parseInt(value, 10))
    .filter((value) => {
      if (!Number.isInteger(value) || value <= 0 || seen.has(value)) {
        return false;
      }
      seen.add(value);
      return true;
    })
    .sort((a, b) => a - b);
}

function normalizeSearchValue(value) {
  return String(value || "").trim().toLowerCase();
}

function submitInventoryDropForm(form) {
  if (!(form instanceof HTMLFormElement)) {
    return Promise.resolve(false);
  }
  const formData = new FormData(form);
  return fetch(form.action, {
    method: form.method || "POST",
    body: formData,
    headers: {
      "X-Requested-With": "XMLHttpRequest",
      Accept: "application/json",
    },
    credentials: "same-origin",
  }).then(async (response) => {
    if (!response.ok) {
      throw new Error("inventory drop request failed");
    }
    const payload = await response.json();
    if (!payload?.ok) {
      throw new Error("inventory drop payload invalid");
    }
    applySheetPartials(payload);
    return true;
  });
}

function resolveInventoryDropAction(zone, row) {
  if (!(zone instanceof HTMLElement) || !(row instanceof HTMLElement)) {
    return null;
  }
  const zoneType = String(zone.dataset.inventoryZone || "");
  const rowStored = (row.dataset.stored || "0") === "1";
  const rowEquipped = (row.dataset.equipped || "0") === "1";
  const equipZone = String(row.dataset.equipDropZone || "");
  if (zoneType === "container") {
    const containerId = String(zone.dataset.containerId || "");
    const allowedSizes = String(zone.dataset.allowedSizeClasses || "").split(",").filter(Boolean);
    if (allowedSizes.length && !allowedSizes.includes(row.dataset.itemSizeClass)) {
      return null;
    }
    if (rowEquipped || !containerId || row.dataset.inventoryContainer === containerId) {
      return null;
    }
    const form = Array.from(row.querySelectorAll("[data-container-form]")).find((entry) => (
      entry.querySelector("input[name='inventory_container']")?.value === containerId
    ));
    return form instanceof HTMLFormElement ? { form, kind: "storage" } : null;
  }
  if (zoneType === "stored") {
    if (rowEquipped) {
      return null;
    }
    if (rowStored) {
      return null;
    }
    const form = row.querySelector("[data-storage-form]");
    const input = form?.querySelector("input[name='stored']");
    if (!(form instanceof HTMLFormElement) || !(input instanceof HTMLInputElement)) {
      return null;
    }
    input.value = "1";
    return { form, kind: "storage" };
  }
  if (zoneType === "carried") {
    if (rowEquipped) {
      const form = row.querySelector("[data-equip-form]");
      if (!(form instanceof HTMLFormElement)) {
        return null;
      }
      return { form, kind: "unequip" };
    }
    if (!rowStored && !row.dataset.inventoryContainer) {
      return null;
    }
    const form = row.querySelector("[data-storage-form]");
    const input = form?.querySelector("input[name='stored']");
    if (!(form instanceof HTMLFormElement) || !(input instanceof HTMLInputElement)) {
      return null;
    }
    input.value = "0";
    return { form, kind: "storage" };
  }
  if (zoneType === "equip-weapon" || zoneType === "equip-armor") {
    const expectedZone = zoneType === "equip-weapon" ? "weapon" : "armor";
    const equipZones = String(row.dataset.equipDropZones || equipZone || "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    if (!equipZones.includes(expectedZone)) {
      return null;
    }
    const form = row.querySelector("[data-equip-form]");
    if (!(form instanceof HTMLFormElement)) {
      return null;
    }
    return { form, kind: "equip" };
  }
  return null;
}

function updateAllowedDropZoneState(row) {
  const zoneTypes = ["carried", "stored", "equip-weapon", "equip-armor"];
  zoneTypes.forEach((zoneType) => {
    const probe = document.createElement("div");
    probe.dataset.inventoryZone = zoneType;
    const allowed = Boolean(resolveInventoryDropAction(probe, row));
    document.body.dataset[`dragAllow${zoneType.replace(/(^|-)([a-z])/g, (_m, _sep, char) => char.toUpperCase())}`] = allowed ? "1" : "0";
  });
  document.querySelectorAll('[data-inventory-zone="container"]').forEach((zone) => {
    zone.classList.toggle("is-drop-allowed", Boolean(resolveInventoryDropAction(zone, row)));
  });
}

function clearAllowedDropZoneState() {
  document.querySelectorAll(".is-drop-allowed").forEach((zone) => {
    zone.classList.remove("is-drop-allowed");
  });
  [
    "dragAllowCarried",
    "dragAllowStored",
    "dragAllowEquipWeapon",
    "dragAllowEquipArmor",
  ].forEach((key) => {
    delete document.body.dataset[key];
  });
}

function closeMenu(menu) {
  if (!(menu instanceof HTMLElement)) {
    return;
  }
  const trigger = menu.querySelector(".inv_menu_trigger");
  const panel = menu.querySelector(".inv_menu_panel");
  if (!(trigger instanceof HTMLButtonElement) || !(panel instanceof HTMLElement)) {
    return;
  }
  if (panel.hasAttribute("popover") && typeof panel.hidePopover === "function") {
    panel.hidePopover();
  }
  panel.hidden = true;
  panel.style.left = "";
  panel.style.top = "";
  trigger.setAttribute("aria-expanded", "false");
  menu.classList.remove("is-open");
  menu.closest(".inv_row")?.classList.remove("is-menu-open");
}

function positionMenuPanel(menu) {
  if (!(menu instanceof HTMLElement)) {
    return;
  }
  const trigger = menu.querySelector(".inv_menu_trigger");
  const panel = menu.querySelector(".inv_menu_panel");
  if (!(trigger instanceof HTMLButtonElement) || !(panel instanceof HTMLElement)) {
    return;
  }
  const triggerRect = trigger.getBoundingClientRect();
  const panelRect = panel.getBoundingClientRect();
  const maxLeft = Math.max(12, window.innerWidth - panelRect.width - 12);
  const left = Math.min(Math.max(12, triggerRect.right - panelRect.width), maxLeft);
  const top = Math.min(
    Math.max(12, triggerRect.bottom + 4),
    Math.max(12, window.innerHeight - panelRect.height - 12),
  );
  panel.style.left = `${left}px`;
  panel.style.top = `${top}px`;
}

function openMenu(menu) {
  const trigger = menu.querySelector(".inv_menu_trigger");
  const panel = menu.querySelector(".inv_menu_panel");
  if (!(trigger instanceof HTMLButtonElement) || !(panel instanceof HTMLElement)) {
    return;
  }
  panel.hidden = false;
  if (typeof panel.showPopover === "function") {
    panel.setAttribute("popover", "manual");
    panel.style.inset = "auto";
    panel.style.margin = "0";
    panel.showPopover();
  }
  trigger.setAttribute("aria-expanded", "true");
  menu.classList.add("is-open");
  menu.closest(".inv_row")?.classList.add("is-menu-open");
  positionMenuPanel(menu);
}

export function initInventoryMenu({ warningWindowController = null, modifyWindowController = null, catalogEditor = false } = {}) {
  restoreOwnInventory();
  document.querySelectorAll("[data-own-inventory-settings]").forEach(syncOwnInventoryFields);
  document.addEventListener("change", (event) => {
    const section = event.target instanceof Element
      ? event.target.closest("[data-own-inventory-settings]") : null;
    if (section) syncOwnInventoryFields(section);
  });
  if (document.body.dataset.inventoryMenuBound === "1") {
    return;
  }
  document.body.dataset.inventoryMenuBound = "1";

  const warningMessage = document.getElementById("inventoryWarningMessage");
  const deleteWarningMarkup = warningMessage?.innerHTML || "";
  document.addEventListener("inventory:storage-failed", (event) => {
    if (warningMessage) {
      warningMessage.textContent = event.detail?.error || "Verschieben fehlgeschlagen.";
    }
    document.querySelectorAll(".inv_menu.is-open").forEach((menu) => closeMenu(menu));
    warningWindowController?.open?.();
  });

  document.addEventListener("click", (event) => {
    const trigger = event.target instanceof Element
      ? event.target.closest("[data-open-item-damage]") : null;
    if (!trigger) return;
    const template = trigger.parentElement.querySelector("[data-item-damage-dialog]");
    const dialog = template?.content.firstElementChild?.cloneNode(true);
    if (!(dialog instanceof HTMLDialogElement)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    document.body.append(dialog);
    dialog.addEventListener("close", () => dialog.remove(), { once: true });
    dialog.querySelector("[data-close-item-damage]")?.addEventListener("click", () => dialog.close());
    const form = dialog.querySelector("form");
    form.addEventListener("sheet:action-success", () => dialog.close());
    form.addEventListener("sheet:action-failed", (failure) => {
      dialog.querySelector("[data-item-damage-error]").textContent =
        failure.detail?.error || "Speichern fehlgeschlagen. Bitte erneut versuchen.";
    });
    closeMenu(trigger.closest(".inv_menu"));
    dialog.showModal();
  }, true);

  const runeWindow = document.getElementById("runeRetrofitWindow");
  const runeCloseButton = document.getElementById("runeRetrofitWindowClose");
  const runeCancelButton = document.getElementById("runeRetrofitCancelBtn");
  const runeForm = document.getElementById("runeRetrofitForm");
  const workshopStatus = document.getElementById("workshopStatus");
  const runeOptions = document.getElementById("runeRetrofitOptions");
  const runeItemName = document.getElementById("runeRetrofitItemName");
  const runeSearchInput = document.getElementById("runeRetrofitSearch");
  const runeSelectionCount = document.getElementById("runeRetrofitSelectionCount");
  const runeQualitySelect = document.getElementById("runeRetrofitQuality");
  const runeItemTypeSelect = document.getElementById("runeRetrofitItemType");
  const runeExperienceCostInput = document.querySelector("#runeRetrofitForm input[name='experience_cost']");
  const runeMoneyCostInput = document.querySelector("#runeRetrofitForm input[name='money_cost']");
  const runeNameInput = document.getElementById("runeRetrofitCustomName");
  const runePriceInput = document.getElementById("runeRetrofitPrice");
  const runeWeightInput = document.getElementById("runeRetrofitWeight");
  const runeInvestedCpInput = document.getElementById("runeRetrofitInvestedCp");
  const runeInvestedCpSelect = document.getElementById("runeRetrofitInvestedCpSelect");
  const runeInvestedCpStepsInput = document.getElementById("runeRetrofitInvestedCpSteps");
  const runeSizeClassSelect = document.getElementById("runeRetrofitSizeClass");
  const runeDescriptionInput = document.getElementById("runeRetrofitDescription");
  const runeImageInput = document.getElementById("runeRetrofitImageInput");
  const runeImagePreview = document.getElementById("runeRetrofitImagePreview");
  const runeImagePreviewImg = document.getElementById("runeRetrofitImagePreviewImg");
  const runeRemoveImageInput = document.getElementById("runeRetrofitRemoveImageInput");
  const runeRemoveImageRow = document.getElementById("runeRetrofitImageRemoveRow");
  const magicEffectsList = document.getElementById("runeRetrofitMagicEffectsList");
  const magicEffectTemplate = document.getElementById("runeRetrofitMagicEffectTemplate");
  const magicAddEffectButton = document.getElementById("runeRetrofitAddEffectBtn");
  const magicPayloadInput = document.getElementById("runeRetrofitMagicModifierPayloads");
  const updateEffectPreviews = createItemEffectPreview({
    form: runeForm,
    payloadInput: magicPayloadInput,
    cardTarget: document.getElementById("workshopItemCardPreview"),
    cardStatus: document.getElementById("workshopItemCardStatus"),
    getCardFields: () => catalogEditor ? Array.from(new FormData(runeForm)).reduce((fields, [key, value]) => {
      if (value instanceof File) return fields;
      if (key in fields) fields[key] = [].concat(fields[key], value);
      else fields[key] = value;
      return fields;
    }, {}) : ({
      name: runeNameInput?.value || "",
      price: runePriceInput?.value || "0",
      weight: runeWeightInput?.value || "0",
      size_class: runeSizeClassSelect?.value || "",
      size_adjustment_settings: "1",
      base_values_are_size_adjusted: runeForm?.elements.namedItem("base_values_are_size_adjusted")?.checked ? "1" : "",
      quality: runeQualitySelect?.value || "",
      item_type: runeItemTypeSelect?.value || "",
      description: runeDescriptionInput?.value || "",
      remove_image: runeRemoveImageInput?.checked ? "1" : "",
      rune_payloads: document.getElementById("runeRetrofitRunePayloads")?.value || "[]",
    }),
    getInvestedCp: () => runeInvestedCpSelect?.disabled === false
      ? runeInvestedCpSelect.value : runeInvestedCpInput?.value,
  });
  const runePayloadInput = document.getElementById("runeRetrofitRunePayloads");
  const runeArmorFields = document.getElementById("runeRetrofitArmorFields");
  const runeWeaponFields = document.getElementById("runeRetrofitWeaponFields");
  const runeShieldFields = document.getElementById("runeRetrofitShieldFields");
  const runeWeaponWieldMode = document.getElementById("runeRetrofitWeaponWieldMode");
  const runeWeaponTwoHandFields = document.getElementById("runeRetrofitWeaponTwoHandFields");
  let retrofitItemType = "";
  let retrofitCapabilities = {};
  const WEAPON_ONLY_MAGIC_TARGET_KINDS = ["weapon_maneuver", "weapon_damage", "weapon_damage_dice", "weapon_mastery_bonus"];
  const WEAPON_MASTERY_BONUS_KIND = "weapon_mastery_bonus";
  const WEAPON_MASTERY_BONUS_DESCRIPTION = "Waffenmeister-Bonus +1/+1";
  const MAX_RUNES_PER_ITEM = 5;
  const DEFAULT_RUNE_CRAFTER_LEVEL = 1;
  const MAX_RUNE_CRAFTER_LEVEL = 10;
  let runeInstances = [];
  let selectedRune = null;
  let selectedEffect = null;
  const publishCatalogStatus = () => {
    if (!catalogEditor || window.parent === window) return;
    window.parent.postMessage({
      type: "staff-item-workshop-status",
      price: Number(runePriceInput?.value) || 0,
      runeCount: runeInstances.length,
    }, window.location.origin);
  };

  const syncInvestedCpStepControl = (currentValue) => {
    if (!(runeInvestedCpInput instanceof HTMLInputElement) || !(runeInvestedCpSelect instanceof HTMLSelectElement)) {
      return;
    }
    const steps = parseCpSteps(runeInvestedCpStepsInput instanceof HTMLInputElement ? runeInvestedCpStepsInput.value : "");
    const rawValue = String(currentValue ?? runeInvestedCpInput.value ?? "");
    if (!steps.length) {
      runeInvestedCpInput.hidden = false;
      runeInvestedCpInput.disabled = false;
      runeInvestedCpInput.value = rawValue;
      runeInvestedCpSelect.hidden = true;
      runeInvestedCpSelect.disabled = true;
      runeInvestedCpSelect.innerHTML = "";
      return;
    }
    runeInvestedCpSelect.innerHTML = "";
    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = "-";
    runeInvestedCpSelect.appendChild(emptyOption);
    steps.forEach((step) => {
      const option = document.createElement("option");
      option.value = String(step);
      option.textContent = String(step);
      runeInvestedCpSelect.appendChild(option);
    });
    runeInvestedCpSelect.value = steps.includes(Number.parseInt(rawValue, 10)) ? rawValue : "";
    runeInvestedCpInput.hidden = true;
    runeInvestedCpInput.disabled = true;
    runeInvestedCpSelect.hidden = false;
    runeInvestedCpSelect.disabled = false;
  };

  let runeChoices = [];
  try {
    runeChoices = JSON.parse(document.getElementById("rune-retrofit-choices")?.textContent || "[]");
  } catch (_error) {
    runeChoices = [];
  }

  let pendingRuneSubmit = false;
  let draggedInventoryItemId = "";
  const cleanupInventoryDragState = () => {
    draggedInventoryItemId = "";
    document.body.classList.remove("inventory-dragging");
    delete document.body.dataset.dragEquipDropZone;
    clearAllowedDropZoneState();
    document
      .querySelectorAll("[data-inventory-row].is-dragging, [data-equipped-row].is-dragging")
      .forEach((row) => row.classList.remove("is-dragging"));
    document.querySelectorAll("[data-inventory-zone].is-drag-over").forEach((zone) => zone.classList.remove("is-drag-over"));
    const storage = document.querySelector("[data-inventory-storage]");
    if (
      storage instanceof HTMLElement &&
      storage.classList.contains("inventory_storage--drag-preview") &&
      !storage.querySelector("[data-inventory-row]")
    ) {
      storage.hidden = true;
      storage.classList.remove("inventory_storage--drag-preview");
    }
  };
  const floatingController = modifyWindowController || (catalogEditor ? null : createFloatingWindowController({
    windowEl: runeWindow,
    closeButton: runeCloseButton,
    handle: document.getElementById("runeRetrofitWindowHandle"),
    startTop: 116,
    storageKey: "charsheet.runeRetrofitWindow",
    allowPersistedOpen: false,
    startRightInset: 214,
  }));

  const workshopTabs = Array.from(runeWindow?.querySelectorAll("[data-workshop-tab]") || []);
  const showWorkshopPanel = (key, focus = false) => {
    runeWindow?.classList.toggle("workshop--compact-sockets", key === "magic" || key === "advanced");
    workshopTabs.forEach((tab) => {
      const active = tab.dataset.workshopTab === key;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active && focus) tab.focus();
    });
    runeWindow?.querySelectorAll("[data-workshop-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.workshopPanel !== key;
    });
    if (key === "base") updateEffectPreviews();
  };
  workshopTabs.forEach((tab, index) => {
    tab.addEventListener("click", () => showWorkshopPanel(tab.dataset.workshopTab));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      let next = index + (["ArrowDown", "ArrowRight"].includes(event.key) ? 1 : -1);
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = workshopTabs.length - 1;
      showWorkshopPanel(workshopTabs[(next + workshopTabs.length) % workshopTabs.length].dataset.workshopTab, true);
    });
  });

  const normalizeCrafterLevel = (value) => {
    const parsed = Number.parseInt(String(value), 10);
    return Number.isInteger(parsed)
      ? Math.min(MAX_RUNE_CRAFTER_LEVEL, Math.max(DEFAULT_RUNE_CRAFTER_LEVEL, parsed))
      : DEFAULT_RUNE_CRAFTER_LEVEL;
  };

  const runeArtwork = (rune, framed = true) => {
    const ring = document.createElement("span");
    ring.className = framed ? "workshop_socket_ring" : "workshop_rune_image";
    ring.classList.toggle("is-occupied", Boolean(rune));
    if (rune?.image) {
      const image = document.createElement("img");
      image.src = rune.image;
      image.alt = "";
      image.addEventListener("error", () => {
        image.remove();
        ring.textContent = "◇";
      }, { once: true });
      ring.append(image);
    } else if (rune) {
      ring.textContent = "◇";
    }
    ring.setAttribute("aria-hidden", "true");
    return ring;
  };

  const serializeRunePayloads = () => {
    if (!(runePayloadInput instanceof HTMLInputElement)) return;
    const slots = new Map();
    runePayloadInput.value = JSON.stringify(runeInstances.map((instance) => {
      const slot = (slots.get(instance.rune.id) || 0) + 1;
      slots.set(instance.rune.id, slot);
      return {
        rune_id: Number(instance.rune.id),
        slot,
        crafter_level: instance.crafter_level,
        specification: instance.specification,
      };
    }));
  };

  const renderRuneSockets = () => {
    const sockets = document.getElementById("workshopSockets");
    if (!sockets) return;
    sockets.replaceChildren();
    for (let index = 0; index < MAX_RUNES_PER_ITEM; index += 1) {
      const instance = runeInstances[index];
      const button = document.createElement("button");
      button.type = "button";
      button.className = "workshop_socket";
      button.classList.toggle("is-selected", Boolean(instance && instance === selectedRune));
      button.setAttribute("aria-label", instance
        ? catalogEditor ? `${instance.rune.name}, Runenplatz ${index + 1} bearbeiten`
          : `${instance.rune.name}, Runenplatz ${index + 1}, Waffenmeisterstufe ${instance.crafter_level} bearbeiten`
        : `Leerer Runenplatz ${index + 1}, Runenverzeichnis öffnen`);
      button.setAttribute("aria-pressed", String(Boolean(instance && instance === selectedRune)));
      const name = document.createElement("strong");
      name.textContent = instance
        ? catalogEditor ? instance.rune.name : `${instance.rune.name} (${instance.crafter_level})`
        : "Freier Platz";
      button.append(runeArtwork(instance?.rune), name);
      button.addEventListener("click", () => {
        showWorkshopPanel("runes");
        if (instance) {
          selectedRune = instance;
          renderRuneInspector();
          renderRuneSockets();
          document.querySelector("#workshopRuneInspector input")?.focus();
        } else {
          runeSearchInput?.focus();
        }
      });
      sockets.append(button);
    }
  };

  const syncRuneSelectionCount = () => {
    if (runeSelectionCount) runeSelectionCount.textContent = `${runeInstances.length} / ${MAX_RUNES_PER_ITEM}`;
    runeOptions?.querySelectorAll("[data-add-rune]").forEach((button) => {
      const rune = runeChoices.find((choice) => String(choice.id) === button.dataset.addRune);
      const duplicate = !rune?.allow_multiple && runeInstances.some((instance) => instance.rune.id === rune?.id);
      const type = catalogEditor ? runeForm.elements.namedItem("item_type")?.value : retrofitItemType;
      const allowed = !rune?.allowed_item_types?.length || rune.allowed_item_types.includes(type);
      button.disabled = runeInstances.length >= MAX_RUNES_PER_ITEM || duplicate || !allowed;
      button.textContent = duplicate ? "Eingesetzt" : "Hinzufügen";
      button.title = !allowed ? "Für diesen Gegenstandstyp nicht verfügbar"
        : duplicate ? "Diese Rune kann nur einmal eingesetzt werden"
          : runeInstances.length >= MAX_RUNES_PER_ITEM ? "Alle fünf Runenplätze sind belegt" : "";
    });
    serializeRunePayloads();
    renderRuneSockets();
    filterRuneEntries();
    updateEffectPreviews();
    if (catalogEditor) publishCatalogStatus();
  };

  const renderRuneInspector = () => {
    const inspector = document.getElementById("workshopRuneInspector");
    if (!inspector) return;
    inspector.replaceChildren();
    if (!selectedRune || !runeInstances.includes(selectedRune)) {
      selectedRune = null;
      const hint = document.createElement("p");
      hint.textContent = "Wähle eine eingesetzte Rune in der Runenfassung.";
      inspector.append(hint);
      return;
    }
    const instance = selectedRune;
    const title = document.createElement("h3");
    title.textContent = instance.rune.name;
    const description = document.createElement("p");
    description.textContent = instance.rune.description || "Keine Beschreibung vorhanden.";
    const label = document.createElement("div");
    label.className = "shop_item_form_row";
    const caption = document.createElement("span");
    caption.textContent = "Waffenmeisterstufe";
    label.append(caption);
    const input = document.createElement("input");
    input.type = "number";
    input.min = "1";
    input.max = "10";
    input.step = "1";
    input.value = String(instance.crafter_level);
    input.setAttribute("aria-label", `${instance.rune.name}: Waffenmeisterstufe`);
    const update = () => {
      instance.crafter_level = normalizeCrafterLevel(input.value);
      syncRuneSelectionCount();
    };
    input.addEventListener("input", update);
    input.addEventListener("change", () => {
      update();
      input.value = String(instance.crafter_level);
    });
    const stepper = document.createElement("span");
    stepper.className = "workshop_stepper";
    const stepButton = (delta) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = delta < 0 ? "−" : "+";
      button.setAttribute("aria-label", delta < 0 ? "Waffenmeisterstufe senken" : "Waffenmeisterstufe erhöhen");
      button.addEventListener("click", () => {
        input.value = String(normalizeCrafterLevel(instance.crafter_level + delta));
        update();
      });
      return button;
    };
    stepper.append(stepButton(-1), input, stepButton(1));
    label.append(stepper);
    inspector.append(runeArtwork(instance.rune), title, description);
    if (!catalogEditor) inspector.append(label);
    if (instance.rune.has_specialization && !catalogEditor) {
      const specLabel = document.createElement("label");
      specLabel.className = "shop_item_form_row";
      specLabel.textContent = instance.rune.specialization_label || "Spezifikation";
      const spec = document.createElement("input");
      spec.type = "text";
      spec.maxLength = 100;
      spec.value = instance.specification;
      spec.addEventListener("input", () => {
        instance.specification = spec.value;
        serializeRunePayloads();
      });
      specLabel.append(spec);
      inspector.append(specLabel);
    }
    if (instance.rune.is_level_scaled && !catalogEditor) {
      const scaling = document.createElement("p");
      scaling.textContent = "Die Wirkung skaliert mit der Waffenmeisterstufe.";
      inspector.append(scaling);
    }
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Diese Runeninstanz entfernen";
    remove.addEventListener("click", () => {
      runeInstances = runeInstances.filter((entry) => entry !== instance);
      selectedRune = null;
      renderRuneInspector();
      syncRuneSelectionCount();
      runeSearchInput?.focus();
    });
    inspector.append(remove);
  };

  const openRuneWindow = () => {
    runeForm?.querySelector(".rune_window_save_error")?.remove();
    if (workshopStatus) workshopStatus.textContent = "";
    showWorkshopPanel("base");
    selectedRune = null;
    renderRuneInspector();
    syncRuneSelectionCount();
    syncWorkshopPrice();
    floatingController?.open?.();
    runeNameInput?.focus();
  };

  const closeRuneWindow = () => {
    floatingController?.close?.();
    updateEffectPreviews.cancel?.();
    pendingRuneSubmit = false;
    if (runeSearchInput) runeSearchInput.value = "";
  };

  const filterRuneEntries = () => {
    const query = normalizeSearchValue(runeSearchInput?.value);
    const usedSingleRunes = new Set(runeInstances
      .filter((instance) => !instance.rune.allow_multiple)
      .map((instance) => String(instance.rune.id)));
    runeOptions?.querySelectorAll(".rune_option").forEach((entry) => {
      entry.hidden = usedSingleRunes.has(entry.dataset.runeId)
        || Boolean(query && !normalizeSearchValue(entry.dataset.runeSearch || "").includes(query));
    });
  };

  const syncWorkshopPrice = () => {
    const price = document.getElementById("workshopPrice");
    if (price) price.textContent = `${new Intl.NumberFormat("de-DE").format(Number(runePriceInput?.value) || 0)} KS`;
    if (catalogEditor) publishCatalogStatus();
  };
  runePriceInput?.addEventListener("input", syncWorkshopPrice);

  const setFormValue = (fieldName, value) => {
    const field = runeForm?.elements?.namedItem?.(fieldName);
    if (field instanceof HTMLInputElement && field.type === "checkbox") {
      field.checked = Boolean(value);
      return;
    }
    if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement || field instanceof HTMLSelectElement) {
      field.value = value === null || value === undefined ? "" : String(value);
    }
  };

  const syncRetrofitDetailSections = () => {
    if (runeArmorFields instanceof HTMLElement) {
      runeArmorFields.hidden = !(retrofitCapabilities.armor ?? (retrofitItemType === "armor"));
    }
    if (runeWeaponFields instanceof HTMLElement) {
      runeWeaponFields.hidden = !(retrofitCapabilities.weapon ?? (retrofitItemType === "weapon"));
    }
    if (runeShieldFields instanceof HTMLElement) {
      runeShieldFields.hidden = !(retrofitCapabilities.shield ?? (retrofitItemType === "shield"));
    }
    if (runeWeaponTwoHandFields instanceof HTMLElement && runeWeaponWieldMode instanceof HTMLSelectElement) {
      runeWeaponTwoHandFields.hidden = runeWeaponWieldMode.value === "1h";
    }
    [runeArmorFields, runeWeaponFields, runeShieldFields].forEach((section) => {
      section?.querySelectorAll("input, select").forEach((field) => {
        const hiddenParent = field.closest("[hidden]");
        // Hidden tabs/windows must not disable otherwise applicable fields.
        field.disabled = section.hidden || Boolean(hiddenParent && section.contains(hiddenParent));
      });
    });
  };

  // ── Magic effect rows ──────────────────────────────────────────────────────

  const syncMagicEffectRow = (row) => {
    if (!(row instanceof HTMLElement)) {
      return;
    }
    const targetKindSelect = row.querySelector("[data-magic-target-kind]");
    const valueInput = row.querySelector("[data-magic-value-input]");
    const valueRow = row.querySelector("[data-magic-value-row]") || valueInput?.closest(".shop_item_form_row");
    const descriptionInput = row.querySelector("[data-magic-effect-description]");
    const scaleSource = row.querySelector("[data-magic-scale-source]");
    const scaleSourceRow = row.querySelector("[data-magic-scale-source-row]");
    const scaleDivisor = row.querySelector("[data-magic-scale-divisor]");
    const scaleDivisorRow = row.querySelector("[data-magic-scale-divisor-row]");
    const selectedKind = String(targetKindSelect?.value || "");
    const isTextOnly = selectedKind === "text";
    const isRuleFlag = selectedKind === "rule_flag";
    const operator = row.querySelector("[data-magic-operator]");
    const canSet = !isTextOnly && !isRuleFlag && selectedKind !== "wound_stage";
    if (operator) {
      operator.disabled = !canSet;
      operator.closest("label").hidden = !canSet;
      if (!canSet) operator.value = "";
    }
    const divisionRounding = row.querySelector("[data-division-rounding]");
    if (divisionRounding) {
      divisionRounding.hidden = !canSet || operator?.value !== "divide";
      const radios = divisionRounding.querySelectorAll("[data-division-mode]");
      const groupName = radios[0]?.name || `inventory-division-${++divisionGroupId}`;
      radios.forEach((radio) => {
        radio.name = groupName;
        radio.disabled = divisionRounding.hidden;
      });
    }
    const valueLabel = row.querySelector("[data-magic-value-label]");
    if (valueLabel) valueLabel.textContent = selectedKind === "wound_stage" ? "Anzahl" : "Wert";
    row.querySelectorAll("[data-magic-target-row]").forEach((targetRow) => {
      if (!(targetRow instanceof HTMLElement)) {
        return;
      }
      const rowKind = String(targetRow.dataset.magicTargetRow || "");
      const isActive = !isTextOnly && selectedKind === rowKind;
      targetRow.hidden = !isActive;
      const select = targetRow.querySelector("select");
      if (select) {
        select.disabled = !isActive;
      }
    });
    if (valueInput instanceof HTMLInputElement) {
      valueInput.setCustomValidity("");
      valueInput.min = selectedKind === "wound_stage" ? "1" : "";
      valueInput.step = selectedKind === "wound_stage" ? "1" : "any";
      if (valueRow instanceof HTMLElement) {
        valueRow.hidden = isTextOnly || isRuleFlag;
      }
      if (isTextOnly || isRuleFlag) {
        valueInput.value = "0";
      } else if (selectedKind === WEAPON_MASTERY_BONUS_KIND && String(valueInput.value || "").trim() === "") {
        valueInput.value = "1";
      }
    }
    if (descriptionInput instanceof HTMLInputElement && selectedKind === WEAPON_MASTERY_BONUS_KIND) {
      const currentValue = String(descriptionInput.value || "").trim();
      if (!currentValue || currentValue === WEAPON_MASTERY_BONUS_DESCRIPTION) {
        descriptionInput.value = WEAPON_MASTERY_BONUS_DESCRIPTION;
      }
    }
    const canScale = !isTextOnly && !isRuleFlag;
    if (scaleSourceRow instanceof HTMLElement) {
      scaleSourceRow.hidden = !canScale;
    }
    if (scaleSource instanceof HTMLSelectElement) {
      scaleSource.disabled = !canScale;
      if (!canScale) {
        scaleSource.value = "";
      }
    }
    if (scaleDivisorRow instanceof HTMLElement) {
      scaleDivisorRow.hidden = !canScale || !(scaleSource instanceof HTMLSelectElement) || !scaleSource.value;
    }
    if (scaleDivisor instanceof HTMLInputElement) {
      scaleDivisor.disabled = !canScale || !(scaleSource instanceof HTMLSelectElement) || !scaleSource.value;
    }
  };

  const serializeMagicEffects = () => {
    if (!(magicPayloadInput instanceof HTMLInputElement) || !(magicEffectsList instanceof HTMLElement)) {
      return;
    }
    const payloads = [];
    magicEffectsList.querySelectorAll("[data-magic-effect-row]").forEach((row) => {
      if (!(row instanceof HTMLElement)) {
        return;
      }
      const targetKind = String(row.querySelector("[data-magic-target-kind]")?.value || "").trim();
      if (!targetKind) {
        return;
      }
      const isTextOnly = targetKind === "text";
      const isRuleFlag = targetKind === "rule_flag";
      const payload = {
        target_kind: targetKind,
        operator: row.querySelector("[data-magic-operator]")?.value === "divide"
          ? row.querySelector("[data-division-mode]:checked")?.value || "divide"
          : String(row.querySelector("[data-magic-operator]")?.value || ""),
        value: isTextOnly || isRuleFlag ? "0" : String(row.querySelector("[data-magic-value-input]")?.value || "0").trim(),
        effect_description: String(row.querySelector("[data-magic-effect-description]")?.value || "").trim(),
        rules_text: String(row.querySelector("[data-magic-rules-text]")?.value || "").trim(),
        active_flag: row.dataset.magicActiveFlag !== "0",
        toggleable: Boolean(row.querySelector("[data-magic-toggleable]")?.checked),
        toggle_state_inverted: Boolean(row.querySelector("[data-magic-toggle-inverted]")?.checked),
      };
      const semanticEffectIds = parseIdList(row.dataset.semanticEffectIds || "");
      if (semanticEffectIds.length) {
        payload.semantic_effect_ids = semanticEffectIds;
      }
      if (row.dataset.semanticEffectSource) {
        payload.semantic_effect_source = row.dataset.semanticEffectSource;
      }
      const baseItemEffectIds = parseIdList(row.dataset.baseItemEffectIds || "");
      const baseItemEffectId = Number.parseInt(row.dataset.baseItemEffectId || "0", 10);
      if (baseItemEffectIds.length) {
        payload.base_item_effect_ids = baseItemEffectIds;
      } else if (baseItemEffectId > 0) {
        payload.base_item_effect_id = baseItemEffectId;
      }
      payload.condition_races = Array.from(
        row.querySelector("[data-magic-condition-races]")?.selectedOptions || [],
        (option) => Number.parseInt(option.value, 10),
      ).filter((value) => Number.isInteger(value) && value > 0);
      payload.condition_schools = Array.from(
        row.querySelector("[data-magic-condition-schools]")?.selectedOptions || [],
        (option) => Number.parseInt(option.value, 10),
      ).filter((value) => Number.isInteger(value) && value > 0);
      if (row.dataset.displayGroup) {
        payload.display_group = Number.parseInt(row.dataset.displayGroup, 10) || row.dataset.displayGroup;
      }
      if (row.dataset.displayGroupAppend === "1") {
        payload.display_group_append = true;
      }
      const displayGroupInput = row.querySelector("[data-magic-display-group]");
      const displayGroupValue = String(displayGroupInput?.value || "").trim();
      if (displayGroupValue) {
        payload.display_group = Number.parseInt(displayGroupValue, 10) || displayGroupValue;
      }
      if (row.querySelector("[data-magic-display-group-append]")?.checked) {
        payload.display_group_append = true;
      }
      const scaleSource = String(row.querySelector("[data-magic-scale-source]")?.value || "").trim();
      if (!isTextOnly && !isRuleFlag && scaleSource) {
        payload.scale_source = scaleSource;
        payload.scale_divisor = Number.parseInt(row.querySelector("[data-magic-scale-divisor]")?.value || "0", 10) || 0;
      }
      if (targetKind === "attribute") {
        payload.target_attribute = String(row.querySelector("[data-magic-target-select='attribute']")?.value || "").trim();
      } else if (targetKind === "stat") {
        payload.target_stat = String(row.querySelector("[data-magic-target-select='stat']")?.value || "").trim();
      } else if (targetKind === "combat") {
        payload.target_stat = String(row.querySelector("[data-magic-target-select='combat']")?.value || "").trim();
      } else if (targetKind === "wound_stage") {
        payload.target_wound_stage_position = String(row.querySelector("[data-magic-target-select='wound_stage']")?.value || "").trim();
      } else if (targetKind === "rule_flag") {
        payload.target_rule_flag = String(row.querySelector("[data-magic-target-select='rule_flag']")?.value || "").trim();
      } else if (targetKind === "skill") {
        payload.target_skill = String(row.querySelector("[data-magic-target-select='skill']")?.value || "").trim();
        payload.target_skills = Array.from(row.querySelector("[data-magic-target-select='skill']")?.selectedOptions || [], option => option.value);
      } else if (targetKind === "category") {
        payload.target_skill_category = String(row.querySelector("[data-magic-target-select='category']")?.value || "").trim();
      } else if (targetKind === "movement") {
        payload.target_movement = String(row.querySelector("[data-magic-target-select='movement']")?.value || "").trim();
      } else if (targetKind === "item") {
        payload.target_item = String(row.querySelector("[data-magic-target-select='item']")?.value || "").trim();
      } else if (targetKind === "item_category") {
        payload.target_item_category = String(row.querySelector("[data-magic-target-select='item_category']")?.value || "").trim();
      } else if (targetKind === "trait") {
        payload.target_trait = row.querySelector("[data-magic-target-select='trait']")?.value || "";
      } else if (targetKind === "specialization") {
        payload.target_specialization = String(row.querySelector("[data-magic-target-select='specialization']")?.value || "").trim();
      } else if (["school_level", "school_level_grant"].includes(targetKind)) {
        payload.target_school_level = String(row.querySelector(`[data-magic-target-select='${targetKind}']`)?.value || "").trim();
      }
      payloads.push(payload);
    });
    magicPayloadInput.value = JSON.stringify(payloads);
  };

  const syncWorkshopEffects = () => {
    const catalog = document.getElementById("workshopEffectCatalog");
    if (!catalog || !magicEffectsList) return;
    const rows = Array.from(magicEffectsList.querySelectorAll("[data-magic-effect-row]"));
    if (!rows.includes(selectedEffect)) selectedEffect = rows[0] || null;
    const previewTargets = [];
    const displayGroups = new Map();
    catalog.replaceChildren();
    if (!rows.length) {
      const empty = document.createElement("p");
      empty.textContent = "Noch keine magischen Effekte. Füge eine Wirkung hinzu.";
      catalog.append(empty);
    }
    rows.forEach((row, index) => {
      row.hidden = row !== selectedEffect;
      const kind = row.querySelector("[data-magic-target-kind]");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "workshop_effect_entry";
      button.setAttribute("aria-pressed", String(row === selectedEffect));
      const title = document.createElement("strong");
      title.textContent = `${index + 1}. ${kind?.selectedOptions[0]?.textContent || "Effekt"}`;
      const summary = document.createElement("small");
      summary.className = "workshop_effect_preview";
      const rawGroup = row.querySelector("[data-magic-display-group]")?.value || row.dataset.displayGroup;
      const parsedGroup = Number.parseInt(rawGroup, 10);
      const group = Number.isInteger(parsedGroup) ? String(parsedGroup) : "";
      summary.dataset.previewLabel = group ? `Itemkarte · Gruppe ${group}` : "Itemkarte";
      summary.setAttribute("aria-label", "Vorschau auf der Itemkarte");
      summary.textContent = "Wähle eine Wirkung und den zugehörigen Zielwert.";
      if (kind?.value) previewTargets.push(summary);
      button.append(title, summary);
      button.addEventListener("click", () => {
        selectedEffect = row;
        syncWorkshopEffects();
        row.querySelector("[data-magic-target-kind]")?.focus();
      });
      const entry = document.createElement("div");
      entry.className = "workshop_effect_catalog_row";
      entry.dataset.effectIndex = String(index);
      entry.append(button);
      [-1, 1].forEach((direction) => {
        const move = document.createElement("button");
        move.type = "button";
        move.textContent = direction < 0 ? "↑" : "↓";
        move.setAttribute("aria-label", `Effekt ${index + 1} nach ${direction < 0 ? "oben" : "unten"} verschieben`);
        move.disabled = !rows[index + direction];
        move.addEventListener("click", () => {
          const sibling = rows[index + direction];
          if (!sibling) return;
          magicEffectsList.insertBefore(direction < 0 ? row : sibling, direction < 0 ? sibling : row);
          syncMagicEffectRemoveButtons();
          serializeMagicEffects();
          syncWorkshopEffects();
          Array.from(catalog.querySelectorAll(".workshop_effect_catalog_row"))
            .find((candidate) => Number(candidate.dataset.effectIndex) === index + direction)
            ?.querySelector("button")?.focus();
        });
        entry.append(move);
      });
      if (group) {
        if (!displayGroups.has(group)) {
          const groupEl = document.createElement("div");
          groupEl.className = "workshop_effect_group";
          groupEl.dataset.effectGroup = group;
          groupEl.setAttribute("role", "group");
          groupEl.setAttribute("aria-label", `Anzeigegruppe ${group}`);
          displayGroups.set(group, groupEl);
          catalog.append(groupEl);
        }
        displayGroups.get(group).append(entry);
      } else {
        catalog.append(entry);
      }
    });
    serializeMagicEffects();
    updateEffectPreviews(previewTargets);
  };

  const syncMagicEffectRemoveButtons = () => {
    if (!(magicEffectsList instanceof HTMLElement)) {
      return;
    }
    const rows = Array.from(magicEffectsList.querySelectorAll("[data-magic-effect-row]"));
    rows.forEach((row, index) => {
      if (!(row instanceof HTMLElement)) {
        return;
      }
      const title = row.querySelector(".shop_magic_effect_title");
      if (title instanceof HTMLElement) {
        title.textContent = `Effekt ${index + 1}`;
      }
      const removeButton = row.querySelector("[data-remove-magic-effect]");
      if (removeButton instanceof HTMLButtonElement) {
        removeButton.hidden = false;
      }
    });
  };

  const addMagicEffectRow = (initialPayload = null) => {
    if (!(magicEffectsList instanceof HTMLElement) || !(magicEffectTemplate instanceof HTMLTemplateElement)) {
      return null;
    }
    const fragment = magicEffectTemplate.content.cloneNode(true);
    const row = fragment.querySelector("[data-magic-effect-row]");
    if (!(row instanceof HTMLElement)) {
      return null;
    }
    magicEffectsList.append(row);
    selectedEffect = row;
    const targetKindSelect = row.querySelector("[data-magic-target-kind]");
    if (targetKindSelect instanceof HTMLSelectElement) {
      WEAPON_ONLY_MAGIC_TARGET_KINDS.forEach((optionValue) => {
        const weaponOnlyOption = targetKindSelect.querySelector(`option[value='${optionValue}']`);
        if (weaponOnlyOption instanceof HTMLOptionElement) {
          weaponOnlyOption.hidden = !(retrofitCapabilities.weapon ?? (retrofitItemType === "weapon"));
          weaponOnlyOption.disabled = weaponOnlyOption.hidden;
        }
      });
    }
    if (initialPayload && typeof initialPayload === "object") {
      const valueInput = row.querySelector("[data-magic-value-input]");
      const descriptionInput = row.querySelector("[data-magic-effect-description]");
      const rulesTextInput = row.querySelector("[data-magic-rules-text]");
      const displayGroupInput = row.querySelector("[data-magic-display-group]");
      const displayGroupAppendInput = row.querySelector("[data-magic-display-group-append]");
      const toggleableInput = row.querySelector("[data-magic-toggleable]");
      const toggleInvertedInput = row.querySelector("[data-magic-toggle-inverted]");
      row.dataset.magicActiveFlag = initialPayload.active_flag === false ? "0" : "1";
      row.dataset.semanticEffectIds = parseIdList(
        initialPayload.semantic_effect_ids || [],
      ).join(",");
      row.dataset.semanticEffectSource = String(initialPayload.semantic_effect_source || "");
      row.dataset.baseItemEffectId = String(initialPayload.base_item_effect_id || "");
      row.dataset.baseItemEffectIds = parseIdList(
        initialPayload.base_item_effect_ids || [],
      ).join(",");
      row.dataset.displayGroup = initialPayload.display_group == null ? "" : String(initialPayload.display_group);
      row.dataset.displayGroupAppend = initialPayload.display_group_append ? "1" : "0";
      if (targetKindSelect instanceof HTMLSelectElement) {
        targetKindSelect.value = String(initialPayload.target_kind || "");
        if (!(retrofitCapabilities.weapon ?? (retrofitItemType === "weapon")) && WEAPON_ONLY_MAGIC_TARGET_KINDS.includes(targetKindSelect.value)) {
          targetKindSelect.value = "";
        }
      }
      if (valueInput instanceof HTMLInputElement) {
        valueInput.value = String(initialPayload.value ?? "0");
      }
      const operator = row.querySelector("[data-magic-operator]");
      if (operator) {
        const isDivision = ["divide", "floor_divide", "ceil_divide"].includes(initialPayload.operator);
        operator.value = isDivision ? "divide"
          : ["override", "multiply", "min_value", "max_value"].includes(initialPayload.operator)
            ? initialPayload.operator : "";
        row.querySelectorAll("[data-division-mode]").forEach((radio) => {
          radio.checked = radio.value === (isDivision ? initialPayload.operator : "divide");
        });
      }
      if (descriptionInput instanceof HTMLTextAreaElement) {
        descriptionInput.value = String(initialPayload.effect_description || "");
      }
      if (rulesTextInput instanceof HTMLTextAreaElement) {
        rulesTextInput.value = String(initialPayload.rules_text || "");
      }
      if (displayGroupInput instanceof HTMLInputElement) {
        displayGroupInput.value = initialPayload.display_group == null ? "" : String(initialPayload.display_group);
      }
      if (displayGroupAppendInput instanceof HTMLInputElement) {
        displayGroupAppendInput.checked = Boolean(initialPayload.display_group_append);
      }
      if (toggleableInput instanceof HTMLInputElement) {
        toggleableInput.checked = Boolean(initialPayload.toggleable);
      }
      if (toggleInvertedInput instanceof HTMLInputElement) {
        toggleInvertedInput.checked = Boolean(initialPayload.toggle_state_inverted);
      }
      [
        ["[data-magic-condition-races]", initialPayload.condition_races],
        ["[data-magic-condition-schools]", initialPayload.condition_schools],
      ].forEach(([selector, selectedValues]) => {
        const select = row.querySelector(selector);
        const selectedIds = new Set(parseIdList(selectedValues || []));
        if (select instanceof HTMLSelectElement) {
          Array.from(select.options).forEach((option) => {
            option.selected = selectedIds.has(Number.parseInt(option.value, 10));
          });
        }
      });
      const scaleSource = row.querySelector("[data-magic-scale-source]");
      const scaleDivisor = row.querySelector("[data-magic-scale-divisor]");
      if (scaleSource instanceof HTMLSelectElement) {
        scaleSource.value = String(initialPayload.scale_source || "");
      }
      if (scaleDivisor instanceof HTMLInputElement) {
        scaleDivisor.value = String(initialPayload.scale_divisor || 2);
      }
      const targetFieldMap = {
        attribute: "target_attribute",
        stat: "target_stat",
        combat: "target_stat",
        wound_stage: "target_wound_stage_position",
        rule_flag: "target_rule_flag",
        skill: "target_skill",
        category: "target_skill_category",
        movement: "target_movement",
        item: "target_item",
        item_category: "target_item_category",
        trait: "target_trait",
        specialization: "target_specialization",
        school_level: "target_school_level",
        school_level_grant: "target_school_level",
      };
      Object.entries(targetFieldMap).forEach(([kind, fieldName]) => {
        const select = row.querySelector(`[data-magic-target-select='${kind}']`);
        if (kind === "skill" && select instanceof HTMLSelectElement) {
          const ids = new Set((initialPayload.target_skills || [initialPayload.target_skill]).map(String));
          Array.from(select.options).forEach(option => { option.selected = ids.has(option.value); });
          return;
        }
        if (select instanceof HTMLSelectElement && initialPayload[fieldName] !== undefined) {
          select.value = String(initialPayload[fieldName] || "");
        }
      });
    }
    row.querySelector("[data-magic-target-kind]")?.addEventListener("change", () => {
      syncMagicEffectRow(row);
      serializeMagicEffects();
    });
    row.querySelector("[data-magic-value-input]")?.addEventListener("input", serializeMagicEffects);
    row.querySelectorAll("[data-division-mode]").forEach((radio) => {
      radio.addEventListener("change", serializeMagicEffects);
    });
    row.querySelector("[data-magic-operator]")?.addEventListener("change", () => {
      syncMagicEffectRow(row);
      serializeMagicEffects();
    });
    row.querySelector("[data-magic-effect-description]")?.addEventListener("input", serializeMagicEffects);
    row.querySelector("[data-magic-rules-text]")?.addEventListener("input", serializeMagicEffects);
    row.querySelector("[data-magic-display-group]")?.addEventListener("input", serializeMagicEffects);
    row.querySelector("[data-magic-display-group-append]")?.addEventListener("change", serializeMagicEffects);
    row.querySelector("[data-magic-toggleable]")?.addEventListener("change", serializeMagicEffects);
    row.querySelector("[data-magic-toggle-inverted]")?.addEventListener("change", serializeMagicEffects);
    row.querySelector("[data-magic-condition-races]")?.addEventListener("change", serializeMagicEffects);
    row.querySelector("[data-magic-condition-schools]")?.addEventListener("change", serializeMagicEffects);
    row.querySelector("[data-magic-scale-source]")?.addEventListener("change", () => {
      syncMagicEffectRow(row);
      serializeMagicEffects();
    });
    row.querySelector("[data-magic-scale-divisor]")?.addEventListener("input", serializeMagicEffects);
    row.querySelectorAll("[data-magic-target-select]").forEach((select) => {
      select.addEventListener("change", serializeMagicEffects);
    });
    row.querySelector("[data-remove-magic-effect]")?.addEventListener("click", () => {
      row.remove();
      syncMagicEffectRemoveButtons();
      serializeMagicEffects();
      syncWorkshopEffects();
      selectedEffect?.querySelector("[data-magic-target-kind]")?.focus();
    });
    syncMagicEffectRow(row);
    syncMagicEffectRemoveButtons();
    serializeMagicEffects();
    syncWorkshopEffects();
    return row;
  };

  const populateMagicEffects = (payloads) => {
    if (!(magicEffectsList instanceof HTMLElement)) {
      return;
    }
    magicEffectsList.innerHTML = "";
    selectedEffect = null;
    payloads.forEach((payload) => {
      addMagicEffectRow(payload);
    });
    if (!payloads.length) {
      serializeMagicEffects();
    }
    selectedEffect = magicEffectsList.querySelector("[data-magic-effect-row]");
    syncWorkshopEffects();
  };

  const buildRuneOption = (rune, existingSlots) => {
    existingSlots.slice().sort((a, b) => a.slot - b.slot).forEach((slot) => {
      runeInstances.push({
        rune,
        crafter_level: normalizeCrafterLevel(slot.crafter_level),
        specification: String(slot.specification || ""),
      });
    });
    const wrapper = document.createElement("article");
    wrapper.className = "rune_option workshop_catalog_entry";
    wrapper.dataset.runeId = String(rune.id);
    wrapper.dataset.runeSearch = `${rune.name || ""} ${rune.description || ""}`;
    const copy = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = rune.name;
    const description = document.createElement("p");
    description.textContent = rune.description || "Keine Beschreibung vorhanden.";
    copy.append(name, description);
    const add = document.createElement("button");
    add.type = "button";
    add.dataset.addRune = String(rune.id);
    add.textContent = "Hinzufügen";
    add.setAttribute("aria-label", `${rune.name} hinzufügen`);
    add.addEventListener("click", () => {
      if (add.disabled || runeInstances.length >= MAX_RUNES_PER_ITEM) return;
      selectedRune = { rune, crafter_level: DEFAULT_RUNE_CRAFTER_LEVEL, specification: "" };
      runeInstances.push(selectedRune);
      renderRuneInspector();
      syncRuneSelectionCount();
      document.querySelector("#workshopRuneInspector input")?.focus();
    });
    wrapper.append(runeArtwork(rune, false), copy, add);
    return wrapper;
  };

  // ── Open rune window ───────────────────────────────────────────────────────

  document.addEventListener("pointerdown", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest(".inv_menu_trigger")) {
      event.stopPropagation();
    }
  }, true);

  document.addEventListener("click", (event) => {
    const inventoryToggle = event.target instanceof Element
      ? event.target.closest("[data-own-inventory-toggle]") : null;
    if (inventoryToggle instanceof HTMLButtonElement) {
      event.preventDefault();
      showOwnInventory(
        inventoryToggle.closest("#sheetInventoryPanel"),
        inventoryToggle.getAttribute("aria-expanded") === "true"
          ? "" : inventoryToggle.dataset.containerId,
      );
      return;
    }
    const toggleBtn = event.target instanceof Element
      ? event.target.closest("[data-rune-toggle]")
      : null;
    if (toggleBtn instanceof HTMLButtonElement) {
      event.preventDefault();
      event.stopPropagation();
      const controlsId = toggleBtn.getAttribute("aria-controls");
      const list = controlsId
        ? document.getElementById(controlsId)
        : toggleBtn.closest(".inv_row")?.querySelector(".inv_rune_list");
      if (list instanceof HTMLElement) {
        const willOpen = list.hidden;
        list.hidden = !willOpen;
        toggleBtn.setAttribute("aria-expanded", willOpen ? "true" : "false");
        toggleBtn.classList.toggle("is-open", willOpen);
      }
      return;
    }
  });

  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const trigger = target?.closest(".inv_menu_trigger");
    const menu = trigger?.closest(".inv_menu") || target?.closest(".inv_menu");

    document.querySelectorAll(".inv_menu").forEach((entry) => {
      if (entry !== menu) {
        closeMenu(entry);
      }
    });

    if (trigger instanceof HTMLButtonElement && menu instanceof HTMLElement) {
      event.preventDefault();
      event.stopPropagation();
      const panel = menu.querySelector(".inv_menu_panel");
      if (panel instanceof HTMLElement && panel.hidden) {
        openMenu(menu);
      } else {
        closeMenu(menu);
      }
      return;
    }

    if (target?.closest(".inv_permission_details > summary") && menu instanceof HTMLElement) {
      requestAnimationFrame(() => positionMenuPanel(menu));
    }

    if (target?.closest(".inv_menu_panel")) {
      return;
    }


    document.querySelectorAll(".inv_menu").forEach((entry) => closeMenu(entry));
  }, true);

  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.classList.contains("permission-form")) {
      return;
    }
    event.preventDefault();
    if (form.dataset.permissionPending === "1") {
      return;
    }

    const toggle = form.querySelector(".permission-toggle");
    const enabledInput = form.querySelector("input[name='enabled']");
    if (!(toggle instanceof HTMLButtonElement) || !(enabledInput instanceof HTMLInputElement)) {
      return;
    }

    form.dataset.permissionPending = "1";
    toggle.disabled = true;
    toggle.classList.add("is-pending");
    try {
      const response = await fetch(form.action, {
        method: form.method || "POST",
        body: new FormData(form),
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        credentials: "same-origin",
      });
      const payload = await response.json();
      if (!response.ok || !payload?.ok) {
        throw new Error("permission update failed");
      }

      const isActive = Boolean(payload.enabled);
      toggle.classList.toggle("is-active", isActive);
      toggle.setAttribute("aria-checked", isActive ? "true" : "false");
      enabledInput.value = isActive ? "0" : "1";
      toggle.setAttribute(
        "aria-label",
        `${form.querySelector(".permission-form__label")?.textContent?.trim() || "Recht"} ${isActive ? "widerrufen" : "erteilen"}`,
      );
    } catch (_error) {
      form.classList.add("has-error");
      window.setTimeout(() => form.classList.remove("has-error"), 900);
    } finally {
      delete form.dataset.permissionPending;
      toggle.classList.remove("is-pending");
      toggle.disabled = false;
    }
  });

  document.addEventListener("click", (event) => {
    const button = event.target instanceof Element
      ? event.target.closest("[data-require-shift-delete]")
      : null;
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    if (event.shiftKey) {
      warningWindowController?.close?.();
      return;
    }
    event.preventDefault();
    if (warningMessage) warningMessage.innerHTML = deleteWarningMarkup;
    warningWindowController?.open?.();
  });

  document.addEventListener("click", (event) => {
    const button = event.target instanceof Element
      ? event.target.closest("[data-open-rune-window]")
      : null;
    if (
      !(button instanceof HTMLButtonElement) ||
      !(runeForm instanceof HTMLFormElement) ||
      !(runeOptions instanceof HTMLElement)
    ) {
      return;
    }

    const characterItemId = button.getAttribute("data-character-item-id") || "";
    const itemName = button.getAttribute("data-item-name") || "-";
    const currentQuality = String(button.getAttribute("data-current-quality") || "common");
    const description = String(button.getAttribute("data-description") || "");
    const itemImage = String(button.getAttribute("data-item-image") || "");
    const itemImageOverride = String(button.getAttribute("data-item-image-override") || "");
    retrofitItemType = String(button.getAttribute("data-item-type") || "");
    if (runeItemTypeSelect instanceof HTMLSelectElement) {
      runeItemTypeSelect.value = retrofitItemType;
      Array.from(runeItemTypeSelect.options).forEach((option) => {
        option.disabled = option.dataset.active === "0" && option.value !== retrofitItemType;
      });
    }
    retrofitCapabilities = {};
    ["weapon", "armor", "shield"].forEach((type) => {
      const value = button.getAttribute(`data-supports-${type}`);
      if (value !== null) retrofitCapabilities[type] = value === "1";
    });
    const magicModifierPayloads = parseJsonList(button.getAttribute("data-magic-modifier-payloads"));
    const modifyPayload = parseJsonObject(button.getAttribute("data-modify-payload"));
    loadOwnInventorySettings(runeForm, modifyPayload);

    // Build spec map: rune_id → [{specification, slot}]
    const rawRuneSpecs = parseJsonList(button.getAttribute("data-rune-specs"));
    const runeSpecsByRuneId = {};
    rawRuneSpecs.forEach((spec) => {
      const runeId = Number(spec.rune_id);
      if (!runeId) {
        return;
      }
      if (!runeSpecsByRuneId[runeId]) {
        runeSpecsByRuneId[runeId] = [];
      }
      runeSpecsByRuneId[runeId].push({
        specification: String(spec.specification || ""),
        slot: Number(spec.slot || 1),
        crafter_level: normalizeCrafterLevel(spec.crafter_level),
      });
    });

    // Legacy fallback: use extra_rune_ids when no rune_specs exist yet
    const extraRuneIds = new Set(parseIdList(button.getAttribute("data-extra-rune-ids")));
    const useLegacy = rawRuneSpecs.length === 0 && extraRuneIds.size > 0;

    const groupAction = button.dataset.workshopAction;
    runeForm.action = groupAction || `/character-item/${characterItemId}/runes/update/`;
    if (groupAction) runeForm.dataset.effectPreviewUrl = `${groupAction}?preview=1`;
    else delete runeForm.dataset.effectPreviewUrl;
    [runeExperienceCostInput, runeMoneyCostInput].forEach((input) => {
      if (!input) return;
      input.disabled = button.dataset.workshopChargeCosts === "0";
      const section = input.closest("details");
      if (section) section.hidden = input.disabled;
    });
    runeOptions.innerHTML = "";
    if (runeSearchInput instanceof HTMLInputElement) {
      runeSearchInput.value = "";
    }
    if (runeQualitySelect instanceof HTMLSelectElement) {
      runeQualitySelect.value = currentQuality;
    }
    if (runeExperienceCostInput instanceof HTMLInputElement) {
      runeExperienceCostInput.value = "0";
    }
    if (runeMoneyCostInput instanceof HTMLInputElement) {
      runeMoneyCostInput.value = "0";
    }
    if (runeNameInput instanceof HTMLInputElement) {
      runeNameInput.value = String(modifyPayload.name || itemName);
    }
    if (runePriceInput instanceof HTMLInputElement) {
      runePriceInput.value = String(modifyPayload.price ?? "0");
    }
    if (runeWeightInput instanceof HTMLInputElement) {
      runeWeightInput.value = String(modifyPayload.weight ?? "0");
    }
    if (runeInvestedCpStepsInput instanceof HTMLInputElement) {
      runeInvestedCpStepsInput.value = String(modifyPayload.invested_cp_steps ?? "");
    }
    if (runeInvestedCpInput instanceof HTMLInputElement) {
      runeInvestedCpInput.value = String(modifyPayload.invested_cp ?? "");
    }
    syncInvestedCpStepControl(modifyPayload.invested_cp ?? "");
    if (runeSizeClassSelect instanceof HTMLSelectElement) {
      runeSizeClassSelect.value = String(modifyPayload.size_class || "");
    }
    if (runeDescriptionInput instanceof HTMLTextAreaElement) {
      runeDescriptionInput.value = description;
    }
    if (runeImageInput instanceof HTMLInputElement) {
      runeImageInput.value = "";
    }
    if (runeRemoveImageInput instanceof HTMLInputElement) {
      runeRemoveImageInput.checked = false;
    }
    if (runeImagePreview instanceof HTMLElement && runeImagePreviewImg instanceof HTMLImageElement) {
      if (itemImage) {
        runeImagePreviewImg.src = itemImage;
        runeImagePreviewImg.alt = `${itemName} Bild`;
        runeImagePreview.hidden = false;
        if (runeRemoveImageRow instanceof HTMLElement) {
          runeRemoveImageRow.hidden = !itemImageOverride;
        }
      } else {
        runeImagePreviewImg.removeAttribute("src");
        runeImagePreviewImg.alt = "";
        runeImagePreview.hidden = true;
        if (runeRemoveImageRow instanceof HTMLElement) {
          runeRemoveImageRow.hidden = true;
        }
      }
    }
    if (runeItemName instanceof HTMLElement) {
      runeItemName.textContent = itemName;
    }

    runeInstances = [];
    selectedRune = null;
    let availableCount = 0;
    runeChoices.forEach((rune) => {
      availableCount += 1;

      const runeId = Number(rune.id);
      let existingSlots = runeSpecsByRuneId[runeId] || [];

      // Legacy: single checked slot without spec
      if (useLegacy && existingSlots.length === 0 && extraRuneIds.has(runeId)) {
        existingSlots = [{ specification: "", slot: 1, crafter_level: DEFAULT_RUNE_CRAFTER_LEVEL }];
      }

      runeOptions.append(buildRuneOption(rune, existingSlots));
    });

    [
      "amount",
      "weapon_type",
      "weapon_min_st",
      "weapon_damage_source",
      "weapon_damage_dice_amount",
      "weapon_damage_dice_faces",
      "weapon_damage_flat_operator",
      "weapon_damage_flat_bonus",
      "weapon_wield_mode",
      "weapon_damage_type",
      "weapon_h2_dice_amount",
      "weapon_h2_dice_faces",
      "weapon_h2_flat_operator",
      "weapon_h2_flat_bonus",
      "weapon_h2_damage_type",
      "armor_rs_total",
      "armor_rs_head",
      "armor_rs_torso",
      "armor_rs_arm_left",
      "armor_rs_arm_right",
      "armor_rs_leg_left",
      "armor_rs_leg_right",
      "armor_encumbrance",
      "armor_min_st",
      "shield_rs",
      "shield_encumbrance",
      "shield_min_st",
      "shield_parade_bonus",
      "not_buyable",
      "not_sellable",
      "magic_effects_without_equipping",
      "rune_effects_without_equipping",
      "base_values_are_size_adjusted",
    ].forEach((fieldName) => {
      setFormValue(fieldName, modifyPayload[fieldName]);
    });

    if (!availableCount) {
      const empty = document.createElement("p");
      empty.className = "shop_empty";
      empty.textContent = "Keine Runen verfügbar.";
      runeOptions.append(empty);
    }

    populateMagicEffects(magicModifierPayloads);
    syncRetrofitDetailSections();
    syncRuneSelectionCount();
    serializeRunePayloads();
    filterRuneEntries();
    openRuneWindow();
    closeMenu(button.closest(".inv_menu"));
  });

  document.addEventListener("click", (event) => {
    const handle = event.target instanceof Element
      ? event.target.closest("[data-equip-handle-submit]")
      : null;
    if (!(handle instanceof HTMLElement)) {
      return;
    }
    const form = handle.closest("form");
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    event.preventDefault();
    form.requestSubmit();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    const handle = event.target instanceof Element
      ? event.target.closest("[data-equip-handle-submit]")
      : null;
    if (!(handle instanceof HTMLElement)) {
      return;
    }
    const form = handle.closest("form");
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    event.preventDefault();
    form.requestSubmit();
  });

  runeSearchInput?.addEventListener("input", filterRuneEntries);
  runeRemoveImageInput?.addEventListener("change", () => {
    if (!(runeImagePreview instanceof HTMLElement) || !(runeRemoveImageInput instanceof HTMLInputElement)) {
      return;
    }
    runeImagePreview.hidden = runeRemoveImageInput.checked;
  });

  document.addEventListener("dragstart", (event) => {
    const handle = event.target instanceof Element ? event.target.closest("[data-drag-handle]") : null;
    if (!(handle instanceof HTMLElement)) {
      return;
    }
    const row = handle.closest("[data-inventory-row], [data-equipped-row]");
    if (!(row instanceof HTMLElement)) {
      return;
    }
    draggedInventoryItemId = row.dataset.characterItemId || "";
    row.classList.add("is-dragging");
    document.body.classList.add("inventory-dragging");
    document.body.dataset.dragEquipDropZone = row.dataset.equipDropZone || "";
    updateAllowedDropZoneState(row);
    const storage = document.querySelector("[data-inventory-storage]");
    if (
      storage instanceof HTMLElement && storage.hidden &&
      !storage.hasAttribute("data-own-inventory-panel")
    ) {
      storage.hidden = false;
      storage.classList.add("inventory_storage--drag-preview");
    }
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", draggedInventoryItemId);
    }
  });

  document.addEventListener("dragend", (event) => {
    const handle = event.target instanceof Element ? event.target.closest("[data-drag-handle]") : null;
    if (!(handle instanceof HTMLElement) && !draggedInventoryItemId && !document.body.classList.contains("inventory-dragging")) {
      return;
    }
    cleanupInventoryDragState();
  });

  document.addEventListener("dragover", (event) => {
    const zone = event.target instanceof Element ? event.target.closest("[data-inventory-zone]") : null;
    if (!(zone instanceof HTMLElement) || !draggedInventoryItemId) {
      return;
    }
    const row = document.querySelector(
      `[data-inventory-row][data-character-item-id="${draggedInventoryItemId}"], [data-equipped-row][data-character-item-id="${draggedInventoryItemId}"]`,
    );
    if (!(row instanceof HTMLElement)) {
      return;
    }
    const dropAction = resolveInventoryDropAction(zone, row);
    if (!dropAction) {
      zone.classList.remove("is-drag-over");
      return;
    }
    if (zone.matches("[data-own-inventory-toggle]")) {
      showOwnInventory(zone.closest("#sheetInventoryPanel"), zone.dataset.containerId);
    }
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    document.querySelectorAll("[data-inventory-zone].is-drag-over").forEach((entry) => {
      if (entry !== zone) {
        entry.classList.remove("is-drag-over");
      }
    });
    zone.classList.add("is-drag-over");
  });

  document.addEventListener("dragleave", (event) => {
    const zone = event.target instanceof Element ? event.target.closest("[data-inventory-zone]") : null;
    if (!(zone instanceof HTMLElement)) {
      return;
    }
    const related = event.relatedTarget instanceof Element ? event.relatedTarget.closest("[data-inventory-zone]") : null;
    if (related === zone) {
      return;
    }
    zone.classList.remove("is-drag-over");
  });

  document.addEventListener("drop", async (event) => {
    const zone = event.target instanceof Element ? event.target.closest("[data-inventory-zone]") : null;
    if (!(zone instanceof HTMLElement) || !draggedInventoryItemId) {
      cleanupInventoryDragState();
      return;
    }
    event.preventDefault();
    zone.classList.remove("is-drag-over");
    const row = document.querySelector(
      `[data-inventory-row][data-character-item-id="${draggedInventoryItemId}"], [data-equipped-row][data-character-item-id="${draggedInventoryItemId}"]`,
    );
    if (!(row instanceof HTMLElement)) {
      cleanupInventoryDragState();
      return;
    }
    const dropAction = resolveInventoryDropAction(zone, row);
    if (!dropAction) {
      cleanupInventoryDragState();
      return;
    }
    cleanupInventoryDragState();
    try {
      await submitInventoryDropForm(dropAction.form);
    } catch (_error) {
      dropAction.form.requestSubmit();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      cleanupInventoryDragState();
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      cleanupInventoryDragState();
    }
  });

  window.addEventListener("blur", () => {
    cleanupInventoryDragState();
  });
  runeWeaponWieldMode?.addEventListener("change", syncRetrofitDetailSections);
  runeCloseButton?.addEventListener("click", closeRuneWindow);
  runeCancelButton?.addEventListener("click", closeRuneWindow);
  runeForm?.addEventListener("input", () => updateEffectPreviews());
  runeForm?.addEventListener("change", () => updateEffectPreviews());
  magicEffectsList?.addEventListener("input", syncWorkshopEffects);
  magicEffectsList?.addEventListener("change", syncWorkshopEffects);
  runeInvestedCpInput?.addEventListener("input", syncWorkshopEffects);
  runeInvestedCpSelect?.addEventListener("change", syncWorkshopEffects);
  runeForm?.addEventListener("invalid", (event) => {
    const field = event.target;
    if (catalogEditor) return;
    const panel = field.closest("[data-workshop-panel]");
    if (panel) showWorkshopPanel(panel.dataset.workshopPanel);
    const effect = field.closest("[data-magic-effect-row]");
    if (effect) {
      selectedEffect = effect;
      syncWorkshopEffects();
    }
    let parent = field.parentElement;
    while (parent && parent !== runeForm) {
      if (parent instanceof HTMLDetailsElement) parent.open = true;
      parent = parent.parentElement;
    }
  }, true);
  magicAddEffectButton?.addEventListener("click", () => {
    const row = addMagicEffectRow();
    row?.querySelector("[data-magic-target-kind]")?.focus();
  });

  runeForm?.addEventListener("submit", async (event) => {
    pendingRuneSubmit = true;
    if (workshopStatus) workshopStatus.textContent = "Wird gespeichert …";
    serializeMagicEffects();
    serializeRunePayloads();
    runeForm?.querySelector(".rune_window_save_error")?.remove();
    const groupButton = document.querySelector(
      "[data-open-rune-window][data-workshop-action]",
    );
    if (!groupButton || !runeForm.querySelector("[name='shared_workshop']")) return;
    event.preventDefault();
    if (runeForm.dataset.savePending === "1") return;
    runeForm.dataset.savePending = "1";
    const saveButton = runeForm.querySelector(".workshop_submit");
    if (saveButton) saveButton.disabled = true;
    try {
      const response = await fetch(runeForm.action, {
        method: "POST",
        body: new FormData(runeForm),
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (response.headers.get("content-type")?.includes("application/json")) {
        const result = await response.json();
        throw new Error(result.error || "Speichern fehlgeschlagen.");
      }
      if (!response.ok) throw new Error("Speichern fehlgeschlagen.");
      const updated = new DOMParser().parseFromString(await response.text(), "text/html");
      const selector = `[data-open-rune-window][data-workshop-action="${CSS.escape(runeForm.action.replace(window.location.origin, ""))}"]`;
      const currentButton = document.querySelector(selector);
      const nextButton = updated.querySelector(selector);
      if (!currentButton || !nextButton) {
        throw new Error("Gespeichert, aber der Inventareintrag konnte nicht aktualisiert werden. Bitte die Seite neu laden.");
      }
      const currentRow = currentButton.closest("tr");
      const nextRow = nextButton.closest("tr");
      // Preserve the other rows and their listeners, selection and open dialogs.
      currentRow.cells[1].querySelector("strong").textContent = nextRow.cells[1].querySelector("strong").textContent;
      currentRow.cells[2].replaceChildren(...nextRow.cells[2].childNodes);
      currentRow.cells[3].textContent = nextRow.cells[3].textContent;
      Array.from(nextButton.attributes).forEach(({ name, value }) => {
        if (name.startsWith("data-")) currentButton.setAttribute(name, value);
      });
      const itemId = currentButton.dataset.characterItemId;
      const disclosure = document.getElementById(`disclosure-${itemId}`);
      const nextDisclosure = updated.getElementById(`disclosure-${itemId}`);
      if (disclosure && nextDisclosure) {
        disclosure.replaceChildren(...nextDisclosure.childNodes);
        document.dispatchEvent(new CustomEvent("sl-inventory:item-updated", {
          detail: { root: disclosure },
        }));
      }
      const quantity = document.querySelector(`#send-${CSS.escape(itemId)} input[name='quantity']`);
      if (quantity) {
        quantity.max = currentRow.cells[3].textContent.trim();
        quantity.value = String(Math.min(Number(quantity.value), Number(quantity.max)));
      }
      closeRuneWindow();
    } catch (error) {
      runeForm.dispatchEvent(new CustomEvent("sheet:action-failed", {
        detail: { error: error.message },
      }));
    } finally {
      delete runeForm.dataset.savePending;
      if (saveButton) saveButton.disabled = false;
    }
  });

  runeForm?.addEventListener("sheet:action-failed", (event) => {
    pendingRuneSubmit = false;
    if (workshopStatus) workshopStatus.textContent = "";
    const saveBtn = runeForm?.querySelector(".workshop_submit");
    if (saveBtn instanceof HTMLButtonElement) {
      saveBtn.disabled = false;
    }
    const existingError = runeForm?.querySelector(".rune_window_save_error");
    if (!existingError) {
      const msg = document.createElement("p");
      msg.setAttribute("role", "alert");
      msg.className = "rune_window_save_error shop_item_form_hint shop_item_form_hint--error";
      msg.textContent = event.detail?.error || "Speichern fehlgeschlagen. Bitte Eingaben prüfen.";
      saveBtn?.before(msg);
    }
  });

  document.addEventListener("charsheet:partials-applied", () => {
    restoreOwnInventory();
    if (pendingRuneSubmit) {
      closeRuneWindow();
    }
  });
  window.addEventListener("resize", () => {
    document.querySelectorAll(".inv_menu.is-open").forEach((menu) => {
      positionMenuPanel(menu);
    });
  });
  document.addEventListener("scroll", () => {
    document.querySelectorAll(".inv_menu").forEach((menu) => closeMenu(menu));
  }, true);

  runeItemTypeSelect?.addEventListener("change", () => {
    retrofitItemType = runeItemTypeSelect.value;
    const option = runeItemTypeSelect.selectedOptions[0];
    ["weapon", "armor", "shield"].forEach((type) => {
      retrofitCapabilities[type] = option?.dataset[type] === "1";
    });
    syncRetrofitDetailSections();
    syncRuneSelectionCount();
    updateEffectPreviews();
  });

  // Catalog definitions share the inline workshop's effect catalog and
  // inspector, but have no inventory owner, crafting costs or sheet action.
  if (catalogEditor && runeForm) {
    let toastTimer;
    const showCatalogToast = (message) => {
      runeForm.querySelectorAll("[data-workshop-toast]").forEach((toast) => { toast.hidden = true; });
      if (!workshopStatus) return;
      clearTimeout(toastTimer);
      workshopStatus.textContent = message;
      workshopStatus.classList.add("is-error");
      workshopStatus.getAnimations?.().forEach((animation) => {
        animation.cancel();
        animation.play();
      });
      toastTimer = setTimeout(() => {
        workshopStatus.textContent = "";
        workshopStatus.classList.remove("is-error");
      }, 6000);
    };
    const updateCatalogErrors = () => {
      workshopTabs.forEach((tab) => {
        const panel = runeForm.querySelector(`[data-workshop-panel="${tab.dataset.workshopTab}"]`);
        const invalid = Boolean(panel?.querySelector(".errorlist, [aria-invalid='true']"));
        tab.classList.toggle("has-errors", invalid);
        if (invalid) tab.setAttribute("aria-description", "Enthält fehlerhafte Felder");
        else tab.removeAttribute("aria-description");
      });
    };
    const openCatalogField = (field) => {
      let parent = field.parentElement;
      while (parent && parent !== runeForm) {
        if (parent instanceof HTMLDetailsElement) parent.open = true;
        parent = parent.parentElement;
      }
    };
    const handleCatalogInvalid = (event) => {
      const field = event.target;
      // SelectFilter probes its optional lists with required + checkValidity().
      if (field.matches(".selector-available select, .selector-chosen select")) return;
      event.preventDefault();
      field.setAttribute("aria-invalid", "true");
      openCatalogField(field);
      updateCatalogErrors();
      showCatalogToast("Bitte die rot markierten Felder prüfen.");
    };
    runeForm.addEventListener("invalid", handleCatalogInvalid, true);
    const clearCatalogError = (event) => {
      const field = event.target;
      if (!field.matches("input, select, textarea")
          || field.matches(".selector-available select, .selector-chosen select")) return;
      if (field.validity.valid) {
        field.removeAttribute("aria-invalid");
        const row = field.closest(".catalog-field");
        row?.querySelectorAll(".errorlist").forEach((error) => error.remove());
      } else {
        field.setAttribute("aria-invalid", "true");
        openCatalogField(field);
      }
      updateCatalogErrors();
    };
    runeForm.addEventListener("input", clearCatalogError);
    runeForm.addEventListener("change", clearCatalogError);
    runeForm.querySelectorAll(".errorlist").forEach((error) => {
      openCatalogField(error);
      error.closest(".catalog-field")?.querySelectorAll("input, select, textarea").forEach((field) => {
        if (field.type !== "hidden") field.setAttribute("aria-invalid", "true");
      });
    });
    updateCatalogErrors();
    if (runeForm.querySelector(".errorlist")) showCatalogToast("Bitte die rot markierten Felder prüfen.");
    runeForm.querySelectorAll("[data-workshop-toast]").forEach((toast) => {
      setTimeout(() => { toast.hidden = true; }, 6000);
    });
    runeForm.addEventListener("formdata", (event) => {
      runeForm.querySelectorAll(".selector-chosen select").forEach((select) => {
        const choices = window.SelectBox?.cache[select.id];
        if (!choices) return;
        event.formData.delete(select.name);
        choices.forEach((choice) => event.formData.append(select.name, choice.value));
      });
    });
    const capabilities = JSON.parse(document.getElementById("item-type-capabilities")?.textContent || "{}");
    const type = runeForm.querySelector("[name='item_type']");
    const magic = runeForm.querySelector("[name='is_magic']");
    let runeDraft = [];
    try {
      const parsed = JSON.parse(runePayloadInput?.value || "[]");
      if (Array.isArray(parsed)) runeDraft = parsed;
    } catch (_error) { /* The server renders the validation error. */ }
    const syncCatalogStats = () => {
      const category = capabilities[type?.value] || {};
      retrofitItemType = category.supports_weapon_stats ? "weapon" : type?.value || "";
      runeForm.querySelectorAll("[data-catalog-stat-capability]").forEach((section) => {
        const capability = section.dataset.catalogStatCapability;
        const available = capability === "magic"
          ? magic?.checked || category.forces_magic || category.is_magic_equipment
          : category[capability];
        section.hidden = !available && !section.hasAttribute("data-catalog-existing-stats") && !section.querySelector(".errorlist");
      });
      syncRuneSelectionCount();
    };
    type?.addEventListener("change", syncCatalogStats);
    magic?.addEventListener("change", syncCatalogStats);
    syncCatalogStats();
    const selectedRuneIds = new Set(runeDraft.map((entry) => Number(entry.rune_id)));
    runeChoices.forEach((rune) => {
      runeOptions?.append(buildRuneOption(rune, selectedRuneIds.has(Number(rune.id))
        ? [{ slot: 1, crafter_level: DEFAULT_RUNE_CRAFTER_LEVEL, specification: "" }]
        : []));
    });
    renderRuneInspector();
    syncRuneSelectionCount();
    let effects = [];
    try {
      const parsed = JSON.parse(magicPayloadInput?.value || "[]");
      if (Array.isArray(parsed)) effects = parsed;
    } catch (_error) { /* The server renders the validation error. */ }
    populateMagicEffects(effects);
    runeForm.querySelectorAll("[data-catalog-formset]").forEach((section) => {
      section.querySelector("[data-catalog-add-form]")?.addEventListener("click", () => {
        const total = section.querySelector("input[name$='-TOTAL_FORMS']");
        const template = section.querySelector("[data-catalog-empty-form]");
        const maximum = Number(section.querySelector("input[name$='-MAX_NUM_FORMS']")?.value || 1000);
        if (!total || !template || Number(total.value) >= maximum) return;
        section.querySelector("[data-catalog-forms]")?.insertAdjacentHTML("beforeend", template.innerHTML.replaceAll("__prefix__", total.value));
        total.value = String(Number(total.value) + 1);
        section.querySelectorAll("select.selectfilter").forEach((select) => {
          window.SelectFilter.init(select.id, select.dataset.fieldName, 0);
        });
      });
    });
    showWorkshopPanel("base");
  }
}
