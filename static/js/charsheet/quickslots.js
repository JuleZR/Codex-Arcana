import { getCsrfToken } from "./utils.js";
import { initQuickslotImageEditor } from "./quickslot_image_editor.js?v=20261007-crop-bounds";

const KEYS = [..."1234567890ß"];
const MIME = "application/x-codex-quickslot";
export const FREE_DICE = [
  { type: "dice", sides: 10, count: 1, label: "1W10" },
  { type: "dice", sides: 10, count: 2, label: "2W10" },
  { type: "dice", sides: 100, count: 1, label: "1W100" },
];

export function normalizeAction(action) {
  if (!action || typeof action !== "object") return null;
  if (action.type === "dice") {
    const dice = FREE_DICE.find(die => die.sides === action.sides && die.count === action.count);
    return dice ? appearance(action, { ...dice }) : null;
  }
  if (!["skill", "weapon", "initiative", "debug"].includes(action.type) || typeof action.id !== "string") return null;
  if (action.type === "debug" && !["krit", "mis"].includes(action.id)) return null;
  const clean = { type: action.type, id: action.id, label: String(action.label || action.id) };
  for (const key of ["subentry", "specification", "profile", "mode", "attribute"]) {
    if (typeof action[key] === "string") clean[key] = action[key];
  }
  return appearance(action, clean);
}

function appearance(action, clean) {
  if (action.ignoreBonus === true) clean.ignoreBonus = true;
  if (["top", "center", "bottom", "hidden"].includes(action.labelPosition)) clean.labelPosition = action.labelPosition;
  if (typeof action.customLabel === "string" && action.customLabel.trim()) clean.customLabel = action.customLabel.trim().slice(0, 80);
  if (typeof action.image === "string" && action.image.length <= 120000
      && /^data:image\/jpeg;base64,[A-Za-z0-9+/=]+$/.test(action.image)) clean.image = action.image;
  return clean;
}

export function actionMatches(reference, action) {
  return reference?.type === action.type && reference.id === action.id
    && ["subentry", "specification", "profile", "mode", "attribute"].every(
      key => (reference[key] || "") === (action[key] || ""),
    );
}

export function shortcutIndex(event) {
  const digit = KEYS.indexOf(event.key);
  if (digit !== -1) return digit;
  const functionKey = /^F(1[3-9]|2[0-3])$/.exec(event.key);
  return functionKey ? Number(functionKey[1]) - 13 : -1;
}

export function isEditingText(element) {
  if (!element) return false;
  if (element.isContentEditable || element.tagName === "TEXTAREA") return true;
  return element.tagName === "INPUT" && !element.disabled && !element.readOnly
    && !["button", "submit", "reset", "checkbox", "radio", "range", "color", "file", "hidden"].includes(element.type);
}

export function moveQuickslot(slots, from, to) {
  if (!Number.isInteger(from) || !Number.isInteger(to) || from < 0 || to < 0
      || from >= 11 || to >= 11 || !slots[from]) return;
  [slots[from], slots[to]] = [slots[to], slots[from]];
}

