import { initBookViewer } from "./book_viewer.js?v=20260917e";

export function initAlchemistAlmanac() {
  document.querySelectorAll("[data-alchemist-almanac-root]").forEach((root) => {
    initBookViewer(root);
  });
}
