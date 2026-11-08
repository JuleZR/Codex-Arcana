const workshop = document.querySelector("[data-staff-workshop]");

if (workshop) {
  const frame = workshop.querySelector("[data-catalog-editor]");
  const placeholder = workshop.querySelector("[data-catalog-placeholder]");
  const filters = workshop.querySelector("[data-catalog-filter]");
  const error = workshop.querySelector("[data-catalog-error]");
  let pending;
  let timer;
  let selectedPath;
  let listUrl = new URL(window.location.href);

  const markSelected = () => {
    workshop.querySelectorAll("[data-catalog-open]").forEach((link) => {
      if (new URL(link.href).pathname === selectedPath) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
    });
  };
  const refreshList = async (url) => {
    if (!filters) return;
    pending?.abort();
    const request = new AbortController();
    pending = request;
    const results = workshop.querySelector("[data-catalog-results]");
    const scrollTop = results.querySelector(".staff-catalog__scroll").scrollTop;
    results.setAttribute("aria-busy", "true");
    error.hidden = true;
    try {
      const response = await fetch(url, { signal: request.signal, cache: "no-store" });
      if (!response.ok) throw new Error("Catalog request failed");
      const doc = new DOMParser().parseFromString(await response.text(), "text/html");
      const updated = doc.querySelector("[data-catalog-results]");
      if (!updated) throw new Error("Catalog results missing");
      if (request.signal.aborted) return;
      results.replaceWith(updated);
      updated.querySelector(".staff-catalog__scroll").scrollTop = scrollTop;
      markSelected();
    } catch (err) {
      if (err.name !== "AbortError") error.hidden = false;
    } finally {
      if (pending === request) results.removeAttribute("aria-busy");
    }
  };
  const applyFilters = () => {
    clearTimeout(timer);
    timer = undefined;
    listUrl = new URL(window.location.href);
    listUrl.search = new URLSearchParams(new FormData(filters)).toString();
    refreshList(listUrl);
  };
  filters?.addEventListener("submit", (event) => {
    event.preventDefault();
    applyFilters();
  });
  filters?.addEventListener("input", (event) => {
    pending?.abort();
    clearTimeout(timer);
    if (event.target.matches("select")) applyFilters();
    else timer = setTimeout(applyFilters, 180);
  });
  workshop.addEventListener("click", (event) => {
    const link = event.target.closest("a");
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (link.matches("[data-catalog-open]")) {
      placeholder.hidden = true;
      frame.hidden = false;
      selectedPath = new URL(link.href).pathname;
      markSelected();
    } else if (link.closest(".staff-catalog__pagination")) {
      event.preventDefault();
      clearTimeout(timer);
      timer = undefined;
      listUrl = new URL(link.href);
      refreshList(listUrl);
    }
  });
  frame.addEventListener("load", () => {
    if (!frame.contentDocument?.querySelector("[data-catalog-item-form]")) return;
    selectedPath = frame.contentWindow.location.pathname;
    markSelected();
    // Saving reloads only the editor; retain the list's query, page and scroll.
    if (!timer) refreshList(listUrl);
    frame.contentDocument.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
      }
    });
  });
  window.addEventListener("message", (event) => {
    if (event.origin !== window.location.origin || event.source !== frame.contentWindow
        || event.data?.type !== "staff-item-workshop-status") return;
    window.parent.postMessage(event.data, window.location.origin);
  });
}
