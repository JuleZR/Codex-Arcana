document.addEventListener("DOMContentLoaded", () => {
  const canFlyInput = document.getElementById("id_can_fly");
  if (!canFlyInput) {
    return;
  }

  const flyFieldIds = ["combat_fly_speed", "march_fly_speed", "sprint_fly_speed"];
  const rows = flyFieldIds
    .map((name) => document.querySelector(`.form-row.field-${name}`))
    .filter(Boolean);

  const inputs = flyFieldIds
    .map((name) => document.getElementById(`id_${name}`))
    .filter(Boolean);

  const toggleFlyFields = () => {
    const isEnabled = canFlyInput.checked;
    rows.forEach((row) => {
      row.style.display = isEnabled ? "" : "none";
    });
    if (!isEnabled) {
      inputs.forEach((input) => {
        input.value = "";
      });
    }
  };

  canFlyInput.addEventListener("change", toggleFlyFields);
  toggleFlyFields();
});
