import { applySheetPartials } from "./partial_updates.js";
import { getCsrfToken } from "./utils.js";

function readInt(value, fallback = 0) {
  const parsed = Number.parseInt(String(value ?? "").trim(), 10);
  return Number.isNaN(parsed) ? fallback : parsed;
}

function renderOptimisticArcaneMeter(nextValue) {
  const arcaneMeter = document.querySelector("#sheetDamagePanel .arcane_meter");
  const fill = arcaneMeter?.querySelector(".arcane_meter_fill");
  const valueNode = arcaneMeter?.querySelector(".arcane_meter_current");
  if (!(arcaneMeter instanceof HTMLElement) || !(fill instanceof HTMLElement) || !(valueNode instanceof HTMLElement)) {
    return null;
  }
  const previous = {
    current: readInt(arcaneMeter.dataset.arcaneCurrent, readInt(valueNode.textContent, 0)),
    max: readInt(arcaneMeter.dataset.arcaneMax, 0),
  };
  const safeMax = Math.max(0, previous.max);
  const clampedNext = Math.max(0, Math.min(readInt(nextValue, previous.current), safeMax));
  fill.style.width = `${safeMax <= 0 ? 0 : (clampedNext / safeMax) * 100}%`;
  valueNode.textContent = String(clampedNext);
  arcaneMeter.dataset.arcaneCurrent = String(clampedNext);
  return previous;
}

function rollbackOptimisticArcaneMeter(previous) {
  if (previous && typeof previous === "object") {
    renderOptimisticArcaneMeter(readInt(previous.current, 0));
  }
}

function renderOptimisticExperience(cost) {
  const valueNode = document.querySelector("#sheetExperiencePanel [data-current-experience]");
  if (!valueNode || cost <= 0) {
    return null;
  }
  const previous = valueNode.textContent;
  const current = readInt(previous, 0);
  if (current < cost) {
    return null;
  }
  valueNode.textContent = String(current - cost);
  return { valueNode, previous };
}

async function activateLesson(button) {
  const url = button.getAttribute("data-activate-url") || "";
  if (!url || button.dataset.lessonPending === "1") {
    return;
  }
  const selectedGroup = button.dataset.lessonCostGroup;
  const selectedKpCost = readInt(button.dataset.lessonKpCost, 0);
  const arcaneMeter = document.querySelector("#sheetDamagePanel .arcane_meter");
  const currentArcanePower = readInt(
    arcaneMeter?.dataset.arcaneCurrent,
    readInt(document.querySelector("#sheetDamagePanel .arcane_meter_current")?.textContent, 0),
  );
  const optimisticArcaneSnapshot = selectedKpCost > 0
    ? renderOptimisticArcaneMeter(currentArcanePower - selectedKpCost)
    : null;
  const optimisticExperienceSnapshot = renderOptimisticExperience(
    readInt(button.dataset.lessonEpCost, 0),
  );
  const buttons = document.querySelectorAll("[data-activate-lesson]");
  buttons.forEach((entry) => {
    entry.dataset.lessonPending = "1";
    entry.disabled = true;
  });
  try {
    const body = new URLSearchParams();
    if (selectedGroup) {
      body.set("cost_group", selectedGroup);
    }
    body.set("confirm_manual_costs", "1");
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCsrfToken(),
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      },
      body,
    });
    const payload = await response.json();
    if (!response.ok || !payload?.ok) {
      throw new Error(String(payload?.message || "Lektion konnte nicht angewendet werden."));
    }
    applySheetPartials(payload);
    const manualCosts = Array.isArray(payload.manual_costs) ? payload.manual_costs : [];
    if (manualCosts.length) {
      window.alert(`Lektion angewendet. Manuell zu behandeln: ${manualCosts.join(", ")}`);
    }
  } catch (error) {
    rollbackOptimisticArcaneMeter(optimisticArcaneSnapshot);
    if (optimisticExperienceSnapshot) {
      const { valueNode, previous } = optimisticExperienceSnapshot;
      valueNode.textContent = previous;
    }
    window.alert(error instanceof Error ? error.message : "Lektion konnte nicht angewendet werden.");
  } finally {
    buttons.forEach((entry) => {
      entry.dataset.lessonPending = "0";
      entry.disabled = false;
    });
  }
}

export function initLessonPanel() {
  const panel = document.getElementById("sheetLessonPanel");
  if (!(panel instanceof HTMLElement) || panel.dataset.lessonBound === "1") {
    return;
  }
  panel.dataset.lessonBound = "1";
  const filterInput = panel.querySelector("#lessonFilterInput");
  const groups = Array.from(panel.querySelectorAll("[data-lesson-group]"));

  const applyFilter = () => {
    const needle = filterInput instanceof HTMLInputElement ? filterInput.value.trim().toLowerCase() : "";
    groups.forEach((group) => {
      let visibleRows = 0;
      group.querySelectorAll("[data-lesson-search]").forEach((row) => {
        const textMatches = !needle || String(row.getAttribute("data-lesson-search") || "").includes(needle);
        row.hidden = !textMatches;
        if (!row.hidden) {
          visibleRows += 1;
        }
      });
      group.hidden = visibleRows === 0;
    });
  };

  if (filterInput instanceof HTMLInputElement) {
    filterInput.addEventListener("input", applyFilter);
  }
  panel.querySelectorAll("[data-lesson-card-trigger]").forEach((entry) => {
    entry.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      const nestedInteractive = event.target instanceof Element
        ? event.target.closest("button, a, input, select, textarea")
        : null;
      if (nestedInteractive && nestedInteractive !== entry) {
        return;
      }
      event.preventDefault();
      entry.click();
    });
  });
  panel.querySelectorAll("[data-activate-lesson]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      activateLesson(button);
    });
  });
}
