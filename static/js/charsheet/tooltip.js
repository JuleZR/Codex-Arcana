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

function renderInlineMarkdown(text) {
  let html = escapeHtml(String(text || ""));
  html = html.replace(/\[\[EMPTY\]\]/g, "&nbsp;");
  html = html.replace(
    /\[\[RUNEINLINE:(.+?)::(.*?)\]\]/g,
    (_match, name, image) => {
      const safeName = escapeHtml(String(name || "").trim() || "Rune");
      const safeImage = escapeHtml(String(image || "").trim());
      const imageHtml = safeImage
        ? `<img class="tooltip_rune_inline_image" src="${safeImage}" alt="">`
        : '<span class="tooltip_rune_inline_image tooltip_rune_inline_image--placeholder" aria-hidden="true"></span>';
      return `<span class="tooltip_rune_inline">${imageHtml}<span class="tooltip_rune_inline_name">${safeName}</span></span>`;
    },
  );
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
            tableHtml += isEffectTableRow(row) ? '<tr class="tooltip_effect_row">' : "<tr>";
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

  const SHOW_DELAY_MS = 1100;
  const HIDE_HOLD_MS = 380;
  let activeTarget = null;
  let pendingTarget = null;
  let showTimeoutId = null;
  let hideTimeoutId = null;
  let lastMouseX = 0;
  let lastMouseY = 0;

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
    const targetRect = target.getBoundingClientRect();
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

  document.addEventListener("mouseover", (event) => {
    const target = event.target instanceof Element ? event.target.closest(".tooltip_target[data-tooltip]") : null;
    if (!(target instanceof HTMLElement)) {
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
    if (!(target instanceof HTMLElement)) {
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

  window.addEventListener("scroll", () => {
    if (activeTarget) {
      positionTooltip(activeTarget);
    }
  }, true);

  window.addEventListener("resize", () => {
    if (activeTarget) {
      positionTooltip(activeTarget);
    }
  });

  document.addEventListener("mouseleave", () => {
    clearShowTimer();
    scheduleHide();
  });
}
