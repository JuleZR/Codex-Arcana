import * as THREE from "../vendor/three.module.js";

let centerState = null;
let isInitialized = false;
let animationFrameId = 0;

const CENTER_PALETTE = {
  colorDeep: 0x12062d,
  colorMid: 0x3a1f8f,
  colorBright: 0x7f6cff,
  shellColor: 0xb59cff,
};

const noiseFunctions = `
  vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 permute(vec4 x) { return mod289(((x * 34.0) + 1.0) * x); }
  vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

  float snoise(vec3 v) {
    const vec2 C = vec2(1.0 / 6.0, 1.0 / 3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    vec3 i = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy;
    vec3 x3 = x0 - D.yyy;
    i = mod289(i);
    vec4 p = permute(permute(permute(
      i.z + vec4(0.0, i1.z, i2.z, 1.0))
      + i.y + vec4(0.0, i1.y, i2.y, 1.0))
      + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    float n_ = 0.142857142857;
    vec3 ns = n_ * D.wyz - D.xzx;
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    vec4 x = x_ * ns.x + ns.yyyy;
    vec4 y = y_ * ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);
    vec4 s0 = floor(b0) * 2.0 + 1.0;
    vec4 s1 = floor(b1) * 2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);
    vec4 norm = taylorInvSqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
    p0 *= norm.x;
    p1 *= norm.y;
    p2 *= norm.z;
    p3 *= norm.w;
    vec4 m = max(0.6 - vec4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
    m = m * m;
    return 42.0 * dot(m * m, vec4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
  }

  float fbm(vec3 p) {
    float total = 0.0;
    float amplitude = 0.5;
    float frequency = 1.0;
    for (int i = 0; i < 3; i++) {
      total += snoise(p * frequency) * amplitude;
      amplitude *= 0.5;
      frequency *= 2.0;
    }
    return total;
  }
`;

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

function buildRenderer(target) {
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.9;
  target.replaceChildren(renderer.domElement);
  return renderer;
}

function resizeState(state) {
  const width = Math.max(state.container.clientWidth, 1);
  const height = Math.max(state.container.clientHeight, 1);
  state.camera.aspect = width / height;
  state.camera.updateProjectionMatrix();
  state.renderer.setSize(width, height, false);
}

function createShellMaterial(side, color, opacity) {
  return new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: new THREE.Color(color) },
      uOpacity: { value: opacity },
    },
    vertexShader: `
      varying vec3 vNormal;
      varying vec3 vViewPosition;
      void main() {
        vNormal = normalize(normalMatrix * normal);
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        vViewPosition = -mvPosition.xyz;
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      varying vec3 vNormal;
      varying vec3 vViewPosition;
      uniform vec3 uColor;
      uniform float uOpacity;
      void main() {
        float fresnel = pow(1.0 - dot(normalize(vNormal), normalize(vViewPosition)), 2.5);
        gl_FragColor = vec4(uColor, fresnel * uOpacity);
      }
    `,
    transparent: true,
    blending: THREE.AdditiveBlending,
    side,
    depthWrite: false,
  });
}

function createPlasmaMaterial(palette, side) {
  return new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uScale: { value: 0.2 },
      uBrightness: { value: 0.98 },
      uThreshold: { value: 0.2 },
      uColorDeep: { value: new THREE.Color(palette.colorDeep) },
      uColorMid: { value: new THREE.Color(palette.colorMid) },
      uColorBright: { value: new THREE.Color(palette.colorBright) },
    },
    vertexShader: `
      varying vec3 vPosition;
      varying vec3 vNormal;
      varying vec3 vViewPosition;
      void main() {
        vPosition = position;
        vNormal = normalize(normalMatrix * normal);
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        vViewPosition = -mvPosition.xyz;
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      uniform float uTime;
      uniform float uScale;
      uniform float uBrightness;
      uniform float uThreshold;
      uniform vec3 uColorDeep;
      uniform vec3 uColorMid;
      uniform vec3 uColorBright;

      varying vec3 vPosition;
      varying vec3 vNormal;
      varying vec3 vViewPosition;

      ${noiseFunctions}

      void main() {
        vec3 p = vPosition * uScale;
        vec3 q = vec3(
          fbm(p + vec3(0.0, uTime * 0.05, 0.0)),
          fbm(p + vec3(5.2, 1.3, 2.8) + uTime * 0.05),
          fbm(p + vec3(2.2, 8.4, 0.5) - uTime * 0.02)
        );
        float density = fbm(p + 2.0 * q);
        float t = (density + 0.4) * 0.8;
        float alpha = smoothstep(uThreshold, 0.7, t);

        vec3 color = mix(uColorDeep, uColorMid, smoothstep(uThreshold, 0.5, t));
        color = mix(color, uColorBright, smoothstep(0.5, 0.8, t));
        color = mix(color, vec3(1.0), smoothstep(0.8, 1.0, t));

        float facing = dot(normalize(vNormal), normalize(vViewPosition));
        float depthFactor = (facing + 1.0) * 0.5;
        float finalAlpha = alpha * (0.02 + 0.98 * depthFactor);

        gl_FragColor = vec4(color * uBrightness, finalAlpha);
      }
    `,
    transparent: true,
    blending: THREE.AdditiveBlending,
    side,
    depthWrite: false,
  });
}

