// Static alpha compositing, based on https://codepen.io/leusrox/pen/Xaadrx.
const MASK_URL = new URL("../../img/watercolor-cloud-mask.png", import.meta.url).href;
let maskPromise;
const initializedImages = new WeakSet();

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Watercolor image could not be loaded"));
    image.src = src;
  });
}

export function renderWatercolorImage(canvas, image, mask) {
  const ctx = canvas.getContext("2d");
  if (!ctx || !image.naturalWidth || !image.naturalHeight) {
    throw new Error("Watercolor canvas unavailable");
  }
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  const { width, height } = canvas;
  ctx.clearRect(0, 0, width, height);
  ctx.globalCompositeOperation = "source-over";
  ctx.save();
  // Turn the cloud with portrait images and widen its footprint around the motif.
  ctx.translate(width * 0.43, height / 2);
  const portrait = height > width;
  if (portrait) ctx.rotate(Math.PI / 2);
  const maskWidth = (portrait ? height : width) * 1.08;
  const maskHeight = (portrait ? width : height) * 1.08;
  ctx.drawImage(mask, -maskWidth / 2, -maskHeight / 2, maskWidth, maskHeight);
  ctx.restore();
  try {
    ctx.globalCompositeOperation = "source-in";
    ctx.drawImage(image, 0, 0, width, height);
  } finally {
    ctx.globalCompositeOperation = "source-over";
  }
  return canvas;
}

export function initWatercolorImages(root) {
  root.querySelectorAll("img[data-watercolor-image]").forEach((image) => {
    if (initializedImages.has(image)) return;
    initializedImages.add(image);
    const render = async () => {
      try {
        maskPromise ??= loadImage(MASK_URL);
        const [source, mask] = await Promise.all([
          loadImage(image.currentSrc || image.src), maskPromise,
        ]);
        const canvas = document.createElement("canvas");
        renderWatercolorImage(canvas, source, mask);
        // An image survives PageFlip's DOM cloning, unlike a canvas bitmap.
        const result = canvas.toDataURL("image/png");
        image.removeAttribute("srcset");
        image.src = result;
      } catch (_error) {
        // Keep the original image for failed loads, CORS or unavailable canvas.
      }
    };
    if (image.complete && image.naturalWidth) void render();
    else image.addEventListener("load", render, { once: true });
  });
}
