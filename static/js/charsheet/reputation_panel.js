import { loadJsonStorage, saveJsonStorage } from "./utils.js";

export function initReputationPanel() {
  const reputationWrapper = document.querySelector(".reputation_wrapper");
  const reputationList = document.getElementById("reputationList");
  const reputationEditBtn = document.getElementById("reputationEditBtn");
  if (!reputationWrapper || !reputationList || !reputationEditBtn) {
    return;
  }

  const reputationInputs = Array.from(reputationList.querySelectorAll(".reputation_input"));
  const characterId = reputationList.dataset.characterId || "0";
  const storageKey = `charsheet.reputation.${characterId}`;

  const saveReputation = () => {
    const payload = {};
    reputationInputs.forEach((input) => {
      const key = input.dataset.reputationKey || "";
      if (key) {
        payload[key] = input.value || "";
      }
    });
    saveJsonStorage(storageKey, payload);
  };

  const setEditMode = (isEditing) => {
    reputationWrapper.classList.toggle("is-editing", isEditing);
    reputationInputs.forEach((input) => {
      input.readOnly = !isEditing;
    });
    reputationEditBtn.setAttribute("aria-pressed", String(isEditing));
    if (isEditing && reputationInputs.length) {
      reputationInputs[0].focus();
    }
    if (!isEditing) {
      saveReputation();
    }
  };

  const persisted = loadJsonStorage(storageKey, {});
  reputationInputs.forEach((input) => {
    const key = input.dataset.reputationKey || "";
    input.value = key && Object.prototype.hasOwnProperty.call(persisted, key) ? (persisted[key] || "") : "";
    input.addEventListener("input", () => {
      if (reputationWrapper.classList.contains("is-editing")) {
        saveReputation();
      }
    });
  });

  setEditMode(false);
  reputationEditBtn.addEventListener("click", () => {
    setEditMode(!reputationWrapper.classList.contains("is-editing"));
  });
}
