import { escapeHtml } from "./utils.js";

function parseTableRow(line) {
  const trimmed = String(line || "").trim();
  if (!trimmed.includes("|")) {
    return [];
  }
  const content = trimmed.replace(/^\|/, "").replace(/\|$/, "");
  const cells = [];
  let current = "";
  let escaped = false;

  for (const char of content) {
    if (escaped) {
      current += char;
      escaped = false;
      continue;
    }
    if (char === "\\") {
      escaped = true;
      continue;
    }
    if (char === "|") {
      cells.push(current.trim());
      current = "";
      continue;
    }
    current += char;
  }

  if (escaped) {
    current += "\\";
  }
  cells.push(current.trim());
  return cells;
}

function isTableDividerRow(row) {
  return row.length > 0 && row.every((cell) => /^:?-{2,}:?$/.test(cell));
}

function parseQualityLine(line) {
  const match = String(line || "").trim().match(/^\[\[QUALITY:(.+?)\|(.+?)\]\]$/);
  if (!match) {
    return null;
  }
  return { label: match[1].trim(), color: match[2].trim() };
}

function parseStatusLine(line) {
  const match = String(line || "").trim().match(/^\[\[STATUS:(.+?)\|(.+?)\]\]$/);
  if (!match) {
    return null;
  }
  return { label: match[1].trim(), color: match[2].trim() };
}

function parseRuneLine(line) {
  const match = String(line || "").trim().match(/^\[\[RUNE:(.*?)\|(.*?)\|(.*?)\]\]$/);
  if (!match) {
    return null;
  }
  return {
    name: match[1].trim(),
    description: match[2].trim(),
    image: match[3].trim(),
  };
}

function parseRuneSocketLine(line) {
  const match = String(line || "").trim().match(/^\[\[RUNESOCKET:(.*?)::(.*?)\]\]$/);
  if (!match) {
    return null;
  }
  return {
    name: match[1].trim(),
    image: match[2].trim(),
  };
}

function parseRuneInline(line) {
  const match = String(line || "").trim().match(/^\[\[RUNEINLINE:(.+?)\|(.*?)\|(.*?)\]\]$/);
  if (!match) {
    const legacyMatch = String(line || "").trim().match(/^\[\[RUNEINLINE:(.+?)\|(.*)\]\]$/);
    if (!legacyMatch) {
      return null;
    }
    return {
      name: legacyMatch[1].trim(),
      description: legacyMatch[2].trim(),
      image: "",
    };
  }
  return {
    name: match[1].trim(),
    description: match[2].trim(),
    image: match[3].trim(),
  };
}

function renderInlineMarkdown(text) {
  let html = escapeHtml(String(text || ""));
  html = html.replace(/\[\[EMPTY\]\]/g, "&nbsp;");
  html = html.replace(/\[\[RUNEINLINE:(.+?)\|(.*?)\|(.*?)\]\]/g, (_match, name, description, image) => {
    const safeName = escapeHtml(String(name || "").trim() || "Rune");
    const safeDescription = escapeHtml(String(description || "").trim());
    const safeImage = escapeHtml(String(image || "").trim());
    const imageHtml = safeImage
      ? `<img class="tooltip_rune_inline_image" src="${safeImage}" alt="">`
      : '<span class="tooltip_rune_inline_image tooltip_rune_inline_image--placeholder" aria-hidden="true"></span>';
    const copyHtml = safeDescription
      ? `<span class="tooltip_rune_inline_name"><strong>${safeName} &middot;</strong> ${safeDescription}</span>`
      : `<span class="tooltip_rune_inline_name"><strong>${safeName}</strong></span>`;
    return `<span class="tooltip_rune_inline">${imageHtml}${copyHtml}</span>`;
  });
  html = html.replace(/\[\[RUNEINLINE:(.+?)\|(.*)\]\]/g, (_match, name, description) => {
    const safeName = escapeHtml(String(name || "").trim() || "Rune");
    const safeDescription = escapeHtml(String(description || "").trim());
    const copyHtml = safeDescription
      ? `<span class="tooltip_rune_inline_name"><strong>${safeName} &middot;</strong> ${safeDescription}</span>`
      : `<span class="tooltip_rune_inline_name"><strong>${safeName}</strong></span>`;
    return `<span class="tooltip_rune_inline"><span class="tooltip_rune_inline_image tooltip_rune_inline_image--placeholder" aria-hidden="true"></span>${copyHtml}</span>`;
  });
  html = html.replace(
    /\[\[QUALITY:(.+?)\|(.+?)\]\]/g,
    '<span class="tooltip_quality_badge" style="--tooltip-quality-color: $2;">$1</span>',
  );
  html = html.replace(
    /\[\[STATUS:(.+?)\|(.+?)\]\]/g,
    '<span class="tooltip_status_badge" style="--tooltip-status-color: $2;">$1</span>',
  );
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  html = html.replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,!?:;]|$)/g, "$1<em>$2</em>");
  html = html.replace(/(^|[\s(])_([^_\n]+)_(?=[\s).,!?:;]|$)/g, "$1<em>$2</em>");
  html = html.replace(/\[\[SUB:(.+?)\]\]/g, '<span class="tooltip_sub">$1</span>');
  return html;
}

