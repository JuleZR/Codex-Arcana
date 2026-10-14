document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-flavor-preview-url]");
  if (!button || button.disabled) return;
  const result = button.parentElement.querySelector("[data-flavor-preview-result]");
  button.disabled = true;
  try {
    const response = await fetch(button.dataset.flavorPreviewUrl, {
      method: "POST",
      credentials: "same-origin",
      body: new FormData(button.closest("form")),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Vorschau fehlgeschlagen.");
    result.innerHTML = payload.html;
    if (!payload.html) result.textContent = "Keine passende neutrale Vorlage vorhanden oder Vorlage leer.";
  } catch (error) {
    result.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
