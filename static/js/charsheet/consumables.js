export async function resolveConsumableRolls(payload, { rollDice, manual }) {
  if (!payload.resolutionRequired) return {};
  if (rollDice) {
    try {
      const results = {};
      for (const roll of payload.rolls) {
        const result = await rollDice(roll.faces, roll.count);
        if (!Number.isInteger(result.total) || result.total < roll.min || result.total > roll.max) {
          throw new Error("Ungültiges Würfelergebnis.");
        }
        results[roll.key] = result.total;
      }
      return results;
    } catch (_error) {
      // No consume request has been made; resolve every effect manually.
    }
  }
  return manual(payload);
}

export function manualConsumableResults(payload) {
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    dialog.className = "consumable-dialog";
    dialog.setAttribute("aria-labelledby", "consumable-dialog-title");
    const form = document.createElement("form");
    const title = document.createElement("h3");
    title.id = "consumable-dialog-title";
    title.textContent = `${payload.itemName} verwenden`;
    form.append(title);
    const inputs = [];
    for (const roll of payload.rolls) {
      const label = document.createElement("label");
      label.textContent = `${roll.label} – Würfelergebnis:`;
      const input = document.createElement("input");
      input.type = "number";
      input.inputMode = "numeric";
      input.min = String(roll.min);
      input.max = String(roll.max);
      input.step = "1";
      input.required = true;
      label.append(input);
      form.append(label);
      inputs.push([roll.key, input]);
    }
    const actions = document.createElement("div");
    actions.className = "consumable-dialog-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = "Abbrechen";
    cancel.addEventListener("click", () => dialog.close());
    const confirm = document.createElement("button");
    confirm.type = "submit";
    confirm.textContent = "Verwenden";
    actions.append(cancel, confirm);
    form.append(actions);
    dialog.append(form);
    document.body.append(dialog);
    let results = null;
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      results = Object.fromEntries(inputs.map(([key, input]) => [key, input.value]));
      dialog.close();
    });
    dialog.addEventListener("close", () => {
      dialog.remove();
      resolve(results);
    }, { once: true });
    dialog.showModal();
    inputs[0]?.[1].focus();
  });
}

export async function prepareConsumable(form, formData) {
  const probe = new FormData(form);
  probe.set("prepare", "1");
  const response = await fetch(form.getAttribute("action"), {
    method: "POST", body: probe, credentials: "same-origin",
    headers: { "X-Requested-With": "XMLHttpRequest", Accept: "application/json" },
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) throw new Error(payload.error || "Verbrauch nicht möglich.");
  const results = await resolveConsumableRolls(payload, {
    rollDice: document.getElementById("dddice-config") ? window.characterDice?.rollDice : null,
    manual: manualConsumableResults,
  });
  if (results === null) return false;
  for (const [key, value] of Object.entries(results)) formData.set(key, value);
  return true;
}