function renderRuneMarkup(runes) {
  return `<div class="tooltip_rune_list">${runes.map((rune) => {
    const imageHtml = rune.image
      ? `<img class="tooltip_rune_image" src="${escapeHtml(rune.image)}" alt="">`
      : '<span class="tooltip_rune_image tooltip_rune_image--placeholder" aria-hidden="true"></span>';
    return `<div class="tooltip_rune_row">${imageHtml}<div class="tooltip_rune_name">${escapeHtml(rune.name || "Rune")}</div></div>`;
  }).join("")}</div>`;
}

function renderRuneSocketMarkup(runes) {
  return `<div class="tooltip_rune_sockets">${runes.map((rune) => {
    const safeName = escapeHtml(rune.name || "");
    const imageHtml = rune.image
      ? `<img class="tooltip_rune_socket_image" src="${escapeHtml(rune.image)}" alt="">`
      : '<span class="tooltip_rune_socket_image tooltip_rune_socket_image--placeholder" aria-hidden="true"></span>';
    return `<div class="tooltip_rune_socket"${safeName ? ` title="${safeName}"` : ""}>${imageHtml}</div>`;
  }).join("")}</div>`;
}

function isEffectTableRow(row) {
  if (!Array.isArray(row) || row.length < 2) {
    return false;
  }
  const label = String(row[0] || "").trim();
  return label === "Effekt" || label === "Effekte" || label === "" || label === "[[EMPTY]]";
}

function isRuneTableRow(row) {
  if (!Array.isArray(row) || row.length < 2) {
    return false;
  }
  const label = String(row[0] || "").trim();
  return label === "Rune" || label === "Runen" || Boolean(parseRuneInline(row[1]));
}

function startsStructuredBlock(line, nextLine = "") {
  const trimmed = String(line || "").trim();
  if (!trimmed) {
    return false;
  }
  if (parseQualityLine(trimmed) || parseStatusLine(trimmed) || parseRuneLine(trimmed) || parseRuneSocketLine(trimmed)) {
    return true;
  }
  if (/^\s*[-*]\s+/.test(trimmed)) {
    return true;
  }
  const header = parseTableRow(trimmed);
  const divider = parseTableRow(nextLine);
  return header.length > 0 && header.length === divider.length && isTableDividerRow(divider);
}