export function initQuickslots({ rollDice, isRolling }) {
  const root = document.getElementById("characterQuickslots");
  if (!root || root.dataset.bound === "1") return;
  root.dataset.bound = "1";
  const buttons = [...root.querySelectorAll("[data-quickslot-index]")];
  const toggle = root.querySelector("[data-quickslot-toggle]");
  const editor = document.getElementById("quickslotEditor");
  const typeSelect = document.getElementById("quickslotType");
  const actionSelect = document.getElementById("quickslotAction");
  const saveButton = editor.querySelector("[data-quickslot-save]");
  const status = document.getElementById("quickslotStatus");
  const bonusInput = document.getElementById("quickslotBonus");
  let slots = [...FREE_DICE, ...Array(8).fill(null)];
  let collapsed = window.matchMedia("(max-width: 700px)").matches;
  let catalog = [];
  let editingIndex = null;
  let choices = [];
  let drag = null;
  let statusTimer;
  let revision = 0;
  const labelInput = document.getElementById("quickslotLabel");
  const labelPositionSelect = document.getElementById("quickslotLabelPosition");
  const ignoreBonusInput = document.getElementById("quickslotIgnoreBonus");
  const imageEditor = initQuickslotImageEditor({
    onBusyChange: busy => { saveButton.disabled = busy || !choices.length; },
  });
  try {
    const saved = JSON.parse(window.localStorage.getItem(root.dataset.storageKey));
    if (Array.isArray(saved?.slots)) slots = Array.from({ length: 11 }, (_, i) => normalizeAction(saved.slots[i]));
    if (typeof saved?.collapsed === "boolean") collapsed = saved.collapsed;
  } catch (_error) { /* Keep defaults when browser storage is unavailable. */ }

  function notify(message) {
    clearTimeout(statusTimer);
    status.textContent = message;
    status.hidden = false;
    statusTimer = setTimeout(() => { status.hidden = true; }, 5000);
  }

  function persist() {
    try {
      window.localStorage.setItem(root.dataset.storageKey, JSON.stringify({ slots, collapsed }));
      return true;
    } catch (_error) { notify("Die Hotbar konnte in diesem Browser nicht gespeichert werden."); return false; }
  }

  function render() {
    root.classList.toggle("is-collapsed", collapsed);
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.textContent = collapsed ? "‹" : "›";
    toggle.title = collapsed ? "Hotbar ausklappen" : "Hotbar einklappen";
    toggle.setAttribute("aria-label", toggle.title);
    buttons.forEach((button, index) => {
      const action = slots[index];
      const current = action?.type === "dice" ? action : catalog.find(entry => actionMatches(action, entry));
      const available = current && current.available !== false;
      const label = action?.customLabel || current?.label || action?.label || "Leer";
      const modifier = available && Number.isFinite(current.modifier) ? `${current.modifier >= 0 ? "+" : ""}${current.modifier}` : "";
      button.querySelector(".quickslot__label").textContent = action ? label : "+";
      button.dataset.labelPosition = action?.labelPosition || (action?.image ? "bottom" : "center");
      button.classList.toggle("is-unavailable", Boolean(action && !available));
      button.classList.toggle("is-filled", Boolean(action));
      button.classList.toggle("has-image", Boolean(action?.image));
      const image = button.querySelector(".quickslot__image");
      image.hidden = !action?.image;
      if (action?.image) image.src = action.image;
      else image.removeAttribute("src");
      button.draggable = Boolean(action);
      button.title = `${KEYS[index]} / F${index + 13}: ${label}${current?.detail ? ` · ${current.detail}` : ""}${modifier ? ` ${modifier}` : ""}${action && !available ? " · Nicht verfügbar" : ""}\nRechtsklick: Belegen / Entfernen`;
      button.setAttribute("aria-label", button.title);
    });
  }

  async function refreshCatalog() {
    const token = ++revision;
    const response = await fetch(root.dataset.actionsUrl, { credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("Aktuelle Hotbar-Aktionen konnten nicht geladen werden.");
    const data = await response.json();
    if (!Array.isArray(data.actions)) throw new Error("Ungültige Hotbar-Aktionen.");
    if (token === revision) { catalog = data.actions; render(); }
    return data.actions;
  }

  async function activateQuickslot(index) {
    const action = slots[index];
    if (!action || isRolling()) return;
    const button = buttons[index];
    button.classList.add("is-activated");
    setTimeout(() => button.classList.remove("is-activated"), 250);
    try {
      const bonus = action.ignoreBonus ? 0 : Number(bonusInput?.value || 0);
      if (!Number.isFinite(bonus)) throw new Error("Bitte einen gültigen freien Bonus eingeben.");
      if (action.type === "dice") {
        await rollDice(action.sides, action.count, { bonus });
      } else {
        const weapon = action.type === "weapon";
        const debug = action.type === "debug";
        await rollDice(weapon ? null : 10, weapon ? null : 2, {
          bonus,
          probeKind: action.type === "skill" || debug ? "skill" : weapon ? "damage" : "initiative",
          critical: !weapon,
          resolve: async () => {
            const actions = await refreshCatalog();
            const current = actions.find(entry => actionMatches(action, entry));
            if (!current || current.available === false || (!weapon && !debug && !Number.isFinite(current.modifier))) {
              throw new Error(`${action.label}: nicht verfügbar. Bitte den Slot neu belegen oder entfernen.`);
            }
            if (debug) return { debug: { url: root.dataset.debugResultUrl, mode: current.id } };
            if (!weapon) return { modifier: current.modifier, label: current.label };
            return {
              sides: current.sides, count: current.count, label: current.label,
              complete: async roll => {
                const response = await fetch(root.dataset.weaponResultUrl, {
                  method: "POST", credentials: "same-origin",
                  headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
                  body: JSON.stringify({ action, rolls: roll.rolls, sides: roll.sides }),
                });
                const result = await response.json();
                if (!response.ok || !Number.isFinite(result.total) || !Array.isArray(result.modifiers)) {
                  throw new Error(result.error || "Waffenwurf konnte nicht ausgewertet werden.");
                }
                return result;
              },
            };
          },
        });
      }
    } catch (error) { notify(error.message || "Würfelwurf fehlgeschlagen."); }
  }

  function fillChoices() {
    choices = typeSelect.value === "dice" ? FREE_DICE : catalog.filter(action => action.type === typeSelect.value);
    document.getElementById("quickslotActionField").hidden = typeSelect.value === "initiative";
    document.getElementById("quickslotActionLabel").textContent = {
      skill: "Fertigkeit", weapon: "Waffe", dice: "Würfelwurf", debug: "DEBUG-Wurf",
    }[typeSelect.value] || "Aktion";
    actionSelect.replaceChildren();
    choices.forEach((action, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = `${action.label}${action.detail ? ` · ${action.detail}` : ""}${action.available === false ? " · Nicht verfügbar" : ""}`;
      actionSelect.append(option);
    });
    const selected = choices.findIndex(action => action.type === "dice"
      ? action.sides === slots[editingIndex]?.sides && action.count === slots[editingIndex]?.count
      : actionMatches(slots[editingIndex], action));
    if (selected !== -1) actionSelect.value = String(selected);
    saveButton.disabled = !choices.length || imageEditor.isBusy();
  }

  function openEditor(index) {
    editingIndex = index;
    labelInput.value = slots[index]?.customLabel || "";
    labelPositionSelect.value = slots[index]?.labelPosition || (slots[index]?.image ? "bottom" : "center");
    ignoreBonusInput.checked = slots[index]?.ignoreBonus === true;
    labelInput.placeholder = slots[index]?.label || "Bezeichnung der Aktion";
    imageEditor.setImage(slots[index]?.image || "");
    document.getElementById("quickslotEditorTitle").textContent = `Slot ${KEYS[index]} einrichten`;
    typeSelect.value = slots[index]?.type || "dice";
    fillChoices();
    if (!editor.open) editor.showModal();
    refreshCatalog().then(() => { if (editor.open) fillChoices(); }).catch(error => notify(error.message));
  }

  toggle.addEventListener("click", () => { collapsed = !collapsed; persist(); render(); });
  typeSelect.addEventListener("change", fillChoices);
  saveButton.addEventListener("click", () => {
    if (imageEditor.isBusy()) return;
    const action = normalizeAction({ ...choices[Number(actionSelect.value)],
      customLabel: labelInput.value, image: imageEditor.getImage(),
      labelPosition: labelPositionSelect.value,
      ignoreBonus: ignoreBonusInput.checked,
    });
    if (!action) return;
    const previous = slots[editingIndex];
    slots[editingIndex] = action;
    if (!persist()) {
      slots[editingIndex] = previous;
      const error = document.getElementById("quickslotImageError");
      error.textContent = "Der Slot konnte nicht gespeichert werden. Der Browserspeicher ist möglicherweise voll.";
      error.hidden = false;
      return;
    }
    render(); editor.close();
  });
  editor.querySelector("[data-quickslot-remove]").addEventListener("click", () => {
    slots[editingIndex] = null;
    persist(); render(); editor.close();
  });
  root.addEventListener("click", event => {
    const button = event.target.closest("[data-quickslot-index]");
    if (!button) return;
    const index = Number(button.dataset.quickslotIndex);
    if (!slots[index]) openEditor(index);
    else activateQuickslot(index);
  });
  root.addEventListener("contextmenu", event => {
    const button = event.target.closest("[data-quickslot-index]");
    if (!button) return;
    event.preventDefault(); openEditor(Number(button.dataset.quickslotIndex));
  });
  document.addEventListener("keydown", event => {
    const index = shortcutIndex(event);
    if (index < 0 || event.repeat || event.isComposing
        || event.composedPath().some(isEditingText)) return;
    event.preventDefault(); activateQuickslot(index);
  }, true);
  document.addEventListener("dragstart", event => {
    if (event.target.closest("[data-drag-handle], input, textarea, select")) return;
    const slot = event.target.closest("[data-quickslot-index]");
    const source = event.target.closest("[data-quickslot-source]");
    if (!slot && event.target.closest("button, a")) return;
    if (slot) {
      const index = Number(slot.dataset.quickslotIndex);
      if (!slots[index]) { event.preventDefault(); return; }
      drag = { slot: index };
    } else if (source) {
      const d = source.dataset;
      const action = catalog.find(entry => entry.type === d.quickslotSource && entry.id === d.quickslotId
        && ["subentry", "specification", "profile", "mode", "attribute"].every(key => {
          const value = d[`quickslot${key[0].toUpperCase()}${key.slice(1)}`];
          return value === undefined || value === (entry[key] || "");
        }));
      if (!action) { event.preventDefault(); return; }
      drag = { action: normalizeAction(action) };
    } else return;
    event.stopPropagation();
    event.dataTransfer.setData(MIME, JSON.stringify(drag));
    event.dataTransfer.effectAllowed = slot ? "move" : "copy";
    root.classList.add("is-dragging");
    root.classList.remove("is-collapsed");
    toggle.setAttribute("aria-expanded", "true");
  }, true);
  root.addEventListener("dragover", event => {
    const button = event.target.closest("[data-quickslot-index]");
    if (!drag || !button) return;
    event.preventDefault(); event.stopPropagation();
    event.dataTransfer.dropEffect = drag.action ? "copy" : "move";
    buttons.forEach(slot => slot.classList.toggle("is-drop-target", slot === button));
  });
  root.addEventListener("drop", event => {
    const button = event.target.closest("[data-quickslot-index]");
    if (!drag || !button) return;
    event.preventDefault(); event.stopPropagation();
    const index = Number(button.dataset.quickslotIndex);
    if (drag.action) slots[index] = drag.action;
    else moveQuickslot(slots, drag.slot, index);
    persist(); render(); endDrag();
  });
  function endDrag() {
    drag = null;
    root.classList.remove("is-dragging");
    buttons.forEach(button => button.classList.remove("is-drop-target"));
    render();
  }
  document.addEventListener("dragend", endDrag);
  document.addEventListener("charsheet:partials-applied", () => {
    refreshCatalog().catch(error => notify(error.message));
  });
  render();
  refreshCatalog().catch(error => notify(error.message));
  return { activateQuickslot };
}
