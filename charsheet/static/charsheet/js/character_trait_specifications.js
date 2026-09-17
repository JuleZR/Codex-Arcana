(function () {
  "use strict";

  function initialize() {
    const trait = document.getElementById("id_trait");
    const option = document.getElementById("id_specification_option");
    const specification = document.getElementById("id_specification");
    if (!trait || !option || !specification || !option.dataset.optionsUrl) return;
    const optionRow = option.closest(".form-row");
    const specificationRow = specification.closest(".form-row");

    function showControlled(controlled) {
      option.disabled = !controlled;
      specification.disabled = controlled;
      if (optionRow) optionRow.hidden = !controlled;
      if (specificationRow) specificationRow.hidden = controlled;
    }

    async function refresh(reset) {
      const selected = reset ? "" : option.value;
      option.replaceChildren(new Option("---------", ""));
      if (!trait.value) {
        showControlled(false);
        return;
      }
      const url = new URL(option.dataset.optionsUrl, window.location.origin);
      url.searchParams.set("trait", trait.value);
      const response = await fetch(url, { credentials: "same-origin" });
      if (!response.ok) return;
      const payload = await response.json();
      payload.results.forEach((row) => {
        option.add(new Option(row.label, String(row.id)));
      });
      option.value = payload.results.some(
        (row) => String(row.id) === selected
      ) ? selected : "";
      const controlled = payload.results.length > 0;
      showControlled(controlled);
    }

    trait.addEventListener("change", () => refresh(true));
    refresh(false);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize);
  } else {
    initialize();
  }
})();
