(function () {
  "use strict";

  const twoHandedModes = new Set(["2h", "vh"]);
  const h2Fields = ["h2_dice_amount", "h2_dice_faces", "h2_flat_operator", "h2_flat_bonus"];

  function closestFormRow(element) {
    return element.closest(".form-row") || element.closest(".form-group") || element.parentElement;
  }

  function findField(select, fieldName) {
    const prefix = select.id.replace(/wield_mode$/, "");
    return document.getElementById(`${prefix}${fieldName}`) || document.getElementById(`id_${fieldName}`);
  }

  function updateForm(select) {
    const showH2 = twoHandedModes.has(select.value);
    const rows = new Set();

    h2Fields.forEach((fieldName) => {
      const field = findField(select, fieldName);
      if (!field) {
        return;
      }
      rows.add(closestFormRow(field));
      field.disabled = !showH2;
      if (!showH2) {
        field.value = field.tagName === "SELECT" ? "" : "";
      }
    });

    rows.forEach((row) => {
      if (row) {
        row.hidden = !showH2;
      }
    });
  }

  function bind(root) {
    root.querySelectorAll("select[id$='wield_mode']").forEach((select) => {
      if (select.dataset.weaponStatsBound === "1") {
        return;
      }
      select.dataset.weaponStatsBound = "1";
      select.addEventListener("change", () => updateForm(select));
      updateForm(select);
    });
  }

  document.addEventListener("DOMContentLoaded", () => bind(document));
  document.addEventListener("formset:added", (event) => bind(event.target));
})();
