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
  const quantity = document.getElementById("itemTransferQuantity");
  const permissions = document.getElementById("itemTransferPermissions");
  const originalOwnership = document.getElementById("itemTransferOriginalOwnership");
  let timer = null;
  let canGrantPermissions = false;

  const syncPermissionControls = () => {
    if (!permissions) return;
    const transfersOwnership = Boolean(originalOwnership?.checked);
    permissions.querySelectorAll(".item-transfer-permission-row input").forEach((input) => {
      input.disabled = transfersOwnership;
      if (transfersOwnership) input.checked = false;
    });
    permissions.classList.toggle("is-transferring-ownership", transfersOwnership);
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
      quantity.max = trigger.dataset.itemAmount || "1";
      quantity.value = "1";
      quantity.closest("label")?.removeAttribute("hidden");
      canGrantPermissions = trigger.dataset.canGrantPermissions === "1";
      if (permissions) {
        permissions.hidden = !canGrantPermissions;
        permissions.querySelectorAll('input[type="checkbox"]').forEach((input) => { input.checked = false; });
        syncPermissionControls();
      }
      document.getElementById("itemTransferName").textContent = trigger.dataset.itemName || "";
      windowController?.open();
      search.focus();
    }
    if (event.target.closest("[data-close-item-transfer]")) windowController?.close();
    const option = event.target.closest("[data-transfer-recipient]");
    if (option) {
      recipientId.value = option.dataset.transferRecipient;
      const selectedType = option.dataset.transferRecipientType || "character";
      if (recipientType) recipientType.value = selectedType;
      quantity.closest("label")?.toggleAttribute("hidden", selectedType === "gm_group");
      if (permissions) {
        permissions.hidden = selectedType === "gm_group" || !canGrantPermissions;
        if (selectedType === "gm_group") {
          permissions.querySelectorAll('input[type="checkbox"]').forEach((input) => { input.checked = false; });
        }
      }
      search.value = option.dataset.label || option.textContent.trim();
      results.replaceChildren();
    }
  });

  originalOwnership?.addEventListener("change", syncPermissionControls);

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
    if (!recipientId.value) {
      event.preventDefault();
      search.setCustomValidity("Bitte einen Treffer aus der Liste auswählen.");
      search.reportValidity();
    }
  });
}
