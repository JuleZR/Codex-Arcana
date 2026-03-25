export function initFireflies() {
  const fireflies = Array.from(document.querySelectorAll(".firefly-layer .firefly"));
  if (!fireflies.length) {
    return;
  }

  let seed = 948713;
  const rand = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  const randRange = (min, max) => min + (max - min) * rand();

  const styleId = "firefly-generated-keyframes";
  document.getElementById(styleId)?.remove();

  const keyframes = [];
  fireflies.forEach((firefly, index) => {
    const moveName = `firefly-move-${index + 1}`;
    const stepCount = Math.floor(randRange(16, 29));
    const frames = [];
    for (let step = 0; step <= stepCount; step += 1) {
      const percent = (step / stepCount) * 100;
      const x = randRange(-49, 49).toFixed(2);
      const y = randRange(-49, 49).toFixed(2);
      const scale = randRange(0.26, 1).toFixed(2);
      frames.push(`${percent.toFixed(6)}% { transform: translateX(${x}vw) translateY(${y}vh) scale(${scale}); }`);
    }
    keyframes.push(`@keyframes ${moveName} {\n${frames.join("\n")}\n}`);

    firefly.style.setProperty("--ff-move", moveName);
    firefly.style.setProperty("--ff-move-duration", `${Math.round(randRange(180, 320))}s`);
    firefly.style.setProperty("--ff-move-delay", `-${Math.round(randRange(0, 300))}s`);
    firefly.style.setProperty("--ff-drift-duration", `${randRange(9, 18).toFixed(3)}s`);
    firefly.style.setProperty("--ff-flash-duration", `${Math.round(randRange(5200, 10800))}ms`);
    firefly.style.setProperty("--ff-flash-delay", `${Math.round(randRange(0, 9000))}ms`);
  });

  const styleEl = document.createElement("style");
  styleEl.id = styleId;
  styleEl.textContent = keyframes.join("\n");
  document.head.appendChild(styleEl);
}
