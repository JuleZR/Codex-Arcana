export function initItemTransfers({ windowController = null } = {}) {
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
      input.disabled = transfersOwnership;
      if (transfersOwnership) input.checked = false;
    });
    permissions.classList.toggle("is-transferring-ownership", transfersOwnership);
  };

  const syncSelection = () => {
    const chosenItems = selectedItems();
    selection?.querySelectorAll(".item-transfer-selection__row").forEach((row) => {
      const checkbox = row.querySelector("[data-transfer-item]");
      const amount = row.querySelector('input[type="number"]');
      const checked = Boolean(checkbox?.checked);
      row.classList.toggle("is-selected", checked);
      if (amount) amount.disabled = !checked;
    });
    const names = chosenItems.map((input) => input.dataset.itemName || "");
    document.getElementById("itemTransferName").textContent = names.length > 2
      ? `${names.slice(0, 2).join(", ")} +${names.length - 2}`
      : names.join(", ");
    syncPermissionControls();
  };

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-open-item-transfer]");
    if (trigger) {
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
        syncPermissionControls();
      }
      search.value = option.dataset.label || option.textContent.trim();
      results.replaceChildren();
    }
  });

  originalOwnership?.addEventListener("change", syncPermissionControls);
  selection?.addEventListener("change", (event) => {
    if (event.target.matches("[data-transfer-item]")) syncSelection();
  });

  search.addEventListener("input", () => {
    recipientId.value = "";
    search.setCustomValidity("");
    clearTimeout(timer);
    const query = search.value.trim();
    if (query.length < 2) { results.replaceChildren(); return; }
    timer = setTimeout(async () => {
      const url = new URL(dialog.dataset.searchUrl, window.location.origin);
      url.searchParams.set("q", query);
      url.searchParams.set("exclude", senderId.value);
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      const payload = await response.json();
      results.replaceChildren(...payload.results.map((row) => {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.transferRecipient = row.id;
        button.dataset.transferRecipientType = row.type || "character";
        button.dataset.label = row.name;
        button.textContent = `${row.name} · ${row.race} · ${row.username}`;
        return button;
      }));
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
}
