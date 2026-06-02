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

export function initGodCards(root = document) {
  const cards = Array.from(root.querySelectorAll(".card"));
  cards.forEach((card) => {
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
