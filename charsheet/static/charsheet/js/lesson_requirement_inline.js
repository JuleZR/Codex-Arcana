(function () {
  "use strict";

  function syncRow(row) {
    var type = row.querySelector("select[name$='-requirement_type']");
    if (!type) return;
    var mapping = {
      school: ["required_school", "minimum_value"],
      skill: ["required_skill", "minimum_value"],
      technique: ["required_technique"],
      lesson: ["required_lesson"],
    };
    var visible = new Set(mapping[type.value] || []);
    ["required_school", "required_skill", "required_technique", "required_lesson", "minimum_value"].forEach(function (name) {
      var input = row.querySelector("[name$='-" + name + "']");
      var cell = input && input.closest("td");
      if (!cell) return;
      var isVisible = visible.has(name);
      cell.hidden = false;
      cell.style.visibility = isVisible ? "" : "hidden";
      cell.querySelectorAll("input, select, textarea").forEach(function (field) {
        field.disabled = !isVisible;
      });
    });
  }

  function init(root) {
    root.querySelectorAll(".inline-related tbody tr").forEach(function (row) {
      syncRow(row);
      var type = row.querySelector("select[name$='-requirement_type']");
      if (type && !type.dataset.lessonRequirementBound) {
        type.dataset.lessonRequirementBound = "1";
        type.addEventListener("change", function () { syncRow(row); });
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () { init(document); });
  document.addEventListener("formset:added", function (event) { init(event.target || document); });
}());
