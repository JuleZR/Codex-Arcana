export function initLeftTools() {
  const mobileToggle = document.getElementById("leftToolsMobileToggle");
  const leftTools = document.getElementById("leftTools");
  if (mobileToggle instanceof HTMLButtonElement && leftTools instanceof HTMLElement) {
    const setExpanded = (expanded) => {
      leftTools.classList.toggle("is-menu-collapsed", !expanded);
      mobileToggle.setAttribute("aria-expanded", String(expanded));
      mobileToggle.textContent = expanded ? "Menü ausblenden" : "Menü einblenden";
    };
    setExpanded(!window.matchMedia("(max-width: 900px)").matches);
    mobileToggle.addEventListener("click", () => {
      setExpanded(mobileToggle.getAttribute("aria-expanded") !== "true");
    });
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
