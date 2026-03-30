import { escapeHtml } from "./utils.js";

function parseTableRow(line) {
  const trimmed = String(line || "").trim();
  if (!trimmed.includes("|")) {
    return [];
  }
  return trimmed.replace(/^\|/, "").replace(/\|$/, "").split("|").map((part) => part.trim());
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
        `<p class="tooltip_quality_line"><span class="tooltip_quality_badge" style="--tooltip-quality-color: ${escapeHtml(qualityMeta.color)};">Qualitaet: ${escapeHtml(qualityMeta.label)}</span></p>`,
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
          tableHtml += "<tr>";
          row.forEach((cell) => {
            tableHtml += `<td>${escapeHtml(cell)}</td>`;
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

    const paragraphLines = [];
    let rowIndex = index;
    while (rowIndex < lines.length && lines[rowIndex].trim()) {
      paragraphLines.push(escapeHtml(lines[rowIndex]));
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
    const panel = target.closest(".p2_panel");
    const panelRect = (panel || target).getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    const preferredSide = target.getAttribute("data-tooltip-side") || "left";
    let left = preferredSide === "right"
      ? panelRect.right + gap
      : panelRect.left - tooltipRect.width - gap;

    if (left < viewportPadding || left + tooltipRect.width > window.innerWidth - viewportPadding) {
      left = panelRect.right + gap;
    }
    if (left + tooltipRect.width > window.innerWidth - viewportPadding) {
      left = panelRect.left - tooltipRect.width - gap;
    }

    let top = targetRect.top + (targetRect.height / 2) - (tooltipRect.height / 2);
    const maxTop = window.innerHeight - tooltipRect.height - viewportPadding;
    if (top > maxTop) {
      top = maxTop;
    }

    tooltip.style.left = `${Math.max(viewportPadding, left)}px`;
    tooltip.style.top = `${Math.max(viewportPadding, top)}px`;
  };

  document.addEventListener("mouseover", (event) => {
    const target = event.target instanceof Element ? event.target.closest(".tooltip_target[data-tooltip]") : null;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const text = String(target.getAttribute("data-tooltip") || "").replace(/\r\n/g, "\n").replace(/\\n/g, "\n");
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

