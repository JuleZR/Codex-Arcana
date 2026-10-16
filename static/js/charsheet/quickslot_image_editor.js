let cropperModulePromise;

function loadCropperModule() {
  return cropperModulePromise ||= import("/static/js/vendor/cropperjs/cropper.esm.js")
    .then(module => module.default || module)
    .catch(error => { cropperModulePromise = null; throw error; });
}

export function initQuickslotImageEditor({ onBusyChange, onImageChange = () => {}, loadCropper = loadCropperModule }) {
  const fileInput = document.getElementById("quickslotImageFile");
  const preview = document.getElementById("quickslotImagePreview");
  const previewImage = document.getElementById("quickslotImagePreviewImage");
  const stage = document.getElementById("quickslotImageCrop");
  const image = document.getElementById("quickslotCropImage");
  const error = document.getElementById("quickslotImageError");
  const editor = document.getElementById("quickslotEditor");
  let cropper, objectUrl, picture = "", generation = 0, busy = false;
  let removeSelectionLimit;

  function positionCrop() {
    if (stage.hidden) return;
    let rect = editor.getBoundingClientRect();
    const width = stage.offsetWidth;
    if (window.innerWidth >= rect.width + width + 44) {
      const left = Math.max(16, Math.min(rect.left, window.innerWidth - rect.width - width - 28));
      if (left !== rect.left) {
        Object.assign(editor.style, { left: `${left}px`, top: `${rect.top}px`, right: "auto", bottom: "auto", margin: "0" });
        rect = editor.getBoundingClientRect();
      }
    }
    stage.style.left = `${Math.max(16, Math.min(rect.right + 12, window.innerWidth - width - 16))}px`;
    stage.style.top = `${Math.max(16, Math.min(rect.top, window.innerHeight - stage.offsetHeight - 16))}px`;
  }
  function render() {
    preview.hidden = !picture;
    if (picture) previewImage.src = picture;
    else previewImage.removeAttribute("src");
    onImageChange();
  }
  function cancel() {
    generation++;
    removeSelectionLimit?.(); removeSelectionLimit = null;
    cropper?.destroy(); cropper = null;
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = null;
    image.onload = image.onerror = null;
    image.removeAttribute("src");
    fileInput.value = "";
    stage.hidden = true;
    busy = false; onBusyChange(false);
  }
  function report() {
    error.textContent = "Das Bild konnte nicht verarbeitet werden. Bitte ein anderes Bild wählen.";
    error.hidden = false;
  }
  async function open(source, file = false) {
    cancel(); error.hidden = true;
    const token = generation;
    busy = true; onBusyChange(true); stage.hidden = false;
    positionCrop();
    stage.focus();
    if (file) source = objectUrl = URL.createObjectURL(source);
    try {
      const Cropper = await loadCropper();
      if (token !== generation) return;
      await new Promise((resolve, reject) => {
        image.onload = resolve;
        image.onerror = reject;
        image.src = source;
        if (image.complete && image.naturalWidth > 0) resolve();
      });
      if (token !== generation) return;
      image.onload = image.onerror = null;
      cropper = new Cropper(image, { container: image.parentElement });
      const selection = cropper.getCropperSelection();
      selection.setAttribute("aspect-ratio", "1");
      selection.setAttribute("initial-aspect-ratio", "1");
      selection.setAttribute("initial-coverage", "0.72");
      selection.aspectRatio = selection.initialAspectRatio = 1;
      selection.initialCoverage = .72;
      selection.movable = selection.resizable = true;
      selection.precise = true;
      const cropperImage = cropper.getCropperImage();
      cropperImage.scalable = cropperImage.translatable = false;
      cropperImage.rotatable = cropperImage.skewable = false;
      await cropperImage.$ready();
      if (token !== generation) return;
      cropperImage.$center("contain");
      const canvas = cropper.getCropperCanvas();
      function bounds() {
        const imageRect = cropperImage.getBoundingClientRect();
        const canvasRect = canvas.getBoundingClientRect();
        return {
          x: imageRect.left - canvasRect.left, y: imageRect.top - canvasRect.top,
          width: imageRect.width, height: imageRect.height,
        };
      }
      const limitSelection = event => {
        const box = bounds();
        const { x, y, width, height } = event.detail;
        if (x < box.x || y < box.y || x + width > box.x + box.width
            || y + height > box.y + box.height) event.preventDefault();
      };
      selection.addEventListener("change", limitSelection);
      removeSelectionLimit = () => selection.removeEventListener("change", limitSelection);
      const box = bounds();
      const size = Math.min(box.width, box.height) * .72;
      selection.$change(box.x + (box.width - size) / 2, box.y + (box.height - size) / 2, size, size);
    } catch (_error) {
      if (token === generation) { cancel(); report(); }
    }
  }
  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (file) open(file, true);
  });
  editor.querySelector("[data-quickslot-image-adjust]").addEventListener("click", () => {
    if (picture) open(picture);
  });
  editor.querySelector("[data-quickslot-image-remove]").addEventListener("click", () => {
    cancel(); picture = ""; render(); error.hidden = true;
  });
  stage.querySelector("[data-quickslot-crop-cancel]").addEventListener("click", () => {
    cancel(); fileInput.focus();
  });
  stage.addEventListener("keydown", event => {
    if (event.key !== "Escape") return;
    event.preventDefault(); event.stopPropagation();
    cancel(); fileInput.focus();
  });
  const apply = stage.querySelector("[data-quickslot-crop-apply]");
  apply.addEventListener("click", async () => {
    if (!cropper || apply.disabled) return;
    const token = generation;
    apply.disabled = true;
    try {
      const canvas = await cropper.getCropperSelection().$toCanvas({
        width: 192, height: 192,
        beforeDraw(context, target) {
          context.fillStyle = "#f3ead8";
          context.fillRect(0, 0, target.width, target.height);
        },
      });
      if (token !== generation) return;
      picture = canvas.toDataURL("image/jpeg", .9);
      cancel(); render(); fileInput.focus();
    } catch (_error) {
      if (token === generation) report();
    } finally { apply.disabled = false; }
  });
  editor.addEventListener("close", cancel);
  editor.addEventListener("pointermove", positionCrop);
  window.addEventListener("resize", positionCrop);
  if (typeof ResizeObserver !== "undefined") {
    const observer = new ResizeObserver(positionCrop);
    observer.observe(editor);
    observer.observe(stage);
  }
  return {
    setImage(value) { cancel(); picture = value || ""; error.hidden = true; render(); },
    getImage: () => picture,
    isBusy: () => busy,
  };
}
