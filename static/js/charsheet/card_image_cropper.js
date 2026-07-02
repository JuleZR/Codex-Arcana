let cropper = null;
let cropperModulePromise = null;
let objectUrl = "";

function loadCropperModule() {
  if (!cropperModulePromise) {
    cropperModulePromise = import("/static/js/vendor/cropperjs/cropper.esm.js")
      .then((module) => module.default || module)
      .catch((error) => {
        cropperModulePromise = null;
        throw error;
      });
  }
  return cropperModulePromise;
}

function clearObjectUrl() {
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
    objectUrl = "";
  }
}

function destroyCropper() {
  if (cropper) {
    cropper.destroy();
    cropper = null;
  }
}

function ensureDialog() {
  let dialog = document.getElementById("cardImageCropperDialog");
  if (dialog) {
    return dialog;
  }

  dialog = document.createElement("div");
  dialog.id = "cardImageCropperDialog";
  dialog.className = "card-image-cropper";
  dialog.hidden = true;
  dialog.innerHTML = `
    <div class="card-image-cropper__backdrop" data-card-crop-cancel></div>
    <section class="card-image-cropper__window" role="dialog" aria-modal="true" aria-labelledby="cardImageCropperTitle">
      <header class="card-image-cropper__header">
        <h3 id="cardImageCropperTitle">Kartenbild zuschneiden</h3>
        <button type="button" class="card-image-cropper__close" data-card-crop-cancel aria-label="Fenster schliessen">x</button>
      </header>
      <div class="card-image-cropper__body">
        <div class="card-image-cropper__stage">
          <img id="cardImageCropperImage" alt="Zuschneide-Vorschau">
        </div>
        <p class="card-image-cropper__hint">Waehle den Bildausschnitt. Das Seitenverhaeltnis bleibt fest auf 2:3.</p>
        <div class="card-image-cropper__actions">
          <button type="button" class="card-image-cropper__button" data-card-crop-cancel>Abbrechen</button>
          <button type="button" class="card-image-cropper__button card-image-cropper__button--primary" data-card-crop-apply>Uebernehmen</button>
        </div>
      </div>
    </section>
  `;
  document.body.appendChild(dialog);
  return dialog;
}

function loadImage(imageEl, source) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (callback) => {
      if (settled) {
        return;
      }
      settled = true;
      imageEl.onload = null;
      imageEl.onerror = null;
      callback();
    };
    imageEl.onload = () => finish(resolve);
    imageEl.onerror = () => finish(() => reject(new Error("image-load-failed")));
    imageEl.src = source;
    if (imageEl.complete && imageEl.naturalWidth > 0) {
      finish(resolve);
    }
  });
}

function configureCardSelection(cropperInstance) {
  const selection = cropperInstance?.getCropperSelection?.();
  if (!selection) {
    return;
  }
  selection.setAttribute("aspect-ratio", "0.6666666667");
  selection.setAttribute("initial-aspect-ratio", "0.6666666667");
  selection.setAttribute("initial-coverage", "0.82");
  selection.aspectRatio = 2 / 3;
  selection.initialAspectRatio = 2 / 3;
  selection.initialCoverage = 0.82;
  selection.movable = true;
  selection.resizable = true;
  selection.$center?.();
  selection.$render?.();
}

async function canvasFromSelection() {
  const selection = cropper?.getCropperSelection?.();
  if (!selection || typeof selection.$toCanvas !== "function") {
    return null;
  }
  return selection.$toCanvas({
    width: 900,
    height: 1350,
    beforeDraw: (context, targetCanvas) => {
      context.fillStyle = "#d8caa6";
      context.fillRect(0, 0, targetCanvas.width, targetCanvas.height);
    },
  });
}

export async function openCardImageCropper(file) {
  if (!(file instanceof File)) {
    return "";
  }

  const dialog = ensureDialog();
  const image = dialog.querySelector("#cardImageCropperImage");
  const applyButton = dialog.querySelector("[data-card-crop-apply]");
  const cancelButtons = Array.from(dialog.querySelectorAll("[data-card-crop-cancel]"));
  if (!(image instanceof HTMLImageElement) || !(applyButton instanceof HTMLButtonElement)) {
    return "";
  }

  destroyCropper();
  clearObjectUrl();
  objectUrl = URL.createObjectURL(file);

  const Cropper = await loadCropperModule();
  await loadImage(image, objectUrl);
  cropper = new Cropper(image, {
    container: image.parentElement,
  });
  configureCardSelection(cropper);

  dialog.hidden = false;
  document.body.classList.add("card-image-cropper-open");

  return new Promise((resolve) => {
    let settled = false;
    const cleanup = () => {
      cancelButtons.forEach((button) => button.removeEventListener("click", cancel));
      applyButton.removeEventListener("click", apply);
      dialog.hidden = true;
      document.body.classList.remove("card-image-cropper-open");
      destroyCropper();
      image.removeAttribute("src");
      clearObjectUrl();
    };
    const settle = (value) => {
      if (settled) {
        return;
      }
      settled = true;
      cleanup();
      resolve(value);
    };
    const cancel = () => settle("");
    const apply = async () => {
      const canvas = await canvasFromSelection();
      if (!canvas) {
        settle("");
        return;
      }
      settle(canvas.toDataURL("image/jpeg", 0.92));
    };

    cancelButtons.forEach((button) => button.addEventListener("click", cancel));
    applyButton.addEventListener("click", apply);
  });
}
