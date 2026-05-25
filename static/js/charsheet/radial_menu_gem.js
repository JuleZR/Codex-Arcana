import * as THREE from "../vendor/three.module.js";
import { ConvexBufferGeometry } from "../vendor/ConvexGeometry.js";

let centerState = null;
let isInitialized = false;
let animationFrameId = 0;
const itemStates = [];
let itemGeometry = null;

function buildGeometryFromLegacyData(legacyGeometryData) {
  const vertexSource = Array.isArray(legacyGeometryData?.vertices) ? legacyGeometryData.vertices : [];
  const normalSource = Array.isArray(legacyGeometryData?.normals) ? legacyGeometryData.normals : [];
  const faceSource = Array.isArray(legacyGeometryData?.faces) ? legacyGeometryData.faces : [];
  const positions = [];
  const normals = [];
  let cursor = 0;

  while (cursor < faceSource.length) {
    const type = faceSource[cursor++];
    const isQuad = (type & 1) === 1;
    const hasMaterial = (type & 2) === 2;
    const hasFaceUv = (type & 4) === 4;
    const hasFaceVertexUv = (type & 8) === 8;
    const hasFaceNormal = (type & 16) === 16;
    const hasFaceVertexNormal = (type & 32) === 32;
    const hasFaceColor = (type & 64) === 64;
    const hasFaceVertexColor = (type & 128) === 128;
    const vertexCount = isQuad ? 4 : 3;
    const vertexIndices = [];

    for (let index = 0; index < vertexCount; index += 1) {
      vertexIndices.push(faceSource[cursor++]);
    }
    if (hasMaterial) cursor += 1;
    if (hasFaceUv) cursor += 1;
    if (hasFaceVertexUv) cursor += vertexCount;
    if (hasFaceNormal) cursor += 1;

    let vertexNormalIndices = [];
    if (hasFaceVertexNormal) {
      vertexNormalIndices = faceSource.slice(cursor, cursor + vertexCount);
      cursor += vertexCount;
    }
    if (hasFaceColor) cursor += 1;
    if (hasFaceVertexColor) cursor += vertexCount;

    const triangles = isQuad ? [[0, 1, 3], [1, 2, 3]] : [[0, 1, 2]];
    triangles.forEach((triangle) => {
      triangle.forEach((pointIndex) => {
        const vertexIndex = vertexIndices[pointIndex] * 3;
        positions.push(
          vertexSource[vertexIndex] || 0,
          vertexSource[vertexIndex + 1] || 0,
          vertexSource[vertexIndex + 2] || 0,
        );
        if (vertexNormalIndices.length) {
          const normalIndex = (vertexNormalIndices[pointIndex] || 0) * 3;
          normals.push(
            normalSource[normalIndex] || 0,
            normalSource[normalIndex + 1] || 0,
            normalSource[normalIndex + 2] || 1,
          );
        }
      });
    });
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  if (normals.length === positions.length) {
    geometry.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  } else {
    geometry.computeVertexNormals();
  }
  geometry.computeBoundingBox();
  geometry.center();
  geometry.computeBoundingSphere();
  return geometry;
}

function buildRenderer(target, options = {}) {
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, ...options });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  target.replaceChildren(renderer.domElement);
  return renderer;
}

function createItemGeometry() {
  if (itemGeometry) {
    return itemGeometry;
  }
  const points = [];
  const NUMSIDES = 10;
  const makePoint = (i, radius, y) => {
    const angle = i * 2 * Math.PI / NUMSIDES;
    return new THREE.Vector3(radius * Math.cos(angle), y, radius * Math.sin(angle));
  };

  for (let index = 0; index < NUMSIDES; index += 1) {
    points.push(makePoint(index, 2, 2));
    points.push(makePoint(index + 0.5, 2.5, 1.5));
    points.push(makePoint(index, 3, 1));
    points.push(makePoint(index + 0.5, 2, -2));
    points.push(makePoint(index, 1, -4));
  }
  points.push(makePoint(0, 0, -6));

  itemGeometry = new ConvexBufferGeometry(points);
  itemGeometry.computeVertexNormals();
  itemGeometry.computeVertexNormals();
  return itemGeometry;
}

function resizeState(state) {
  if (!(state.container instanceof HTMLElement)) {
    return;
  }
  const width = Math.max(state.container.clientWidth, 1);
  const height = Math.max(state.container.clientHeight, 1);
  state.camera.aspect = width / height;
  state.camera.updateProjectionMatrix();
  state.renderer.setSize(width, height, false);
}

