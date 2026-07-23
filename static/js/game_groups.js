document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-group-character-picker]").forEach((picker) => {
    const search = picker.querySelector("[data-group-character-query]");
    const hidden = picker.querySelector("[data-group-character-id]");
    const results = picker.querySelector("[data-group-character-results]");
    if (!search || !hidden || !results) return;
    let timer = null;

    const clearResults = () => results.replaceChildren();
    search.addEventListener("input", () => {
      hidden.value = "";
      search.setCustomValidity("");
      clearTimeout(timer);
      const query = search.value.trim();
      if (query.length < 2) {
        clearResults();
        return;
      }
      timer = setTimeout(async () => {
        const url = new URL(picker.dataset.searchUrl, window.location.origin);
        url.searchParams.set("q", query);
        url.searchParams.set("mode", picker.dataset.searchMode || "invite");
        const response = await fetch(url, {
          credentials: "same-origin",
          headers: { Accept: "application/json" },
        });
        const payload = response.ok ? await response.json() : { results: [] };
        clearResults();
        payload.results.forEach((row) => {
          const button = document.createElement("button");
          button.type = "button";
          button.dataset.characterId = row.id;
          button.dataset.characterLabel = row.name;
          button.textContent = `${row.name} · ${row.race} · ${row.username}`;
          results.append(button);
        });
      }, 180);
    });

    results.addEventListener("click", (event) => {
      const option = event.target.closest("[data-character-id]");
      if (!option) return;
      hidden.value = option.dataset.characterId || "";
      search.value = option.dataset.characterLabel || option.textContent.trim();
      clearResults();
    });

    picker.closest("form")?.addEventListener("submit", (event) => {
      if (hidden.value) return;
      event.preventDefault();
      search.setCustomValidity("Bitte einen Treffer aus der Liste auswählen.");
      search.reportValidity();
    });
  });
});
