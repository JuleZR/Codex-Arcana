import { initGodCards } from "./god_card.js?v=20260702a";

function comparableFormState(form) {
  return JSON.stringify(
    Array.from(new FormData(form).entries())
      .filter(([name]) => !["csrfmiddlewaretoken", "religion_entity"].includes(name))
      .map(([name, value]) => [
        name,
        value instanceof File
          ? (value.name || value.size
            ? `${value.name}:${value.size}:${value.lastModified}`
            : "")
          : String(value),
      ]),
  );
}

function replaceReligionCards(payload) {
  const containers = Array.from(document.querySelectorAll('[data-card-key="god"]'));
  if (!payload.cardHtml) {
    containers.forEach((container) => container.remove());
    return true;
  }
  if (!containers.length) {
    return false;
  }

  const wrapper = document.createElement("div");
  wrapper.innerHTML = payload.cardHtml;
  const nextCard = wrapper.querySelector(".card");
  if (!(nextCard instanceof HTMLElement)) {
    throw new Error("Die neue Religionskarte fehlt in der Serverantwort.");
  }

  containers.forEach((container, index) => {
    if (!(container instanceof HTMLElement)) {
      return;
    }
    const currentCard = container.querySelector(".card");
    if (!(currentCard instanceof HTMLElement)) {
      return;
    }
    const replacement = index === 0 ? nextCard : nextCard.cloneNode(true);
    currentCard.replaceWith(replacement);
    if (payload.religionCardTitle) {
      container.setAttribute("title", String(payload.religionCardTitle));
    }
    if (
      container.matches("[data-card-hand-floating]")
      && payload.religionCardStorageKey
    ) {
      const storageKey = String(container.dataset.cardHandStorageKey || "");
      container.dataset.cardHandStorageKey = storageKey.replace(
        /god\.\d+$/,
        String(payload.religionCardStorageKey),
      );
    }
    initGodCards(container);
  });
  return true;
}

export function initCharacterInfoForm() {
  const form = document.getElementById("charInfoForm");
  const religionSelect = document.getElementById("id_religion_entity");
  if (
    !(form instanceof HTMLFormElement)
    || !(religionSelect instanceof HTMLSelectElement)
    || religionSelect.disabled
    || form.dataset.religionAjaxBound === "1"
  ) {
    return;
  }
  form.dataset.religionAjaxBound = "1";

  let initialReligionId = String(religionSelect.value || "");
  let initialOtherFields = comparableFormState(form);

  form.addEventListener("submit", async (event) => {
    const nextReligionId = String(religionSelect.value || "");
    if (
      nextReligionId === initialReligionId
      || comparableFormState(form) !== initialOtherFields
    ) {
      return;
    }

    event.preventDefault();
    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton instanceof HTMLButtonElement) {
      submitButton.disabled = true;
    }
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
      });
      const payload = await response.json();
      if (!response.ok || !payload?.ok) {
        throw new Error(
          payload?.message || "Religion konnte nicht gespeichert werden.",
        );
      }

      if (!replaceReligionCards(payload)) {
        window.location.reload();
        return;
      }
      document.querySelectorAll("[data-character-religion-value]").forEach((element) => {
        element.textContent = String(payload.religionName || "-");
      });
      initialReligionId = nextReligionId;
      initialOtherFields = comparableFormState(form);

      if (payload.requiresMagicRefresh) {
        document.dispatchEvent(new CustomEvent("charsheet:external-refresh-requested", {
          detail: { force: true, learning: true, scope: "magic" },
        }));
      }
    } catch (error) {
      religionSelect.value = initialReligionId;
      window.alert(
        error instanceof Error
          ? error.message
          : "Religion konnte nicht gespeichert werden.",
      );
    } finally {
      if (submitButton instanceof HTMLButtonElement && submitButton.isConnected) {
        submitButton.disabled = false;
      }
    }
  });
}
