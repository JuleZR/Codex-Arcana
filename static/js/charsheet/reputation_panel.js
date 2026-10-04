export function initReputationPanel() {
  const reputationList = document.getElementById("reputationList");
  if (!reputationList) {
    return;
  }

  document.addEventListener("charsheet:reputation-points-updated", (event) => {
    const points = event.detail;
    if (!points) return;
    document.querySelectorAll("#reputationList [data-reputation-points]").forEach((form) => {
      const value = points[form.dataset.reputationPoints];
      if (value !== undefined) form.querySelector("span").textContent = String(value);
      if (form.dataset.reputationPoints === "artefact") {
        form.querySelector('button[value="1"]').disabled = Number(points.availablePersonalRank) < 1;
      }
    });
  });

  const updateArtifactDisplay = () => {
    const fame = document.getElementById("sheetFamePanel");
    const form = document.querySelector('[data-reputation-points="artefact"]');
    if (!fame || !form) return;
    form.querySelector("span").textContent = fame.dataset.artifactInvestment || "0";
    form.querySelector('button[value="1"]').disabled =
      document.body.dataset.readOnly === "1" || Number(fame.dataset.availablePersonalRank) < 1;
  };
  document.addEventListener("charsheet:partials-applied", updateArtifactDisplay);
  document.addEventListener("sheet:action-success", (event) => {
    if (event.target.matches('[data-reputation-points="artefact"]')) {
      queueMicrotask(updateArtifactDisplay);
    }
  });
}
