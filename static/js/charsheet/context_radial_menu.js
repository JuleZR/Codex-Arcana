const DISABLED_QUERY = "(max-width: 900px), (pointer: coarse), (hover: none)";
const SOURCE_SELECTORS = [
  ".left-tools__panel--actions .left-tools__icon_btn",
  ".left-tools__footer-link",
];
const BLOCKED_TARGET_SELECTOR = [
  "input",
  "textarea",
  "select",
  "[contenteditable='true']",
  ".sheet-window.is-open",
  ".floating-tooltip",
  ".floating-tooltip-card",
  ".wallet_inline_tooltip",
].join(", ");

function polarPoint(angleDeg, radius, size) {
  const radians = ((angleDeg - 90) * Math.PI) / 180;
  const center = size / 2;
  const x = center + Math.cos(radians) * radius;
  const y = center + Math.sin(radians) * radius;
  return `${((x / size) * 100).toFixed(3)}% ${((y / size) * 100).toFixed(3)}%`;
}

function buildSectorClipPath({
  startAngle,
  endAngle,
  innerRadius,
  outerRadius,
  size,
}) {
  const span = endAngle - startAngle;
  const steps = Math.max(6, Math.ceil(Math.abs(span) / 10));
  const outerPoints = [];
  const innerPoints = [];
  for (let index = 0; index <= steps; index += 1) {
    const progress = index / steps;
    const angle = startAngle + span * progress;
    outerPoints.push(polarPoint(angle, outerRadius, size));
  }
  for (let index = steps; index >= 0; index -= 1) {
    const progress = index / steps;
    const angle = startAngle + span * progress;
    innerPoints.push(polarPoint(angle, innerRadius, size));
  }
  return `polygon(${outerPoints.concat(innerPoints).join(", ")})`;
}

function isVisible(element) {
  if (!(element instanceof HTMLElement)) {
    return false;
  }
  if (element.hidden || element.getAttribute("aria-hidden") === "true") {
    return false;
  }
  return element.getClientRects().length > 0;
}

function createMenuItem(source, index) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "charsheet-radial-menu__item";
  button.setAttribute("role", "menuitem");
  button.style.setProperty("--radial-item-delay", `${index * 22}ms`);

  const content = document.createElement("span");
  content.className = "charsheet-radial-menu__item_content";

  const iconWrap = document.createElement("span");
  iconWrap.className = "charsheet-radial-menu__item_icon";

  const iconSource = source.querySelector(".left-tools__icon_symbol, .learn_choice_notice_icon");
  const icon = document.createElement("span");
  icon.className = "charsheet-radial-menu__item_icon_text";
  icon.setAttribute("aria-hidden", "true");
  icon.innerHTML = iconSource ? iconSource.innerHTML : "?";
  iconWrap.appendChild(icon);

  const labelSource = source.querySelector(".left-tools__icon_label, .learn_choice_notice_text");
  const labelText = (labelSource?.textContent || source.getAttribute("title") || source.getAttribute("aria-label") || "")
    .trim();
  const label = document.createElement("span");
  label.className = "charsheet-radial-menu__item_label";
  label.textContent = labelText || "Aktion";

  const ariaLabel = source.getAttribute("aria-label") || label.textContent;
  button.setAttribute("aria-label", ariaLabel);
  button.title = source.getAttribute("title") || label.textContent;
  content.append(iconWrap, label);
  button.append(content);
  button.addEventListener("click", (event) => {
    event.preventDefault();
    source.click();
  });
  return button;
}

function collectSources(leftTools) {
  return SOURCE_SELECTORS.flatMap((selector) => Array.from(leftTools.querySelectorAll(selector)))
    .filter((element) => element instanceof HTMLElement)
    .filter((element) => !element.hasAttribute("disabled"))
    .filter((element) => !element.hidden)
    .filter((element) => element.getAttribute("aria-hidden") !== "true");
}

function clampPosition(value, minimum, maximum) {
  return Math.min(Math.max(value, minimum), maximum);
}

function formatGroupedValue(rawValue) {
  const raw = String(rawValue || "").trim();
  const sign = raw.startsWith("-") ? "-" : raw.startsWith("+") ? "+" : "";
  const digits = raw.replace(/[^\d]/g, "");
  if (!digits) {
    return sign;
  }
  return `${sign}${Number.parseInt(digits, 10).toLocaleString("de-DE")}`;
}

function parseGroupedValue(rawValue) {
  const raw = String(rawValue || "").trim();
  const sign = raw.startsWith("-") ? "-" : "";
  const digits = raw.replace(/[^\d]/g, "");
  if (!digits) {
    return "0";
  }
  return `${sign}${digits}`;
}

function bindFormattedDeltaInput(input) {
  if (!(input instanceof HTMLInputElement) || input.dataset.radialBound === "1") {
    return;
  }
  input.dataset.radialBound = "1";
  input.value = formatGroupedValue(input.value);
  input.addEventListener("input", () => {
    input.value = formatGroupedValue(input.value);
  });
  input.addEventListener("blur", () => {
    if (!input.value || input.value === "+" || input.value === "-") {
      input.value = "0";
      return;
    }
    input.value = formatGroupedValue(input.value);
  });
  input.closest("form")?.addEventListener("submit", () => {
    input.value = parseGroupedValue(input.value);
  });
}

