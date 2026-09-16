import { applySheetPartials } from "./partial_updates.js";
import { getCsrfToken } from "./utils.js";

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

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

function parseCostGroups(button) {
  try {
    const parsed = JSON.parse(button.getAttribute("data-lesson-cost-groups") || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch (_error) {
    return [];
  }
}

function chooseCostGroup(groups) {
  if (!groups.length) {
    return Promise.resolve({ number: null, kp_cost: 0, manual_costs: [] });
  }
  if (
    groups.length === 1
    && (!Array.isArray(groups[0].manual_costs) || !groups[0].manual_costs.length)
  ) {
    return Promise.resolve(groups[0]);
  }
  if (typeof HTMLDialogElement === "undefined") {
    let selected = groups[0];
    if (groups.length > 1) {
      const answer = window.prompt(
        `Kostengruppe wählen:\n${groups.map((group, index) => `${index + 1}. ${group.label}`).join("\n")}`,
        "1",
      );
      selected = groups[Number.parseInt(answer || "", 10) - 1];
      if (!selected) {
        return Promise.resolve(null);
      }
    }
    const selectedManualCosts = Array.isArray(selected.manual_costs)
      ? selected.manual_costs : [];
    if (selectedManualCosts.length) {
      const message = [
        "Diese Kosten werden nur bestaetigt und nicht automatisch verrechnet:",
        selectedManualCosts.join("\n"),
        "",
        "Kosten anwenden?",
      ].join("\n");
      if (!window.confirm(message)) {
        return Promise.resolve(null);
      }
    }
    return Promise.resolve(selected);
  }

  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    dialog.className = "lesson_cost_dialog";
    dialog.innerHTML = `
      <form method="dialog" class="lesson_cost_dialog__form">
        <h3>Anwendungskosten wählen</h3>
        <fieldset>
          <legend>${groups.length > 1 ? "Alternative Kostengruppe" : "Kosten"}</legend>
        ${groups.map((group, index) => `
          <label>
            <input type="radio" name="lesson_cost_group" value="${escapeHtml(group.number)}" ${index === 0 ? "checked" : ""}>
            <span>${escapeHtml(group.label)}</span>
            ${(Array.isArray(group.manual_costs) && group.manual_costs.length) ? `<small>Manuell zu behandeln: ${group.manual_costs.map(escapeHtml).join(", ")}</small>` : ""}
          </label>
        `).join("")}
        </fieldset>
        <div class="lesson_cost_dialog__actions">
          <button type="submit" value="cancel">Abbrechen</button>
          <button type="submit" value="activate" class="lesson_cost_dialog__confirm">Kosten zahlen</button>
        </div>
      </form>
    `;
    document.body.appendChild(dialog);
    dialog.addEventListener("close", () => {
      if (dialog.returnValue !== "activate") {
        dialog.remove();
        resolve(null);
        return;
      }
      const input = dialog.querySelector('input[name="lesson_cost_group"]:checked');
      const selected = groups.find(
        (group) => Number(group.number) === Number(input?.value),
      );
      dialog.remove();
      resolve(selected || null);
    }, { once: true });
    dialog.showModal();
  });
}

async function activateLesson(button) {
  const url = button.getAttribute("data-activate-url") || "";
  if (!url || button.dataset.lessonPending === "1") {
    return;
  }
  const groups = parseCostGroups(button);
  const selectedGroup = await chooseCostGroup(groups);
  if (selectedGroup === null) {
    return;
  }
  const selectedKpCost = readInt(selectedGroup.kp_cost, 0);
  const arcaneMeter = document.querySelector("#sheetDamagePanel .arcane_meter");
  const currentArcanePower = readInt(
    arcaneMeter?.dataset.arcaneCurrent,
    readInt(document.querySelector("#sheetDamagePanel .arcane_meter_current")?.textContent, 0),
  );
  const optimisticArcaneSnapshot = selectedKpCost > 0
    ? renderOptimisticArcaneMeter(currentArcanePower - selectedKpCost)
    : null;
  button.dataset.lessonPending = "1";
  button.disabled = true;
  try {
    const body = new URLSearchParams();
    if (selectedGroup.number !== null) {
      body.set("cost_group", String(selectedGroup.number));
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
    window.alert(error instanceof Error ? error.message : "Lektion konnte nicht angewendet werden.");
  } finally {
    button.dataset.lessonPending = "0";
    button.disabled = false;
  }
}

export function initLessonPanel() {
  const panel = document.getElementById("sheetLessonPanel");
  if (!(panel instanceof HTMLElement) || panel.dataset.lessonBound === "1") {
    return;
  }
  panel.dataset.lessonBound = "1";
  const filterInput = panel.querySelector("#lessonFilterInput");
  const rows = Array.from(panel.querySelectorAll("[data-lesson-search]"));
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
  rows.forEach((row) => {
    const button = row.querySelector("[data-activate-lesson]");
    button?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      activateLesson(button);
    });
  });
}
