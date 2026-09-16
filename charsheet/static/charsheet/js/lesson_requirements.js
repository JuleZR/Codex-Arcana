(function () {
  "use strict";
  const typeFields = {
    school_technique: ["required_school", "required_technique"],
    school_specialisation: ["required_school", "specialisation"],
    magic_school_level: ["magic_school", "minimum_value"],
    clerical_magic_level: ["minimum_value"],
    druid_circle_level: ["druid_circle", "minimum_value"],
    specific_creature: ["creature"],
  };

  function initialize(row) {
    if (!row || row.classList.contains("empty-form") || row.dataset.requirementBound) return;
    row.dataset.requirementBound = "1";
    const input = (name) => row.querySelector(`[name$="-${name}"]`);
    const type = input("requirement_type");
    const school = input("required_school");
    const message = row.querySelector("[data-requirement-message]");
    let revision = 0;
    let previousSchool = school.value;

    function replaceOptions(select, options, selected) {
      select.replaceChildren(new Option("---------", ""));
      options.forEach((item) => select.add(new Option(item.label, String(item.id))));
      select.value = options.some((item) => String(item.id) === selected) ? selected : "";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }

    async function refresh(reset) {
      const currentRevision = ++revision;
      const field = type.value === "school_technique" ? "required_technique"
        : type.value === "school_specialisation" ? "specialisation" : null;
      message.textContent = "";
      if (!field) return;
      const select = input(field);
      const selected = reset ? "" : select.value;
      const schoolId = school.value;
      // Immediately remove stale options, including while a request is pending.
      replaceOptions(select, [], "");
      select.disabled = true;
      if (!schoolId) return;
      try {
        const url = new URL(select.dataset.optionsUrl, window.location.origin);
        url.searchParams.set("school", schoolId);
        const response = await fetch(url, { credentials: "same-origin" });
        if (!response.ok) throw new Error("Optionen konnten nicht geladen werden.");
        const payload = await response.json();
        if (currentRevision !== revision) return;
        replaceOptions(select, payload.results, selected);
        select.disabled = false;
      } catch (error) {
        if (currentRevision === revision) {
          message.textContent = "Auswahl konnte nicht geladen werden. Bitte Schule erneut auswählen.";
        }
      }
    }

    function updateType(reset) {
      const fields = typeFields[type.value] || [];
      row.querySelectorAll("[data-requirement-field]").forEach((container) => {
        const name = container.dataset.requirementField;
        const visible = fields.includes(name);
        container.hidden = !visible;
        const control = input(name);
        control.disabled = !visible;
        if (!visible) control.value = "";
      });
      previousSchool = school.value;
      refresh(reset);
    }

    function schoolChanged() {
      // Django emits change during related-widget initialization as well.
      // Only an actual school change invalidates the saved dependent choice.
      if (school.value === previousSchool) return;
      previousSchool = school.value;
      refresh(true);
    }

    type.addEventListener("change", () => updateType(true));
    school.addEventListener("change", schoolChanged);
    if (window.django?.jQuery) {
      // Django's related-object popups emit a jQuery-only change event.
      window.django.jQuery(school).on("change.lessonRequirement", (event) => {
        if (!event.originalEvent) schoolChanged();
      });
    }
    updateType(false);
  }

  function initializeAll(root) {
    if (root.matches?.(".lesson-requirements .form-row")) initialize(root);
    root.querySelectorAll(".lesson-requirements .form-row").forEach(initialize);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => initializeAll(document));
  } else {
    initializeAll(document);
  }
  document.addEventListener("formset:added", (event) => initializeAll(event.target));
})();
