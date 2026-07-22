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

const TEMPLATE_STAGE_SIZE = 420;
const TEMPLATE_CANVAS_SIZE = 500;
const TEMPLATE_BUTTON_SIZE = 100;
const TEMPLATE_START_ANGLE = -100;
const TEMPLATE_END_ANGLE = 100;
const TEMPLATE_SLOT_ORDER = ["fight", "codex", "learn", "shop", "chronicle"];
const SLOT_MATCHERS = [
  { key: "learn", matcher: /learnmenutrigger|lernen|lernmen|offene\s+wahl/u },
  { key: "codex", matcher: /dashboard|codex/u },
  { key: "fight", matcher: /battlecalculatortrigger|kampf|kampfrechner/u },
  { key: "shop", matcher: /shopscaletrigger|shop/u },
  { key: "chronicle", matcher: /diarytrigger|chronik|tagebuch/u },
];

function isVisible(element) {
  if (!(element instanceof HTMLElement)) {
    return false;
  }
  if (element.hidden || element.getAttribute("aria-hidden") === "true") {
    return false;
  }
  return element.getClientRects().length > 0;
}

function collectSources(leftTools) {
  return SOURCE_SELECTORS.flatMap((selector) => Array.from(leftTools.querySelectorAll(selector)))
    .filter((element) => element instanceof HTMLElement)
    .filter((element) => !element.hasAttribute("disabled"))
    .filter((element) => !element.hidden)
    .filter((element) => element.getAttribute("aria-hidden") !== "true");
}

