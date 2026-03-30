export function initCharInfoCounter() {
  const counters = Array.from(document.querySelectorAll("[data-char-count-for]"));
  if (!counters.length) {
    return;
  }

  counters.forEach((counter) => {
    const fieldId = counter.getAttribute("data-char-count-for");
    if (!fieldId) {
      return;
    }
    const field = document.getElementById(fieldId);
    if (!(field instanceof HTMLTextAreaElement || field instanceof HTMLInputElement)) {
      return;
    }

    const maxLength = Number(field.getAttribute("maxlength") || "0");
    if (!maxLength) {
      return;
    }

    const updateCounter = () => {
      const currentLength = field.value.length;
      counter.textContent = `${currentLength} / ${maxLength} Zeichen`;
      counter.classList.toggle("is-near-limit", currentLength >= maxLength - 10 && currentLength < maxLength);
      counter.classList.toggle("is-at-limit", currentLength >= maxLength);
    };

    field.addEventListener("input", updateCounter);
    updateCounter();
  });
}
