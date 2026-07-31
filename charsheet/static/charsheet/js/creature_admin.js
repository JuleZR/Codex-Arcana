(function () {
  "use strict";

  function bindCombinedAbilityAddLinks() {
    document.querySelectorAll("[data-creature-ability-add]").forEach(function (link) {
      link.addEventListener("click", function (event) {
        event.preventDefault();
        var prefix = link.dataset.creatureAbilityAdd;
        var nativeAddLink = document.querySelector("#" + prefix + "-group tr.add-row a");
        if (nativeAddLink) {
          nativeAddLink.click();
        }
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      window.setTimeout(bindCombinedAbilityAddLinks, 0);
    });
  } else {
    window.setTimeout(bindCombinedAbilityAddLinks, 0);
  }
}());