function renderTooltipMarkup(rawText) {
  const text = String(rawText || "").trim();
  if (!text) {
    return "";
  }

  const lines = text.split("\n");
  const chunks = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    const qualityMeta = parseQualityLine(line);
    if (qualityMeta) {
      chunks.push(
        `<p class="tooltip_quality_line"><span class="tooltip_quality_badge" style="--tooltip-quality-color: ${escapeHtml(qualityMeta.color)};">${escapeHtml(qualityMeta.label)}</span></p>`,
      );
      index += 1;
      continue;
    }

    const statusMeta = parseStatusLine(line);
    if (statusMeta) {
      chunks.push(
        `<p class="tooltip_status_line"><span class="tooltip_status_badge" style="--tooltip-status-color: ${escapeHtml(statusMeta.color)};">${escapeHtml(statusMeta.label)}</span></p>`,
      );
      index += 1;
      continue;
    }

    const runeMeta = parseRuneLine(line);
    if (runeMeta) {
      const runeRows = [];
      let rowIndex = index;
      while (rowIndex < lines.length) {
        const runeRow = parseRuneLine(lines[rowIndex]);
        if (!runeRow) {
          break;
        }
        runeRows.push(runeRow);
        rowIndex += 1;
      }
      chunks.push(renderRuneMarkup(runeRows));
      index = rowIndex;
      continue;
    }

    const runeSocketMeta = parseRuneSocketLine(line);
    if (runeSocketMeta) {
      const runeSockets = [];
      let rowIndex = index;
      while (rowIndex < lines.length) {
        const runeSocketRow = parseRuneSocketLine(lines[rowIndex]);
        if (!runeSocketRow) {
          break;
        }
        runeSockets.push(runeSocketRow);
        rowIndex += 1;
      }
      chunks.push(renderRuneSocketMarkup(runeSockets));
      index = rowIndex;
      continue;
    }

    const header = parseTableRow(line);
    const divider = index + 1 < lines.length ? parseTableRow(lines[index + 1]) : [];
    if (header.length > 0 && header.length === divider.length && isTableDividerRow(divider)) {
      let rowIndex = index + 2;
      const bodyRows = [];
      while (rowIndex < lines.length) {
        const row = parseTableRow(lines[rowIndex]);
        if (!row.length || row.length !== header.length) {
          break;
        }
        bodyRows.push(row);
        rowIndex += 1;
      }

      let tableHtml = "<table><thead><tr>";
      header.forEach((cell) => {
        tableHtml += `<th>${escapeHtml(cell)}</th>`;
      });
      tableHtml += "</tr></thead>";
        if (bodyRows.length) {
          tableHtml += "<tbody>";
          bodyRows.forEach((row) => {
            const rowClass = isEffectTableRow(row)
              ? "tooltip_effect_row"
              : isRuneTableRow(row)
                ? "tooltip_rune_comment_row"
                : "";
            tableHtml += rowClass ? `<tr class="${rowClass}">` : "<tr>";
            row.forEach((cell) => {
              tableHtml += `<td>${renderInlineMarkdown(cell)}</td>`;
            });
            tableHtml += "</tr>";
          });
        tableHtml += "</tbody>";
      }
      tableHtml += "</table>";
      chunks.push(tableHtml);
      index = rowIndex;
      continue;
    }

    if (/^\s*[-*]\s+/.test(line)) {
      const listItems = [];
      let listIndex = index;
      while (listIndex < lines.length && /^\s*[-*]\s+/.test(lines[listIndex])) {
        listItems.push(lines[listIndex].replace(/^\s*[-*]\s+/, ""));
        listIndex += 1;
      }
      chunks.push(
        `<ul>${listItems.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</ul>`,
      );
      index = listIndex;
      continue;
    }

    const paragraphLines = [];
    let rowIndex = index;
    while (rowIndex < lines.length) {
      const currentLine = lines[rowIndex];
      const nextLine = rowIndex + 1 < lines.length ? lines[rowIndex + 1] : "";
      if (rowIndex > index && startsStructuredBlock(currentLine, nextLine)) {
        break;
      }
      if (!String(currentLine).trim()) {
        paragraphLines.push("");
      } else {
        paragraphLines.push(renderInlineMarkdown(currentLine));
      }
      rowIndex += 1;
    }
    chunks.push(`<p>${paragraphLines.join("<br>")}</p>`);
    index = rowIndex;
  }

  return chunks.join("");
}

function splitTooltipMarkup(markup) {
  const template = document.createElement("template");
  template.innerHTML = String(markup || "").trim();
  const children = Array.from(template.content.childNodes).filter((node) => (
    node.nodeType === Node.ELEMENT_NODE
    || (node.nodeType === Node.TEXT_NODE && String(node.textContent || "").trim())
  ));
  const firstTableIndex = children.findIndex((node) => node instanceof HTMLElement && node.tagName === "TABLE");
  if (firstTableIndex === -1) {
    return { leadHtml: "", loreHtml: markup };
  }
  const toHtml = (nodes) => nodes.map((node) => {
    if (node instanceof HTMLElement) {
      return node.outerHTML;
    }
    return escapeHtml(String(node.textContent || ""));
  }).join("");
  return {
    leadHtml: toHtml(children.slice(0, firstTableIndex + 1)),
    loreHtml: toHtml(children.slice(firstTableIndex + 1)),
  };
}

