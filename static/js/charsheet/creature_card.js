import { initGodCards } from "./god_card.js?v=20260702a";
import { openCardImageCropper } from "./card_image_cropper.js";

export function initCreatureCards() {
  const getCsrfToken = () => {
    const tokenInput = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (tokenInput instanceof HTMLInputElement && tokenInput.value) {
      return tokenInput.value;
    }
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  };

  const fitCreatureRuleText = (card) => {
    if (!(card instanceof HTMLElement)) {
      return;
    }
    const rules = card.querySelector(".creature-card__rules");
    if (!(rules instanceof HTMLElement)) {
      return;
    }
    const scales = [1, 0.96, 0.92, 0.88];
    const fits = () => (
      rules.scrollHeight <= rules.clientHeight + 1
      && rules.scrollWidth <= rules.clientWidth + 1
    );
    card.style.setProperty("--creature-rules-font-scale", "1");
    window.requestAnimationFrame(() => {
      for (const scale of scales) {
        card.style.setProperty("--creature-rules-font-scale", String(scale));
        if (fits()) {
          return;
        }
      }
    });
  };

  const setCreatureCardUnlocked = (card, isUnlocked) => {
    if (!(card instanceof HTMLElement)) {
      return;
    }
    card.classList.toggle("is-edit-unlocked", isUnlocked);
    const toggle = card.querySelector("[data-creature-card-edit-toggle]");
    if (toggle instanceof HTMLButtonElement) {
      toggle.setAttribute("aria-pressed", isUnlocked ? "true" : "false");
      toggle.title = isUnlocked ? "Karte sperren" : "Karte freigeben";
    }
    const floatingCard = card.closest(".card-hand__floating-card");
    const drawer = floatingCard?.querySelector("[data-creature-training-drawer]");
    if (!isUnlocked && drawer instanceof HTMLElement) {
      drawer.classList.remove("is-open");
      const panel = drawer.querySelector("[data-creature-training-form]");
      const drawerToggle = drawer.querySelector("[data-creature-training-toggle]");
      if (panel instanceof HTMLElement) {
        panel.hidden = true;
      }
      if (drawerToggle instanceof HTMLButtonElement) {
        drawerToggle.setAttribute("aria-expanded", "false");
      }
    }
  };

  const bindCreatureCardEditor = (card) => {
    if (!(card instanceof HTMLElement) || card.dataset.creatureCardEditorBound === "1") {
      return;
    }
    if (!card.hasAttribute("data-creature-card-editor")) {
      return;
    }
    card.dataset.creatureCardEditorBound = "1";
    const toggle = card.querySelector("[data-creature-card-edit-toggle]");
    if (!(toggle instanceof HTMLButtonElement)) {
      return;
    }
    const imageTrigger = card.querySelector("[data-creature-card-image-trigger]");
    const removeImageButton = card.querySelector("[data-creature-card-remove-image]");
    const imageInput = imageTrigger instanceof HTMLElement
      ? imageTrigger.querySelector('input[type="file"]')
      : null;
    const qualitySelect = card.querySelector(".creature-card-quality-select");

    const previewQualityPoints = () => {
      if (!(qualitySelect instanceof HTMLSelectElement)) {
        return;
      }
      const option = qualitySelect.selectedOptions?.[0];
      const floatingCard = card.closest(".card-hand__floating-card");
      const drawer = floatingCard?.querySelector("[data-creature-training-drawer]");
      if (!(option instanceof HTMLOptionElement) || !(drawer instanceof HTMLElement)) {
        return;
      }
      const qualityPoints = Number.parseInt(option.dataset.advantagePoints || "0", 10) || 0;
      const weaknessEl = drawer.querySelector("[data-creature-training-weakness-points]");
      const consumedEl = drawer.querySelector("[data-creature-training-consumed-points]");
      const qualityEl = drawer.querySelector("[data-creature-training-quality-points]");
      const openEl = drawer.querySelector("[data-creature-training-open-points]");
      const weaknessPoints = Number.parseInt(weaknessEl?.textContent || "0", 10) || 0;
      const consumedPoints = Number.parseInt(consumedEl?.textContent || "0", 10) || 0;
      if (qualityEl instanceof HTMLElement) {
        qualityEl.textContent = String(qualityPoints);
      }
      if (openEl instanceof HTMLElement) {
        openEl.textContent = String(qualityPoints + weaknessPoints - consumedPoints);
      }
    };

    if (qualitySelect instanceof HTMLSelectElement) {
      qualitySelect.addEventListener("change", (event) => {
        event.stopPropagation();
        previewQualityPoints();
        const floatingCard = card.closest(".card-hand__floating-card");
        const form = floatingCard?.querySelector("[data-creature-training-form]");
        if (form instanceof HTMLFormElement) {
          form.requestSubmit();
        }
      });
    }

    if (imageTrigger instanceof HTMLElement && imageInput instanceof HTMLInputElement) {
      imageTrigger.addEventListener("click", (event) => {
        if (!card.classList.contains("is-edit-unlocked")) {
          event.preventDefault();
          return;
        }
        if (event.target === imageInput) {
          return;
        }
        event.preventDefault();
        imageInput.click();
      });
      imageInput.addEventListener("change", async () => {
        if (!card.classList.contains("is-edit-unlocked")) {
          return;
        }
        const file = imageInput.files?.[0] || null;
        if (!file) {
          return;
        }
        try {
          const croppedData = await openCardImageCropper(file);
          if (!croppedData) {
            imageInput.value = "";
            return;
          }
          const croppedInput = card.querySelector('input[name="custom_creature_image_cropped_data"]');
          if (croppedInput instanceof HTMLInputElement) {
            croppedInput.value = croppedData;
          }
          imageInput.value = "";
          const art = card.querySelector(".card-art");
          if (!(art instanceof HTMLElement)) {
            return;
          }
          let image = art.querySelector("img");
          if (!(image instanceof HTMLImageElement)) {
            image = document.createElement("img");
            image.alt = card.querySelector(".card-title")?.textContent?.trim() || "";
            art.appendChild(image);
          }
          image.src = croppedData;
          art.classList.remove("card-art--empty");
        } catch (_error) {
          imageInput.value = "";
        }
      });
    }

    if (removeImageButton instanceof HTMLButtonElement) {
      removeImageButton.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (!card.classList.contains("is-edit-unlocked")) {
          return;
        }
        const floatingCard = card.closest(".card-hand__floating-card");
        const form = floatingCard?.querySelector("[data-creature-training-form]");
        if (!(form instanceof HTMLFormElement)) {
          return;
        }
        const croppedInput = card.querySelector('input[name="custom_creature_image_cropped_data"]');
        if (croppedInput instanceof HTMLInputElement) {
          croppedInput.value = "";
        }
        let input = form.querySelector('input[name="remove_custom_creature_image"]');
        if (!(input instanceof HTMLInputElement)) {
          input = document.createElement("input");
          input.type = "hidden";
          input.name = "remove_custom_creature_image";
          form.appendChild(input);
        }
        input.value = "1";
        const art = card.querySelector(".card-art");
        const image = art?.querySelector("img");
        const defaultImageUrl = card.getAttribute("data-creature-card-default-image") || "";
        if (image instanceof HTMLImageElement && defaultImageUrl) {
          image.src = defaultImageUrl;
          art?.classList.remove("card-art--empty");
        } else {
          image?.remove();
          art?.classList.add("card-art--empty");
        }
      });
    }

    toggle.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const wasUnlocked = card.classList.contains("is-edit-unlocked");
      setCreatureCardUnlocked(card, !wasUnlocked);
      if (wasUnlocked) {
        const floatingCard = card.closest(".card-hand__floating-card");
        const form = floatingCard?.querySelector("[data-creature-training-form]");
        if (form instanceof HTMLFormElement) {
          form.requestSubmit();
        }
      }
    });
  };

  const bindTrainingDrawer = (drawer) => {
    if (!(drawer instanceof HTMLElement) || drawer.dataset.creatureTrainingBound === "1") {
      return;
    }
    drawer.dataset.creatureTrainingBound = "1";
    const toggle = drawer.querySelector("[data-creature-training-toggle]");
    const panel = drawer.querySelector("[data-creature-training-form]");
    const normalizeFilterText = (value) => String(value || "")
      .toLocaleLowerCase("de-DE")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
    const applyTrainingFilter = (input) => {
      if (!(input instanceof HTMLInputElement) || !(panel instanceof HTMLElement)) {
        return;
      }
      const targetKey = input.getAttribute("data-filter-target") || "";
      const list = panel.querySelector(`[data-creature-training-filter-list="${CSS.escape(targetKey)}"]`);
      if (!(list instanceof HTMLElement)) {
        return;
      }
      const query = normalizeFilterText(input.value.trim());
      list.querySelectorAll("[data-filter-text]").forEach((item) => {
        if (!(item instanceof HTMLElement)) {
          return;
        }
        const haystack = normalizeFilterText(item.getAttribute("data-filter-text") || item.textContent);
        item.hidden = query.length > 0 && !haystack.includes(query);
      });
    };
    const formatAttributeModifier = (value) => {
      const parsed = Number.parseInt(String(value ?? "").trim(), 10);
      if (Number.isNaN(parsed)) {
        return "-";
      }
      const modifier = parsed - 5;
      return modifier >= 0 ? `+${modifier}` : String(modifier);
    };
    const refreshAttributeModifier = (input) => {
      if (!(input instanceof HTMLInputElement)) {
        return;
      }
      const row = input.closest(".creature-training-attributes__row");
      const modifierCell = row?.querySelector("[data-creature-attribute-mod]");
      if (modifierCell instanceof HTMLElement) {
        modifierCell.textContent = formatAttributeModifier(input.value);
      }
    };
    const readInteger = (value, fallback = 0) => {
      const parsed = Number.parseInt(String(value ?? "").trim(), 10);
      return Number.isNaN(parsed) ? fallback : parsed;
    };
    const formatSignedModifier = (value) => {
      const parsed = readInteger(value, 0);
      return parsed > 0 ? `+${parsed}` : String(parsed);
    };
    const skillFormulaText = ({ baseValue, deviation, attributeCode, attributeModifier, gkModifier, skillModifier }) => {
      const parts = [String(baseValue)];
      if (deviation) {
        parts.push(`${formatSignedModifier(deviation)} Abw.`);
      }
      if (attributeModifier) {
        parts.push(`${formatSignedModifier(attributeModifier)} ${attributeCode}`);
      }
      if (gkModifier) {
        parts.push(`${formatSignedModifier(gkModifier)} GK`);
      }
      if (skillModifier) {
        parts.push(`${formatSignedModifier(skillModifier)} Mod.`);
      }
      return parts.join(" ");
    };
    const skillFormulaTitle = ({ total, baseValue, deviation, attributeCode, attributeModifier, gkModifier, skillModifier }) => {
      const parts = [`Basis ${baseValue}`];
      if (deviation) {
        parts.push(`Abweichung ${formatSignedModifier(deviation)}`);
      }
      if (attributeModifier) {
        parts.push(`${attributeCode} ${formatSignedModifier(attributeModifier)}`);
      }
      if (gkModifier) {
        parts.push(`GK ${formatSignedModifier(gkModifier)}`);
      }
      if (skillModifier) {
        parts.push(`Modifikatoren ${formatSignedModifier(skillModifier)}`);
      }
      return `${parts.join(" + ")} ergibt ${total}`;
    };
    const currentSizeModifier = () => {
      const select = panel.querySelector("[data-creature-size-class]");
      if (!(select instanceof HTMLSelectElement)) {
        return 0;
      }
      return readInteger(select.selectedOptions?.[0]?.dataset.sizeModifier, 0);
    };
    const currentAttributeModifier = (attributeCode, fallback) => {
      const input = panel.querySelector(`[name="attribute_${CSS.escape(String(attributeCode || ""))}"]`);
      if (input instanceof HTMLInputElement) {
        return readInteger(input.value, 5) - 5;
      }
      return readInteger(fallback, 0);
    };
    const refreshSkillEffectiveValues = () => {
      if (!(panel instanceof HTMLElement)) {
        return;
      }
      const sizeModifier = currentSizeModifier();
      panel.querySelectorAll("[data-creature-training-skill-row]").forEach((row) => {
        if (!(row instanceof HTMLElement)) {
          return;
        }
        const output = row.querySelector("[data-creature-skill-effective]");
        const formula = row.querySelector("[data-creature-skill-formula]");
        const input = row.querySelector("[data-creature-skill-base-value]");
        if (!(output instanceof HTMLElement) || !(input instanceof HTMLInputElement)) {
          return;
        }
        const baseValue = readInteger(input.value, 0);
        const attributeModifier = currentAttributeModifier(row.dataset.creatureSkillAttribute, row.dataset.creatureSkillAttributeMod);
        const deviation = readInteger(row.dataset.creatureSkillDeviation, 0);
        const gkMultiplier = readInteger(row.dataset.creatureSkillGkMultiplier, 0);
        const skillModifier = readInteger(row.dataset.creatureSkillModifier, 0);
        const gkModifier = sizeModifier * gkMultiplier;
        const total = baseValue + deviation + attributeModifier + gkModifier + skillModifier;
        output.textContent = String(total);
        const formulaPayload = {
          total,
          baseValue,
          deviation,
          attributeCode: row.dataset.creatureSkillAttribute || "Eig.",
          attributeModifier,
          gkModifier,
          skillModifier,
        };
      if (formula instanceof HTMLElement) {
        formula.textContent = skillFormulaText(formulaPayload);
      }
        const effective = row.querySelector(".creature-training-skill__effective");
        if (effective instanceof HTMLElement) {
          effective.title = skillFormulaTitle(formulaPayload);
        }
      });
    };
    const refreshSizeModifier = () => {
      if (!(panel instanceof HTMLElement)) {
        return;
      }
      const select = panel.querySelector("[data-creature-size-class]");
      const target = panel.querySelector("[data-creature-size-modifier]");
      if (!(select instanceof HTMLSelectElement) || !(target instanceof HTMLElement)) {
        return;
      }
      const option = select.selectedOptions?.[0];
      target.textContent = formatSignedModifier(option?.dataset.sizeModifier || "0");
      refreshSkillEffectiveValues();
    };
    const refreshCommandPrerequisites = () => {
      if (!(panel instanceof HTMLElement)) {
        return;
      }
      let selectedCommandIds = new Set(
        Array.from(panel.querySelectorAll("[data-creature-command-input]:checked"))
          .filter((input) => input instanceof HTMLInputElement)
          .map((input) => String(input.value)),
      );
      const commandChoices = Array.from(panel.querySelectorAll("[data-creature-command-choice]"))
        .filter((choice) => choice instanceof HTMLElement);
      let changed = true;
      while (changed) {
        changed = false;
        commandChoices.forEach((choice) => {
          const input = choice.querySelector("[data-creature-command-input]");
          if (!(input instanceof HTMLInputElement) || !input.checked) {
            return;
          }
          let groups = [];
          try {
            groups = JSON.parse(choice.getAttribute("data-prerequisite-groups") || "[]");
          } catch (_error) {
            groups = [];
          }
          const hasUnmetPrerequisites = groups.some((group) => (
            Array.isArray(group)
            && group.length > 0
            && !group.some((commandId) => selectedCommandIds.has(String(commandId)))
          ));
          if (hasUnmetPrerequisites) {
            input.checked = false;
            selectedCommandIds.delete(String(input.value));
            changed = true;
          }
        });
      }
      commandChoices.forEach((choice) => {
        const input = choice.querySelector("[data-creature-command-input]");
        let groups = [];
        try {
          groups = JSON.parse(choice.getAttribute("data-prerequisite-groups") || "[]");
        } catch (_error) {
          groups = [];
        }
        const hasUnmetPrerequisites = groups.some((group) => (
          Array.isArray(group)
          && group.length > 0
          && !group.some((commandId) => selectedCommandIds.has(String(commandId)))
        ));
        if (input instanceof HTMLInputElement) {
          input.disabled = hasUnmetPrerequisites;
        }
        choice.classList.toggle("creature-training-choice--unmet", hasUnmetPrerequisites);
      });
    };
    const refreshFlySpeedInputs = () => {
      if (!(panel instanceof HTMLElement)) {
        return;
      }
      const checkbox = panel.querySelector("[data-creature-can-fly]");
      const movement = panel.querySelector("[data-creature-training-movement]");
      const canFly = checkbox instanceof HTMLInputElement && checkbox.checked;
      if (movement instanceof HTMLElement) {
        movement.classList.toggle("is-flight-disabled", !canFly);
      }
      panel.querySelectorAll("[data-creature-fly-speed]").forEach((input) => {
        if (input instanceof HTMLInputElement) {
          input.disabled = !canFly;
        }
      });
    };
    const refreshSwimSpeedInputs = () => {
      if (!(panel instanceof HTMLElement)) {
        return;
      }
      const checkbox = panel.querySelector("[data-creature-can-swim]");
      const movement = panel.querySelector("[data-creature-training-movement]");
      const canSwim = checkbox instanceof HTMLInputElement && checkbox.checked;
      if (movement instanceof HTMLElement) {
        movement.classList.toggle("is-swim-disabled", !canSwim);
      }
      panel.querySelectorAll("[data-creature-swim-speed]").forEach((input) => {
        if (input instanceof HTMLInputElement) {
          input.disabled = !canSwim;
        }
      });
    };
    const refreshManaInputs = () => {
      if (!(panel instanceof HTMLElement)) {
        return;
      }
      const checkbox = panel.querySelector("[data-creature-can-mana]");
      const movement = panel.querySelector("[data-creature-training-movement]");
      const canMana = checkbox instanceof HTMLInputElement && checkbox.checked;
      if (movement instanceof HTMLElement) {
        movement.classList.toggle("is-mana-disabled", !canMana);
      }
      panel.querySelectorAll("[data-creature-mana-field]").forEach((input) => {
        if (input instanceof HTMLInputElement) {
          input.disabled = !canMana;
        }
      });
    };
    const resetDrawerShift = () => {
      const floating = drawer.closest(".card-hand__floating");
      if (floating instanceof HTMLElement) {
        floating.style.removeProperty("--creature-training-shift");
      }
    };
    const fitDrawerInViewport = () => {
      const floating = drawer.closest(".card-hand__floating");
      if (!(floating instanceof HTMLElement) || !drawer.classList.contains("is-open")) {
        return;
      }
      floating.style.setProperty("--creature-training-shift", "0px");
      const drawerRect = drawer.getBoundingClientRect();
      const viewportPadding = 12;
      const overflowRight = drawerRect.right - (window.innerWidth - viewportPadding);
      const overflowLeft = viewportPadding - drawerRect.left;
      let shift = 0;
      if (overflowRight > 0) {
        shift -= overflowRight;
      }
      if (drawerRect.left + shift < viewportPadding) {
        shift += viewportPadding - (drawerRect.left + shift);
      }
      floating.style.setProperty("--creature-training-shift", `${Math.round(shift)}px`);
    };
    const registerRemovedSkill = (skillId) => {
      if (!(panel instanceof HTMLElement) || !skillId) {
        return;
      }
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "remove_skill_ids";
      input.value = String(skillId);
      panel.appendChild(input);
    };
    const addSkillRow = () => {
      if (!(panel instanceof HTMLElement)) {
        return;
      }
      const list = panel.querySelector(".creature-training-skill-list");
      const template = panel.querySelector("[data-creature-training-new-skill-row]");
      const addButton = panel.querySelector("[data-creature-training-add-skill]");
      if (!(list instanceof HTMLElement) || !(template instanceof HTMLElement)) {
        return;
      }
      const clone = template.cloneNode(true);
      if (!(clone instanceof HTMLElement)) {
        return;
      }
      clone.querySelectorAll("select, input").forEach((field) => {
        if (field instanceof HTMLSelectElement) {
          field.selectedIndex = 0;
        } else if (field instanceof HTMLInputElement) {
          field.value = "0";
        }
      });
      list.insertBefore(clone, addButton instanceof HTMLElement ? addButton : null);
    };
    drawer.addEventListener("pointerdown", (event) => {
      event.stopPropagation();
    }, true);
    drawer.querySelectorAll("[data-creature-training-section-toggle]").forEach((sectionToggle) => {
      if (!(sectionToggle instanceof HTMLButtonElement)) {
        return;
      }
      sectionToggle.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const section = sectionToggle.closest("[data-creature-training-section]");
        const body = section?.querySelector("[data-creature-training-section-body]");
        if (!(section instanceof HTMLElement) || !(body instanceof HTMLElement)) {
          return;
        }
        const isCollapsed = !section.classList.contains("is-collapsed");
        section.classList.toggle("is-collapsed", isCollapsed);
        body.hidden = isCollapsed;
        sectionToggle.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
      });
    });
    if (toggle instanceof HTMLButtonElement && panel instanceof HTMLElement) {
      toggle.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const floatingCard = drawer.closest(".card-hand__floating-card");
        const card = floatingCard?.querySelector(".creature-card");
        if (!(card instanceof HTMLElement) || !card.classList.contains("is-edit-unlocked")) {
          return;
        }
        const isOpen = !drawer.classList.contains("is-open");
        if (isOpen) {
          panel.hidden = false;
          window.requestAnimationFrame(() => {
            drawer.classList.add("is-open");
            fitDrawerInViewport();
          });
        } else {
          drawer.classList.remove("is-open");
          resetDrawerShift();
          window.setTimeout(() => {
            if (!drawer.classList.contains("is-open")) {
              panel.hidden = true;
            }
          }, 190);
        }
        toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
      });
      window.addEventListener("resize", fitDrawerInViewport);
    }
    if (panel instanceof HTMLFormElement) {
      panel.querySelectorAll("[data-creature-training-filter]").forEach((filterInput) => {
        if (!(filterInput instanceof HTMLInputElement)) {
          return;
        }
        filterInput.addEventListener("input", () => applyTrainingFilter(filterInput));
        applyTrainingFilter(filterInput);
      });
      panel.querySelectorAll("[data-creature-attribute-value]").forEach((attributeInput) => {
        if (!(attributeInput instanceof HTMLInputElement)) {
          return;
        }
        attributeInput.addEventListener("input", () => {
          refreshAttributeModifier(attributeInput);
          refreshSkillEffectiveValues();
        });
        refreshAttributeModifier(attributeInput);
      });
      panel.querySelectorAll("[data-creature-skill-base-value]").forEach((skillInput) => {
        if (!(skillInput instanceof HTMLInputElement)) {
          return;
        }
        skillInput.addEventListener("input", refreshSkillEffectiveValues);
      });
      refreshSkillEffectiveValues();
      panel.addEventListener("change", (event) => {
        const target = event.target instanceof Element ? event.target : null;
        if (target?.matches("[data-creature-command-input]")) {
          refreshCommandPrerequisites();
        }
        if (target?.matches("[data-creature-can-fly]")) {
          refreshFlySpeedInputs();
        }
        if (target?.matches("[data-creature-can-swim]")) {
          refreshSwimSpeedInputs();
        }
        if (target?.matches("[data-creature-can-mana]")) {
          refreshManaInputs();
        }
        if (target?.matches("[data-creature-size-class]")) {
          refreshSizeModifier();
        }
      });
      panel.addEventListener("click", (event) => {
        const target = event.target instanceof Element ? event.target : null;
        const addButton = target?.closest("[data-creature-training-add-skill]");
        if (addButton instanceof HTMLButtonElement) {
          event.preventDefault();
          event.stopPropagation();
          addSkillRow();
          return;
        }
        const removeExisting = target?.closest("[data-creature-training-remove-skill]");
        if (removeExisting instanceof HTMLButtonElement) {
          event.preventDefault();
          event.stopPropagation();
          registerRemovedSkill(removeExisting.getAttribute("data-skill-id") || "");
          removeExisting.closest("[data-creature-training-skill-row]")?.remove();
          return;
        }
        const removeNew = target?.closest("[data-creature-training-remove-new-skill]");
        if (removeNew instanceof HTMLButtonElement) {
          event.preventDefault();
          event.stopPropagation();
          const row = removeNew.closest("[data-creature-training-new-skill-row]");
          const rows = panel.querySelectorAll("[data-creature-training-new-skill-row]");
          if (row instanceof HTMLElement && rows.length > 1) {
            row.remove();
          } else if (row instanceof HTMLElement) {
            row.querySelectorAll("select, input").forEach((field) => {
              if (field instanceof HTMLSelectElement) {
                field.selectedIndex = 0;
              } else if (field instanceof HTMLInputElement) {
                field.value = "0";
              }
            });
          }
        }
      });
      refreshCommandPrerequisites();
      refreshSwimSpeedInputs();
      refreshFlySpeedInputs();
      refreshManaInputs();
      refreshSizeModifier();
      panel.addEventListener("pointerdown", (event) => {
        event.stopPropagation();
      }, true);
      panel.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(panel);
        const floatingCard = drawer.closest(".card-hand__floating-card");
        floatingCard?.querySelectorAll("[data-creature-card-field]").forEach((field) => {
          if (
            !(field instanceof HTMLInputElement)
            && !(field instanceof HTMLTextAreaElement)
            && !(field instanceof HTMLSelectElement)
          ) {
            return;
          }
          if (field instanceof HTMLInputElement && field.type === "file") {
            if (field.files && field.files.length > 0) {
              formData.append(field.name, field.files[0]);
            }
            return;
          }
          formData.append(field.name, field.value);
        });
        const response = await fetch(panel.action, {
          method: "POST",
          body: formData,
          headers: {
            "X-CSRFToken": getCsrfToken(),
            "X-Requested-With": "XMLHttpRequest",
            Accept: "application/json",
          },
          credentials: "same-origin",
        });
        if (!response.ok) {
          return;
        }
        const payload = await response.json();
        if (!payload?.ok) {
          return;
        }
        replaceCreatureCardFragments(drawer, payload);
      });
    }
  };

  const replaceCreatureCardFragments = (drawer, payload) => {
    const floating = drawer.closest("[data-card-hand-floating]");
    const hand = floating?.closest("[data-card-hand]");
    const cardKey = String(payload.cardKey || floating?.getAttribute("data-card-key") || "");
    if (hand instanceof HTMLElement && cardKey && payload.miniCardHtml) {
      const mini = hand.querySelector(`[data-card-hand-open-card][data-card-key="${CSS.escape(cardKey)}"]`);
      if (mini instanceof HTMLElement) {
        const wrapper = document.createElement("div");
        wrapper.innerHTML = payload.miniCardHtml;
        const nextMiniCard = wrapper.querySelector(".creature-card");
        const currentMiniCard = mini.querySelector(".creature-card");
        if (nextMiniCard instanceof HTMLElement && currentMiniCard instanceof HTMLElement) {
          currentMiniCard.replaceWith(nextMiniCard);
          fitCreatureRuleText(nextMiniCard);
        }
        if (payload.cardTitle) {
          mini.title = String(payload.cardTitle);
        }
      }
    }
    const containers = [floating].filter(Boolean);
    containers.forEach((container) => {
      if (!(container instanceof HTMLElement)) {
        return;
      }
      const previousCard = container.querySelector(".creature-card");
      const wasUnlocked = previousCard instanceof HTMLElement && previousCard.classList.contains("is-edit-unlocked");
      if (payload.cardHtml) {
        const wrapper = document.createElement("div");
        wrapper.innerHTML = payload.cardHtml;
        const nextCard = wrapper.querySelector(".creature-card");
        const currentCard = container.querySelector(".creature-card");
        if (nextCard instanceof HTMLElement && currentCard instanceof HTMLElement) {
          currentCard.replaceWith(nextCard);
          fitCreatureRuleText(nextCard);
        }
      }
      if (payload.drawerHtml) {
        const wrapper = document.createElement("div");
        wrapper.innerHTML = payload.drawerHtml;
        const nextDrawer = wrapper.querySelector("[data-creature-training-drawer]");
        const currentDrawer = container.querySelector("[data-creature-training-drawer]");
        if (nextDrawer instanceof HTMLElement && currentDrawer instanceof HTMLElement) {
          const wasOpen = currentDrawer.classList.contains("is-open");
          currentDrawer.replaceWith(nextDrawer);
          if (wasOpen) {
            nextDrawer.classList.add("is-open");
            const panel = nextDrawer.querySelector("[data-creature-training-form]");
            const toggle = nextDrawer.querySelector("[data-creature-training-toggle]");
            if (panel instanceof HTMLElement) {
              panel.hidden = false;
            }
            if (toggle instanceof HTMLButtonElement) {
              toggle.setAttribute("aria-expanded", "true");
            }
          }
          bindTrainingDrawer(nextDrawer);
          const nextCard = container.querySelector(".creature-card");
          if (nextCard instanceof HTMLElement && (wasOpen || wasUnlocked)) {
            setCreatureCardUnlocked(nextCard, true);
          }
          bindCreatureCardEditor(nextCard);
          fitCreatureRuleText(nextCard);
          initGodCards(container);
        }
      }
    });
  };

  document.querySelectorAll("[data-creature-card-editor]").forEach(bindCreatureCardEditor);
  document.querySelectorAll("[data-creature-training-drawer]").forEach(bindTrainingDrawer);
  document.querySelectorAll(".creature-card").forEach(fitCreatureRuleText);

  if (document.documentElement.dataset.creatureCardsBound === "1") {
    return;
  }
  document.documentElement.dataset.creatureCardsBound = "1";

  let creatureRuleFitTimer = 0;
  window.addEventListener("resize", () => {
    window.clearTimeout(creatureRuleFitTimer);
    creatureRuleFitTimer = window.setTimeout(() => {
      document.querySelectorAll(".creature-card").forEach(fitCreatureRuleText);
    }, 120);
  });

  document.addEventListener("pointerdown", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target?.closest(".creature-card__damage-cluster")) {
      return;
    }
    event.stopPropagation();
  }, true);

  const damageRequestQueues = new WeakMap();

  const submitCreatureDamageForm = (form) => {
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    const cluster = form.closest("[data-creature-damage-cluster]");
    if (!(cluster instanceof HTMLElement)) {
      form.submit();
      return;
    }

    const request = async () => {
      const requestUrl = form.getAttribute("action") || window.location.href;
      const response = await fetch(requestUrl, {
        method: "POST",
        body: new FormData(form),
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        credentials: "same-origin",
      });
      if (!response.ok) {
        throw new Error("creature damage update failed");
      }
      const payload = await response.json();
      renderPreviewDamage(
        cluster,
        readInt(payload.current_damage, readInt(cluster.dataset.creatureCurrentDamage, 0)),
      );
    };

    const queuedRequest = (damageRequestQueues.get(cluster) || Promise.resolve())
      .then(request)
      .catch(() => {
        // Keep the card on the table; the unchanged value signals a failed update.
      });
    damageRequestQueues.set(cluster, queuedRequest);
  };

  const readInt = (value, fallback = 0) => {
    const parsed = Number.parseInt(String(value ?? "").trim(), 10);
    return Number.isNaN(parsed) ? fallback : parsed;
  };

  const woundPenaltyForLabel = (label) => {
    if (label === "-2" || label === "-4" || label === "-6") {
      return readInt(label, 0);
    }
    return 0;
  };

  const formatPenalty = (penalty) => (
    penalty ? `${penalty > 0 ? `+${penalty}` : penalty}` : ""
  );

  const woundZoneForDamage = (cluster, damage) => {
    const rows = Array.from(cluster.querySelectorAll("[data-creature-wound-row]"))
      .map((row) => ({
        label: String(row.getAttribute("data-label") || "-"),
        threshold: readInt(row.getAttribute("data-threshold"), 0),
      }))
      .sort((a, b) => a.threshold - b.threshold);
    let current = { label: "-", threshold: 0, penalty: 0 };
    for (const row of rows) {
      if (damage >= row.threshold) {
        current = {
          label: row.label,
          threshold: row.threshold,
          penalty: woundPenaltyForLabel(row.label),
        };
      } else {
        break;
      }
    }
    return current;
  };

  const renderPreviewDamage = (cluster, nextDamage) => {
    const card = cluster.closest(".creature-card");
    const currentEl = cluster.querySelector("[data-creature-damage-current]");
    const maxEl = cluster.querySelector("[data-creature-damage-max]");
    const maxDamage = readInt(cluster.getAttribute("data-creature-wound-max") || maxEl?.textContent, 0);
    const damage = Math.max(0, Math.min(nextDamage, Math.max(0, maxDamage)));
    cluster.dataset.creatureCurrentDamage = String(damage);
    if (currentEl instanceof HTMLElement) {
      currentEl.textContent = String(damage);
    }
    if (maxEl instanceof HTMLElement) {
      maxEl.textContent = String(maxDamage);
    }

    const zone = woundZoneForDamage(cluster, damage);
    const status = card?.querySelector("[data-creature-wound-status]");
    if (!(status instanceof HTMLElement)) {
      return;
    }
    status.hidden = !zone.penalty;
    const labelEl = status.querySelector("[data-creature-wound-label]");
    const thresholdEl = status.querySelector("[data-creature-wound-threshold]");
    const penaltyEl = status.querySelector("[data-creature-wound-penalty]");
    if (labelEl instanceof HTMLElement) {
      labelEl.textContent = zone.label;
    }
    if (thresholdEl instanceof HTMLElement) {
      thresholdEl.textContent = String(zone.threshold);
    }
    if (penaltyEl instanceof HTMLElement) {
      penaltyEl.textContent = formatPenalty(zone.penalty);
    }
    fitCreatureRuleText(card);
  };

  const applyPreviewDamageAction = (cluster, action) => {
    if (action !== "heal" && action !== "damage") {
      return;
    }
    const current = readInt(cluster.getAttribute("data-creature-current-damage"), 0);
    const nextDamage = action === "damage" ? current + 1 : current - 1;
    renderPreviewDamage(cluster, nextDamage);
  };

  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const button = target?.closest(".creature-card__damage-cluster button");
    if (button instanceof HTMLButtonElement && !button.disabled && button.form instanceof HTMLFormElement) {
      const form = button.form;
      event.preventDefault();
      event.stopPropagation();
      submitCreatureDamageForm(form);
      return;
    }

    const cluster = target?.closest(".creature-card__damage-cluster");
    if (!(cluster instanceof HTMLElement)) {
      return;
    }
    const rect = cluster.getBoundingClientRect();
    const edgeWidth = Math.min(24, Math.max(14, rect.width * 0.32));
    const forms = Array.from(cluster.querySelectorAll("form"));
    if (!forms.length) {
      const action = button instanceof HTMLButtonElement
        ? button.getAttribute("data-creature-damage-action")
        : event.clientX <= rect.left + edgeWidth
          ? "heal"
          : event.clientX >= rect.right - edgeWidth
            ? "damage"
            : "";
      if (!action) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      applyPreviewDamageAction(cluster, action);
      return;
    }

    const form = event.clientX <= rect.left + edgeWidth
      ? forms[0]
      : event.clientX >= rect.right - edgeWidth
        ? forms[forms.length - 1]
        : null;
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    const submitter = form.querySelector("button[type='submit']");
    if (submitter instanceof HTMLButtonElement && submitter.disabled) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    submitCreatureDamageForm(form);
  }, true);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initCreatureCards, { once: true });
} else {
  initCreatureCards();
}
