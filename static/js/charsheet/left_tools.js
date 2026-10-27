export function initLeftTools() {
  const leftTools = document.getElementById("leftTools");
  if (leftTools instanceof HTMLElement) {
    const mobile = window.matchMedia("(max-width: 900px)");
    const triggers = Array.from(leftTools.querySelectorAll("[data-resource-target]"));
    const panels = Array.from(leftTools.querySelectorAll(".left-tools__group--resource"));
    const updateKeyboardOffset = () => {
      const viewport = window.visualViewport;
      const editing = mobile.matches && panels.some((panel) => panel.contains(document.activeElement));
      const offset = editing && viewport
        ? Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop)
        : 0;
      leftTools.style.setProperty("--left-tools-keyboard-offset", `${offset}px`);
    };
    const closeResources = (restoreFocus = false) => {
      const activeTrigger = triggers.find((trigger) => trigger.getAttribute("aria-expanded") === "true");
      const focusInPanel = panels.some((panel) => panel.contains(document.activeElement));
      if (focusInPanel) document.activeElement.blur();
      panels.forEach((panel) => panel.classList.remove("is-resource-open"));
      triggers.forEach((trigger) => trigger.setAttribute("aria-expanded", "false"));
      updateKeyboardOffset();
      if (restoreFocus && activeTrigger) activeTrigger.focus({ preventScroll: true });
    };
    triggers.forEach((trigger) => {
      trigger.addEventListener("click", () => {
        const wasOpen = trigger.getAttribute("aria-expanded") === "true";
        closeResources();
        if (!mobile.matches || wasOpen) return;
        const panel = panels.find((entry) => entry.id === trigger.dataset.resourceTarget);
        if (!panel) return;
        panel.classList.add("is-resource-open");
        trigger.setAttribute("aria-expanded", "true");
        panel.querySelector("input")?.focus({ preventScroll: true });
        updateKeyboardOffset();
      });
    });
    leftTools.querySelectorAll("[data-resource-close]").forEach((button) => {
      button.addEventListener("click", () => closeResources(true));
    });
    leftTools.addEventListener("click", (event) => {
      if (event.target.closest(".left-tools__icon_btn:not([data-resource-target]), [data-pending-choice-trigger]")) {
        closeResources();
      }
    });
    document.addEventListener("pointerdown", (event) => {
      if (mobile.matches && !leftTools.contains(event.target)) closeResources();
    });
    document.addEventListener("keydown", (event) => {
      if (mobile.matches && event.key === "Escape") closeResources(true);
    });
    mobile.addEventListener("change", () => closeResources());
    leftTools.addEventListener("focusin", updateKeyboardOffset);
    leftTools.addEventListener("focusout", () => window.requestAnimationFrame(updateKeyboardOffset));
    window.visualViewport?.addEventListener("resize", updateKeyboardOffset);
    window.visualViewport?.addEventListener("scroll", updateKeyboardOffset);
  }

  const moneyXpInputs = Array.from(document.querySelectorAll(".left-tools__delta_input"));
  if (!moneyXpInputs.length) {
    return;
  }

  const formatGroupedValue = (rawValue, allowStar = false) => {
    const raw = String(rawValue || "").trim();
    const sign = raw.includes("-") ? "-" : raw.includes("+") ? "+" : "";
    const star = allowStar && raw.includes("*") ? "*" : "";
    const digits = raw.replace(/[^\d]/g, "");
    if (!digits) {
      return `${sign}${star}`;
    }
    return `${sign}${Number.parseInt(digits, 10).toLocaleString("de-DE")}${star}`;
  };

  const parseGroupedValue = (rawValue, allowStar = false) => {
    const raw = String(rawValue || "").trim();
    const sign = raw.includes("-") ? "-" : raw.includes("+") ? "+" : "";
    const star = allowStar && raw.includes("*") ? "*" : "";
    const digits = raw.replace(/[^\d]/g, "");
    if (!digits) {
      return "0";
    }
    return `${sign}${digits}${star}`;
  };

  moneyXpInputs.forEach((input) => {
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

    const form = input.closest("form");
    if (form) {
      form.addEventListener("submit", () => {
        input.value = parseGroupedValue(input.value, allowStar);
      });
    }
  });
}
