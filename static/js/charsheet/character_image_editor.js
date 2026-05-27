import { createFloatingWindowController } from "./window_manager.js";

let cropper = null;
let objectUrl = "";
let cropperModulePromise = null;
let pendingSnapshot = null;

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

function destroyCropper({ revokeUrl = false } = {}) {
  if (cropper) {
    cropper.destroy();
    cropper = null;
  }
  if (revokeUrl) {
    clearObjectUrl();
  }
}

function loadImageIntoCropperStage(imageEl, source) {
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

function ensurePreviewImage(previewFrame) {
  let image = document.getElementById("charPicturePreviewImage");
  if (image) {
    return image;
  }

  const placeholder = document.getElementById("charPicturePreviewPlaceholder");
  image = document.createElement("img");
  image.id = "charPicturePreviewImage";
  image.alt = "Vorschau des Charakterbilds";
  previewFrame.appendChild(image);
  placeholder?.remove();
  return image;
}

function ensurePlaceholder(previewFrame) {
  let placeholder = document.getElementById("charPicturePreviewPlaceholder");
  if (placeholder) {
    return placeholder;
  }

  placeholder = document.createElement("div");
  placeholder.id = "charPicturePreviewPlaceholder";
  placeholder.className = "char_picture_editor__placeholder";
  placeholder.textContent = "Kein Bild";
  previewFrame.appendChild(placeholder);
  return placeholder;
}

function snapshotCurrentState(elements) {
  const previewImage = elements.previewFrame.querySelector("#charPicturePreviewImage");
  return {
    croppedData: elements.croppedDataInput.value,
    hasImage: Boolean(previewImage?.getAttribute("src")),
    previewSrc: previewImage?.getAttribute("src") || "",
    removeHidden: elements.removeButton.hidden,
    removeValue: elements.removeFlagInput.value,
  };
}

function restoreSnapshot(elements, snapshot) {
  if (!snapshot) {
    return;
  }

  destroyCropper({ revokeUrl: false });
  elements.cropperImage.removeAttribute("src");
  elements.fileInput.value = "";
  elements.croppedDataInput.value = snapshot.croppedData || "";
  elements.removeFlagInput.value = snapshot.removeValue || "0";
  elements.removeButton.hidden = snapshot.removeHidden;

  const previewImage = elements.previewFrame.querySelector("#charPicturePreviewImage");
  if (snapshot.hasImage && snapshot.previewSrc) {
    const image = previewImage || ensurePreviewImage(elements.previewFrame);
    image.src = snapshot.previewSrc;
    elements.previewFrame.classList.add("has-image");
  } else {
    previewImage?.remove();
    ensurePlaceholder(elements.previewFrame);
    elements.previewFrame.classList.remove("has-image");
  }
}

function resetToEmptyState(elements) {
  destroyCropper({ revokeUrl: true });
  elements.previewFrame.querySelector("#charPicturePreviewImage")?.remove();
  ensurePlaceholder(elements.previewFrame);
  elements.previewFrame.classList.remove("has-image");
  elements.croppedDataInput.value = "";
  elements.removeFlagInput.value = "1";
  elements.fileInput.value = "";
  elements.adjustButton.hidden = true;
  elements.removeButton.hidden = true;
  elements.cropperImage.removeAttribute("src");
}

async function updatePreviewFromCropper(previewFrame, croppedDataInput) {
  if (!cropper) {
    return false;
  }

  const selection = cropper.getCropperSelection?.();
  if (!selection || typeof selection.$toCanvas !== "function") {
    return false;
  }

  let canvas;
  try {
    canvas = await selection.$toCanvas({
      width: 800,
      height: 1000,
      beforeDraw: (context, targetCanvas) => {
        context.fillStyle = "#f3ead8";
        context.fillRect(0, 0, targetCanvas.width, targetCanvas.height);
      },
    });
  } catch (_error) {
    return false;
  }
  if (!canvas) {
    return false;
  }

  const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
  const previewImage = ensurePreviewImage(previewFrame);
  previewImage.src = dataUrl;
  previewFrame.classList.add("has-image");
  croppedDataInput.value = dataUrl;
  return true;
}

function configurePortraitSelection(cropperInstance) {
  const selection = cropperInstance?.getCropperSelection?.();
  if (!selection) {
    return;
  }

  selection.setAttribute("aspect-ratio", "0.8");
  selection.setAttribute("initial-aspect-ratio", "0.8");
  selection.setAttribute("initial-coverage", "0.72");
  selection.aspectRatio = 4 / 5;
  selection.initialAspectRatio = 4 / 5;
  selection.initialCoverage = 0.72;
  selection.movable = true;
  selection.resizable = true;
  selection.$center?.();
  selection.$render?.();
}

export function initCharacterImageEditor() {
  const form = document.getElementById("charInfoForm");
  const fileInput = document.getElementById("charPictureInput");
  const croppedDataInput = document.getElementById("charPictureCroppedData");
  const removeFlagInput = document.getElementById("charPictureRemoveFlag");
  const previewFrame = document.getElementById("charPicturePreviewFrame");
  const adjustButton = document.getElementById("charPictureAdjustBtn");
  const removeButton = document.getElementById("charPictureRemoveBtn");
  const cropperImage = document.getElementById("charPictureCropperImage");
  const cropWindow = document.getElementById("characterImageCropWindow");
  const cropWindowClose = document.getElementById("characterImageCropWindowClose");
  const cropWindowHandle = document.getElementById("characterImageCropWindowHandle");
  const cropApplyButton = document.getElementById("charPictureCropApplyBtn");
  const cropCancelButton = document.getElementById("charPictureCropCancelBtn");

  if (
    !form
    || !fileInput
    || !croppedDataInput
    || !removeFlagInput
    || !previewFrame
    || !adjustButton
    || !removeButton
    || !cropperImage
    || !cropWindow
    || !cropWindowClose
    || !cropWindowHandle
    || !cropApplyButton
    || !cropCancelButton
  ) {
    return null;
  }

  const previewImage = document.getElementById("charPicturePreviewImage");
  if (previewImage && !previewImage.getAttribute("src")) {
    previewImage.remove();
  }
  if (previewFrame.querySelector("img")) {
    previewFrame.classList.add("has-image");
  }

  const elements = {
    cropperImage,
    croppedDataInput,
    fileInput,
    previewFrame,
    adjustButton,
    removeButton,
    removeFlagInput,
  };
  const cropWindowController = createFloatingWindowController({
    windowEl: cropWindow,
    closeButton: cropWindowClose,
    handle: cropWindowHandle,
    startTop: 96,
    startRightInset: 120,
    storageKey: "charsheet.characterImageCropWindow",
    allowPersistedOpen: false,
  });

  if (form.dataset.charImageEditorBound === "1") {
    return {
      destroy() {
        destroyCropper();
      },
    };
  }

  form.dataset.charImageEditorBound = "1";

  const cancelCropping = () => {
    restoreSnapshot(elements, pendingSnapshot);
    pendingSnapshot = null;
    cropWindowController?.close?.();
  };

  const openCropWindowForSource = async (source, { preserveSnapshot = true } = {}) => {
    if (!source) {
      return false;
    }

    if (preserveSnapshot) {
      pendingSnapshot = snapshotCurrentState(elements);
    }
    destroyCropper({ revokeUrl: false });

    let Cropper;
    try {
      Cropper = await loadCropperModule();
    } catch (_error) {
      pendingSnapshot = null;
      return false;
    }

    try {
      await loadImageIntoCropperStage(cropperImage, source);
    } catch (_error) {
      pendingSnapshot = null;
      return false;
    }

    cropper = new Cropper(cropperImage, {
      container: cropperImage.parentElement,
    });
    configurePortraitSelection(cropper);
    cropWindowController?.open?.();
    return true;
  };

  fileInput.addEventListener("change", async () => {
    const [file] = fileInput.files || [];
    if (!file) {
      return;
    }

    destroyCropper({ revokeUrl: true });
    objectUrl = URL.createObjectURL(file);
    removeFlagInput.value = "0";
    adjustButton.hidden = false;
    removeButton.hidden = false;

    const opened = await openCropWindowForSource(objectUrl);
    if (!opened) {
      const previewImageFallback = ensurePreviewImage(previewFrame);
      previewImageFallback.src = objectUrl;
      previewFrame.classList.add("has-image");
      croppedDataInput.value = "";
      pendingSnapshot = null;
    }
  });

  adjustButton.addEventListener("click", async () => {
    const currentSrc = previewFrame.querySelector("#charPicturePreviewImage")?.getAttribute("src") || "";
    if (!currentSrc) {
      return;
    }
    fileInput.value = "";
    await openCropWindowForSource(currentSrc);
  });

  removeButton.addEventListener("click", () => {
    pendingSnapshot = null;
    resetToEmptyState(elements);
  });

  cropApplyButton.addEventListener("click", async () => {
    const didUpdate = await updatePreviewFromCropper(previewFrame, croppedDataInput);
    if (!didUpdate) {
      return;
    }
    removeFlagInput.value = "0";
    adjustButton.hidden = false;
    removeButton.hidden = false;
    fileInput.value = "";
    pendingSnapshot = null;
    destroyCropper({ revokeUrl: true });
    cropperImage.removeAttribute("src");
    cropWindowController?.close?.();
  });

  cropCancelButton.addEventListener("click", cancelCropping);
  cropWindowClose.addEventListener("click", cancelCropping);

  form.addEventListener("submit", async (event) => {
    if (cropper && pendingSnapshot) {
      event.preventDefault();
      const didUpdate = await updatePreviewFromCropper(previewFrame, croppedDataInput);
      if (!didUpdate) {
        return;
      }
      pendingSnapshot = null;
      destroyCropper({ revokeUrl: true });
      form.submit();
    }
  });

  return {
    destroy() {
      destroyCropper({ revokeUrl: true });
    },
  };
}