function getActionIdentity(source) {
  return [
    source.id,
    source.getAttribute("data-action"),
    source.getAttribute("aria-label"),
    source.getAttribute("title"),
    source.textContent,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function mapSourcesToSlots(sources) {
  const mapped = new Map();
  const used = new Set();

  SLOT_MATCHERS.forEach(({ key, matcher }) => {
    const source = sources.find((candidate) => {
      if (used.has(candidate)) {
        return false;
      }
      return matcher.test(getActionIdentity(candidate));
    });
    if (!source) {
      return;
    }
    mapped.set(key, source);
    used.add(source);
  });

  return mapped;
}

function clampPosition(value, minimum, maximum) {
  return Math.min(Math.max(value, minimum), maximum);
}

function formatGroupedValue(rawValue, allowStar = false) {
  const raw = String(rawValue || "").trim();
  const sign = raw.includes("-") ? "-" : raw.includes("+") ? "+" : "";
  const star = allowStar && raw.includes("*") ? "*" : "";
  const digits = raw.replace(/[^\d]/g, "");
  if (!digits) {
    return `${sign}${star}`;
  }
  return `${sign}${Number.parseInt(digits, 10).toLocaleString("de-DE")}${star}`;
}

function parseGroupedValue(rawValue, allowStar = false) {
  const raw = String(rawValue || "").trim();
  const sign = raw.includes("-") ? "-" : raw.includes("+") ? "+" : "";
  const star = allowStar && raw.includes("*") ? "*" : "";
  const digits = raw.replace(/[^\d]/g, "");
  if (!digits) {
    return "0";
  }
  return `${sign}${digits}${star}`;
}

function formatDisplayValue(rawValue) {
  const raw = String(rawValue || "").trim();
  const digits = raw.replace(/[^\d]/g, "");
  if (!digits) {
    return raw || "0";
  }
  return Number.parseInt(digits, 10).toLocaleString("de-DE");
}

function readPanelText(selector) {
  return document.querySelector(selector)?.textContent?.trim() || "";
}

function getResourceDisplayValues() {
  return {
    money: formatDisplayValue(readPanelText("#sheetWalletPanel .wallet_inline_tooltip span:first-child")),
    experience: formatDisplayValue(readPanelText("#sheetExperiencePanel .exp_rows .exp_row:first-child .exp_value")),
  };
}

function bindFormattedDeltaInput(input) {
  if (!(input instanceof HTMLInputElement) || input.dataset.radialBound === "1") {
    return;
  }
  input.dataset.radialBound = "1";
  const allowStar = input.hasAttribute("data-experience-delta");
  input.value = formatGroupedValue(input.value, allowStar);
  input.addEventListener("input", () => {
    input.value = formatGroupedValue(input.value, allowStar);
  });
  input.addEventListener("blur", () => {
    if (!input.value || input.value === "+" || input.value === "-") {
      input.value = "0";
      return;
    }
    input.value = formatGroupedValue(input.value, allowStar);
  });
  input.closest("form")?.addEventListener("submit", () => {
    input.value = parseGroupedValue(input.value, allowStar);
  });
}

function rebuildResourcePanel(leftTools, host, slots) {
  const groups = Array.from(leftTools.querySelectorAll(".left-tools__panel--resources .left-tools__group--resource"));

  Object.values(slots).forEach(({ slot, content }) => {
    slot.hidden = true;
    content.replaceChildren();
  });

  groups.forEach((group) => {
    if (!(group instanceof HTMLElement) || group.hidden || group.getAttribute("aria-hidden") === "true") {
      return;
    }

    const label = (group.getAttribute("aria-label") || "").trim().toLowerCase();
    const kind = label === "geld" ? "money" : label === "erfahrung" ? "experience" : null;
    if (!kind || !slots[kind]) {
      return;
    }

    const clone = group.cloneNode(true);
    clone.classList.add("charsheet-radial-menu__resource");

    const heading = clone.querySelector("h3");
    if (heading instanceof HTMLElement) {
      heading.textContent = kind === "money" ? "Gold" : "EP";
    }

    clone.querySelectorAll(".left-tools__delta_input").forEach((input) => {
      bindFormattedDeltaInput(input);
    });

    const form = clone.querySelector("form");
    void form;

    slots[kind].content.appendChild(clone);
    slots[kind].slot.hidden = false;
  });

  host.hidden = Object.values(slots).every(({ slot }) => slot.hidden);
}

function createButtonContent(source) {
  const content = document.createElement("span");
  content.className = "charsheet-radial-menu__item_content";

  const iconWrap = document.createElement("span");
  iconWrap.className = "charsheet-radial-menu__item_icon";

  const icon = document.createElement("span");
  icon.className = "charsheet-radial-menu__item_icon_text";
  icon.setAttribute("aria-hidden", "true");
  icon.innerHTML = source.querySelector(".left-tools__icon_symbol, .learn_choice_notice_icon")?.innerHTML || "?";
  iconWrap.appendChild(icon);

  const label = document.createElement("span");
  label.className = "charsheet-radial-menu__item_label";
  label.textContent = (
    source.querySelector(".left-tools__icon_label, .learn_choice_notice_text")?.textContent
    || source.getAttribute("title")
    || source.getAttribute("aria-label")
    || "Aktion"
  ).trim();

  content.append(iconWrap, label);
  return { content, labelText: label.textContent };
}

function hydrateButton(button, source, closeMenu) {
  button.replaceChildren();

  if (!(source instanceof HTMLElement)) {
    button.hidden = true;
    button.disabled = true;
    button.removeAttribute("aria-label");
    button.removeAttribute("title");
    button.onclick = null;
    return;
  }

  const { content, labelText } = createButtonContent(source);
  button.hidden = false;
  button.disabled = false;
  button.appendChild(content);
  button.setAttribute("aria-label", source.getAttribute("aria-label") || labelText);
  button.setAttribute("title", source.getAttribute("title") || labelText);
  button.onclick = (event) => {
    event.preventDefault();
    source.click();
    closeMenu();
  };
}

function layoutTemplateButtons(stage, buttons) {
  if (!(stage instanceof HTMLElement) || !buttons.length) {
    return;
  }

  const radius = (TEMPLATE_STAGE_SIZE / 2) - (TEMPLATE_BUTTON_SIZE / 2) + 30;
  const step = buttons.length > 1
    ? (TEMPLATE_END_ANGLE - TEMPLATE_START_ANGLE) / (buttons.length - 1)
    : 0;

  buttons.forEach((button, index) => {
    const angle = TEMPLATE_START_ANGLE + (step * index);
    button.style.setProperty("--angle", `${angle}deg`);
    button.style.setProperty("--radius", `${radius}px`);
  });
}

function computeStageScale() {
  return Math.min(
    1,
    (window.innerWidth - 24) / TEMPLATE_CANVAS_SIZE,
    (window.innerHeight - 24) / TEMPLATE_CANVAS_SIZE,
  );
}

function canOpenForEvent(event, mediaQuery, appContainer) {
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
}

export function initContextRadialMenu() {
  const root = document.getElementById("contextRadialMenu");
  const appContainer = document.getElementById("charsheetApp");
  const anchor = root?.querySelector("[data-radial-menu-anchor]");
  const stage = root?.querySelector(".menu-stage");
  const itemsHost = root?.querySelector("[data-radial-menu-items]");
  const resourcesHost = root?.querySelector("[data-radial-menu-resources]");
  const moneySlot = root?.querySelector("[data-radial-menu-resource-slot='money']");
  const moneyContent = root?.querySelector("[data-radial-menu-resource-content='money']");
  const experienceSlot = root?.querySelector("[data-radial-menu-resource-slot='experience']");
  const experienceContent = root?.querySelector("[data-radial-menu-resource-content='experience']");
  const pinButton = root?.querySelector("[data-radial-menu-pin-button]");
  const leftTools = document.getElementById("leftTools");
  const mediaQuery = window.matchMedia(DISABLED_QUERY);

  if (
    !(root instanceof HTMLElement)
    || !(appContainer instanceof HTMLElement)
    || !(anchor instanceof HTMLElement)
    || !(stage instanceof HTMLElement)
    || !(itemsHost instanceof HTMLElement)
    || !(resourcesHost instanceof HTMLElement)
    || !(moneySlot instanceof HTMLElement)
    || !(moneyContent instanceof HTMLElement)
    || !(experienceSlot instanceof HTMLElement)
    || !(experienceContent instanceof HTMLElement)
    || !(pinButton instanceof HTMLButtonElement)
    || !(leftTools instanceof HTMLElement)
  ) {
    return;
  }

  const buttonBySlot = new Map(
    Array.from(itemsHost.querySelectorAll("[data-radial-slot]"))
      .filter((element) => element instanceof HTMLButtonElement)
      .map((button) => [button.dataset.radialSlot || "", button]),
  );
  const orderedButtons = TEMPLATE_SLOT_ORDER
    .map((slot) => buttonBySlot.get(slot))
    .filter((button) => button instanceof HTMLButtonElement);

  let isOpen = false;
  let isPinned = false;
  let lastOpenPoint = null;

  const syncPinState = () => {
    pinButton.setAttribute("aria-pressed", isPinned ? "true" : "false");
    pinButton.classList.toggle("is-active", isPinned);
    pinButton.setAttribute("title", isPinned ? "Fixierung loesen" : "Menue fixieren");
    pinButton.setAttribute("aria-label", isPinned ? "Fixierung loesen" : "Menue fixieren");
  };

  const closeMenu = () => {
    if (!isOpen || isPinned) {
      return;
    }
    isOpen = false;
    root.classList.remove("is-open");
    root.setAttribute("aria-hidden", "true");
  };

  const forceCloseMenu = () => {
    if (!isOpen) {
      return;
    }
    isOpen = false;
    root.classList.remove("is-open");
    root.setAttribute("aria-hidden", "true");
  };

  const rebuildButtons = () => {
    const sources = collectSources(leftTools);
    const mappedSources = mapSourcesToSlots(sources);

    TEMPLATE_SLOT_ORDER.forEach((slotKey) => {
      const button = buttonBySlot.get(slotKey);
      if (!(button instanceof HTMLButtonElement)) {
        return;
      }
      hydrateButton(button, mappedSources.get(slotKey) || null, closeMenu);
    });

    layoutTemplateButtons(stage, orderedButtons);
    return orderedButtons.some((button) => !button.hidden);
  };

  const rebuildResources = () => {
    rebuildResourcePanel(leftTools, resourcesHost, {
      money: { slot: moneySlot, content: moneyContent },
      experience: { slot: experienceSlot, content: experienceContent },
    });
  };

  const positionMenu = (clientX, clientY) => {
    const scale = computeStageScale();
    const halfWidth = (TEMPLATE_CANVAS_SIZE * scale) / 2;
    const halfHeight = (TEMPLATE_CANVAS_SIZE * scale) / 2;
    anchor.style.setProperty("--radial-stage-scale", String(scale));
    anchor.style.left = `${clampPosition(clientX, halfWidth + 12, window.innerWidth - halfWidth - 12)}px`;
    anchor.style.top = `${clampPosition(clientY, halfHeight + 12, window.innerHeight - halfHeight - 12)}px`;
  };

  const openMenu = (clientX, clientY) => {
    const hasButtons = rebuildButtons();
    rebuildResources();
    if (!hasButtons) {
      return;
    }

    lastOpenPoint = { x: clientX, y: clientY };
    positionMenu(clientX, clientY);
    root.setAttribute("aria-hidden", "false");
    root.classList.add("is-open");
    isOpen = true;
    syncPinState();
  };

  const repositionOpenMenu = () => {
    if (!isOpen || !lastOpenPoint || mediaQuery.matches) {
      return;
    }
    positionMenu(lastOpenPoint.x, lastOpenPoint.y);
  };

  appContainer.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (!canOpenForEvent(event, mediaQuery, appContainer)) {
      closeMenu();
      return;
    }
    if (isOpen) {
      if (!isPinned) {
        closeMenu();
      }
      return;
    }
    openMenu(event.clientX, event.clientY);
  }, true);

  document.addEventListener("pointerdown", (event) => {
    if (!isOpen) {
      return;
    }
    const target = event.target instanceof Element ? event.target : null;
    if (target && anchor.contains(target)) {
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
      return;
    }
    repositionOpenMenu();
  });
  mediaQuery.addEventListener("change", () => {
    if (mediaQuery.matches) {
      closeMenu();
      return;
    }
    repositionOpenMenu();
  });

  pinButton.addEventListener("click", (event) => {
    event.preventDefault();
    isPinned = !isPinned;
    syncPinState();
  });

  document.addEventListener("charsheet:partials-applied", forceCloseMenu);
  syncPinState();
}
