import { initItemTransfers } from "./item_transfers.js?v=20261015-post3";

let submitting = false;
let contentObserver = null;
const notifyParent = (payload) => {
  if (window.parent !== window) {
    window.parent.postMessage({ type: "codex:item-transfer-accepted", payload }, window.location.origin);
  }
};
const feedback = (message, error = false) => {
  const box = document.querySelector("[data-transfer-feedback]");
  if (!box) return;
  box.textContent = message;
  box.classList.toggle("is-error", error);
  box.hidden = !message;
};

const activateTab = (name, focus = false) => {
  const tabs = Array.from(document.querySelectorAll("[data-transfer-tab]"));
  const selected = tabs.find((tab) => tab.dataset.transferTab === name) || tabs[0];
  if (!selected) return;
  tabs.forEach((tab) => {
    const active = tab === selected;
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
  });
  document.querySelectorAll("[data-transfer-view]").forEach((panel) => {
    panel.hidden = panel.dataset.transferView !== selected.dataset.transferTab;
  });
  const url = new URL(window.location.href);
  url.searchParams.set("tab", selected.dataset.transferTab);
  window.history.replaceState(null, "", url);
  if (focus) selected.focus();
};

const refreshCenter = async () => {
  const url = new URL(window.location.href);
  url.searchParams.delete("item");
  const response = await fetch(url, { credentials: "same-origin" });
  if (!response.ok) throw new Error("Die Postzentrale konnte nicht aktualisiert werden.");
  const page = new DOMParser().parseFromString(await response.text(), "text/html");
  const next = page.querySelector(".transfer-center");
  if (!next) throw new Error("Die Postzentrale konnte nicht aktualisiert werden.");
  contentObserver?.disconnect();
  document.querySelector(".transfer-center").replaceWith(next);
  window.history.replaceState(null, "", url);
  initTransferCenter();
};

