(function () {
  "use strict";

  const twoHandedModes = new Set(["2h", "vh"]);
  const h2Fields = ["h2_dice_amount", "h2_dice_faces", "h2_flat_operator", "h2_flat_bonus", "h2_damage_type"];

  function closestFormRow(element) {
    return element.closest(".form-row") || element.closest(".form-group") || element.parentElement;
  }

  function closestFormScope(select) {
    return (
      select.closest(".inline-related")
      || select.closest("fieldset")
      || select.closest("form")
      || document
    );
  }

  function findRowsByFieldClass(select, fieldName) {
    const scope = closestFormScope(select);
    return Array.from(scope.querySelectorAll(`.field-${fieldName}`));
  }

  function findGroupedH2Rows(select) {
    const scope = closestFormScope(select);
    return Array.from(scope.querySelectorAll(".form-row, .form-group")).filter((row) =>
      h2Fields.some((fieldName) => row.classList.contains(`field-${fieldName}`) || row.querySelector(`[name$='${fieldName}']`))
    );
  }

  function findField(select, fieldName) {
    const prefix = select.id.replace(/wield_mode$/, "");
    const scope = closestFormScope(select);
    return (
      document.getElementById(`${prefix}${fieldName}`)
      || scope.querySelector(`[name$='${fieldName}']`)
      || document.getElementById(`id_${fieldName}`)
    );
  }

  function updateForm(select) {
    const showH2 = twoHandedModes.has(select.value);
    const rows = new Set(findGroupedH2Rows(select));

    h2Fields.forEach((fieldName) => {
      const field = findField(select, fieldName);
      findRowsByFieldClass(select, fieldName).forEach((row) => rows.add(row));
      if (field) {
        rows.add(closestFormRow(field));
        field.disabled = !showH2;
        field.required = showH2 && (fieldName === "h2_dice_amount" || fieldName === "h2_dice_faces" || fieldName === "h2_damage_type");
        if (!showH2) {
          const baseDamageType = findField(select, "damage_type");
          field.value = fieldName === "h2_damage_type" && baseDamageType ? baseDamageType.value : "";
        }
      }
    });

    rows.forEach((row) => {
      if (row) {
        row.hidden = !showH2;
        row.style.display = showH2 ? "" : "none";
      }
    });
  }

  function bind(root) {
    root.querySelectorAll("select[id$='wield_mode'], select[name$='wield_mode']").forEach((select) => {
      if (select.dataset.weaponStatsBound === "1") {
        updateForm(select);
        return;
      }
      select.dataset.weaponStatsBound = "1";
      select.addEventListener("change", () => updateForm(select));
      select.addEventListener("input", () => updateForm(select));
      updateForm(select);
    });
  }

  document.addEventListener("change", (event) => {
    const select = event.target;
    if (select instanceof HTMLSelectElement && /wield_mode$/.test(select.name || select.id || "")) {
      updateForm(select);
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