function normalizeInlineText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function createTooltipCardTableMarkup(table, rows, { includeHead = true } = {}) {
  if (!(table instanceof HTMLTableElement) || !Array.isArray(rows) || !rows.length) {
    return "";
  }
  const headHtml = includeHead && table.tHead ? table.tHead.outerHTML : "";
  const bodyHtml = `<tbody>${rows.map((row) => row.outerHTML).join("")}</tbody>`;
  return `<table>${headHtml}${bodyHtml}</table>`;
}

function normalizeTooltipSectionRows(rows, sectionLabel) {
  return rows.map((row, index) => {
    const clone = row.cloneNode(true);
    const firstCell = clone.cells[0];
    if (firstCell && normalizeInlineText(firstCell.textContent || "") === normalizeInlineText(sectionLabel) && index === 0) {
      firstCell.innerHTML = "&nbsp;";
    }
    return clone;
  });
}

function buildTooltipCardSections(markup) {
  const template = document.createElement("template");
  template.innerHTML = String(markup || "").trim();
  const table = template.content.querySelector("table");
  if (!(table instanceof HTMLTableElement) || !(table.tBodies[0] instanceof HTMLTableSectionElement)) {
    return splitTooltipMarkup(markup);
  }

  const topRows = [];
  const effectRows = [];
  const runeRows = [];
  let activeSection = "";
  Array.from(table.tBodies[0].rows).forEach((row) => {
    const label = normalizeInlineText(row.cells[0]?.textContent || "");
    if (label === "Effekt" || label === "Effekte") {
      activeSection = "effects";
      effectRows.push(row.cloneNode(true));
      return;
    }
    if (label === "Rune" || label === "Runen") {
      activeSection = "runes";
      runeRows.push(row.cloneNode(true));
      return;
    }
    if (!label && activeSection === "effects") {
      effectRows.push(row.cloneNode(true));
      return;
    }
    if (!label && activeSection === "runes") {
      runeRows.push(row.cloneNode(true));
      return;
    }
    activeSection = "";
    topRows.push(row.cloneNode(true));
  });

  const extras = [];
  const normalizedEffectRows = normalizeTooltipSectionRows(effectRows, "Effekte");
  const normalizedRuneRows = normalizeTooltipSectionRows(runeRows, "Runen");
  const emptySectionMarkup = '<p class="floating-tooltip-card__empty">Keine</p>';
  extras.push(`
    <section class="floating-tooltip-card__section">
      <h4 class="floating-tooltip-card__section_title">Effekte</h4>
      <div class="floating-tooltip-card__section_body">${createTooltipCardTableMarkup(table, normalizedEffectRows, { includeHead: false }) || emptySectionMarkup}</div>
    </section>
  `);
  extras.push(`
    <section class="floating-tooltip-card__section">
      <h4 class="floating-tooltip-card__section_title">Runen</h4>
      <div class="floating-tooltip-card__section_body">${createTooltipCardTableMarkup(table, normalizedRuneRows, { includeHead: false }) || emptySectionMarkup}</div>
    </section>
  `);

  Array.from(template.content.childNodes).forEach((node) => {
    if (node === table) {
      return;
    }
    if (node instanceof HTMLElement) {
      extras.push(node.outerHTML);
      return;
    }
    if (node.nodeType === Node.TEXT_NODE && String(node.textContent || "").trim()) {
      extras.push(`<p>${escapeHtml(String(node.textContent || "").trim())}</p>`);
    }
  });

  return {
    leadHtml: createTooltipCardTableMarkup(table, topRows) || table.outerHTML,
    extraHtml: extras.join(""),
  };
}

