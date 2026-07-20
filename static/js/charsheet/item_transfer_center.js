const initEmbeddedItemTransferCenter = () => {
  if (window.parent === window || document.documentElement.dataset.transferCenterBound === "1") {
    return;
  }
  document.documentElement.dataset.transferCenterBound = "1";

  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.hasAttribute("data-transfer-accept")) {
      return;
    }
    event.preventDefault();
    const buttons = Array.from(form.querySelectorAll("button"));
    buttons.forEach((button) => {
      button.disabled = true;
    });

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        credentials: "same-origin",
      });
      const payload = await response.json();
      if (!response.ok || !payload?.ok) {
        throw new Error(payload?.message || "Gegenstand konnte nicht angenommen werden.");
      }
      window.parent.postMessage(
        { type: "codex:item-transfer-accepted", payload },
        window.location.origin,
      );
      window.setTimeout(() => window.location.reload(), 0);
    } catch (error) {
      buttons.forEach((button) => {
        button.disabled = false;
      });
      const message = error instanceof Error ? error.message : "Gegenstand konnte nicht angenommen werden.";
      window.alert(message);
    }
  });
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initEmbeddedItemTransferCenter, { once: true });
} else {
  initEmbeddedItemTransferCenter();
}
