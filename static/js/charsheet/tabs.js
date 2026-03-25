export function initTabs(root = document) {
  const tabRoots = Array.from(root.querySelectorAll("[data-tabs]"));
  tabRoots.forEach((tabRoot) => {
    const tabs = Array.from(tabRoot.querySelectorAll("[role='tab'][data-tab-target]"));
    const panels = Array.from(tabRoot.querySelectorAll("[data-tab-panel]"));
    if (!tabs.length || !panels.length) {
      return;
    }

    const activateTab = (tabToActivate) => {
      const targetId = tabToActivate.getAttribute("data-tab-target") || "";
      tabs.forEach((tab) => {
        const isActive = tab === tabToActivate;
        tab.setAttribute("aria-selected", String(isActive));
        tab.tabIndex = isActive ? 0 : -1;
      });
      panels.forEach((panel) => {
        panel.hidden = panel.id !== targetId;
      });
    };

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        activateTab(tab);
      });
      tab.addEventListener("keydown", (event) => {
        const currentIndex = tabs.indexOf(tab);
        if (currentIndex < 0) {
          return;
        }

        let nextIndex = currentIndex;
        if (event.key === "ArrowRight") {
          nextIndex = (currentIndex + 1) % tabs.length;
        } else if (event.key === "ArrowLeft") {
          nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
        } else if (event.key === "Home") {
          nextIndex = 0;
        } else if (event.key === "End") {
          nextIndex = tabs.length - 1;
        } else {
          return;
        }

        event.preventDefault();
        const nextTab = tabs[nextIndex];
        activateTab(nextTab);
        nextTab.focus();
      });
    });

    const activeTab = tabs.find((tab) => tab.getAttribute("aria-selected") === "true") || tabs[0];
    activateTab(activeTab);
  });
}
