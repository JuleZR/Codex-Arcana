import { getCsrfToken } from "./utils.js";

function getObjectFitCoverDrawRect(image, width, height) {
  const naturalWidth = image.naturalWidth || width;
  const naturalHeight = image.naturalHeight || height;
  const scale = Math.max(width / naturalWidth, height / naturalHeight);
  const drawnWidth = naturalWidth * scale;
  const drawnHeight = naturalHeight * scale;
  return {
    x: (width - drawnWidth) * 0.5,
    y: (height - drawnHeight) * 0.33,
    width: drawnWidth,
    height: drawnHeight,
  };
}

function resolveTitleTone(card) {
  const image = card.querySelector(".card-art img");
  if (!(image instanceof HTMLImageElement) || !image.complete || !image.naturalWidth) {
    card.dataset.titleTone = "light";
    return;
  }

  const width = 80;
  const height = 112;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) {
    card.dataset.titleTone = "light";
    return;
  }

  try {
    const drawRect = getObjectFitCoverDrawRect(image, width, height);
    context.drawImage(image, drawRect.x, drawRect.y, drawRect.width, drawRect.height);
    const sample = context.getImageData(8, 7, 64, 10).data;
    let luminanceTotal = 0;
    let saturationTotal = 0;
    let samples = 0;

    for (let index = 0; index < sample.length; index += 4) {
      const red = sample[index] / 255;
      const green = sample[index + 1] / 255;
      const blue = sample[index + 2] / 255;
      const max = Math.max(red, green, blue);
      const min = Math.min(red, green, blue);
      luminanceTotal += (0.2126 * red) + (0.7152 * green) + (0.0722 * blue);
      saturationTotal += max - min;
      samples += 1;
    }

    const luminance = luminanceTotal / Math.max(1, samples);
    const saturation = saturationTotal / Math.max(1, samples);
    card.dataset.titleTone = luminance > 0.58 || (luminance > 0.5 && saturation < 0.18)
      ? "dark"
      : "light";
  } catch (_error) {
    card.dataset.titleTone = "light";
  }
}

function applyCardTextScale(card) {
  const rules = card.querySelector(".card-rules");
  if (!(rules instanceof HTMLElement)) {
    return;
  }

  const minScale = 0.82;
  const maxScale = 1.08;
  let low = minScale;
  let high = maxScale;
  let best = minScale;

  const applyScale = (scale) => {
    card.style.setProperty("--card-ability-font-size", `${14.6 * scale}px`);
    card.style.setProperty("--card-vow-font-size", `${13.6 * scale}px`);
    card.style.setProperty("--card-tabstop-font-size", `${13.4 * scale}px`);
    card.style.setProperty("--card-roll-range-font-size", `${10.5 * scale}px`);
    card.style.setProperty("--card-roll-result-font-size", `${11.5 * scale}px`);
  };

  const fits = () => rules.scrollHeight <= rules.clientHeight + 1;

  applyScale(maxScale);
  if (fits()) {
    return;
  }

  for (let index = 0; index < 8; index += 1) {
    const mid = (low + high) / 2;
    applyScale(mid);
    if (fits()) {
      best = mid;
      low = mid;
    } else {
      high = mid;
    }
  }
  applyScale(best);
}

