/* Mobile status HUD: keeps damage and arcane power visible on small screens */

export function initMobileHud() {
  const hud = document.getElementById("mobileStatusHud");
  if (!hud) return;

  const damageCurEl = hud.querySelector("[data-hud-damage-cur]");
  const damageMaxEl = hud.querySelector("[data-hud-damage-max]");
  const damageFill  = hud.querySelector(".mobile-status-hud__fill--damage");
  const woundStageHudEl = hud.querySelector("[data-hud-wound-stage]");
  const woundPenaltyHudEl = hud.querySelector("[data-hud-wound-penalty]");
  const damageMetaEl = hud.querySelector("[data-hud-damage-meta]");
  const arcaneCurEl = hud.querySelector("[data-hud-arcane-cur]");
  const arcaneMaxEl = hud.querySelector("[data-hud-arcane-max]");
  const arcaneFill  = hud.querySelector(".mobile-status-hud__fill--arcane");

  function readInt(raw, fallback = 0) {
    const n = parseInt(String(raw ?? "").trim(), 10);
    return isNaN(n) ? fallback : n;
  }

  function setPct(el, cur, max) {
    if (!el) return;
    const pct = max > 0 ? Math.min(100, Math.max(0, (cur / max) * 100)) : 0;
    el.style.setProperty("--hud-pct", `${pct.toFixed(1)}%`);
  }

  function normalizeWoundStage(raw) {
    const text = String(raw ?? "").trim();
    return !text || text === "-" ? "Unverletzt" : text;
  }

  function normalizeWoundPenalty(raw) {
    const text = String(raw ?? "").trim();
    return !text || text === "-" ? "0" : text;
  }

  function syncDamage() {
    const gauge = document.querySelector(".damage_gauge");
    if (!gauge) return;
    const woundStageEl = document.querySelector(".damage_stage_value");
    const woundPenaltyEl = document.querySelector(".damage_penalty_value");
    const cur = readInt(gauge.dataset.damageValue, 0);
    const max = readInt(gauge.dataset.damageMax, 1);
    if (damageCurEl) damageCurEl.textContent = cur;
    if (damageMaxEl) damageMaxEl.textContent = max;
    if (woundStageHudEl) woundStageHudEl.textContent = normalizeWoundStage(woundStageEl?.textContent);
    if (woundPenaltyHudEl) woundPenaltyHudEl.textContent = normalizeWoundPenalty(woundPenaltyEl?.textContent);
    if (damageMetaEl) {
      const isDisabled = Boolean(
        woundStageEl?.classList.contains("is-disabled") ||
        woundPenaltyEl?.classList.contains("is-disabled"),
      );
      damageMetaEl.classList.toggle("is-disabled", isDisabled);
    }
    setPct(damageFill, cur, max);
  }

  function syncArcane() {
    const meter = document.querySelector(".arcane_meter");
    if (!meter) return;
    const cur = readInt(meter.dataset.arcaneCurrent, 0);
    const max = readInt(meter.dataset.arcaneMax, 1);
    if (arcaneCurEl) arcaneCurEl.textContent = cur;
    if (arcaneMaxEl) arcaneMaxEl.textContent = max;
    setPct(arcaneFill, cur, max);
  }

  function syncAll() {
    syncDamage();
    syncArcane();
  }

  syncAll();

  const gauge = document.querySelector(".damage_gauge");
  const meter = document.querySelector(".arcane_meter");

  if (gauge) {
    new MutationObserver(syncDamage).observe(gauge, {
      attributes: true,
      attributeFilter: ["data-damage-value", "data-damage-max"],
    });
  }

  if (meter) {
    new MutationObserver(syncArcane).observe(meter, {
      attributes: true,
      attributeFilter: ["data-arcane-current", "data-arcane-max"],
    });
  }

  document.addEventListener("charsheet:partials-applied", syncAll);
}
