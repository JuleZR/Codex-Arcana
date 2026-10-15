const card = document.createElement("dialog");
card.className = "attribute-flavor-card";
card.lang = "de";
card.setAttribute("aria-label", "Eigenschaftsbeschreibung");
card.setAttribute("aria-modal", "false");
card.innerHTML = '<form method="dialog"><button data-attribute-flavor-control aria-label="Schließen">×</button></form>'
  + '<div data-flavor-body aria-live="polite"></div>';
document.body.append(card);
let sequence = 0;
let trigger = null;
let controller = null;

function positionCard() {
  if (!card.open || !trigger?.isConnected) return;
  const anchor = trigger.getBoundingClientRect();
  if (anchor.bottom <= 0 || anchor.top >= window.innerHeight
      || anchor.right <= 0 || anchor.left >= window.innerWidth) {
    card.close();
    return;
  }
  const bounds = card.getBoundingClientRect();
  const inset = 12;
  const gap = 12;
  const clamp = (value, maximum) => Math.max(inset, Math.min(value, maximum));
  let left;
  let top;
  let side;
  if (anchor.right + gap + bounds.width <= window.innerWidth - inset) {
    left = anchor.right + gap;
    top = anchor.top + anchor.height / 2 - bounds.height / 2;
    side = "left";
  } else if (anchor.left - gap - bounds.width >= inset) {
    left = anchor.left - gap - bounds.width;
    top = anchor.top + anchor.height / 2 - bounds.height / 2;
    side = "right";
  } else {
    left = anchor.left + anchor.width / 2 - bounds.width / 2;
    const below = window.innerHeight - anchor.bottom;
    const above = anchor.top;
    const useBelow = below >= bounds.height + gap + inset || below >= above;
    top = useBelow ? anchor.bottom + gap : anchor.top - bounds.height - gap;
    side = useBelow ? "top" : "bottom";
  }
  left = clamp(left, window.innerWidth - bounds.width - inset);
  top = clamp(top, window.innerHeight - bounds.height - inset);
  card.style.left = `${left}px`;
  card.style.top = `${top}px`;
  card.dataset.anchorSide = side;
  card.style.setProperty("--flavor-anchor-x", `${Math.max(18, Math.min(bounds.width - 18, anchor.left + anchor.width / 2 - left))}px`);
  card.style.setProperty("--flavor-anchor-y", `${Math.max(18, Math.min(bounds.height - 18, anchor.top + anchor.height / 2 - top))}px`);
}

async function openCard(cell) {
  const panel = cell.closest("[data-flavor-url]");
  const row = cell.closest("[data-attribute-short-name]");
  if (!panel || !row) return;
  trigger = cell;
  controller?.abort();
  controller = new AbortController();
  const requestSequence = ++sequence;
  const value = cell.textContent.trim();
  const body = card.querySelector("[data-flavor-body]");
  try {
    let result;
    try {
      result = JSON.parse(row.querySelector("script[type='application/json']")?.textContent || "null");
    } catch (_error) {
      result = null;
    }
    // An optimistic temporary adjustment may precede its updated panel.
    // Never show the pre-rendered portrait for a different displayed value.
    if (!result || String(result.value) !== value) {
      const url = new URL(panel.dataset.flavorUrl, window.location.href);
      url.searchParams.set("attribute", row.dataset.attributeShortName);
      url.searchParams.set("value", value);
      if (panel.dataset.flavorGroup) url.searchParams.set("group", panel.dataset.flavorGroup);
      const response = await fetch(url, {
        credentials: "same-origin", signal: controller.signal,
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("Beschreibung konnte nicht geladen werden.");
      result = await response.json();
    }
    if (requestSequence !== sequence) return;
    card.setAttribute("aria-label", `${result.attribute} — ${result.value}`);
    body.replaceChildren();
    for (const [html, className] of [
      [result.designation_html || (!result.absolute_html ? result.meaning_html : ""), "attribute-flavor-designation"],
      [result.absolute_html, "attribute-flavor-absolute"],
      [result.relative_html, "attribute-flavor-relative"],
    ]) {
      if (!html) continue;
      const section = document.createElement("div");
      section.className = className;
      // Only the server's existing HTML-disabled Markdown renderer supplies HTML.
      section.innerHTML = html;
      if (!section.textContent.trim()) continue;
      body.append(section);
    }
    if (!body.childNodes.length) {
      if (card.open) card.close();
      return;
    }
    if (!card.open) card.show();
    positionCard();
  } catch (error) {
    if (error.name !== "AbortError" && requestSequence === sequence) {
      if (card.open) card.close();
    }
  }
}

document.addEventListener("click", (event) => {
  const cell = event.target.closest("[data-attribute-flavor]");
  if (cell) openCard(cell);
  else if (!card.contains(event.target)) {
    ++sequence;
    controller?.abort();
    if (card.open) card.close();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && card.open) {
    event.preventDefault();
    card.close();
    return;
  }
  if (!["Enter", " "].includes(event.key)) return;
  const cell = event.target.closest("[data-attribute-flavor]");
  if (cell) {
    event.preventDefault();
    openCard(cell);
  }
});
card.addEventListener("close", () => {
  ++sequence;
  controller?.abort();
  if (card.contains(document.activeElement) || document.activeElement === document.body) trigger?.focus();
});
window.addEventListener("resize", positionCard);
document.addEventListener("scroll", positionCard, true);
card.addEventListener("toggle", positionCard, true);
document.addEventListener("charsheet:partials-applied", () => {
  ++sequence;
  controller?.abort();
  if (card.open) card.close();
});
