const RING_VARIANTS = {

  normal: {
    theme: "normal",
    modeClass: "mode-normal",

    outerText:
      "SI • ALEAE • FATALES • PRO • NOBIS • QUIS • CONTRA • NOS •",

    innerText:
      "WENN DIE SCHICKSALHAFTEN WÜRFEL FÜR UNS SIND • WER KANN DANN GEGEN UNS SEIN •"
  },

  critSuccess: {
    theme: "crit-success",
    modeClass: "mode-crit-success",

    outerText:
      "SUCCESSUS • ET • FORTUNA • STULTIS • FAVENT •",

    innerText:
      "ERFOLG UND GLÜCK SIND AUF DER SEITE DER NARREN •"
  },

  critFail: {
    theme: "crit-fail",
    modeClass: "mode-crit-fail",

    outerText:
      "FORTUNA • DEFUIT • INFORTUNIUM • ACCESSIT •",

    innerText:
      "ERST HATTEN WIR KEIN GLÜCK • DANN KAM AUCH NOCH PECH DAZU •"
  }
};


const TIMING = {
  numberAppearGap: 120,
  numberHold: 1600,
  mergeDuration: 620,
  flashDelay: 60,
  runeDelay: 100,
  resultDelay: 650,
  settleDelay: 450,
  resultHold: 5000
};


const PARTICLE_COUNT = 300;

export function layoutCriticalText(text, measure = (line, size) => Array.from(line).length * size * 1.1) {
  const words = text.trim().split(/\s+/);
  for (let fontSize = 72; fontSize >= 2.5; fontSize -= .5) {
    const lines = [];
    let line = "";
    if (words.some(word => measure(word, fontSize) > 210)) continue;
    for (const word of words) {
      const candidate = line ? `${line} ${word}` : word;
      if (line && measure(candidate, fontSize) > 210) { lines.push(line); line = word; }
      else line = candidate;
    }
    lines.push(line);
    if (lines.length * fontSize * 1.2 <= 110) return { text: lines.join("\n"), fontSize };
  }
  return { text, fontSize: 3 };
}




export function layoutFusionElements(elements, width, height) {
  const count = elements.length;
  if (!count) return [];
  let scale = 1;
  for (;;) {
    const boxWidth = 150 * scale;
    const positions = elements.map((entry, index) => {
      const numberLength = String(entry.value ?? 0).length + (entry.type === "modifier" ? 1 : 0);
      const fontSize = Math.min((entry.type === "modifier" ? 48 : 82) * scale, boxWidth / numberLength);
      return { angle: -Math.PI / 2 + index * Math.PI * 2 / count,
        width: boxWidth, height: fontSize, fontSize };
    });
    const radiusLimit = Math.min(...positions.flatMap(position => [
      (width / 2 - position.width / 2 - 16) / Math.max(.001, Math.abs(Math.cos(position.angle))),
      (height / 2 - position.height / 2 - 16) / Math.max(.001, Math.abs(Math.sin(position.angle))),
    ]));
    const radius = Math.max(0, Math.min(radiusLimit, 150 + count * 14));
    positions.forEach(position => { position.x = Math.cos(position.angle) * radius; position.y = Math.sin(position.angle) * radius; });
    const overlap = positions.some((a, index) => positions.slice(index + 1).some(b =>
      Math.abs(a.x - b.x) < (a.width + b.width) / 2 + 12 * scale
        && Math.abs(a.y - b.y) < (a.height + b.height) / 2 + 12 * scale));
    if (!overlap) return positions;
    scale *= .9;
  }
}

const instances = new WeakMap();

