export function initLeftTools() {
  const leftTools = document.getElementById("leftTools");
  const leftToolsToggle = document.getElementById("leftToolsToggle");
  if (leftTools && leftToolsToggle) {
    const setToolsOpenState = (isOpen) => {
      leftTools.classList.toggle("is-open", isOpen);
      leftToolsToggle.classList.toggle("is-open", isOpen);
      leftToolsToggle.setAttribute("aria-expanded", String(isOpen));
      leftToolsToggle.setAttribute("aria-label", isOpen ? "Werkzeugleiste schliessen" : "Werkzeugleiste oeffnen");
      leftToolsToggle.setAttribute("title", isOpen ? "Werkzeugleiste schliessen" : "Werkzeugleiste oeffnen");
      document.documentElement.setAttribute("data-left-tools-open", isOpen ? "1" : "0");
    };

    setToolsOpenState(false);
    leftToolsToggle.addEventListener("click", () => {
      setToolsOpenState(!leftTools.classList.contains("is-open"));
    });

    // Close when clicking the backdrop — but not the toggle button itself
    document.addEventListener("click", (e) => {
      if (!leftTools.classList.contains("is-open")) return;
      if (leftToolsToggle.contains(e.target)) return;
      const stack = leftTools.closest(".sheet-side-stack");
      if (stack && !stack.contains(e.target)) {
        setToolsOpenState(false);
      }
    });
  }

  const moneyXpInputs = Array.from(document.querySelectorAll(".left-tools__delta_input"));
  if (!moneyXpInputs.length) {
    return;
  }

  const formatGroupedValue = (rawValue) => {
    const raw = String(rawValue || "").trim();
    const sign = raw.startsWith("-") ? "-" : raw.startsWith("+") ? "+" : "";
    const digits = raw.replace(/[^\d]/g, "");
    if (!digits) {
      return sign;
    }
    return `${sign}${Number.parseInt(digits, 10).toLocaleString("de-DE")}`;
  };

  const parseGroupedValue = (rawValue) => {
    const raw = String(rawValue || "").trim();
    const sign = raw.startsWith("-") ? "-" : "";
    const digits = raw.replace(/[^\d]/g, "");
    if (!digits) {
      return "0";
    }
    return `${sign}${digits}`;
  };

  moneyXpInputs.forEach((input) => {
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

    const form = input.closest("form");
    if (form) {
      form.addEventListener("submit", () => {
        input.value = parseGroupedValue(input.value);
      });
    }
  });
}