function buildTooltipCardMarkup({ title, subtitle, image, accent, bodyMarkup }) {
  const { leadHtml, extraHtml } = buildTooltipCardSections(bodyMarkup);
  const safeTitle = escapeHtml(title || "Details");
  const safeSubtitle = escapeHtml(subtitle || "");
  const safeImage = escapeHtml(image || "");
  const safeAccent = escapeHtml(accent || "");
  const mediaHtml = safeImage
    ? `<div class="floating-tooltip-card__media"><img class="floating-tooltip-card__image" src="${safeImage}" alt=""></div>`
    : "";
  return `
    <div class="floating-tooltip-card__frame"${safeAccent ? ` style="--tooltip-card-accent: ${safeAccent};"` : ""}>
      <div class="floating-tooltip-card__header" data-tooltip-card-drag-handle>
        <div class="floating-tooltip-card__heading">
          <h3 class="floating-tooltip-card__title">${safeTitle}</h3>
          ${safeSubtitle ? `<p class="floating-tooltip-card__subtitle">${safeSubtitle}</p>` : ""}
        </div>
        <button type="button" class="floating-tooltip-card__close" data-tooltip-card-close aria-label="Details schließen">x</button>
      </div>
      <div class="floating-tooltip-card__content${safeImage ? " has-media" : ""}">
        ${mediaHtml}
        <div class="floating-tooltip-card__details">${leadHtml || bodyMarkup}</div>
      </div>
      ${extraHtml ? `<section class="floating-tooltip-card__lore">${extraHtml}</section>` : ""}
    </div>
  `;
}

function syncTooltipCardMediaHeight(card) {
  if (!(card instanceof HTMLElement)) {
    return;
  }
  const content = card.querySelector(".floating-tooltip-card__content.has-media");
  const media = card.querySelector(".floating-tooltip-card__media");
  const details = card.querySelector(".floating-tooltip-card__details");
  if (!(content instanceof HTMLElement) || !(media instanceof HTMLElement) || !(details instanceof HTMLElement)) {
    return;
  }
  const frame = card.querySelector(".floating-tooltip-card__frame");
  const detailsHeight = details.offsetHeight;
  const frameHeight = frame instanceof HTMLElement ? frame.offsetHeight : 0;
  const preferredSize = frameHeight > 0
    ? Math.round(frameHeight / 3)
    : Math.round(detailsHeight * 0.72);
  if (preferredSize > 0 || detailsHeight > 0) {
    const clampedSize = Math.min(Math.max(preferredSize || detailsHeight, 150), 260);
    card.style.setProperty("--tooltip-card-media-size", `${clampedSize}px`);
    media.style.width = `${clampedSize}px`;
    media.style.height = `${clampedSize}px`;
    media.style.maxHeight = `${clampedSize}px`;
    return;
  }
  card.style.removeProperty("--tooltip-card-media-size");
  media.style.width = "";
  media.style.height = "";
  media.style.maxHeight = "";
}

