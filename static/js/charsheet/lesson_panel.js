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

function parseAlternativeGroups(button) {
  try {
    const parsed = JSON.parse(button.getAttribute("data-lesson-alternatives") || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch (_error) {
    return [];
  }
}

function parseManualCosts(button) {
  try {
    const parsed = JSON.parse(button.getAttribute("data-lesson-manual-costs") || "[]");
    return Array.isArray(parsed) ? parsed.map((value) => String(value)) : [];
  } catch (_error) {
    return [];
  }
}

function lessonOpenStateKey() {
  return `charsheet.lessonPanel.openSchools:${window.location.pathname}`;
}

function readOpenSchools() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(lessonOpenStateKey()) || "[]");
    return new Set(Array.isArray(parsed) ? parsed.map((value) => String(value)) : []);
  } catch (_error) {
    return new Set();
  }
}

function writeOpenSchools(openSchools) {
  try {
    window.localStorage.setItem(lessonOpenStateKey(), JSON.stringify(Array.from(openSchools)));
  } catch (_error) {
    // Non-critical preference storage; the panel remains usable without it.
  }
}

function chooseCosts(groups, ungroupedManualCosts) {
  if (!groups.length && !ungroupedManualCosts.length) {
    return Promise.resolve({});
  }
  if (typeof HTMLDialogElement === "undefined") {
    const choices = {};
    for (const group of groups) {
      const options = Array.isArray(group.options) ? group.options : [];
      const answer = window.prompt(
        `Kostenoption wählen:\n${options.map((option, index) => `${index + 1}. ${option.label}`).join("\n")}`,
        "1",
      );
      const selected = options[Number.parseInt(answer || "", 10) - 1];
      if (!selected) {
        return Promise.resolve(null);
      }
      choices[group.number] = selected.id;
    }
    const selectedManualCosts = [
      ...ungroupedManualCosts,
      ...groups.flatMap((group) => {
        const selectedId = choices[group.number];
        const selected = (Array.isArray(group.options) ? group.options : [])
          .find((option) => Number(option.id) === Number(selectedId));
        return selected?.manual ? [selected.label] : [];
      }),
    ];
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
    return Promise.resolve(choices);
  }

  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    dialog.className = "lesson_cost_dialog";
    dialog.innerHTML = `
      <form method="dialog" class="lesson_cost_dialog__form">
        <h3>Anwendungskosten wählen</h3>
        ${ungroupedManualCosts.length ? `
          <p class="lesson_cost_dialog__manual">
            Diese Kosten werden bestätigt, aber nicht automatisch verrechnet:
            <strong>${ungroupedManualCosts.map(escapeHtml).join(", ")}</strong>
          </p>
        ` : ""}
        ${groups.map((group) => `
          <fieldset>
            <legend>Alternative ${escapeHtml(group.number)}</legend>
            ${(Array.isArray(group.options) ? group.options : []).map((option, index) => `
              <label>
                <input type="radio" name="lesson_cost_${escapeHtml(group.number)}" value="${escapeHtml(option.id)}" ${index === 0 ? "checked" : ""}>
                <span>${escapeHtml(option.label)}</span>
                ${option.description || option.manual ? `<small>${option.manual ? "Manuell zu behandeln. " : ""}${escapeHtml(option.description || "")}</small>` : ""}
              </label>
            `).join("")}
          </fieldset>
        `).join("")}
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
      const choices = {};
      groups.forEach((group) => {
        const selected = dialog.querySelector(`input[name="lesson_cost_${String(group.number)}"]:checked`);
        if (selected instanceof HTMLInputElement) {
          choices[group.number] = Number.parseInt(selected.value, 10);
        }
      });
      dialog.remove();
      resolve(choices);
    }, { once: true });
    dialog.showModal();
  });
}

async function activateLesson(button) {
  const url = button.getAttribute("data-activate-url") || "";
  if (!url || button.dataset.lessonPending === "1") {
    return;
  }
  const groups = parseAlternativeGroups(button);
  const choices = await chooseCosts(groups, parseManualCosts(button));
  if (choices === null) {
    return;
  }
  const selectedKpCost = groups.reduce((sum, group) => {
    const selectedId = choices[group.number];
    const selected = (Array.isArray(group.options) ? group.options : [])
      .find((option) => Number(option.id) === Number(selectedId));
    return sum + (selected?.cost_type === "kp" ? readInt(selected.value, 0) : 0);
  }, readInt(button.getAttribute("data-lesson-base-kp-cost"), 0));
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
    Object.entries(choices).forEach(([group, costId]) => {
      body.set(`cost_choice_${group}`, String(costId));
    });
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
  const openSchools = readOpenSchools();
  let activeSchool = "all";

  const applyFilter = () => {
    const needle = filterInput instanceof HTMLInputElement ? filterInput.value.trim().toLowerCase() : "";
    groups.forEach((group) => {
      const schoolMatches = activeSchool === "all" || group.getAttribute("data-lesson-school-id") === activeSchool;
      let visibleRows = 0;
      group.querySelectorAll("[data-lesson-search]").forEach((row) => {
        const textMatches = !needle || String(row.getAttribute("data-lesson-search") || "").includes(needle);
        row.hidden = !(schoolMatches && textMatches);
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
  panel.querySelectorAll("[data-lesson-school-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      activeSchool = button.getAttribute("data-lesson-school-filter") || "all";
      panel.querySelectorAll("[data-lesson-school-filter]").forEach((candidate) => {
        const active = candidate === button;
        candidate.classList.toggle("is-active", active);
        candidate.setAttribute("aria-pressed", active ? "true" : "false");
      });
      applyFilter();
    });
  });
  groups.forEach((group) => {
    const toggle = group.querySelector("[data-lesson-group-toggle]");
    const list = group.querySelector(".lesson_group_rows");
    const schoolId = String(group.getAttribute("data-lesson-school-id") || "");
    if (list instanceof HTMLElement && toggle instanceof HTMLElement && openSchools.has(schoolId)) {
      list.hidden = false;
      toggle.setAttribute("aria-expanded", "true");
    }
    toggle?.addEventListener("click", () => {
      if (!(list instanceof HTMLElement)) {
        return;
      }
      list.hidden = !list.hidden;
      toggle.setAttribute("aria-expanded", list.hidden ? "false" : "true");
      if (schoolId) {
        if (list.hidden) {
          openSchools.delete(schoolId);
        } else {
          openSchools.add(schoolId);
        }
        writeOpenSchools(openSchools);
      }
    });
  });
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
