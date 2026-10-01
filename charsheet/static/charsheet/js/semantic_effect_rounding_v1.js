(function () {
  "use strict";
  if (window.__semanticEffectRoundingV1Loaded) return;
  window.__semanticEffectRoundingV1Loaded = true;

  function initialize(root) {
    root.querySelectorAll("input[data-semantic-rounding]").forEach(function (input) {
      if (input.dataset.roundingInitialized || input.name.includes("__prefix__")) return;
      input.dataset.roundingInitialized = "1";
      input.addEventListener("change", function () {
        if (!input.checked) return;
        var ownKind = input.dataset.semanticRounding;
        var otherKind = ownKind === "round_up" ? "round_down" : "round_up";
        var otherName = input.name.slice(0, -ownKind.length) + otherKind;
        var container = input.closest(".inline-related") || input.closest("form");
        if (!container) return;
        container.querySelectorAll("input[data-semantic-rounding]").forEach(function (other) {
          if (other.name === otherName) other.checked = false;
        });
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { initialize(document); });
  } else {
    initialize(document);
  }
  document.addEventListener("formset:added", function (event) {
    initialize(event.target);
  });
  if (window.django && window.django.jQuery) {
    window.django.jQuery(document).on("formset:added.semanticRounding", function (event, row) {
      if (row && row[0]) initialize(row[0]);
    });
  }
}());