export function initTooltips() {
  const dbAnchors = document.querySelectorAll(".db_tooltip_anchor[data-db-tooltip]");
  dbAnchors.forEach((anchor) => {
    const text = anchor.getAttribute("data-db-tooltip") || "";
    if (!text.trim()) {
      return;
    }
    anchor.classList.add("tooltip_target");
    if (!anchor.getAttribute("data-tooltip")) {
      anchor.setAttribute("data-tooltip", text);
    }
    if (!anchor.getAttribute("data-tooltip-side")) {
      anchor.setAttribute("data-tooltip-side", "right");
    }
    anchor.removeAttribute("data-db-tooltip");
  });

  if (document.body.dataset.tooltipBound === "1") {
    return;
  }
  document.body.dataset.tooltipBound = "1";

  const tooltip = document.createElement("div");
  tooltip.className = "floating-tooltip";
  document.body.appendChild(tooltip);

  const card = document.createElement("div");
  card.className = "floating-tooltip-card";
  document.body.appendChild(card);

  const SHOW_DELAY_MS = 1100;
  const HIDE_HOLD_MS = 380;
  let activeTarget = null;
  let activeCardTarget = null;
  let pendingTarget = null;
  let showTimeoutId = null;
  let hideTimeoutId = null;
  let lastMouseX = 0;
  let lastMouseY = 0;
  let dragPointerId = null;
  let dragOffsetX = 0;
  let dragOffsetY = 0;

  document.addEventListener("mousemove", (event) => {
    lastMouseX = event.clientX;
    lastMouseY = event.clientY;
    if (
      activeTarget
      && (activeTarget.getAttribute("data-tooltip-side") || "left") === "cursor-right"
      && tooltip.classList.contains("is-visible")
    ) {
      positionTooltip(activeTarget);
    }
  }, { passive: true });

  const clearShowTimer = () => {
    if (showTimeoutId) {
      window.clearTimeout(showTimeoutId);
      showTimeoutId = null;
    }
  };

  const closeCard = () => {
    card.classList.remove("is-visible", "is-dragging");
    card.innerHTML = "";
    activeCardTarget = null;
    dragPointerId = null;
  };

  const scheduleHide = () => {
    if (hideTimeoutId) {
      window.clearTimeout(hideTimeoutId);
    }
    hideTimeoutId = window.setTimeout(() => {
      tooltip.classList.remove("is-visible");
      activeTarget = null;
      pendingTarget = null;
      hideTimeoutId = null;
    }, HIDE_HOLD_MS);
  };

  const positionTooltip = (target) => {
    const gap = 10;
    const viewportPadding = 8;
    const tooltipRect = tooltip.getBoundingClientRect();
    const preferredSide = target.getAttribute("data-tooltip-side") || "left";

    let left;
    let top;

    if (preferredSide === "left") {
      left = lastMouseX - tooltipRect.width - gap - 4;
    } else {
      left = lastMouseX + gap + 4;
    }
    if (left + tooltipRect.width > window.innerWidth - viewportPadding) {
      left = lastMouseX - tooltipRect.width - gap - 4;
    }
    if (left < viewportPadding) {
      left = lastMouseX + gap + 4;
    }

    top = lastMouseY - tooltipRect.height / 2;

    const maxTop = window.innerHeight - tooltipRect.height - viewportPadding;
    if (top > maxTop) top = maxTop;

    tooltip.style.left = `${Math.max(viewportPadding, left)}px`;
    tooltip.style.top = `${Math.max(viewportPadding, top)}px`;
  };

  const clampCardPosition = (left, top) => {
    const viewportPadding = 12;
    const cardRect = card.getBoundingClientRect();
    const maxLeft = Math.max(viewportPadding, window.innerWidth - cardRect.width - viewportPadding);
    const maxTop = Math.max(viewportPadding, window.innerHeight - cardRect.height - viewportPadding);
    return {
      left: Math.min(Math.max(viewportPadding, left), maxLeft),
      top: Math.min(Math.max(viewportPadding, top), maxTop),
    };
  };

  const positionCardFromTarget = (target) => {
    const viewportPadding = 12;
    const gap = 18;
    const rect = target.getBoundingClientRect();
    const cardRect = card.getBoundingClientRect();
    let left = rect.right + gap;
    if (left + cardRect.width > window.innerWidth - viewportPadding) {
      left = rect.left - cardRect.width - gap;
    }
    if (left < viewportPadding) {
      left = Math.max(viewportPadding, (window.innerWidth - cardRect.width) / 2);
    }
    let top = rect.top;
    if (top + cardRect.height > window.innerHeight - viewportPadding) {
      top = window.innerHeight - cardRect.height - viewportPadding;
    }
    const clamped = clampCardPosition(left, top);
    card.style.left = `${clamped.left}px`;
    card.style.top = `${clamped.top}px`;
  };

  const openCard = (target) => {
    const text = String(target.getAttribute("data-tooltip") || "")
      .replace(/\r\n/g, "\n")
      .replace(/\\n/g, "\n");
    if (!text.trim()) {
      return;
    }
    card.innerHTML = buildTooltipCardMarkup({
      title: normalizeInlineText(target.getAttribute("data-tooltip-title") || target.textContent || "Details"),
      subtitle: normalizeInlineText(target.getAttribute("data-tooltip-subtitle") || ""),
      image: String(target.getAttribute("data-tooltip-image") || "").trim(),
      accent: String(target.getAttribute("data-tooltip-accent") || "").trim(),
      bodyMarkup: renderTooltipMarkup(text),
    });
    card.classList.add("is-visible");
    activeCardTarget = target;
    syncTooltipCardMediaHeight(card);
    const cardImage = card.querySelector(".floating-tooltip-card__image");
    if (cardImage instanceof HTMLImageElement) {
      if (cardImage.complete) {
        syncTooltipCardMediaHeight(card);
      } else {
        cardImage.addEventListener("load", () => syncTooltipCardMediaHeight(card), { once: true });
      }
    }
    positionCardFromTarget(target);
  };

  card.addEventListener("click", (event) => {
    const closeButton = event.target instanceof Element
      ? event.target.closest("[data-tooltip-card-close]")
      : null;
    if (closeButton) {
      closeCard();
      return;
    }
    event.stopPropagation();
  });

  card.addEventListener("pointerdown", (event) => {
    const closeButton = event.target instanceof Element
      ? event.target.closest("[data-tooltip-card-close]")
      : null;
    if (closeButton) {
      return;
    }
    const handle = event.target instanceof Element
      ? event.target.closest("[data-tooltip-card-drag-handle]")
      : null;
    if (!(handle instanceof HTMLElement)) {
      return;
    }
    const rect = card.getBoundingClientRect();
    dragPointerId = event.pointerId;
    dragOffsetX = event.clientX - rect.left;
    dragOffsetY = event.clientY - rect.top;
    card.classList.add("is-dragging");
    handle.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  });

  card.addEventListener("pointermove", (event) => {
    if (dragPointerId !== event.pointerId) {
      return;
    }
    const clamped = clampCardPosition(event.clientX - dragOffsetX, event.clientY - dragOffsetY);
    card.style.left = `${clamped.left}px`;
    card.style.top = `${clamped.top}px`;
  });

  const finishDrag = (event) => {
    if (dragPointerId !== event.pointerId) {
      return;
    }
    dragPointerId = null;
    card.classList.remove("is-dragging");
  };

  card.addEventListener("pointerup", finishDrag);
  card.addEventListener("pointercancel", finishDrag);

  document.addEventListener("mouseover", (event) => {
    const target = event.target instanceof Element ? event.target.closest(".tooltip_target[data-tooltip]") : null;
    if (!(target instanceof HTMLElement) || target.dataset.tooltipMode === "card") {
      return;
    }
    const text = String(target.getAttribute("data-tooltip") || "")
      .replace(/\r\n/g, "\n")
      .replace(/\\n/g, "\n");
    if (!text.trim()) {
      return;
    }

    if (hideTimeoutId) {
      window.clearTimeout(hideTimeoutId);
      hideTimeoutId = null;
    }
    clearShowTimer();
    if (activeTarget && activeTarget !== target) {
      tooltip.classList.remove("is-visible");
      activeTarget = null;
    }

    pendingTarget = target;
    showTimeoutId = window.setTimeout(() => {
      if (pendingTarget !== target) {
        return;
      }
      tooltip.innerHTML = renderTooltipMarkup(text);
      activeTarget = target;
      tooltip.classList.add("is-visible");
      positionTooltip(target);
      showTimeoutId = null;
    }, SHOW_DELAY_MS);
  });

  document.addEventListener("mouseout", (event) => {
    const target = event.target instanceof Element ? event.target.closest(".tooltip_target[data-tooltip]") : null;
    if (!(target instanceof HTMLElement) || target.dataset.tooltipMode === "card") {
      return;
    }
    if (event.relatedTarget instanceof Node && target.contains(event.relatedTarget)) {
      return;
    }
    if (pendingTarget === target) {
      pendingTarget = null;
    }
    clearShowTimer();
    scheduleHide();
  });

  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element
      ? event.target.closest(".tooltip_target[data-tooltip][data-tooltip-mode='card']")
      : null;
    if (target instanceof HTMLElement) {
      const nestedInteractive = event.target instanceof Element
        ? event.target.closest("button, a, input, select, textarea, form")
        : null;
      if (nestedInteractive && nestedInteractive !== target) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      if (activeCardTarget === target && card.classList.contains("is-visible")) {
        closeCard();
        return;
      }
      closeCard();
      openCard(target);
      return;
    }
    if (card.classList.contains("is-visible") && !(event.target instanceof Node && card.contains(event.target))) {
      closeCard();
    }
  });

  window.addEventListener("scroll", () => {
    if (activeTarget) {
      positionTooltip(activeTarget);
    }
  }, true);

  window.addEventListener("resize", () => {
    if (activeTarget) {
      positionTooltip(activeTarget);
    }
    if (activeCardTarget) {
      syncTooltipCardMediaHeight(card);
      const left = Number.parseFloat(card.style.left || "0");
      const top = Number.parseFloat(card.style.top || "0");
      const clamped = clampCardPosition(left, top);
      card.style.left = `${clamped.left}px`;
      card.style.top = `${clamped.top}px`;
    }
  });

  document.addEventListener("mouseleave", () => {
    clearShowTimer();
    scheduleHide();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && card.classList.contains("is-visible")) {
      closeCard();
    }
  });
}
