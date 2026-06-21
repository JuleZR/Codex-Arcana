export function initLeftTools() {
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