function addCenterLights(scene) {
  const shadowLight = new THREE.DirectionalLight(0xffffff, 0.32);
  shadowLight.position.set(2, 10, 1);
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.18);
  const ambientLight2 = new THREE.AmbientLight(0x2d124b, 0.42);
  const light1 = new THREE.PointLight(0xa86cff, 1.45, 100);
  light1.position.set(30, 0, 10);
  const light2 = new THREE.PointLight(0x5b63ff, 1.1, 100);
  light2.position.set(-40, 0, 20);
  const light3 = new THREE.PointLight(0x3f0f86, 1.2, 100);
  light3.position.set(0, -5, 5);
  const light4 = new THREE.PointLight(0xffffff, 0.58, 100);
  light4.position.set(-1, 1, 3);
  const light5 = new THREE.PointLight(0x1a063d, 0.62, 100);
  light5.position.set(-5, -2, 5);
  const light6 = new THREE.PointLight(0xf6d7ff, 0.5, 100);
  light6.position.set(2, -1, 2.2);
  scene.add(shadowLight, ambientLight, ambientLight2, light1, light2, light3, light4, light5, light6);
}

function addItemLights(scene, color, accent) {
  const lightA = new THREE.DirectionalLight(0xffffff, 1);
  lightA.position.set(15, 10, 0);
  const lightB = new THREE.DirectionalLight(0x80bfff, 1);
  lightB.position.set(-10, -16, -10);
  const ambient = new THREE.AmbientLight(0x001050);
  const colorFill = new THREE.PointLight(color, 1.05, 30);
  colorFill.position.set(0, 0, 8);
  const accentLight = new THREE.PointLight(accent, 0.72, 24);
  accentLight.position.set(-2.4, 1.6, 5.5);
  scene.add(lightA, lightB, ambient, colorFill, accentLight);
}

function createCenterMaterial(legacyMaterial) {
  const shininess = Number.isFinite(legacyMaterial?.shininess) ? legacyMaterial.shininess : 50;
  return new THREE.MeshPhongMaterial({
    color: 0x2d1149,
    specular: 0xfff8ff,
    emissive: 0x090114,
    shininess: shininess + 180,
    transparent: true,
    opacity: 0.56,
    side: THREE.FrontSide,
    flatShading: true,
  });
}

function createCenterGlowMaterial() {
  return new THREE.MeshPhongMaterial({
    color: 0x6d52d8,
    emissive: 0x30105d,
    specular: 0xffffff,
    shininess: 240,
    transparent: true,
    opacity: 0.2,
    side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    flatShading: true,
  });
}

function renderLoop() {
  animationFrameId = window.requestAnimationFrame(renderLoop);
  if (centerState?.gem) {
    centerState.gem.rotation.y += 0.0032;
    centerState.gem.rotation.x = -0.18 + Math.sin(performance.now() * 0.0009) * 0.03;
  }
  if (centerState) {
    centerState.renderer.render(centerState.scene, centerState.camera);
  }

  for (let index = itemStates.length - 1; index >= 0; index -= 1) {
    const state = itemStates[index];
    if (!state.container.isConnected) {
      state.renderer.dispose();
      itemStates.splice(index, 1);
      continue;
    }
    resizeState(state);
    state.group.rotation.y += 0.0044;
    state.renderer.render(state.scene, state.camera);
  }
}