function bindGodCardEditor(card) {
  if (!(card instanceof HTMLElement) || !card.hasAttribute("data-god-card-editor")) {
    return;
  }
  if (card.dataset.godCardEditorBound === "1") {
    return;
  }
  card.dataset.godCardEditorBound = "1";

  const toggle = card.querySelector("[data-god-card-edit-toggle]");
  const triggers = Array.from(card.querySelectorAll("[data-god-card-aspect-trigger]"));
  const picker = card.querySelector("[data-god-card-aspect-picker]");
  const imageTrigger = card.querySelector("[data-god-card-image-trigger]");
  const removeImageButton = card.querySelector("[data-god-card-remove-image]");
  const updateUrl = card.getAttribute("data-god-card-update-url") || "";
  let replaceAspectId = "";

  const syncDruidCultDisplayName = (payload) => {
    const displayName = String(payload?.druidCultDisplayName || "").trim();
    if (!displayName) {
      return;
    }
    document.querySelectorAll(".school_group_binding_display").forEach((element) => {
      if (!(element instanceof HTMLElement)) {
        return;
      }
      element.textContent = displayName;
      element.classList.remove("school_group_binding_display--missing");
    });
  };

  const replaceCardFromPayload = (payload, { keepUnlocked = false } = {}) => {
    if (!payload?.ok || !payload.cardHtml) {
      throw new Error("god card update invalid");
    }
    const wrapper = document.createElement("div");
    wrapper.innerHTML = payload.cardHtml;
    const nextCard = wrapper.querySelector(".card");
      if (nextCard instanceof HTMLElement) {
        card.replaceWith(nextCard);
        syncDruidCultDisplayName(payload);
        initGodCards(nextCard.parentElement || document);
      if (keepUnlocked) {
        nextCard.classList.add("is-edit-unlocked");
        const nextToggle = nextCard.querySelector("[data-god-card-edit-toggle]");
        if (nextToggle instanceof HTMLButtonElement) {
          nextToggle.setAttribute("aria-pressed", "true");
          nextToggle.title = "Karte sperren";
        }
      }
    }
  };

  const saveCardFields = async () => {
    if (!updateUrl) {
      return;
    }
    card.classList.add("is-saving");
    const formData = new FormData();
    card.querySelectorAll("[data-god-card-field]").forEach((field) => {
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
    const response = await fetch(updateUrl, {
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
      throw new Error("god card update failed");
    }
    replaceCardFromPayload(await response.json());
  };

  const removeCustomImage = async () => {
    if (!updateUrl) {
      return;
    }
    card.classList.add("is-saving");
    const formData = new FormData();
    formData.append("remove_custom_god_image", "1");
    const response = await fetch(updateUrl, {
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
      throw new Error("god card image remove failed");
    }
    replaceCardFromPayload(await response.json(), { keepUnlocked: true });
  };

  const setUnlocked = (isUnlocked) => {
    card.classList.toggle("is-edit-unlocked", isUnlocked);
    if (toggle instanceof HTMLButtonElement) {
      toggle.setAttribute("aria-pressed", isUnlocked ? "true" : "false");
      toggle.title = isUnlocked ? "Karte sperren" : "Karte freigeben";
    }
    if (!isUnlocked) {
      closePicker();
    }
  };

  const closePicker = () => {
    if (picker instanceof HTMLElement) {
      picker.hidden = true;
      card.classList.remove("is-choosing-aspect");
    }
  };

  const openPicker = (trigger = null) => {
    if (picker instanceof HTMLElement) {
      replaceAspectId = trigger instanceof HTMLElement
        ? String(trigger.getAttribute("data-god-card-aspect-id") || "")
        : "";
      picker.hidden = false;
      card.classList.add("is-choosing-aspect");
      const firstChoice = picker.querySelector("button");
      if (firstChoice instanceof HTMLButtonElement) {
        firstChoice.focus();
      }
    }
  };

  if (toggle instanceof HTMLButtonElement) {
    toggle.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (card.classList.contains("is-edit-unlocked")) {
        if (!updateUrl) {
          setUnlocked(false);
          return;
        }
        try {
          await saveCardFields();
        } catch (_error) {
          card.classList.remove("is-saving");
        }
        return;
      }
      setUnlocked(true);
    });
  }

  if (imageTrigger instanceof HTMLElement) {
    const imageInput = imageTrigger.querySelector('input[type="file"]');
    imageTrigger.addEventListener("click", (event) => {
      if (!card.classList.contains("is-edit-unlocked")) {
        event.preventDefault();
        return;
      }
      if (event.target === imageInput) {
        return;
      }
      event.preventDefault();
      if (imageInput instanceof HTMLInputElement) {
        imageInput.click();
      }
    });
  }

  if (removeImageButton instanceof HTMLButtonElement) {
    removeImageButton.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (!card.classList.contains("is-edit-unlocked")) {
        return;
      }
      try {
        await removeCustomImage();
      } catch (_error) {
        card.classList.remove("is-saving");
      }
    });
  }

  triggers.forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (!card.classList.contains("is-edit-unlocked")) {
        return;
      }
      if (!(picker instanceof HTMLElement)) {
        return;
      }
      if (picker.hidden) {
        openPicker(trigger);
      } else {
        closePicker();
      }
    });
  });

  if (picker instanceof HTMLFormElement) {
    picker.addEventListener("click", (event) => {
      event.stopPropagation();
    });
    picker.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!updateUrl) {
        return;
      }
      card.classList.add("is-saving");
      try {
        const formData = new FormData();
        formData.append("action", "choose_aspect");
        picker.querySelectorAll('input[name="core_aspects"]').forEach((input) => {
          if (!(input instanceof HTMLInputElement)) {
            return;
          }
          if (replaceAspectId && input.value === replaceAspectId) {
            return;
          }
          formData.append("core_aspects", input.value);
        });
        const submitter = event.submitter instanceof HTMLButtonElement ? event.submitter : null;
        if (submitter?.name) {
          formData.append(submitter.name, submitter.value);
        }
        const response = await fetch(updateUrl, {
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
          throw new Error("god card update failed");
        }
        const payload = await response.json();
        replaceCardFromPayload(payload, { keepUnlocked: true });
      } catch (_error) {
        card.classList.remove("is-saving");
      }
    });
  }

  document.addEventListener("click", closePicker);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closePicker();
    }
  });
}

export function initGodCards(root = document) {
  const cards = Array.from(root.querySelectorAll(".card"));
  cards.forEach((card) => {
    bindGodCardEditor(card);
    const image = card.querySelector(".card-art img");
    if (image instanceof HTMLImageElement && !image.complete) {
      image.addEventListener("load", () => resolveTitleTone(card), { once: true });
      image.addEventListener("error", () => {
        card.dataset.titleTone = "light";
      }, { once: true });
      return;
    }
    resolveTitleTone(card);
    requestAnimationFrame(() => applyCardTextScale(card));
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => initGodCards(), { once: true });
} else {
  initGodCards();
}