export function createResultAnimation(stage) {
  if (!stage) return null;
  if (instances.has(stage)) return instances.get(stage);
  const timers = new Map();
  const cancelled = Symbol("cancelled");
  let generation = 0;
  let frameId = null;
const canvas =
  stage.querySelector("#dice-result-particleCanvas");

const ctx =
  canvas.getContext("2d");

const dieResultTop =
  stage.querySelector("#dice-result-dieResultTop");

const dieResultBottom =
  stage.querySelector("#dice-result-dieResultBottom");

const topValue =
  stage.querySelector("#dice-result-topValue");

const bottomValue =
  stage.querySelector("#dice-result-bottomValue");

const modifierResult = stage.querySelector("#dice-result-modifierResult");
const modifierValue = stage.querySelector("#dice-result-modifierValue");
const modifierLabel = stage.querySelector("#dice-result-modifierLabel");
const fusionNodes = [
  { node: dieResultTop, value: topValue },
  { node: dieResultBottom, value: bottomValue },
  { node: modifierResult, value: modifierValue, label: modifierLabel },
];
let fusionPositions = [];
let mergeStartedAt = null;
let mergeProgress = 0;

const resultSigil =
  stage.querySelector("#dice-result-resultSigil");

const resultValue =
  stage.querySelector("#dice-result-resultValue");

const fusionFlash =
  stage.querySelector("#dice-result-fusionFlash");

const largeRingText =
  stage.querySelector("#dice-result-largeRingText");

const smallRingText =
  stage.querySelector("#dice-result-smallRingText");








const particles = [];

let particleMode = "idle";
let particleRgb;
let particleCoolRgb;

let width = 0;
let height = 0;
let dpr = 1;

let running = false;


function rand(
  min,
  max
) {
  return (
    min +
    Math.random() *
    (max - min)
  );
}


function randInt(
  min,
  max
) {
  return (
    Math.floor(
      Math.random() *
      (max - min + 1)
    ) +
    min
  );
}


function lerp(
  a,
  b,
  amount
) {
  return (
    a +
    (b - a) *
    amount
  );
}


function wait(milliseconds, token) {
  return new Promise(resolve => {
    const id = setTimeout(() => {
      timers.delete(id);
      resolve();
    }, milliseconds);
    timers.set(id, resolve);
  }).then(() => {
    if (token !== generation) throw cancelled;
  });
}


function getVisibleD10(value) {
  const number = Number(value);
  if (!Number.isInteger(number) || number < 0 || number > 9) {
    throw new Error("Ungültiger sichtbarer d10-Wert.");
  }
  return number;
}


function getD10Value(
  visibleValue
) {
  return (
    visibleValue === 0
      ? 10
      : visibleValue
  );
}


function getRingVariant(
  die1,
  die2
) {

  if (
    die1 === 0 &&
    die2 === 0
  ) {
    return RING_VARIANTS.critSuccess;
  }

  if (
    die1 === 1 &&
    die2 === 1
  ) {
    return RING_VARIANTS.critFail;
  }

  return RING_VARIANTS.normal;
}


function setVariantText(
  variant
) {

  largeRingText.textContent =
    variant.outerText;

  smallRingText.textContent =
    variant.innerText;
}


function activateVariantTheme(
  variant
) {

  stage.classList.remove(
    "mode-normal",
    "mode-crit-success",
    "mode-crit-fail"
  );

  stage.classList.add(
    variant.modeClass
  );



  readParticleColors();
}


function activateNormalTheme() {

  stage.classList.remove(
    "mode-normal",
    "mode-crit-success",
    "mode-crit-fail"
  );

  stage.classList.add(
    "mode-normal"
  );



  readParticleColors();
}


function resizeCanvas() {

  positionStage();

  width =
    stage.clientWidth;

  height =
    stage.clientHeight;

  dpr =
    Math.min(
      window.devicePixelRatio || 1,
      2
    );

  canvas.width =
    Math.round(
      width * dpr
    );

  canvas.height =
    Math.round(
      height * dpr
    );

  ctx.setTransform(
    dpr,
    0,
    0,
    dpr,
    0,
    0
  );
}


window.addEventListener(
  "resize",
  resizeCanvas
);


function getParticleRgb(particle) {
  return particle.cool ? particleCoolRgb : particleRgb;
}


class Particle {

  constructor(
    index
  ) {

    this.index =
      index;

    this.side =
      index % 2 === 0
        ? -1
        : 1;

    this.x =
      rand(
        0,
        width
      );

    this.y =
      rand(
        0,
        height
      );

    const origin = fusionPositions[index % fusionPositions.length] || { x: 0, y: 0 };
    this.x = width / 2 + origin.x + rand(-60, 60);
    this.y = height / 2 + origin.y + rand(-35, 35);

    this.vx =
      rand(
        -0.10,
        0.10
      );

    this.vy =
      rand(
        -0.08,
        0.08
      );

    this.phase =
      rand(
        0,
        Math.PI * 2
      );

    this.phase2 =
      rand(
        0,
        Math.PI * 2
      );

    this.layer =
      randInt(
        0,
        2
      );

    if (
      this.layer === 0
    ) {
      this.radius =
        rand(
          0.6,
          1.5
        );
    }

    else if (
      this.layer === 1
    ) {
      this.radius =
        rand(
          1.4,
          2.8
        );
    }

    else {
      this.radius =
        rand(
          2.8,
          5.4
        );
    }

    this.alpha =
      rand(
        0.12,
        0.48
      );

    this.cool =
      Math.random() <
      0.17;

    this.gatherRadius =
      rand(
        40,
        100
      );

    this.resultRadius =
      rand(
        75,
        180
      );

    this.spiralRadius =
      rand(
        130,
        320
      );
  }


  updateIdle(
    time
  ) {

    this.x +=
      this.vx;

    this.y +=
      this.vy;

    this.x +=
      Math.sin(
        time * 0.00045 +
        this.phase
      ) *
      0.05;

    this.y +=
      Math.cos(
        time * 0.00038 +
        this.phase2
      ) *
      0.04;

    if (
      this.x < -25
    ) {
      this.x =
        width + 25;
    }

    if (
      this.x > width + 25
    ) {
      this.x =
        -25;
    }

    if (
      this.y < -25
    ) {
      this.y =
        height + 25;
    }

    if (
      this.y > height + 25
    ) {
      this.y =
        -25;
    }
  }


  updateGather(
    time
  ) {

    const origin = fusionPositions[this.index % fusionPositions.length] || { x: 0, y: 0 };
    const centerX = width / 2 + origin.x;
    const centerY = height / 2 + origin.y;

    const angle =
      this.phase +
      time *
      (
        0.00025 +
        this.layer *
        0.00006
      );

    const wobble =
      Math.sin(
        time * 0.0011 +
        this.phase2
      ) *
      17;

    const tx =
      centerX +
      Math.cos(angle) *
      (
        this.gatherRadius +
        wobble
      );

    const ty =
      centerY +
      Math.sin(angle) *
      (
        this.gatherRadius *
        0.48
      ) +
      Math.sin(
        this.phase * 3
      ) *
      8;

    this.x =
      lerp(
        this.x,
        tx,
        0.038
      );

    this.y =
      lerp(
        this.y,
        ty,
        0.038
      );
  }


  updateMerge(time) {
    const origin = fusionPositions[this.index % fusionPositions.length] || { x: 0, y: 0 };
    const remaining = 1 - mergeProgress;
    const angle = this.phase + time * .001;
    const tx = width / 2 + (origin.x + Math.cos(angle) * this.gatherRadius) * remaining;
    const ty = height / 2 + (origin.y + Math.sin(angle) * this.gatherRadius * .48) * remaining;
    this.x = lerp(this.x, tx, .22);
    this.y = lerp(this.y, ty, .22);
  }


  updateCollapse() {

    const centerX =
      width / 2;

    const centerY =
      height / 2;

    this.x =
      lerp(
        this.x,
        centerX,
        0.22
      );

    this.y =
      lerp(
        this.y,
        centerY,
        0.22
      );
  }


  updateResult(
    time
  ) {

    const centerX =
      width / 2;

    const centerY =
      height / 2;

    const direction =
      this.index % 2 === 0
        ? 1
        : -1;

    const angle =
      this.phase +
      time *
      0.00016 *
      direction;

    const pulse =
      Math.sin(
        time * 0.0008 +
        this.phase2
      ) *
      9;

    const tx =
      centerX +
      Math.cos(angle) *
      (
        this.resultRadius +
        pulse
      );

    const ty =
      centerY +
      Math.sin(angle) *
      (
        this.resultRadius +
        pulse
      ) *
      0.67;

    this.x =
      lerp(
        this.x,
        tx,
        0.026
      );

    this.y =
      lerp(
        this.y,
        ty,
        0.026
      );
  }


  update(
    time
  ) {

    switch (
      particleMode
    ) {

      case "gather":
        this.updateGather(
          time
        );
        break;

      case "merge":
        this.updateMerge(
          time
        );
        break;

      case "collapse":
        this.updateCollapse();
        break;

      case "result":
        this.updateResult(
          time
        );
        break;

      default:
        this.updateIdle(
          time
        );
    }
  }


  draw(
    time
  ) {

    const pulse =
      1 +
      Math.sin(
        time * 0.0013 +
        this.phase
      ) *
      0.13;

    const radius =
      this.radius *
      pulse;

    const rgb =
      getParticleRgb(
        this
      );

    let strength =
      this.alpha;

    if (
      particleMode ===
      "merge"
    ) {
      strength *=
        1.35;
    }

    if (
      particleMode ===
      "collapse"
    ) {
      strength *=
        1.7;
    }

    const gradient =
      ctx.createRadialGradient(
        this.x,
        this.y,
        0,
        this.x,
        this.y,
        radius * 4
      );

    gradient.addColorStop(
      0,
      `rgba(${rgb}, ${Math.min(
        strength,
        0.85
      )})`
    );

    gradient.addColorStop(
      0.28,
      `rgba(${rgb}, ${strength * 0.38})`
    );

    gradient.addColorStop(
      1,
      `rgba(${rgb}, 0)`
    );

    ctx.beginPath();

    ctx.arc(
      this.x,
      this.y,
      radius * 4,
      0,
      Math.PI * 2
    );

    ctx.fillStyle =
      gradient;

    ctx.fill();

    ctx.beginPath();

    ctx.arc(
      this.x,
      this.y,
      radius * 0.42,
      0,
      Math.PI * 2
    );

    ctx.fillStyle =
      `rgba(${rgb}, ${Math.min(
        strength + 0.18,
        0.88
      )})`;

    ctx.fill();
  }
}


function initParticles() {

  particles.length =
    0;

  for (
    let i = 0;
    i < PARTICLE_COUNT;
    i++
  ) {
    particles.push(
      new Particle(i)
    );
  }
}


function renderParticles(
  time
) {

  if (particleMode === "merge") {
    mergeStartedAt ??= time;
    mergeProgress = Math.min(1, (time - mergeStartedAt) / (TIMING.mergeDuration - 100));
  }
  ctx.clearRect(
    0,
    0,
    width,
    height
  );

  ctx.globalCompositeOperation =
    (
      particleMode === "merge" ||
      particleMode === "collapse"
    )
      ? "lighter"
      : "source-over";

  for (
    const particle
    of particles
  ) {

    particle.update(
      time
    );

    particle.draw(
      time
    );
  }

  ctx.globalCompositeOperation =
    "source-over";

  frameId = requestAnimationFrame(renderParticles);
}


function resetVisuals() {
  generation++;
  for (const [id, resolve] of timers) {
    clearTimeout(id);
    resolve();
  }
  timers.clear();
  running = false;
  cancelAnimationFrame(frameId);
  frameId = null;
  stage.classList.remove("is-active", "is-fading", "has-modifier");
  fusionPositions = [];
  mergeStartedAt = null;
  mergeProgress = 0;
  for (const entry of fusionNodes) {
    entry.node.classList.remove("visible", "merging", "vanish", "is-modifier");
    entry.value.textContent = "";
    if (entry.label) entry.label.textContent = "";
  }
  if (modifierResult) modifierResult.classList.remove("visible", "merging", "vanish");
  if (modifierValue) modifierValue.textContent = "";
  if (modifierLabel) modifierLabel.textContent = "";
  topValue.textContent = "";
  bottomValue.textContent = "";
  resultValue.textContent = "";
  resultValue.classList.remove("is-critical-text");
  setVariantText(RING_VARIANTS.normal);


  dieResultTop.classList.remove(
    "visible",
    "merging",
    "vanish"
  );

  dieResultBottom.classList.remove(
    "visible",
    "merging",
    "vanish"
  );

  resultSigil.classList.remove(
    "visible",
    "settled"
  );

  resultValue.classList.remove(
    "visible"
  );

  fusionFlash.classList.remove(
    "active"
  );

  activateNormalTheme();

  particleMode =
    "idle";

  for (
    const particle
    of particles
  ) {

    particle.gatherRadius =
      rand(
        40,
        100
      );

    particle.resultRadius =
      rand(
        75,
        180
      );

    particle.spiralRadius =
      rand(
        130,
        320
      );
  }

  void stage.offsetWidth;
}


function triggerFusionFlash() {

  fusionFlash.classList.remove(
    "active"
  );

  void fusionFlash.offsetWidth;

  fusionFlash.classList.add(
    "active"
  );
}

function scheduleResultFade() {
  const id = setTimeout(() => {
    timers.delete(id);
    stage.classList.add("is-fading");
    cancelAnimationFrame(frameId);
    frameId = null;
  }, TIMING.resultHold);
  timers.set(id, () => {});
}

stage.addEventListener("transitionend", event => {
  if (event.target === stage && event.propertyName === "opacity"
      && stage.classList.contains("is-fading")) {
    resetVisuals();
  }
});


function prepareFusionNodes(elements) {
  fusionPositions = layoutFusionElements(elements, width, height);
  return elements.map((element, index) => {
    if (!fusionNodes[index]) {
      const node = document.createElement("div"), value = document.createElement("span");
      const label = document.createElement("span"), trace = document.createElement("span");
      value.className = "die-value"; label.className = "modifier-label"; trace.className = "value-trace";
      node.append(value, label, trace); stage.append(node);
      fusionNodes.push({ node, value, label });
    }
    const entry = fusionNodes[index], position = fusionPositions[index];
    if (element.type === "modifier" && !entry.label) {
      entry.label = document.createElement("span");
      entry.label.className = "modifier-label";
      entry.node.append(entry.label);
    }
    entry.node.classList.add("die-result", "fusion-element");
    if (element.type === "modifier") entry.node.classList.add("is-modifier");
    entry.node.style.setProperty("--fusion-x", `${position.x}px`);
    entry.node.style.setProperty("--fusion-y", `${position.y}px`);
    entry.node.style.setProperty("--fusion-width", `${position.width}px`);
    entry.node.style.setProperty("--fusion-height", `${position.height}px`);
    entry.node.style.setProperty("--fusion-font-size", `${position.fontSize}px`);
    entry.value.textContent = element.type === "modifier"
      ? `${element.operator === "/" ? "/" : element.operator === "*" ? "×" : element.value >= 0 ? "+" : ""}${element.value}` : element.value;
    if (entry.label) entry.label.textContent = "";
    entry.node.title = "";
    return entry.node;
  });
}

async function playFusion(elements, options = {}) {
  if (running) return;
  if (!Array.isArray(elements) || !elements.length || elements.some(entry =>
    !["die", "modifier"].includes(entry.type) || !Number.isFinite(entry.value))) throw new Error("Invalid fusion elements.");
  elements = elements.filter(entry => entry.type !== "modifier" || entry.value !== 0);
  if (!elements.length) return;
  elements = elements.map(entry => entry.type === "die" ? {
    ...entry, rawValue: entry.rawValue ?? entry.value,
    value: entry.value === 0 ? 10 : entry.value,
    arithmeticValue: entry.arithmeticValue ?? (entry.value === 0 ? 10 : entry.value),
  } : entry);
  resetVisuals(); running = true;
  const token = generation;
  resizeCanvas();
  const result = options.total ?? elements.reduce((sum, entry) =>
    sum + (entry.type === "die" ? entry.arithmeticValue ?? entry.value : entry.value), 0);
  const skipFusion = elements.length === 1 && elements[0].type === "die"
    && result === elements[0].arithmeticValue;
  const nodes = skipFusion ? [] : prepareFusionNodes(elements);
  initParticles(); stage.classList.add("is-active");
  frameId = requestAnimationFrame(renderParticles);
  const dice = elements.filter(entry => entry.type === "die");
  const variant = options.critical === true && dice.length === 2
    ? getRingVariant(dice[0].rawValue, dice[1].rawValue) : RING_VARIANTS.normal;
  resultValue.textContent = result;
  if (options.probeKind === "skill" && variant !== RING_VARIANTS.normal) {
    const success = variant === RING_VARIANTS.critSuccess;
    const configured = stage.dataset?.[success ? "criticalSuccessText" : "criticalFailureText"];
    const text = Array.from(String(configured || "").trim()).slice(0, 64).join("")
      || (success ? "KRITISCHER ERFOLG" : "KRITISCHER FEHLSCHLAG");
    const fitted = layoutCriticalText(text, typeof ctx.measureText === "function" ? (line, size) => {
      ctx.font = `800 ${size}px Cinzel`;
      return ctx.measureText(line).width;
    } : undefined);
    resultValue.classList.add("is-critical-text");
    resultValue.style.setProperty("--critical-font-size", `${fitted.fontSize}px`);
    resultValue.textContent = fitted.text;
  }
  setVariantText(variant);
  try {
    if (skipFusion) {
      activateVariantTheme(variant);
    } else {
      particleMode = "gather";
      await wait(120, token); nodes[0].classList.add("visible");
      await wait(TIMING.numberAppearGap, token); nodes.forEach(node => node.classList.add("visible"));
      await wait(TIMING.numberHold, token);
      activateVariantTheme(variant); particleMode = "merge";
      nodes.forEach(node => node.classList.add("merging"));
      await wait(TIMING.mergeDuration - 100, token);
      nodes.forEach(node => node.classList.add("vanish")); particleMode = "collapse";
      await wait(220 + TIMING.flashDelay, token); triggerFusionFlash();
      await wait(TIMING.runeDelay, token);
    }
    resultSigil.classList.add("visible"); particleMode = "result";
    await wait(TIMING.resultDelay, token); resultValue.classList.add("visible"); scheduleResultFade();
    await wait(TIMING.settleDelay, token); resultSigil.classList.add("settled");
    return result;
  } catch (error) { if (error !== cancelled) throw error; }
  finally { if (token === generation) running = false; }
}

function playResultAnimation(die1, die2, percentileTotal = null, options = {}) {
  if (percentileTotal !== null) return playTotal(percentileTotal);
  const elements = [getVisibleD10(die1), getVisibleD10(die2)]
    .map(rawValue => ({ type: "die", rawValue, value: getD10Value(rawValue), arithmeticValue: getD10Value(rawValue) }));
  if (options.modifier !== undefined) elements.push({ type: "modifier", value: options.modifier, label: options.label });
  return playFusion(elements, { ...options, critical: options.critical !== false });
}

function playPercentileAnimation(tens, ones, total) {
  if (!Number.isInteger(tens) || tens < 0 || tens > 90 || tens % 10 !== 0
      || !Number.isInteger(total) || total < 1 || total > 100) {
    throw new Error("Ungültige Prozentwürfelwerte.");
  }
  getVisibleD10(ones);
  return playTotal(total);
}

function readParticleColors() {
  const style = getComputedStyle(stage);
  particleRgb = style.getPropertyValue("--particle-rgb").trim();
  particleCoolRgb = style.getPropertyValue("--particle-cool-rgb").trim();
}

function positionStage() {
  const pages = Array.from(document.querySelectorAll(".book-spread > .page"))
    .filter(page => page.getClientRects().length).map(page => page.getBoundingClientRect());
  let x = window.innerWidth / 2;
  let y = window.innerHeight / 2;
  if (pages.length === 2) {
    const [left, right] = pages;
    const horizontal = right.left >= left.right - 1;
    x = horizontal ? (left.right + right.left) / 2 : (left.left + left.right) / 2;
    const top = Math.max(0, Math.min(left.top, right.top));
    const bottom = Math.min(window.innerHeight, Math.max(left.bottom, right.bottom));
    y = horizontal ? (top + bottom) / 2 : (left.bottom + right.top) / 2;
  }
  const scale = Math.max(0.1, Math.min(1, (window.innerWidth - 24) / 720,
    (window.innerHeight - 24) / 720));
  const half = 360 * scale;
  x = Math.max(half, Math.min(window.innerWidth - half, x));
  y = Math.max(half, Math.min(window.innerHeight - half, y));
  stage.style.setProperty("--result-x", `${x}px`);
  stage.style.setProperty("--result-y", `${y}px`);
  stage.style.setProperty("--result-scale", String(scale));
}

function playTotal(total) {
  return playFusion([{ type: "die", value: total }], { total });
}

window.addEventListener("scroll", positionStage, { passive: true });
const observer = new ResizeObserver(resizeCanvas);
for (const page of document.querySelectorAll(".book-spread > .page")) observer.observe(page);
resizeCanvas();
activateNormalTheme();
setVariantText(RING_VARIANTS.normal);
const instance = { reset: resetVisuals, playResultAnimation, playPercentileAnimation, playTotal, playFusion };
instances.set(stage, instance);
return instance;
}
