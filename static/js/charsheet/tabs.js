export function initTabs(root = document) {
  const tabRoots = Array.from(root.querySelectorAll("[data-tabs]"));
  tabRoots.forEach((tabRoot) => {
    const tabs = Array.from(tabRoot.querySelectorAll("[role='tab'][data-tab-target]"));
    const panels = Array.from(tabRoot.querySelectorAll("[data-tab-panel]"));
    const tabList = tabRoot.querySelector("[role='tablist']");
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
      const conditionalBlocks = Array.from(tabRoot.querySelectorAll("[data-hide-on-tab]"));
      conditionalBlocks.forEach((block) => {
        const hiddenOnTab = block.getAttribute("data-hide-on-tab") || "";
        block.hidden = hiddenOnTab === targetId;
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

        const orientation = (tabList?.getAttribute("aria-orientation") || "horizontal").toLowerCase();
        const nextKey = orientation === "vertical" ? "ArrowDown" : "ArrowRight";
        const previousKey = orientation === "vertical" ? "ArrowUp" : "ArrowLeft";
        let nextIndex = currentIndex;
        if (event.key === nextKey) {
          nextIndex = (currentIndex + 1) % tabs.length;
        } else if (event.key === previousKey) {
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
