document.addEventListener("DOMContentLoaded", () => {
  const setupToastQueue = ({
    selector,
    visibleClass,
    hidingClass,
    visibleDuration = 2400,
    transitionDuration = 360,
  }) => {
    const noisyTableMessages = new Set([
      "Tabelle angelegt.",
      "Tabelle gespeichert.",
      "Tabelle gelöscht.",
    ]);
    const seen = new Set();
    const queue = [];

    document.querySelectorAll(selector).forEach((toast) => {
      const text = toast.textContent.replace(/\s+/g, " ").trim();
      const deduplicationKey = text.toLocaleLowerCase("de");
      if (
        !text
        || noisyTableMessages.has(text)
        || seen.has(deduplicationKey)
      ) {
        toast.remove();
        return;
      }
      seen.add(deduplicationKey);
      toast.hidden = true;
      toast.classList.remove(visibleClass, hidingClass);
      queue.push(toast);
    });

    const showNext = () => {
      const toast = queue.shift();
      if (!toast) {
        return;
      }
      toast.hidden = false;
      window.requestAnimationFrame(() => {
        toast.classList.add(visibleClass);
        window.setTimeout(() => {
          toast.classList.add(hidingClass);
          window.setTimeout(() => {
            toast.remove();
            showNext();
          }, transitionDuration);
        }, visibleDuration);
      });
    };

    showNext();
  };

  setupToastQueue({
    selector: "[data-autohide-message]",
    visibleClass: "is-visible",
    hidingClass: "is-hidden",
  });
  setupToastQueue({
    selector: "[data-game-group-message]",
    visibleClass: "is-visible",
    hidingClass: "is-hiding",
  });

  const groupPage = document.querySelector("[data-game-group]");
  if (groupPage) {
    if (window.parent !== window) {
      document.body.classList.add("game-group-embedded");
      const cleanUrl = new URL(window.location.href);
      if (cleanUrl.searchParams.get("dashboard_refresh") === "quiet") {
        cleanUrl.searchParams.delete("dashboard_refresh");
        window.history.replaceState({}, "", cleanUrl);
        window.parent.postMessage(
          { type: groupPage.dataset.dashboardRefreshMessage }, window.location.origin,
        );
      }
    }

    const tabs = Array.from(groupPage.querySelectorAll("[data-group-tab]"));
    const panels = groupPage.querySelectorAll("[data-group-panel]");
    const tablist = groupPage.querySelector('[role="tablist"]');
    const mobileNav = window.matchMedia("(max-width: 540px)");
    const updateOrientation = () => {
      tablist.setAttribute("aria-orientation", mobileNav.matches ? "horizontal" : "vertical");
    };
    updateOrientation();
    mobileNav.addEventListener("change", updateOrientation);
    const activateTab = (name, focus = false) => {
      tabs.forEach((tab) => {
        const active = tab.dataset.groupTab === name;
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
        if (active && focus) tab.focus();
      });
      panels.forEach((panel) => { panel.hidden = panel.dataset.groupPanel !== name; });
      groupPage.querySelector(".game-group-stage").scrollTop = 0;
    };
    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => activateTab(tab.dataset.groupTab));
      tab.addEventListener("keydown", (event) => {
        const previous = mobileNav.matches ? "ArrowLeft" : "ArrowUp";
        const next = mobileNav.matches ? "ArrowRight" : "ArrowDown";
        let target;
        if (event.key === previous) target = (index + tabs.length - 1) % tabs.length;
        if (event.key === next) target = (index + 1) % tabs.length;
        if (event.key === "Home") target = 0;
        if (event.key === "End") target = tabs.length - 1;
        if (target === undefined) return;
        event.preventDefault();
        activateTab(tabs[target].dataset.groupTab, true);
      });
    });

    const members = Array.from(groupPage.querySelectorAll("[data-group-member]"));
    const details = groupPage.querySelectorAll("[data-group-detail]");
    const roster = groupPage.querySelector(".game-group-roster");
    let selectedMember = null;
    const selectMember = (member) => {
      selectedMember = member;
      members.forEach((row) => row.setAttribute("aria-pressed", String(row === member)));
      details.forEach((detail) => {
        detail.hidden = detail.dataset.groupDetail !== member?.dataset.groupMember;
        if (!detail.hidden) detail.focus();
      });
      roster.classList.toggle("has-selection", Boolean(member));
    };
    members.forEach((member) => member.addEventListener("click", () => selectMember(member)));
    const closeDetail = () => {
      const previous = selectedMember;
      selectMember(null);
      previous?.focus();
    };
    groupPage.querySelectorAll("[data-group-close-detail]").forEach((button) => {
      button.addEventListener("click", closeDetail);
    });
    groupPage.querySelector("#gameGroupMemberSearch").addEventListener("input", (event) => {
      const query = event.target.value.trim().toLocaleLowerCase("de");
      members.forEach((member) => {
        member.hidden = !member.textContent.toLocaleLowerCase("de").includes(query);
      });
      if (selectedMember?.hidden) selectMember(null);
      groupPage.querySelector("#gameGroupNoMatches").hidden = !members.length
        || members.some((member) => !member.hidden);
    });

    const inviteToggle = groupPage.querySelector("#gameGroupInviteToggle");
    const invitePanel = groupPage.querySelector("#gameGroupInvitePanel");
    const toggleInvite = (open) => {
      if (!invitePanel || !inviteToggle) return;
      invitePanel.hidden = !open;
      inviteToggle.setAttribute("aria-expanded", String(open));
      if (open) invitePanel.querySelector("[data-group-character-query]").focus();
      else inviteToggle.focus();
    };
    inviteToggle?.addEventListener("click", () => toggleInvite(invitePanel.hidden));
    groupPage.querySelector("[data-group-open-invite]")?.addEventListener("click", () => {
      activateTab("invites");
      toggleInvite(true);
    });
    groupPage.querySelector("[data-group-close-invite]")?.addEventListener("click", () => toggleInvite(false));

    const dialog = groupPage.querySelector("#gameGroupConfirm");
    let pendingForm = null;
    let submitter = null;
    let restoreFocus = null;
    let confirmedForm = null;
    groupPage.addEventListener("submit", (event) => {
      const form = event.target.closest("[data-group-confirm]");
      if (!form) return;
      if (confirmedForm === form) {
        confirmedForm = null;
        return;
      }
      event.preventDefault();
      pendingForm = form;
      submitter = event.submitter;
      restoreFocus = document.activeElement;
      dialog.querySelector("#group-confirm-title").textContent = form.dataset.confirmTitle;
      dialog.querySelector("#group-confirm-message").textContent = form.dataset.groupConfirm;
      dialog.querySelector("[data-group-confirm-accept]").textContent = submitter?.textContent.trim() || "Bestätigen";
      dialog.showModal();
      dialog.querySelector("[data-group-confirm-cancel]").focus();
    });
    dialog.querySelector("[data-group-confirm-cancel]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => {
      pendingForm = null;
      restoreFocus?.focus();
    });
    dialog.querySelector("[data-group-confirm-accept]").addEventListener("click", () => {
      const form = pendingForm;
      const button = submitter;
      if (!form) return;
      pendingForm = null;
      confirmedForm = form;
      dialog.close();
      if (button) form.requestSubmit(button);
      else form.requestSubmit();
    });
    groupPage.addEventListener("keydown", (event) => {
      if (event.key !== "Escape" || dialog.open || event.defaultPrevented) return;
      if (event.target.closest("#gameGroupInvitePanel")) {
        toggleInvite(false);
      } else if (event.target.closest("[data-group-detail]")) {
        closeDetail();
      } else {
        const disclosure = event.target.closest("details[open]");
        if (!disclosure) return;
        disclosure.open = false;
        disclosure.querySelector("summary").focus();
      }
      event.preventDefault();
      event.stopPropagation();
    });
  }

  document.querySelectorAll("[data-group-character-picker]").forEach((picker) => {
    const search = picker.querySelector("[data-group-character-query]");
    const hidden = picker.querySelector("[data-group-character-id]");
    const results = picker.querySelector("[data-group-character-results]");
    if (!search || !hidden || !results) return;
    let timer = null;
    let requestVersion = 0;
    let controller = null;
    const status = picker.querySelector("[data-group-character-status]");
    const announce = (message) => { if (status) status.textContent = message; };

    const clearResults = () => {
      results.replaceChildren();
      search.setAttribute("aria-expanded", "false");
    };
    search.addEventListener("input", () => {
      hidden.value = "";
      search.setCustomValidity("");
      clearTimeout(timer);
      controller?.abort();
      const version = ++requestVersion;
      clearResults();
      announce("");
      const query = search.value.trim();
      if (query.length < 2) {
        clearResults();
        return;
      }
      timer = setTimeout(async () => {
        const url = new URL(picker.dataset.searchUrl, window.location.origin);
        url.searchParams.set("q", query);
        url.searchParams.set("mode", picker.dataset.searchMode || "invite");
        controller = new AbortController();
        announce("Charaktere werden gesucht …");
        try {
          const response = await fetch(url, {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
            signal: controller.signal,
          });
          if (!response.ok) throw new Error("search_failed");
          const payload = await response.json();
          if (version !== requestVersion) return;
          clearResults();
          payload.results.forEach((row) => {
            const button = document.createElement("button");
            button.type = "button";
            button.dataset.characterId = row.id;
            button.dataset.characterLabel = row.name;
            button.textContent = `${row.name} · ${row.race} · ${row.username}`;
            results.append(button);
          });
          search.setAttribute("aria-expanded", String(Boolean(payload.results.length)));
          announce(payload.results.length
            ? `${payload.results.length} Treffer. Bitte einen Charakter auswählen.`
            : "Keine passenden Charaktere gefunden.");
        } catch (error) {
          if (error.name === "AbortError" || version !== requestVersion) return;
          clearResults();
          announce("Die Suche ist fehlgeschlagen. Bitte erneut versuchen.");
        }
      }, 180);
    });

    results.addEventListener("click", (event) => {
      const option = event.target.closest("[data-character-id]");
      if (!option) return;
      hidden.value = option.dataset.characterId || "";
      search.value = option.dataset.characterLabel || option.textContent.trim();
      search.setCustomValidity("");
      clearResults();
      announce(`Ausgewählt: ${option.textContent.trim()}`);
      search.focus();
    });

    search.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown" && results.firstElementChild) {
        event.preventDefault();
        results.firstElementChild.focus();
      }
      if (event.key === "Escape" && results.childElementCount) {
        event.preventDefault();
        event.stopPropagation();
        clearResults();
      }
    });
    results.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        clearResults();
        search.focus();
      } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const options = Array.from(results.children);
        const index = options.indexOf(document.activeElement);
        const step = event.key === "ArrowDown" ? 1 : -1;
        options[(index + step + options.length) % options.length]?.focus();
      }
    });

    picker.closest("form")?.addEventListener("submit", (event) => {
      if (hidden.value) return;
      event.preventDefault();
      search.setCustomValidity("Bitte einen Treffer aus der Liste auswählen.");
      search.reportValidity();
    });
  });
});