function initTransferCenter() {
  const center = document.querySelector(".transfer-center");
  if (!center || center.dataset.bound === "1") return;
  center.dataset.bound = "1";
  const reportSize = () => {
    if (window.parent === window) return;
    window.parent.postMessage({
      type: "codex:item-transfer-size",
      height: Math.ceil(center.getBoundingClientRect().height),
    }, window.location.origin);
  };
  if (typeof ResizeObserver !== "undefined") {
    contentObserver = new ResizeObserver(reportSize);
    contentObserver.observe(center);
  }
  window.requestAnimationFrame(reportSize);

  const url = new URL(window.location.href);
  const item = url.searchParams.get("item");
  center.querySelectorAll("[data-transfer-item]").forEach((checkbox) => {
    checkbox.checked = checkbox.value === item;
  });
  activateTab(url.searchParams.get("tab") || "inbox");

  const checkboxes = Array.from(center.querySelectorAll("[data-transfer-checkbox]"));
  const selectAll = center.querySelector("[data-transfer-select-all]");
  const updateBulk = () => {
    const selected = checkboxes.filter((box) => box.checked);
    if (selectAll) {
      selectAll.checked = checkboxes.length > 0 && selected.length === checkboxes.length;
      selectAll.indeterminate = selected.length > 0 && selected.length < checkboxes.length;
    }
    const button = center.querySelector("[data-transfer-accept-selected]");
    if (button) {
      button.disabled = !selected.length;
      button.textContent = selected.length ? selected.length + " annehmen" : "Auswahl annehmen";
    }
  };
  const filter = (view) => {
    const query = (view.querySelector("[data-transfer-search]")?.value || "").trim().toLocaleLowerCase("de");
    const status = view.querySelector("[data-transfer-status]")?.value || "all";
    const offers = Array.from(view.querySelectorAll("[data-transfer-offer]"));
    offers.forEach((offer) => {
      const matchesStatus = status === "all" || (status === "pending"
        ? offer.dataset.status === "pending" : offer.dataset.status !== "pending");
      offer.hidden = !matchesStatus || !offer.textContent.toLocaleLowerCase("de").includes(query);
    });
    const empty = view.querySelector("[data-transfer-no-results]");
    if (empty) empty.hidden = !offers.length || offers.some((offer) => !offer.hidden);
  };
  center.addEventListener("input", (event) => {
    if (event.target.matches("[data-transfer-search], [data-transfer-status]")) {
      filter(event.target.closest("[data-transfer-view]"));
    }
  });
  center.addEventListener("change", (event) => {
    if (event.target === selectAll) checkboxes.forEach((box) => { box.checked = selectAll.checked; });
    updateBulk();
  });
  center.addEventListener("click", (event) => {
    const tab = event.target.closest("[data-transfer-tab], [data-transfer-go]");
    if (tab) activateTab(tab.dataset.transferTab || tab.dataset.transferGo);
    if (event.target.closest("[data-transfer-close]")) {
      window.parent.postMessage({ type: "codex:item-transfer-close" }, window.location.origin);
    }
    if (event.target.closest("[data-transfer-clear-selection]")) {
      checkboxes.forEach((box) => { box.checked = false; });
      updateBulk();
    }
    const toggle = event.target.closest("[data-transfer-selection-toggle]");
    if (toggle) {
      const expanded = toggle.getAttribute("aria-expanded") !== "true";
      toggle.setAttribute("aria-expanded", String(expanded));
      toggle.textContent = expanded ? "Auswahl beenden" : "Auswählen";
      center.querySelector("[data-transfer-bulk-accept]").hidden = !expanded;
      center.querySelectorAll(".transfer-offer__select").forEach((label) => { label.hidden = !expanded; });
      if (!expanded) checkboxes.forEach((box) => { box.checked = false; });
      updateBulk();
    }
  });
  center.querySelector('[role="tablist"]')?.addEventListener("keydown", (event) => {
    if (!["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const tabs = Array.from(center.querySelectorAll("[data-transfer-tab]"));
    const index = tabs.indexOf(document.activeElement);
    if (index < 0) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1
      : (index + (["ArrowDown", "ArrowRight"].includes(event.key) ? 1 : -1) + tabs.length) % tabs.length;
    activateTab(tabs[next].dataset.transferTab, true);
  });
  center.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.method.toLowerCase() !== "post" || event.defaultPrevented) return;
    event.preventDefault();
    if (submitting || form.dataset.completed === "1") return;
    if (event.submitter?.hasAttribute("data-transfer-accept-all")) {
      checkboxes.forEach((box) => { box.checked = true; });
      updateBulk();
    }
    if (form.matches("[data-transfer-recall]")
      && !window.confirm("Diese ausstehende Sendung zurückrufen?")) return;
    const data = new FormData(form);
    const buttons = Array.from(center.querySelectorAll('button[type="submit"], form button:not([type])'));
    submitting = true;
    buttons.forEach((button) => { button.disabled = true; });
    let completed = false;
    try {
      const response = await fetch(form.action, {
        method: "POST", body: data, credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest", Accept: "application/json" },
      });
      const payload = await response.json();
      if (!response.ok || !payload?.ok) throw new Error(payload?.message || "Die Übergabe konnte nicht verarbeitet werden.");
      completed = true;
      form.dataset.completed = "1";
      const sender = form.querySelector('[name="sender_id"], [name="return_character_id"]')?.value;
      notifyParent({ ...payload, transferCharacterId: sender || payload.characterId });
      await refreshCenter();
      const gmEdit = data.get("recipient_type") === "gm_group";
      const sentItems = data.getAll("item_ids").length;
      const sentMoney = Number.parseInt(data.get("money") || "0", 10) > 0;
      const sentMessage = gmEdit ? "Gegenstand zur SL-Bearbeitung aufgegeben."
        : [sentItems ? "Gegenstände aufgegeben; sie warten auf Annahme." : "",
          sentMoney ? "Geld unmittelbar übertragen." : ""].filter(Boolean).join(" ");
      feedback(form.id === "itemTransferForm"
        ? sentMessage
        : "Sendung erfolgreich aktualisiert.");
    } catch (error) {
      feedback((completed ? "Die Aktion wurde ausgeführt. " : "") + (error instanceof Error ? error.message : "Die Übergabe konnte nicht verarbeitet werden."), true);
      if (completed) {
        // Keep a completed request locked if refreshing fails; never resend it.
        buttons.forEach((button) => { button.disabled = true; });
      }
    } finally {
      submitting = false;
      if (!completed) buttons.forEach((button) => { button.disabled = false; });
      if (!completed) updateBulk();
    }
  });
  updateBulk();
  initItemTransfers({ eventRoot: center.querySelector("#itemTransferDialog") || center });
}
initTransferCenter();