function rebuildResourcePanel(leftTools, host) {
  host.replaceChildren();
  const groups = Array.from(leftTools.querySelectorAll(".left-tools__panel--resources .left-tools__group--resource"));
  groups.forEach((group) => {
    if (!(group instanceof HTMLElement) || group.hidden || group.getAttribute("aria-hidden") === "true") {
      return;
    }
    const clone = group.cloneNode(true);
    clone.classList.add("charsheet-radial-menu__resource");
    clone.querySelectorAll(".left-tools__delta_input").forEach((input) => {
      bindFormattedDeltaInput(input);
    });
    host.appendChild(clone);
  });
  host.hidden = host.childElementCount === 0;
}

function configureItemGeometry(item, count, index, geometry) {
  const step = 360 / count;
  const separatorDegrees = geometry.separatorDegrees;
  const rawStart = index * step;
  const rawEnd = rawStart + step;
  const startAngle = rawStart + separatorDegrees / 2;
  const endAngle = rawEnd - separatorDegrees / 2;
  const midAngle = startAngle + (endAngle - startAngle) / 2;
  const clipPath = buildSectorClipPath({
    startAngle,
    endAngle,
    innerRadius: geometry.innerRadius,
    outerRadius: geometry.outerRadius,
    size: geometry.size,
  });
  const labelRadius = geometry.innerRadius + (geometry.outerRadius - geometry.innerRadius) * 0.56;
  const contentPoint = polarPoint(midAngle, labelRadius, geometry.size).split(" ");
  item.style.clipPath = clipPath;
  item.style.setProperty("--content-x", contentPoint[0]);
  item.style.setProperty("--content-y", contentPoint[1]);
}

export function initContextRadialMenu() {
  const root = document.getElementById("contextRadialMenu");
  const appContainer = document.getElementById("charsheetApp");
  const anchor = root?.querySelector("[data-radial-menu-anchor]");
  const itemsHost = root?.querySelector("[data-radial-menu-items]");
  const resourcesHost = root?.querySelector("[data-radial-menu-resources]");
  const leftTools = document.getElementById("leftTools");
  const mediaQuery = window.matchMedia(DISABLED_QUERY);
  if (
    !(root instanceof HTMLElement)
    || !(appContainer instanceof HTMLElement)
    || !(anchor instanceof HTMLElement)
    || !(itemsHost instanceof HTMLElement)
    || !(resourcesHost instanceof HTMLElement)
    || !(leftTools instanceof HTMLElement)
  ) {
    return;
  }

  let isOpen = false;

  const closeMenu = () => {
    if (!isOpen) {
      return;
    }
    isOpen = false;
    root.classList.remove("is-open");
    root.setAttribute("aria-hidden", "true");
  };

  const rebuildItems = () => {
    itemsHost.replaceChildren();
    const sources = collectSources(leftTools);
    const count = sources.length;
    if (!count) {
      return 0;
    }
    const geometry = {
      size: count <= 4 ? 280 : 300,
      innerRadius: count <= 4 ? 52 : 56,
      outerRadius: count <= 4 ? 134 : 144,
      separatorDegrees: Math.min(3.8, 360 / count / 4.4),
    };
    itemsHost.style.setProperty("--radial-menu-size", `${geometry.size}px`);
    sources.forEach((source, index) => {
      const item = createMenuItem(source, index);
      configureItemGeometry(item, count, index, geometry);
      itemsHost.appendChild(item);
    });
    rebuildResourcePanel(leftTools, resourcesHost);
    return count;
  };

  const canOpenForEvent = (event) => {
    if (mediaQuery.matches) {
      return false;
    }
    const target = event.target instanceof Element ? event.target : null;
    if (!target) {
      return false;
    }
    if (!appContainer.contains(target)) {
      return false;
    }
    if (target.closest(BLOCKED_TARGET_SELECTOR)) {
      return false;
    }
    return true;
  };

  const openMenu = (clientX, clientY) => {
    const count = rebuildItems();
    if (!count) {
      return;
    }
    const radius = count <= 4 ? 104 : count <= 6 ? 112 : 122;
    const horizontalPadding = radius + 68;
    const topPadding = radius + 68;
    const bottomPadding = radius + 164;
    const left = clampPosition(clientX, horizontalPadding, window.innerWidth - horizontalPadding);
    const top = clampPosition(clientY, topPadding, window.innerHeight - bottomPadding);
    anchor.style.left = `${left}px`;
    anchor.style.top = `${top}px`;
    anchor.style.setProperty("--radial-menu-radius", `${radius}px`);
    root.setAttribute("aria-hidden", "false");
    root.classList.add("is-open");
    isOpen = true;
  };

  document.addEventListener("contextmenu", (event) => {
    if (!canOpenForEvent(event)) {
      return;
    }
    event.preventDefault();
    if (isOpen) {
      closeMenu();
      return;
    }
    openMenu(event.clientX, event.clientY);
  });

  document.addEventListener("pointerdown", (event) => {
    if (!isOpen) {
      return;
    }
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest(".charsheet-radial-menu__item, .charsheet-radial-menu__anchor")) {
      return;
    }
    closeMenu();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeMenu();
    }
  });

  window.addEventListener("blur", closeMenu);
  window.addEventListener("resize", () => {
    if (mediaQuery.matches) {
      closeMenu();
    }
  });
  mediaQuery.addEventListener("change", () => {
    if (mediaQuery.matches) {
      closeMenu();
    }
  });

  root.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target.closest(".charsheet-radial-menu__item") : null;
    if (target) {
      closeMenu();
    }
  });

  document.addEventListener("charsheet:partials-applied", closeMenu);
}