function createParticleSystem(color) {
  const count = 180;
  const positions = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const radius = 0.86;

  for (let index = 0; index < count; index += 1) {
    const r = radius * Math.cbrt(Math.random());
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    positions[index * 3] = r * Math.sin(phi) * Math.cos(theta);
    positions[index * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    positions[index * 3 + 2] = r * Math.cos(phi);
    sizes[index] = Math.random();
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));

  const material = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uColor: { value: new THREE.Color(color) },
    },
    vertexShader: `
      uniform float uTime;
      attribute float aSize;
      varying float vAlpha;

      void main() {
        vec3 pos = position;
        pos.y += sin(uTime * 0.2 + pos.x) * 0.02;
        pos.x += cos(uTime * 0.15 + pos.z) * 0.02;

        vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
        gl_Position = projectionMatrix * mvPosition;

        float baseSize = 7.0 * aSize + 3.0;
        gl_PointSize = baseSize * (1.0 / -mvPosition.z);
        vAlpha = 0.8 + 0.2 * sin(uTime + aSize * 10.0);
      }
    `,
    fragmentShader: `
      uniform vec3 uColor;
      varying float vAlpha;

      void main() {
        vec2 uv = gl_PointCoord - vec2(0.5);
        float dist = length(uv);
        if (dist > 0.5) discard;

        float glow = 1.0 - (dist * 2.0);
        glow = pow(glow, 1.8);
        gl_FragColor = vec4(uColor, glow * vAlpha);
      }
    `,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const particles = new THREE.Points(geometry, material);
  particles.renderOrder = 1;
  return particles;
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

function createOrbLayers(palette) {
  const orbBackGroup = new THREE.Group();
  const orbFrontGroup = new THREE.Group();
  const shellGeometry = new THREE.SphereGeometry(1.0, 64, 64);
  const plasmaGeometry = new THREE.SphereGeometry(0.998, 96, 96);

  const shellBack = new THREE.Mesh(
    shellGeometry,
    createShellMaterial(THREE.BackSide, 0x08031a, 0.26),
  );
  shellBack.renderOrder = 0;

  const plasmaBackMaterial = createPlasmaMaterial(palette, THREE.BackSide);
  const plasmaBack = new THREE.Mesh(plasmaGeometry, plasmaBackMaterial);
  plasmaBack.renderOrder = 1;

  const particles = createParticleSystem(palette.colorBright);
  const orbLight = new THREE.PointLight(palette.colorBright, 1.4, 10);
  orbLight.position.set(0, 0, 0);

  orbBackGroup.add(shellBack, plasmaBack, particles, orbLight);

  const plasmaFrontMaterial = createPlasmaMaterial(palette, THREE.FrontSide);
  const plasmaFront = new THREE.Mesh(plasmaGeometry, plasmaFrontMaterial);
  plasmaFront.renderOrder = 3;

  const shellFront = new THREE.Mesh(
    shellGeometry,
    createShellMaterial(THREE.FrontSide, palette.shellColor, 0.42),
  );
  shellFront.renderOrder = 4;

  orbFrontGroup.add(plasmaFront, shellFront);

  return {
    orbBackGroup,
    orbFrontGroup,
    animatables: {
      plasmaBackMaterial,
      plasmaFrontMaterial,
      particleMaterial: particles.material,
      plasmaBackMesh: plasmaBack,
      plasmaFrontMesh: plasmaFront,
    },
  };
}