async function createCenterGem() {
  if (!centerState) {
    return;
  }
  try {
    const response = await fetch("/static/js/vendor/gem1.json", { credentials: "same-origin" });
    if (!response.ok) {
      throw new Error("gem fetch failed");
    }
    const legacyScene = await response.json();
    const legacyMesh = legacyScene?.object?.children?.[0];
    const legacyGeometry = legacyScene?.geometries?.find((entry) => entry.uuid === legacyMesh?.geometry);
    const legacyMaterial = legacyScene?.materials?.find((entry) => entry.uuid === legacyMesh?.material);
    if (!legacyMesh || !legacyGeometry?.data) {
      throw new Error("gem payload invalid");
    }

    const geometry = buildGeometryFromLegacyData(legacyGeometry.data);
    const bodyMesh = new THREE.Mesh(geometry, createCenterMaterial(legacyMaterial));
    const reflectiveShell = new THREE.Mesh(
      geometry,
      new THREE.MeshPhongMaterial({
        color: 0x5f2aa1,
        specular: 0xffffff,
        emissive: 0x120223,
        shininess: 320,
        transparent: false,
        opacity: 1,
        side: THREE.FrontSide,
        polygonOffset: true,
        polygonOffsetFactor: -1,
        polygonOffsetUnits: -1,
        flatShading: true,
      }),
    );
    const glowMesh = new THREE.Mesh(geometry, createCenterGlowMaterial());
    const innerSpark = new THREE.Mesh(
      geometry,
      new THREE.MeshPhongMaterial({
        color: 0xffffff,
        emissive: 0x6f3bd6,
        specular: 0xffffff,
        shininess: 320,
        transparent: true,
        opacity: 0.18,
        flatShading: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    );
    const facetFlash = new THREE.Mesh(
      geometry,
      new THREE.MeshPhongMaterial({
        color: 0xfbf6ff,
        emissive: 0x6d4ae0,
        specular: 0xffffff,
        shininess: 360,
        transparent: true,
        opacity: 0.08,
        flatShading: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    );

    const fireShell = new THREE.Mesh(
      geometry,
      new THREE.MeshPhongMaterial({
        color: 0x5f34c0,
        emissive: 0x2f0f67,
        specular: 0xffffff,
        shininess: 280,
        transparent: true,
        opacity: 0.2,
        side: THREE.BackSide,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        flatShading: true,
      }),
    );

    glowMesh.scale.setScalar(1.08);
    fireShell.scale.setScalar(1.04);
    reflectiveShell.scale.setScalar(0.992);
    innerSpark.scale.set(0.22, 0.3, 0.22);
    innerSpark.position.set(0.12, -0.02, 0.14);
    facetFlash.scale.set(0.58, 0.72, 0.58);
    facetFlash.position.set(0.08, 0.06, 0.08);
    facetFlash.rotation.set(0.08, 0.44, -0.14);

    const group = new THREE.Group();
    group.add(glowMesh, fireShell, bodyMesh, reflectiveShell, facetFlash, innerSpark);
    group.position.z = -2;
    group.scale.setScalar(14.7);
    group.rotation.x = -0.18;
    centerState.scene.add(group);
    centerState.gem = group;
  } catch (_error) {
    centerState.container?.setAttribute("data-gem-failed", "1");
  }
}

export function initRadialMenuGem() {
  const container = document.getElementById("radialMenuGemWorld");
  if (!(container instanceof HTMLElement)) {
    return;
  }
  if (isInitialized && centerState) {
    resizeState(centerState);
    return;
  }

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(75, 1, 0.1, 1000);
  camera.position.z = 4.75;
  const renderer = buildRenderer(container);
  centerState = {
    container,
    scene,
    camera,
    renderer,
    gem: null,
  };

  addCenterLights(scene);
  resizeState(centerState);
  createCenterGem();
  window.addEventListener("resize", () => {
    if (centerState) {
      resizeState(centerState);
    }
  });

  if (!animationFrameId) {
    renderLoop();
  }
  isInitialized = true;
}

function createItemGemGroup({ colorHex, accentHex, fireHex }) {
  const geometry = createItemGeometry();
  const group = new THREE.Group();
  const whiteFlashHex = 0xfdfcff;

  const backMesh = new THREE.Mesh(
    geometry,
    new THREE.MeshPhysicalMaterial({
      color: colorHex,
      side: THREE.BackSide,
      flatShading: true,
      transparent: true,
      opacity: 0.38,
      roughness: 0.02,
      metalness: 0,
      clearcoat: 0.42,
      clearcoatRoughness: 0.08,
    }),
  );

  const frontMesh = new THREE.Mesh(
    geometry,
    new THREE.MeshPhysicalMaterial({
      color: colorHex,
      side: THREE.FrontSide,
      flatShading: true,
      transparent: true,
      opacity: 0.48,
      roughness: 0.01,
      metalness: 0,
      clearcoat: 1,
      clearcoatRoughness: 0.02,
      reflectivity: 1,
    }),
  );

  const glowMesh = new THREE.Mesh(
    geometry,
    new THREE.MeshPhongMaterial({
      color: accentHex,
      emissive: fireHex,
      specular: 0xffffff,
      shininess: 220,
      transparent: true,
      opacity: 0.18,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      flatShading: true,
    }),
  );

  const fireCore = new THREE.Mesh(
    geometry,
    new THREE.MeshPhongMaterial({
      color: accentHex,
      emissive: fireHex,
      specular: 0xffffff,
      shininess: 280,
      side: THREE.FrontSide,
      flatShading: true,
      transparent: true,
      opacity: 0.3,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );

  const fireSparkA = new THREE.Mesh(
    geometry,
    new THREE.MeshPhongMaterial({
      color: whiteFlashHex,
      emissive: accentHex,
      specular: 0xffffff,
      shininess: 340,
      side: THREE.FrontSide,
      flatShading: true,
      transparent: true,
      opacity: 0.14,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );

  const fireSparkB = new THREE.Mesh(
    geometry,
    new THREE.MeshPhongMaterial({
      color: whiteFlashHex,
      emissive: accentHex,
      specular: 0xffffff,
      shininess: 360,
      side: THREE.FrontSide,
      flatShading: true,
      transparent: true,
      opacity: 0.08,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );

  const fireShell = new THREE.Mesh(
    geometry,
    new THREE.MeshPhongMaterial({
      color: accentHex,
      emissive: fireHex,
      specular: 0xffffff,
      shininess: 260,
      side: THREE.BackSide,
      flatShading: true,
      transparent: true,
      opacity: 0.22,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );

  const reflectiveShell = new THREE.Mesh(
    geometry,
    new THREE.MeshPhongMaterial({
      color: colorHex,
      specular: 0xffffff,
      emissive: 0x090914,
      shininess: 320,
      transparent: false,
      opacity: 1,
      side: THREE.FrontSide,
      polygonOffset: true,
      polygonOffsetFactor: -1,
      polygonOffsetUnits: -1,
      flatShading: true,
    }),
  );

  glowMesh.scale.setScalar(1.08);
  backMesh.scale.setScalar(1.002);
  frontMesh.scale.setScalar(0.998);
  fireShell.scale.setScalar(1.05);
  reflectiveShell.scale.setScalar(0.992);
  fireCore.scale.set(0.78, 0.78, 0.78);
  fireCore.position.set(0.02, 0.06, 0.04);
  fireSparkA.scale.set(0.42, 0.52, 0.42);
  fireSparkA.position.set(0.14, 0.26, 0.14);
  fireSparkA.rotation.set(0.08, 0.42, -0.14);
  fireSparkB.scale.set(0.3, 0.44, 0.3);
  fireSparkB.position.set(-0.08, -0.04, 0.16);
  fireSparkB.rotation.set(-0.04, 0.76, 0.12);
  group.add(glowMesh, fireShell, backMesh, frontMesh, reflectiveShell, fireCore, fireSparkA, fireSparkB);
  return group;
}

export function decorateRadialMenuItems() {
  const palette = [
    { colorHex: 0x19b978, accentHex: 0xcaffea, fireHex: 0x5df2b2 }, // emerald
    { colorHex: 0xb3122b, accentHex: 0xffc0cc, fireHex: 0xff355e }, // ruby
    { colorHex: 0x123aa4, accentHex: 0xb8c9ff, fireHex: 0x3f74ff }, // sapphire
    { colorHex: 0xc89210, accentHex: 0xffefb0, fireHex: 0xffc93a }, // citrine
    { colorHex: 0xd56a18, accentHex: 0xffd1a8, fireHex: 0xff9a2f }, // orange sapphire
  ];
  const targets = Array.from(document.querySelectorAll(".charsheet-radial-menu__item_gem"));
  targets.forEach((target, index) => {
    if (!(target instanceof HTMLElement) || target.dataset.radialGemBound === "1") {
      return;
    }
    target.dataset.radialGemBound = "1";
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, 1, 0.1, 100);
    camera.position.set(-3, 2.5, 5);
    camera.lookAt(new THREE.Vector3(0, 0, 0));
    const renderer = buildRenderer(target, { logarithmicDepthBuffer: true });
    const paletteEntry = palette[index % palette.length];
    const group = createItemGemGroup(paletteEntry);
    group.scale.setScalar(0.72);
    group.rotation.y = index * 0.32;
    scene.add(group);
    addItemLights(scene, paletteEntry.colorHex, paletteEntry.fireHex);

    const state = {
      container: target,
      renderer,
      camera,
      scene,
      group,
      offset: index * 0.7,
    };
    itemStates.push(state);
    resizeState(state);
  });
}
