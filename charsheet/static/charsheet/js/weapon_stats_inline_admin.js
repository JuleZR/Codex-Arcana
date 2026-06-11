(function () {
  "use strict";

  const twoHandedModes = new Set(["2h", "vh"]);
  const h2Fields = ["h2_dice_amount", "h2_dice_faces", "h2_flat_operator", "h2_flat_bonus", "h2_damage_type"];

  function closestFormScope(select) {
    return select.closest(".inline-related") || select.closest("fieldset") || select.closest("form") || document;
  }

  function fieldRows(select) {
    const scope = closestFormScope(select);
    return Array.from(scope.querySelectorAll(".form-row, .form-group")).filter((row) =>
      h2Fields.some((fieldName) => row.classList.contains(`field-${fieldName}`) || row.querySelector(`[name$='${fieldName}']`))
    );
  }

  function findField(select, fieldName) {
    const scope = closestFormScope(select);
    const prefix = select.id ? select.id.replace(/wield_mode$/, "") : "";
    return (
      (prefix ? document.getElementById(`${prefix}${fieldName}`) : null) ||
      scope.querySelector(`[name$='${fieldName}']`) ||
      document.getElementById(`id_${fieldName}`)
    );
  }

  function update(select) {
    const showH2 = twoHandedModes.has(String(select.value || ""));
    const baseDamageType = findField(select, "damage_type");

    fieldRows(select).forEach((row) => {
      row.hidden = !showH2;
      row.style.display = showH2 ? "" : "none";
    });

    h2Fields.forEach((fieldName) => {
      const field = findField(select, fieldName);
      if (!field) {
        return;
      }
      field.disabled = !showH2;
      field.required = showH2 && ["h2_dice_amount", "h2_dice_faces", "h2_damage_type"].includes(fieldName);
      if (!showH2) {
        field.value = fieldName === "h2_damage_type" && baseDamageType ? baseDamageType.value : "";
      }
    });
  }

  function bind(root) {
    root.querySelectorAll("select[id$='wield_mode'], select[name$='wield_mode']").forEach((select) => {
      if (!(select instanceof HTMLSelectElement)) {
        return;
      }
      update(select);
      if (select.dataset.weaponStatsInlineBound === "1") {
        return;
      }
      select.dataset.weaponStatsInlineBound = "1";
      select.addEventListener("change", () => update(select));
      select.addEventListener("input", () => update(select));
    });
  }

  document.addEventListener("change", (event) => {
    const select = event.target;
    if (select instanceof HTMLSelectElement && /wield_mode$/.test(select.name || select.id || "")) {
      update(select);
    }
  });

  document.addEventListener("DOMContentLoaded", () => bind(document));
  window.addEventListener("load", () => bind(document));
  document.addEventListener("formset:added", (event) => bind(event.target));

  new MutationObserver((mutations) => {
    if (mutations.some((mutation) => mutation.addedNodes.length > 0)) {
      bind(document);
    }
  }).observe(document.documentElement, { childList: true, subtree: true });
})();