function createCenterGemGroup(geometry, legacyMaterial) {
  const bodyMesh = new THREE.Mesh(geometry, createCenterMaterial(legacyMaterial));
  bodyMesh.renderOrder = 2;

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
  reflectiveShell.renderOrder = 2;

  const glowMesh = new THREE.Mesh(geometry, createCenterGlowMaterial());
  glowMesh.renderOrder = 2;

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
  innerSpark.renderOrder = 2.2;

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
  facetFlash.renderOrder = 2.25;

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
  fireShell.renderOrder = 2;

  glowMesh.scale.setScalar(1.08);
  fireShell.scale.setScalar(1.04);
  reflectiveShell.scale.setScalar(0.992);
  innerSpark.scale.set(0.22, 0.3, 0.22);
  innerSpark.position.set(0.12, -0.02, 0.14);
  facetFlash.scale.set(0.58, 0.72, 0.58);
  facetFlash.position.set(0.08, 0.06, 0.08);
  facetFlash.rotation.set(0.08, 0.44, -0.14);

  const scaleFactor = 0.66 / Math.max(geometry.boundingSphere?.radius || 1, 0.0001);
  const group = new THREE.Group();
  group.add(glowMesh, fireShell, bodyMesh, reflectiveShell, facetFlash, innerSpark);
  group.scale.setScalar(scaleFactor);
  group.position.set(0, 0, 0);
  group.rotation.x = -0.18;
  return group;
}

async function createCenterGem(scene) {
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
    const gem = createCenterGemGroup(geometry, legacyMaterial);
    scene.add(gem);
    centerState.gem = gem;
  } catch (_error) {
    centerState.container?.setAttribute("data-gem-failed", "1");
  }
}

function updateOrb(state, elapsedTime) {
  const { orbAnimatables, orbBackGroup, orbFrontGroup } = state;
  if (!orbAnimatables || !orbBackGroup || !orbFrontGroup) {
    return;
  }

  orbAnimatables.plasmaBackMaterial.uniforms.uTime.value = elapsedTime * 1.2;
  orbAnimatables.plasmaFrontMaterial.uniforms.uTime.value = elapsedTime * 1.2;
  orbAnimatables.particleMaterial.uniforms.uTime.value = elapsedTime;
  orbAnimatables.plasmaBackMesh.rotation.y = elapsedTime * 0.08;
  orbAnimatables.plasmaFrontMesh.rotation.y = elapsedTime * 0.08;

  const orbitX = -0.22 + Math.sin(elapsedTime * 0.45) * 0.04;
  const orbitY = elapsedTime * 0.12;
  orbBackGroup.rotation.set(orbitX, orbitY, 0);
  orbFrontGroup.rotation.set(orbitX, orbitY, 0);
}

function updateGem(gem, elapsedTime) {
  if (!gem) {
    return;
  }
  gem.rotation.y = elapsedTime * 0.64;
  gem.rotation.x = -0.18 + Math.sin(elapsedTime * 0.9) * 0.03;
}

function renderLoop() {
  animationFrameId = window.requestAnimationFrame(renderLoop);
  if (!centerState) {
    return;
  }

  resizeState(centerState);
  const elapsedTime = centerState.clock.getElapsedTime();
  updateOrb(centerState, elapsedTime);
  updateGem(centerState.gem, elapsedTime);
  centerState.renderer.render(centerState.scene, centerState.camera);
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
  const camera = new THREE.PerspectiveCamera(75, 1, 0.1, 100);
  camera.position.z = 2.52;
  const renderer = buildRenderer(container);

  addCenterLights(scene);

  const { orbBackGroup, orbFrontGroup, animatables } = createOrbLayers(CENTER_PALETTE);
  orbBackGroup.scale.setScalar(1.14);
  orbFrontGroup.scale.setScalar(1.14);
  scene.add(orbBackGroup, orbFrontGroup);

  centerState = {
    container,
    scene,
    camera,
    renderer,
    orbBackGroup,
    orbFrontGroup,
    orbAnimatables: animatables,
    gem: null,
    clock: new THREE.Clock(),
  };

  createCenterGem(scene);
  resizeState(centerState);
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

export function decorateRadialMenuItems() {
  // The action items are now rendered as DOM cards inside the central plasma sphere.
}
