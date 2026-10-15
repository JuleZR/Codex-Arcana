export function initItemTransfers({ windowController = null, eventRoot = document } = {}) {
  const dialog = document.getElementById("itemTransferDialog");
  if (!dialog || dialog.dataset.initialized === "1") return;
  dialog.dataset.initialized = "1";
  const form = document.getElementById("itemTransferForm");
  const search = document.getElementById("itemTransferRecipientSearch");
  const recipientId = document.getElementById("itemTransferRecipientId");
  const recipientType = document.getElementById("itemTransferRecipientType");
  const senderId = document.getElementById("itemTransferSenderId");
  const results = document.getElementById("itemTransferResults");
  const selection = document.getElementById("itemTransferSelection");
  const money = document.getElementById("itemTransferMoney");
  const errorBox = document.getElementById("itemTransferError");
  const permissions = document.getElementById("itemTransferPermissions");
  const originalOwnership = document.getElementById("itemTransferOriginalOwnership");
  let timer = null;
  let selectedRecipientType = "character";

  const selectedItems = () => Array.from(
    selection?.querySelectorAll("[data-transfer-item]:checked") || [],
  );

  const syncPermissionControls = () => {
    if (!permissions) return;
    const chosenItems = selectedItems();
    const canGrantPermissions = chosenItems.length > 0 && chosenItems.every(
      (input) => input.dataset.canGrantPermissions === "1",
    );
    if ((!canGrantPermissions || selectedRecipientType === "gm_group") && originalOwnership) {
      originalOwnership.checked = false;
    }
    const transfersOwnership = Boolean(originalOwnership?.checked);
    permissions.hidden = selectedRecipientType === "gm_group" || !canGrantPermissions;
    permissions.querySelectorAll(".item-transfer-permission-row input").forEach((input) => {
      input.disabled = transfersOwnership || permissions.hidden;
      if (input.disabled) input.checked = false;
    });
    if (originalOwnership) originalOwnership.disabled = permissions.hidden;
    const gmHint = document.getElementById("itemTransferGmHint");
    if (gmHint) gmHint.hidden = selectedRecipientType !== "gm_group";
    permissions.classList.toggle("is-transferring-ownership", transfersOwnership);
  };

  const syncSelection = () => {
    const chosenItems = selectedItems();
    selection?.querySelectorAll(".item-transfer-selection__row").forEach((row) => {
      const checkbox = row.querySelector("[data-transfer-item]");
      const amount = row.querySelector('input[type="number"]');
      const checked = Boolean(checkbox?.checked);
      row.classList.toggle("is-selected", checked);
      if (amount) {
        amount.disabled = !checked;
        amount.readOnly = selectedRecipientType === "gm_group";
        if (checked && amount.readOnly) amount.value = amount.max;
      }
    });
    const names = chosenItems.map((input) => input.dataset.itemName || "");
    document.getElementById("itemTransferName").textContent = names.length > 2
      ? `${names.slice(0, 2).join(", ")} +${names.length - 2}`
      : names.join(", ") || "Noch keine Gegenstände ausgewählt";
    syncPermissionControls();
  };

  eventRoot.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-open-item-transfer]");
    if (trigger) {
      if (document.querySelector("[data-item-transfer-window]")) {
        event.preventDefault();
        document.dispatchEvent(new CustomEvent("charsheet:open-transfer-compose", {
          detail: {
            senderId: trigger.dataset.senderId,
            itemId: trigger.closest("[data-character-item-id]")?.dataset.characterItemId,
          },
        }));
        return;
      }
      form.action = trigger.dataset.action || "";
      senderId.value = trigger.dataset.senderId || "";
      recipientId.value = "";
      if (recipientType) recipientType.value = "character";
      search.value = "";
      results.replaceChildren();
      selectedRecipientType = "character";
      if (money) money.disabled = false;
      errorBox?.toggleAttribute("hidden", true);
      selection?.querySelectorAll("[data-transfer-item]").forEach((input) => {
        input.checked = input.value === trigger.closest("[data-character-item-id]")?.dataset.characterItemId;
      });
      if (permissions) {
        permissions.querySelectorAll('input[type="checkbox"]').forEach((input) => { input.checked = false; });
      }
      syncSelection();
      windowController?.open();
      search.focus();
    }
    if (event.target.closest("[data-close-item-transfer]")) windowController?.close();
    const option = event.target.closest("[data-transfer-recipient]");
    if (option) {
      recipientId.value = option.dataset.transferRecipient;
      const selectedType = option.dataset.transferRecipientType || "character";
      selectedRecipientType = selectedType;
      if (money) {
        money.disabled = selectedType === "gm_group";
        if (money.disabled) money.value = "0";
      }
      if (recipientType) recipientType.value = selectedType;
      if (permissions) {
        if (selectedType === "gm_group") {
          permissions.querySelectorAll('input[type="checkbox"]').forEach((input) => { input.checked = false; });
        }
        syncSelection();
      }
      search.value = option.dataset.label || option.textContent.trim();
      search.setCustomValidity("");
      results.replaceChildren();
    }
  });

  originalOwnership?.addEventListener("change", syncPermissionControls);
  dialog.querySelector("[data-transfer-inventory-search]")?.addEventListener("input", (event) => {
    const query = event.target.value.trim().toLocaleLowerCase("de");
    selection.querySelectorAll(".item-transfer-selection__row").forEach((row) => {
      row.hidden = !row.textContent.toLocaleLowerCase("de").includes(query);
    });
  });
  selection?.addEventListener("change", (event) => {
    if (event.target.matches("[data-transfer-item]")) syncSelection();
  });

  search.addEventListener("input", () => {
    recipientId.value = "";
    selectedRecipientType = "character";
    if (recipientType) recipientType.value = "character";
    if (money) money.disabled = false;
    syncSelection();
    search.setCustomValidity("");
    clearTimeout(timer);
    const query = search.value.trim();
    if (query.length < 2) { results.replaceChildren(); return; }
    timer = setTimeout(async () => {
      try {
        const url = new URL(dialog.dataset.searchUrl, window.location.origin);
        url.searchParams.set("q", query);
        url.searchParams.set("exclude", senderId.value);
        const response = await fetch(url, { headers: { Accept: "application/json" } });
        const payload = await response.json();
        if (!response.ok) throw new Error("Empfängersuche fehlgeschlagen.");
        if (search.value.trim() !== query || !search.isConnected) return;
        results.replaceChildren(...payload.results.map((row) => {
          const button = document.createElement("button");
          button.type = "button";
          button.dataset.transferRecipient = row.id;
          button.dataset.transferRecipientType = row.type || "character";
          button.dataset.label = row.name;
          button.textContent = `${row.name} · ${row.race} · ${row.username}`;
          return button;
        }));
      } catch (_error) {
        if (errorBox && search.value.trim() === query) {
          errorBox.textContent = "Empfängersuche fehlgeschlagen. Bitte erneut suchen.";
          errorBox.hidden = false;
        }
      }
    }, 180);
  });

  form.addEventListener("submit", (event) => {
    errorBox?.toggleAttribute("hidden", true);
    if (!recipientId.value) {
      event.preventDefault();
      search.setCustomValidity("Bitte einen Treffer aus der Liste auswählen.");
      search.reportValidity();
      return;
    }
    if (!selectedItems().length && Number.parseInt(money?.value || "0", 10) < 1) {
      event.preventDefault();
      if (errorBox) {
        errorBox.textContent = "Bitte mindestens einen Gegenstand oder einen Geldbetrag auswählen.";
        errorBox.hidden = false;
      }
    }
    if (selectedRecipientType === "gm_group" && selectedItems().length !== 1) {
      event.preventDefault();
      if (errorBox) {
        errorBox.textContent = "Zur SL-Bearbeitung bitte genau einen Gegenstand auswählen.";
        errorBox.hidden = false;
      }
    }
    if (!event.defaultPrevented && originalOwnership?.checked
      && !window.confirm("Eigentum endgültig übertragen? Der Empfänger erhält dauerhaft Rückholrecht und Rechteverwaltung.")) {
      event.preventDefault();
    }
  });

  form.addEventListener("sheet:action-success", () => {
    selectedItems().forEach((input) => {
      const row = input.closest(".item-transfer-selection__row");
      const amount = row?.querySelector('input[type="number"]');
      const sent = Number.parseInt(amount?.value || "0", 10);
      const available = Number.parseInt(amount?.max || "0", 10);
      if (row && sent >= available) row.remove();
      else if (amount) amount.max = String(Math.max(1, available - sent));
    });
    windowController?.close();
    form.reset();
    results.replaceChildren();
    syncPermissionControls();
  });

  form.addEventListener("sheet:action-failed", (event) => {
    if (!errorBox) return;
    errorBox.textContent = event.detail?.message || "Die Übergabe konnte nicht erstellt werden.";
    errorBox.hidden = false;
  });
  syncSelection();
}
