import { createFloatingWindowController, placeWindow } from "./charsheet/window_manager.js";

const win = document.querySelector("[data-dashboard-item-window]");
const frame = document.querySelector("[data-staff-items-frame]");
const backdrop = document.querySelector("[data-staff-items-backdrop]");
const closeButton = document.querySelector("[data-close-staff-items]");

if (win && frame && backdrop && closeButton) {
  const dashboard = document.querySelector(".dashboard_spread");
  const wasInert = dashboard?.inert || false;
  const controller = createFloatingWindowController({
    windowEl: win, closeButton,
    handle: document.querySelector("[data-staff-items-handle]"),
    allowPersistedOpen: false,
    storageKey: "dashboard.itemWorkshop",
  });
  let previousFocus;
  const close = () => {
    controller.close();
    backdrop.hidden = true;
    document.body.classList.remove("staff-items-open");
    if (dashboard) dashboard.inert = wasInert;
    previousFocus?.focus();
  };
  const keydown = (event) => {
    if (event.key === "Escape" && win.classList.contains("is-open")) {
      event.preventDefault();
      close();
    }
  };
  document.querySelectorAll("[data-open-staff-items]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!win.classList.contains("is-open")) previousFocus = button;
      const url = new URL(button.dataset.openStaffItems, window.location.origin);
      url.searchParams.set("embedded", "1");
      if (!frame.getAttribute("src")) frame.src = url.href;
      document.getElementById("dashboardItemWindowTitle").textContent = button.dataset.itemWindowTitle;
      backdrop.hidden = false;
      document.body.classList.add("staff-items-open");
      if (dashboard) dashboard.inert = true;
      controller.open();
      const rect = win.getBoundingClientRect();
      placeWindow(win, (window.innerWidth - rect.width) / 2, (window.innerHeight - rect.height) / 2);
      closeButton.focus();
    });
  });
  frame.addEventListener("load", () => {
    frame.contentDocument?.addEventListener("keydown", keydown);
    const title = frame.contentDocument?.body.dataset.itemWindowTitle;
    if (title) document.getElementById("dashboardItemWindowTitle").textContent = title;
    const resources = document.querySelector("[data-staff-item-resources]");
    if (resources) resources.hidden = frame.contentDocument?.body.dataset.itemEditor !== "1";
  });
  window.addEventListener("message", (event) => {
    if (event.origin !== window.location.origin || event.source !== frame.contentWindow || event.data?.type !== "staff-item-workshop-status") return;
    const price = Number(event.data.price);
    const count = Number(event.data.runeCount);
    if (!Number.isFinite(price) || !Number.isInteger(count)) return;
    document.querySelector("[data-staff-item-resources]").hidden = false;
    document.querySelector("[data-staff-item-price]").textContent = `${new Intl.NumberFormat("de-DE").format(price)} KS`;
    document.querySelector("[data-staff-item-runes]").textContent = `${count} / 5`;
  });
  closeButton.addEventListener("click", close);
  backdrop.addEventListener("click", close);
  document.addEventListener("keydown", keydown);
}
