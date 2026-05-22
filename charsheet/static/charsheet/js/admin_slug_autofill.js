document.addEventListener("DOMContentLoaded", () => {
  const slugInputs = document.querySelectorAll("input[data-autoslug-source]");
  if (!slugInputs.length) {
    return;
  }

  const normalizeSlug = (value) =>
    value
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9\s_-]/g, "")
      .replace(/[\s-]+/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_+|_+$/g, "");

  slugInputs.forEach((slugInput) => {
    const sourceFieldName = slugInput.dataset.autoslugSource;
    const sourceInput = document.getElementById(`id_${sourceFieldName}`);
    if (!sourceInput) {
      return;
    }

    let isManual = slugInput.value.trim().length > 0;

    const syncSlug = () => {
      if (isManual) {
        return;
      }
      slugInput.value = normalizeSlug(sourceInput.value);
    };

    sourceInput.addEventListener("input", syncSlug);

    slugInput.addEventListener("input", () => {
      const normalizedSource = normalizeSlug(sourceInput.value);
      const currentSlug = slugInput.value.trim();
      isManual = currentSlug !== "" && currentSlug !== normalizedSource;
      if (currentSlug === "") {
        isManual = false;
        syncSlug();
      }
    });

    syncSlug();
  });
});
