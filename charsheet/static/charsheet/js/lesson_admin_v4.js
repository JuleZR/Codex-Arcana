(function () {
  function ready(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback);
    } else {
      callback();
    }
  }

  function replaceOptions(select, rows, selectedValue) {
    select.innerHTML = "";

    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "---------";
    select.appendChild(empty);

    rows.forEach((row) => {
      const option = document.createElement("option");
      option.value = String(row.id);
      option.textContent = row.label;
      if (String(row.id) === String(selectedValue || "")) {
        option.selected = true;
      }
      select.appendChild(option);
    });

    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  async function refreshTechniques(schoolSelect, techniqueSelect, selectedValue) {
    const schoolId = schoolSelect.value;
    if (!schoolId) {
      replaceOptions(techniqueSelect, [], "");
      return;
    }

    techniqueSelect.disabled = true;
    try {
      const url = new URL("/admin/charsheet/lesson/techniques/", window.location.origin);
      url.searchParams.set("school", schoolId);
      const response = await fetch(url.toString(), {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
      });
      if (!response.ok) {
        throw new Error(`Technique lookup failed: ${response.status}`);
      }
      const payload = await response.json();
      replaceOptions(techniqueSelect, payload.results || [], selectedValue || "");
    } catch (error) {
      console.error(error);
    } finally {
      techniqueSelect.disabled = false;
    }
  }

  ready(function () {
    const schoolSelect = document.getElementById("id_school");
    const techniqueSelect = document.getElementById("id_technique");
    if (!schoolSelect || !techniqueSelect) {
      return;
    }

    const initialSchoolValue = schoolSelect.value;
    const initialTechniqueValue = techniqueSelect.value;

    const onSchoolChange = function () {
      const keepInitialSelection =
        schoolSelect.value === initialSchoolValue && initialTechniqueValue;
      refreshTechniques(
        schoolSelect,
        techniqueSelect,
        keepInitialSelection ? initialTechniqueValue : ""
      );
    };

    schoolSelect.addEventListener("change", onSchoolChange);
    if (window.django && window.django.jQuery) {
      window.django.jQuery(schoolSelect).on("change", onSchoolChange);
    }

    const previousDismissAddRelatedObjectPopup = window.dismissAddRelatedObjectPopup;
    if (typeof previousDismissAddRelatedObjectPopup === "function") {
      window.dismissAddRelatedObjectPopup = function (win, newId, newRepr) {
        previousDismissAddRelatedObjectPopup.apply(this, arguments);
        if (win && win.name && win.name.includes("school")) {
          refreshTechniques(schoolSelect, techniqueSelect, "");
        }
      };
    }
  });
})();
