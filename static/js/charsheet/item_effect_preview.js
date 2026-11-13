import { renderInlineMarkdown, syncTooltipCardLayout } from "./tooltip.js?v=20261113-counter-preview2";

export function createItemEffectPreview({ form, payloadInput, getInvestedCp, cardTarget, cardStatus, getCardFields = () => ({}) }) {
  let targets = [];
  let currentSignature = "";
  let completedSignature = "";
  let previews = [];
  let itemCardHtml = "";
  let revision = 0;
  let timer;
  let controller;
  let previewCard;
  const fitCard = () => {
    if (!previewCard || !cardTarget.clientHeight) return;
    syncTooltipCardLayout(previewCard, {
      maxHeight: previewCard.offsetWidth * 297 / 210,
    });
    const scale = Math.min(
      1,
      cardTarget.clientWidth / previewCard.offsetWidth,
      cardTarget.clientHeight / previewCard.offsetHeight,
    );
    previewCard.style.transform = `scale(${scale})`;
  };
  const cardResizeObserver = cardTarget && typeof ResizeObserver !== "undefined"
    ? new ResizeObserver(fitCard) : null;
  cardResizeObserver?.observe(cardTarget);

  const status = (message) => {
    targets.forEach((target) => { target.textContent = message; });
    if (cardStatus) cardStatus.textContent = message;
  };
  const renderLines = (target, lines) => {
    if (!lines.length) {
      target.textContent = "Keine sichtbare Kartenwirkung.";
      return;
    }
    target.innerHTML = lines.map((line) => renderInlineMarkdown(line)).join("<br>");
  };
  const render = () => {
    targets.forEach((target, index) => renderLines(target, previews[index] || []));
    if (cardStatus) cardStatus.textContent = "";
    if (cardTarget) {
      if (previewCard) cardResizeObserver?.unobserve(previewCard);
      cardTarget.innerHTML = itemCardHtml;
      previewCard = cardTarget.querySelector?.("[data-shared-item-card]");
      if (previewCard) cardResizeObserver?.observe(previewCard);
      fitCard();
    }
  };

  const cancel = () => {
    clearTimeout(timer);
    controller?.abort();
    revision += 1;
    currentSignature = "";
    if (cardStatus) cardStatus.textContent = "";
  };
  const update = (nextTargets = targets) => {
    targets = nextTargets;
    if (!targets.length && !cardTarget) {
      cancel();
      return;
    }
    if (!form?.action || !payloadInput) return;
    const investedCp = String(getInvestedCp() || "0");
    const payload = payloadInput.value;
    const cardFields = cardTarget ? getCardFields() : {};
    const signature = JSON.stringify([form.action, investedCp, payload, cardFields]);
    const changed = signature !== currentSignature;
    if (changed) {
      currentSignature = signature;
      revision += 1;
      clearTimeout(timer);
      controller?.abort();
    }
    if (signature === completedSignature) {
      render();
      return;
    }
    status("Vorschau wird aktualisiert …");
    if (!changed) return;
    const requestRevision = revision;
    timer = setTimeout(async () => {
      controller = new AbortController();
      const body = new URLSearchParams();
      Object.entries(cardFields).forEach(([key, value]) => {
        (Array.isArray(value) ? value : [value]).forEach((entry) => body.append(key, entry));
      });
      Object.entries({
        include_item_card: cardTarget ? "1" : "",
        csrfmiddlewaretoken: form.querySelector("[name='csrfmiddlewaretoken']")?.value || "",
        magic_modifier_payloads: payload,
        invested_cp: investedCp,
      }).forEach(([key, value]) => body.set(key, value));
      try {
        const response = await fetch(form.dataset?.effectPreviewUrl || form.action.replace(/runes\/update\/$/, "effects/preview/"), {
          method: "POST",
          credentials: "same-origin",
          headers: { "X-Requested-With": "XMLHttpRequest" },
          body,
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("preview_failed");
        const result = await response.json();
        if (requestRevision !== revision) return;
        if (!Array.isArray(result.previews)) throw new Error("invalid_preview");
        if (cardTarget && typeof result.item_card_html !== "string") throw new Error("invalid_card_preview");
        previews = result.previews;
        itemCardHtml = result.item_card_html || "";
        completedSignature = signature;
        render();
      } catch (error) {
        if (requestRevision === revision && error.name !== "AbortError") {
          currentSignature = "";
          status("Vorschau momentan nicht verfügbar.");
        }
      }
    }, 180);
  };
  update.cancel = cancel;
  return update;
}
