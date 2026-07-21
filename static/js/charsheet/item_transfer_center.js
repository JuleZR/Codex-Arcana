const initEmbeddedItemTransferCenter = () => {
  if (window.parent === window || document.documentElement.dataset.transferCenterBound === "1") {
    return;
  }
  document.documentElement.dataset.transferCenterBound = "1";

  const transferCenter = document.querySelector(".transfer-center");
  let lastReportedHeight = 0;
  const reportContentHeight = () => {
    if (!transferCenter) return;
    const contentHeight = Math.ceil(transferCenter.getBoundingClientRect().height + 18);
    if (contentHeight === lastReportedHeight) return;
    lastReportedHeight = contentHeight;
    window.parent.postMessage(
      {
        type: "codex:item-transfer-size",
        height: contentHeight,
      },
      window.location.origin,
    );
  };
  window.requestAnimationFrame(reportContentHeight);
  if (transferCenter) new ResizeObserver(reportContentHeight).observe(transferCenter);

  const queuedToasts = Array.from(document.querySelectorAll("[data-transfer-toast]"));
  const showNextToast = () => {
    const toast = queuedToasts.shift();
    if (!toast) return;
    toast.classList.add("is-visible");
    window.setTimeout(() => {
      toast.classList.remove("is-visible");
      window.setTimeout(() => {
        toast.remove();
        showNextToast();
      }, 180);
    }, 2400);
  };
  showNextToast();

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
