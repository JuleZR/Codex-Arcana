import { initWatercolorImages } from "./watercolor_image.js?v=20260908d";

const PAGE_FLIP_MODULE_URL = "../vendor/page-flip.module.js";
let activeBook = null;

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;
}

function readStageSize(stage) {
  const rect = stage.getBoundingClientRect();
  const singlePage = window.innerWidth < 760;
  const width = Math.max(260, Math.floor(singlePage ? rect.width : rect.width / 2));
  const height = Math.max(320, Math.floor(rect.height));
  return { width, height, singlePage };
}

export function initBookViewer(root, options = {}) {
  if (!(root instanceof HTMLElement) || root.dataset.bookViewerBound === "1") {
    return null;
  }
  const overlay = root.matches("[data-book-overlay]") ? root : root.querySelector("[data-book-overlay]");
  const stage = root.querySelector(".book_viewer_stage");
  const pages = root.querySelector("[data-book-pages]");
  const closeControls = root.querySelectorAll("[data-book-close]");
  if (!(overlay instanceof HTMLElement) || !(stage instanceof HTMLElement) || !(pages instanceof HTMLElement)) {
    return null;
  }

  root.dataset.bookViewerBound = "1";
  initWatercolorImages(pages);
  let pageFlip = null;
  let isOpen = false;
  let isBusy = false;
  let initialized = false;
  let lastTrigger = null;

  const setFallbackMode = () => {
    pages.classList.remove("is-pageflip");
    pages.querySelectorAll(".book_page").forEach((page) => {
      page.style.width = "";
      page.style.height = "";
    });
  };

  const initPageFlip = async () => {
    if (initialized) {
      return;
    }
    initialized = true;
    try {
      const module = await import(PAGE_FLIP_MODULE_URL);
      const { PageFlip } = module;
      const size = readStageSize(stage);
      pages.classList.add("is-pageflip");
      pageFlip = new PageFlip(pages, {
        width: size.width,
        height: size.height,
        size: "stretch",
        minWidth: 260,
        maxWidth: size.width,
        minHeight: 320,
        maxHeight: size.height,
        showCover: true,
        mobileScrollSupport: false,
        useMouseEvents: true,
        clickEventForward: true,
        flippingTime: prefersReducedMotion() ? 120 : 640,
      });
      const ready = new Promise((resolve) => pageFlip.on("init", resolve));
      const pageNodes = Array.from(pages.querySelectorAll(".book_page"));
      if (typeof pageFlip.loadFromHTML === "function") {
        pageFlip.loadFromHTML(pageNodes);
      } else {
        pageFlip.loadFromHtml(pageNodes);
      }
      await ready;
      // PageFlip positions the cover in its render loop, after its init event.
      await new Promise((resolve) => window.requestAnimationFrame(resolve));
    } catch (_error) {
      pageFlip = null;
      setFallbackMode();
    }
  };

  const open = async (trigger = null) => {
    if (isOpen || isBusy) {
      return;
    }
    if (trigger instanceof HTMLElement) {
      lastTrigger = trigger;
    }
    isBusy = true;
    // Keep the overlay hidden until the cover has its final initial position.
    await options.beforeOpen?.();
    await initPageFlip();
    if (options.startClosed && pageFlip) pageFlip.turnToPage(0);
    isOpen = true;
    overlay.classList.remove("is-closing");
    overlay.classList.add("is-open");
    overlay.setAttribute("aria-hidden", "false");
    pages.scrollTo({ left: 0, top: 0, behavior: "auto" });
    document.body.classList.add("book-viewer-active");
    activeBook = root;
    root.querySelector("button[data-book-close]")?.focus({ preventScroll: true });
    window.setTimeout(() => {
      isBusy = false;
    }, prefersReducedMotion() ? 1 : 520);
  };

  const close = async () => {
    if (!isOpen || isBusy) {
      return;
    }
    if (options.beforeClose && await options.beforeClose() === false) {
      return;
    }
    isBusy = true;
    isOpen = false;
    overlay.classList.add("is-closing");
    overlay.classList.remove("is-open");
    overlay.setAttribute("aria-hidden", "true");
    if (activeBook === root) activeBook = document.querySelector(".book_viewer_overlay.is-open");
    if (!document.querySelector(".book_viewer_overlay.is-open")) {
      document.body.classList.remove("book-viewer-active");
    }
    window.setTimeout(() => {
      overlay.classList.remove("is-closing");
      isBusy = false;
      lastTrigger?.focus({ preventScroll: true });
    }, prefersReducedMotion() ? 1 : 260);
  };

  const handleTriggerClick = (event) => {
    const trigger = event.target instanceof Element
      ? event.target.closest("[data-book-trigger]")
      : null;
    if (!(trigger instanceof HTMLElement) || trigger.getAttribute("aria-controls") !== overlay.id) {
      return;
    }
    event.preventDefault();
    open(trigger);
  };

  const handlePageTargetClick = (event) => {
    if (!isOpen) {
      return;
    }
    const targetButton = event.target instanceof Element
      ? event.target.closest("[data-book-page-target]")
      : null;
    if (!(targetButton instanceof HTMLElement) || !root.contains(targetButton)) {
      return;
    }
    const pageIndex = Number.parseInt(targetButton.getAttribute("data-book-page-target") || "", 10);
    if (!Number.isFinite(pageIndex) || pageIndex < 0) {
      return;
    }
    event.preventDefault();
    if (pageFlip) {
      pageFlip.flip(pageIndex, "bottom");
      return;
    }
    const targetPage = pages.querySelector(`[data-book-page-index="${pageIndex}"]`);
    if (targetPage instanceof HTMLElement) {
      pages.scrollTo({
        left: targetPage.offsetLeft,
        top: 0,
        behavior: prefersReducedMotion() ? "auto" : "smooth",
      });
    }
  };

  const handleKeydown = (event) => {
    if (!isOpen || activeBook !== root) {
      return;
    }
    if (event.key === "Tab") {
      const controls = Array.from(root.querySelectorAll("button, input, textarea, select, [tabindex]"))
        .filter((control) => !control.disabled && control.tabIndex >= 0 && control.getClientRects().length);
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.target instanceof Element && event.target.closest("input, textarea, select, [contenteditable]")) {
      return;
    }
    if (event.target instanceof Element && event.target.closest("[data-book-editor]")) return;
    if (event.key === "ArrowRight") {
      event.preventDefault();
      if (pageFlip) {
        pageFlip.flipNext("bottom");
      } else {
        pages.scrollBy({ left: pages.clientWidth, behavior: prefersReducedMotion() ? "auto" : "smooth" });
      }
      return;
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      if (pageFlip) {
        pageFlip.flipPrev("bottom");
      } else {
        pages.scrollBy({ left: -pages.clientWidth, behavior: prefersReducedMotion() ? "auto" : "smooth" });
      }
    }
  };

  document.addEventListener("click", handleTriggerClick);
  root.addEventListener("click", handlePageTargetClick);
  closeControls.forEach((control) => control.addEventListener("click", close));
  document.addEventListener("keydown", handleKeydown);
  window.addEventListener("resize", () => {
    if (!pageFlip || !isOpen) {
      return;
    }
    const size = readStageSize(stage);
    pageFlip.update();
    pages.style.setProperty("--book-page-width", `${size.width}px`);
  });

  const updatePages = (nodes) => {
    if (pageFlip) {
      const current = pageFlip.getCurrentPageIndex();
      if (current >= nodes.length) pageFlip.turnToPage(nodes.length - 1);
      pageFlip.updateFromHtml(nodes);
    } else {
      pages.replaceChildren(...nodes);
    }
  };

  return { open, close, updatePages };
}
