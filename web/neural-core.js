import * as THREE from "/vendor/three.module.min.js";

const QUALITY = {
  eco: { nodes: 460, links: 210, pulses: 48, particles: 90, pixelRatio: 1 },
  balanced: { nodes: 1180, links: 520, pulses: 116, particles: 180, pixelRatio: 1.45 },
  cinematic: { nodes: 2400, links: 1080, pulses: 240, particles: 340, pixelRatio: 2 },
};

const STATE = {
  dormant: { colour: 0xffb13b, activity: 0.72 },
  listening: { colour: 0xffd66b, activity: 2.1 },
  understanding: { colour: 0xffedb0, activity: 2.5 },
  planning: { colour: 0xffc34f, activity: 2.8 },
  executing: { colour: 0xff8a31, activity: 3.2 },
  speaking: { colour: 0xffd889, activity: 2.25 },
  approval: { colour: 0xff8a31, activity: 1.4 },
  completed: { colour: 0x63e6ad, activity: 1.1 },
  warning: { colour: 0xff9f43, activity: 1.7 },
  critical: { colour: 0xff5369, activity: 2.2 },
};

const CLUSTERS = [
  { name: "memory", label: "MEMORY LATTICE", position: [-2.55, 1.35, 0.2], colour: 0xffc45d },
  { name: "reasoning", label: "REASONING ENGINE", position: [2.55, 1.32, -0.1], colour: 0xff9d3f },
  { name: "knowledge", label: "KNOWLEDGE GRAPH", position: [-2.75, -1.35, -0.3], colour: 0xffdc76 },
  { name: "agents", label: "AGENT CONSTELLATION", position: [0, 2.72, -0.4], colour: 0x6ee7ff },
  { name: "system", label: "SYSTEM FABRIC", position: [2.75, -1.28, 0.15], colour: 0x54cce9 },
  { name: "perception", label: "PERCEPTION ARRAY", position: [0.2, -2.72, -0.25], colour: 0xffbd4a },
];

export function createAurisNeuralCore(canvas) {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
    });
  } catch (_error) {
    canvas.dataset.renderer = "unavailable";
    return inertCore();
  }

  canvas.dataset.renderer = "three-webgl";
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setClearColor(0x020507, 0);
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x030608, 0.048);

  const camera = new THREE.PerspectiveCamera(43, 1, 0.1, 90);
  camera.position.set(0, 0.12, 9.6);
  const root = new THREE.Group();
  root.rotation.x = -0.06;
  scene.add(root);

  scene.add(new THREE.AmbientLight(0x4db8cb, 0.23));
  const amberLight = new THREE.PointLight(0xffaa38, 30, 18, 2);
  amberLight.position.set(0.5, 1.25, 4.4);
  const cyanLight = new THREE.PointLight(0x58d7ef, 11, 15, 2);
  cyanLight.position.set(-3.3, -1.7, 3.2);
  scene.add(amberLight, cyanLight);

  const coreMaterial = new THREE.MeshPhysicalMaterial({
    color: STATE.dormant.colour,
    emissive: STATE.dormant.colour,
    emissiveIntensity: 1.5,
    roughness: 0.22,
    metalness: 0.34,
    transparent: true,
    opacity: 0.82,
    wireframe: true,
  });
  const core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.74, 3), coreMaterial);
  const innerMaterial = new THREE.MeshBasicMaterial({
    color: 0xfff1bd,
    transparent: true,
    opacity: 0.35,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const innerCore = new THREE.Mesh(new THREE.IcosahedronGeometry(0.31, 2), innerMaterial);
  const shell = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.98, 2),
    new THREE.MeshBasicMaterial({
      color: 0xffb649,
      transparent: true,
      opacity: 0.07,
      wireframe: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  root.add(core, innerCore, shell);

  const rings = [];
  [1.08, 1.3, 1.58, 1.92, 2.28, 2.7, 3.14, 3.62, 4.08].forEach((radius, index) => {
    const isStructure = index === 2 || index === 6;
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius, 0.006 + (index % 3) * 0.003, 4, 128),
      new THREE.MeshBasicMaterial({
        color: isStructure ? 0x58d7ef : index % 2 ? 0xff9e35 : 0xffd067,
        transparent: true,
        opacity: isStructure ? 0.2 : 0.16,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    ring.rotation.set(
      index % 2 ? Math.PI / 2.35 : Math.PI / 3.05,
      index * 0.39,
      index * 0.19,
    );
    ring.userData = {
      direction: index % 2 ? -1 : 1,
      speed: 0.045 + index * 0.009,
    };
    rings.push(ring);
    root.add(ring);
  });

  const cages = [2.25, 2.92, 3.55].map((radius, index) => {
    const cage = new THREE.Mesh(
      new THREE.SphereGeometry(radius, 28 + index * 4, 16 + index * 2),
      new THREE.MeshBasicMaterial({
        color: index === 1 ? 0x58d7ef : 0xffb447,
        transparent: true,
        opacity: index === 1 ? 0.055 : 0.07,
        wireframe: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    cage.scale.y = 0.9 + index * 0.025;
    cage.rotation.set(index * 0.22, index * 0.31, index * 0.14);
    root.add(cage);
    return cage;
  });

  const plinthRings = [1.55, 2.15, 2.78, 3.42].map((radius, index) => {
    const plinth = new THREE.Mesh(
      new THREE.TorusGeometry(radius, index === 1 ? 0.025 : 0.012, 6, 144),
      new THREE.MeshBasicMaterial({
        color: index === 2 ? 0x58d7ef : 0xffb447,
        transparent: true,
        opacity: 0.16 - index * 0.018,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    plinth.rotation.x = Math.PI / 2;
    plinth.rotation.z = index * 0.09;
    plinth.position.y = (index - 1.5) * 0.08;
    root.add(plinth);
    return plinth;
  });

  const beamGeometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-0.08, -4.35, 0), new THREE.Vector3(-0.08, 4.35, 0),
    new THREE.Vector3(0, -4.65, 0), new THREE.Vector3(0, 4.65, 0),
    new THREE.Vector3(0.08, -4.35, 0), new THREE.Vector3(0.08, 4.35, 0),
  ]);
  const processingSpine = new THREE.LineSegments(
    beamGeometry,
    new THREE.LineBasicMaterial({
      color: 0xffc75a,
      transparent: true,
      opacity: 0.2,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  root.add(processingSpine);

  const beamMarkers = Array.from({ length: 7 }, (_, index) => {
    const marker = new THREE.Mesh(
      new THREE.OctahedronGeometry(index === 3 ? 0.085 : 0.052, 0),
      new THREE.MeshBasicMaterial({
        color: index % 3 === 0 ? 0x65ddf1 : 0xffd56c,
        transparent: true,
        opacity: 0.78,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    marker.userData.phase = index / 7;
    marker.position.x = (index % 3 - 1) * 0.08;
    marker.position.y = (marker.userData.phase - 0.5) * 8.2;
    root.add(marker);
    return marker;
  });

  const axisGeometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, -4.8, 0),
    new THREE.Vector3(0, 4.8, 0),
  ]);
  const axis = new THREE.Line(
    axisGeometry,
    new THREE.LineDashedMaterial({
      color: 0x61d9ef,
      dashSize: 0.12,
      gapSize: 0.15,
      transparent: true,
      opacity: 0.28,
    }),
  );
  axis.computeLineDistances();
  root.add(axis);

  const axisMarkers = new THREE.Group();
  [-3.75, -2.25, 2.25, 3.75].forEach((y) => {
    const marker = new THREE.Mesh(
      new THREE.TorusGeometry(0.11, 0.008, 4, 32),
      new THREE.MeshBasicMaterial({ color: 0x63d8ef, transparent: true, opacity: 0.45 }),
    );
    marker.rotation.x = Math.PI / 2;
    marker.position.y = y;
    axisMarkers.add(marker);
  });
  root.add(axisMarkers);

  const scanMaterial = new THREE.MeshBasicMaterial({
    color: 0xffb447,
    transparent: true,
    opacity: 0.075,
    side: THREE.DoubleSide,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const scanPlane = new THREE.Mesh(new THREE.CircleGeometry(4.35, 96), scanMaterial);
  scanPlane.rotation.x = Math.PI / 2;
  root.add(scanPlane);

  const waves = [0, 1, 2].map((index) => {
    const wave = new THREE.Mesh(
      new THREE.SphereGeometry(1, 24, 12),
      new THREE.MeshBasicMaterial({
        color: index === 1 ? 0x64d7ed : 0xffb343,
        transparent: true,
        opacity: 0,
        wireframe: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    wave.userData.phase = index / 3;
    root.add(wave);
    return wave;
  });

  const clusterGroup = new THREE.Group();
  const clusterMeshes = CLUSTERS.map((cluster, index) => {
    const mesh = new THREE.Mesh(
      new THREE.OctahedronGeometry(index === 3 ? 0.12 : 0.095, 0),
      new THREE.MeshBasicMaterial({
        color: cluster.colour,
        transparent: true,
        opacity: 0.92,
        blending: THREE.AdditiveBlending,
      }),
    );
    mesh.position.set(...cluster.position);
    mesh.userData = { ...cluster, index, active: true };
    clusterGroup.add(mesh);
    return mesh;
  });
  root.add(clusterGroup);

  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2(2, 2);
  let quality = "balanced";
  let state = "dormant";
  let viewMode = "3d";
  let network = null;
  let pointerX = 0;
  let pointerY = 0;
  let dragX = 0;
  let dragY = 0;
  let dragging = false;
  let lastPointer = null;
  let hoveredCluster = null;
  let focusedCluster = null;
  let targetCamera = new THREE.Vector3(0, 0.12, 9.6);
  let topologyClock = 0;
  let frameHandle = 0;
  let lastFrame = performance.now();
  let fpsWindow = lastFrame;
  let fpsFrames = 0;
  let pixelCheckComplete = false;

  function disposeNetwork() {
    if (!network) return;
    root.remove(network.group);
    network.geometries.forEach((geometry) => geometry.dispose());
    network.materials.forEach((material) => material.dispose());
    network = null;
  }

  function buildNetwork(profileName) {
    disposeNetwork();
    const profile = QUALITY[profileName] || QUALITY.balanced;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, profile.pixelRatio));
    const random = seededRandom(0xa0715 + profile.nodes);
    const group = new THREE.Group();
    const positions = new Float32Array(profile.nodes * 3);
    const basePositions = new Float32Array(profile.nodes * 3);
    const phases = new Float32Array(profile.nodes);
    const colours = new Float32Array(profile.nodes * 3);
    const palette = [
      new THREE.Color(0xffb33f),
      new THREE.Color(0xffd56c),
      new THREE.Color(0xff8f32),
      new THREE.Color(0xffedb0),
      new THREE.Color(0x58d7ef),
    ];

    for (let index = 0; index < profile.nodes; index += 1) {
      const layer = index % 7;
      const radius = 0.9 + Math.pow(random(), 0.66) * (2.72 + layer * 0.07);
      const theta = random() * Math.PI * 2;
      const phi = Math.acos(2 * random() - 1);
      const flatten = 0.84 + (layer % 3) * 0.04;
      const offset = index * 3;
      positions[offset] = Math.sin(phi) * Math.cos(theta) * radius;
      positions[offset + 1] = Math.sin(phi) * Math.sin(theta) * radius * flatten;
      positions[offset + 2] = Math.cos(phi) * radius * 0.91;
      basePositions.set(positions.subarray(offset, offset + 3), offset);
      phases[index] = random() * Math.PI * 2;
      const colour = palette[index % 11 === 0 ? 4 : (index + layer) % 4];
      const brightness = 0.42 + random() * 0.58;
      colours[offset] = colour.r * brightness;
      colours[offset + 1] = colour.g * brightness;
      colours[offset + 2] = colour.b * brightness;
    }

    const nodeGeometry = new THREE.BufferGeometry();
    nodeGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    nodeGeometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
    const nodeMaterial = new THREE.PointsMaterial({
      size: profileName === "cinematic" ? 0.024 : 0.031,
      vertexColors: true,
      transparent: true,
      opacity: 0.9,
      sizeAttenuation: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    group.add(new THREE.Points(nodeGeometry, nodeMaterial));

    const routes = [];
    const routePositions = new Float32Array(profile.links * 18);
    for (let index = 0; index < profile.links; index += 1) {
      const from = Math.floor(random() * profile.nodes);
      const offset = 1 + Math.floor(random() * Math.min(67, profile.nodes - 1));
      const to = (from + offset) % profile.nodes;
      const bend = (random() - 0.5) * 0.75;
      routes.push({ from, to, nextTo: to, bend, blend: 1 });
    }
    const linkGeometry = new THREE.BufferGeometry();
    linkGeometry.setAttribute("position", new THREE.BufferAttribute(routePositions, 3));
    const linkMaterial = new THREE.LineBasicMaterial({
      color: 0xffab3d,
      transparent: true,
      opacity: 0.135,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    group.add(new THREE.LineSegments(linkGeometry, linkMaterial));

    const pulsePositions = new Float32Array(profile.pulses * 3);
    const pulseData = Array.from({ length: profile.pulses }, () => ({
      route: Math.floor(random() * routes.length),
      progress: random(),
      speed: 0.075 + random() * 0.15,
    }));
    const pulseGeometry = new THREE.BufferGeometry();
    pulseGeometry.setAttribute("position", new THREE.BufferAttribute(pulsePositions, 3));
    const pulseMaterial = new THREE.PointsMaterial({
      color: 0xfff0ba,
      size: 0.075,
      transparent: true,
      opacity: 0.98,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    group.add(new THREE.Points(pulseGeometry, pulseMaterial));

    const ambientPositions = new Float32Array(profile.particles * 3);
    const ambientData = [];
    for (let index = 0; index < profile.particles; index += 1) {
      ambientData.push({
        radius: 3.45 + random() * 1.85,
        phase: random() * Math.PI * 2,
        speed: 0.025 + random() * 0.08,
        elevation: (random() - 0.5) * 3.7,
      });
    }
    const ambientGeometry = new THREE.BufferGeometry();
    ambientGeometry.setAttribute("position", new THREE.BufferAttribute(ambientPositions, 3));
    const ambientMaterial = new THREE.PointsMaterial({
      color: 0x5ed9ef,
      size: 0.018,
      transparent: true,
      opacity: 0.38,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    group.add(new THREE.Points(ambientGeometry, ambientMaterial));
    root.add(group);

    network = {
      group,
      positions,
      basePositions,
      phases,
      routes,
      routePositions,
      linkGeometry,
      pulsePositions,
      pulseData,
      pulseGeometry,
      ambientPositions,
      ambientData,
      ambientGeometry,
      nodeGeometry,
      nodeMaterial,
      linkMaterial,
      pulseMaterial,
      ambientMaterial,
      random,
      geometries: [nodeGeometry, linkGeometry, pulseGeometry, ambientGeometry],
      materials: [nodeMaterial, linkMaterial, pulseMaterial, ambientMaterial],
    };
    quality = profileName;
    updateRoutes(1);
  }

  function routePoint(route, progress, output = new THREE.Vector3()) {
    const fromOffset = route.from * 3;
    const currentTo = route.to;
    const blendedTo = route.nextTo;
    const toX = THREE.MathUtils.lerp(
      network.positions[currentTo * 3],
      network.positions[blendedTo * 3],
      route.blend,
    );
    const toY = THREE.MathUtils.lerp(
      network.positions[currentTo * 3 + 1],
      network.positions[blendedTo * 3 + 1],
      route.blend,
    );
    const toZ = THREE.MathUtils.lerp(
      network.positions[currentTo * 3 + 2],
      network.positions[blendedTo * 3 + 2],
      route.blend,
    );
    const from = new THREE.Vector3(
      network.positions[fromOffset],
      network.positions[fromOffset + 1],
      network.positions[fromOffset + 2],
    );
    const to = new THREE.Vector3(toX, toY, toZ);
    const control = from.clone().add(to).multiplyScalar(0.5);
    control.z += route.bend;
    control.y += route.bend * 0.35;
    const inverse = 1 - progress;
    output.set(
      inverse * inverse * from.x + 2 * inverse * progress * control.x + progress * progress * to.x,
      inverse * inverse * from.y + 2 * inverse * progress * control.y + progress * progress * to.y,
      inverse * inverse * from.z + 2 * inverse * progress * control.z + progress * progress * to.z,
    );
    return output;
  }

  function updateRoutes(blendStep) {
    if (!network) return;
    const point = new THREE.Vector3();
    network.routes.forEach((route, routeIndex) => {
      route.blend = Math.min(1, route.blend + blendStep);
      for (let segment = 0; segment < 3; segment += 1) {
        const first = routePoint(route, segment / 3, point);
        const offset = routeIndex * 18 + segment * 6;
        network.routePositions.set([first.x, first.y, first.z], offset);
        const second = routePoint(route, (segment + 1) / 3, point);
        network.routePositions.set([second.x, second.y, second.z], offset + 3);
      }
      if (route.blend >= 1) route.to = route.nextTo;
    });
    network.linkGeometry.attributes.position.needsUpdate = true;
  }

  function evolveTopology() {
    if (!network) return;
    const count = Math.max(1, Math.floor(network.routes.length * 0.035));
    for (let index = 0; index < count; index += 1) {
      const route = network.routes[Math.floor(network.random() * network.routes.length)];
      route.nextTo = Math.floor(network.random() * QUALITY[quality].nodes);
      route.bend = (network.random() - 0.5) * 0.9;
      route.blend = 0;
    }
  }

  function updateNetwork(now, delta, activity) {
    if (!network) return;
    if (!reducedMotion) {
      const positionAttribute = network.nodeGeometry.attributes.position;
      for (let index = 0; index < network.phases.length; index += 1) {
        const offset = index * 3;
        const drift = Math.sin(now * 0.00034 + network.phases[index]) * 0.018;
        network.positions[offset] = network.basePositions[offset] * (1 + drift * 0.38);
        network.positions[offset + 1] = network.basePositions[offset + 1] + drift;
        network.positions[offset + 2] = network.basePositions[offset + 2] * (1 - drift * 0.24);
      }
      positionAttribute.needsUpdate = true;
    }
    network.routes.forEach((route) => {
      if (route.blend < 1) route.blend = Math.min(1, route.blend + delta * 0.72);
    });
    updateRoutes(0);

    const point = new THREE.Vector3();
    network.pulseData.forEach((pulse, index) => {
      if (!reducedMotion) pulse.progress = (pulse.progress + pulse.speed * delta * activity) % 1;
      routePoint(network.routes[pulse.route], pulse.progress, point);
      network.pulsePositions.set([point.x, point.y, point.z], index * 3);
    });
    network.pulseGeometry.attributes.position.needsUpdate = true;

    network.ambientData.forEach((particle, index) => {
      const angle = particle.phase + now * 0.00008 * particle.speed * 25;
      network.ambientPositions[index * 3] = Math.cos(angle) * particle.radius;
      network.ambientPositions[index * 3 + 1] = particle.elevation + Math.sin(angle * 1.7) * 0.18;
      network.ambientPositions[index * 3 + 2] = Math.sin(angle) * particle.radius * 0.55;
    });
    network.ambientGeometry.attributes.position.needsUpdate = true;
  }

  function resize() {
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    renderer.setSize(rect.width, rect.height, false);
    camera.aspect = rect.width / rect.height;
    camera.updateProjectionMatrix();
  }

  function updateHover() {
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObjects(clusterMeshes, false)[0]?.object || null;
    if (hit === hoveredCluster) return;
    hoveredCluster = hit;
    canvas.style.cursor = hit ? "pointer" : dragging ? "grabbing" : "grab";
    canvas.dispatchEvent(new CustomEvent("auris-core-hover", {
      detail: hit ? {
        name: hit.userData.name,
        label: hit.userData.label,
        active: hit.userData.active,
      } : null,
    }));
  }

  function animate(now) {
    const delta = Math.min((now - lastFrame) / 1000, 0.05);
    lastFrame = now;
    const activity = STATE[state]?.activity || 1;
    topologyClock += delta;
    if (topologyClock > 2.8 && !reducedMotion) {
      evolveTopology();
      topologyClock = 0;
    }

    if (!reducedMotion) {
      const flatFactor = viewMode === "2d" ? 0.08 : 1;
      root.rotation.y += delta * 0.018 * activity;
      root.rotation.x += ((dragY * 0.002 + pointerY * 0.055) * flatFactor - root.rotation.x) * 0.032;
      const parallaxX = (pointerX * 0.29 + dragX * 0.002) * flatFactor;
      camera.position.x += (targetCamera.x + parallaxX - camera.position.x) * 0.045;
      camera.position.y += (targetCamera.y - pointerY * 0.19 * flatFactor - camera.position.y) * 0.045;
      camera.position.z += (targetCamera.z - camera.position.z) * 0.045;
      camera.lookAt(focusedCluster ? focusedCluster.position : root.position);
      core.rotation.x += delta * 0.2 * activity;
      core.rotation.y -= delta * 0.25 * activity;
      innerCore.rotation.y += delta * 0.42 * activity;
      shell.rotation.x -= delta * 0.08;
      shell.rotation.z += delta * 0.12;
      const corePulse = 1 + Math.sin(now * 0.0028 * activity) * (state === "dormant" ? 0.028 : 0.07);
      core.scale.setScalar(corePulse);
      rings.forEach((ring) => {
        ring.rotation.z += delta * ring.userData.speed * ring.userData.direction * activity;
      });
      cages.forEach((cage, index) => {
        cage.rotation.y += delta * (0.018 + index * 0.006) * (index % 2 ? -1 : 1) * activity;
        cage.rotation.z += delta * (0.006 + index * 0.003) * activity;
      });
      plinthRings.forEach((plinth, index) => {
        plinth.rotation.z += delta * (0.014 + index * 0.006) * (index % 2 ? -1 : 1) * activity;
      });
      beamMarkers.forEach((marker) => {
        const cycle = (now * 0.00009 * activity + marker.userData.phase) % 1;
        marker.position.y = -4.1 + cycle * 8.2;
        marker.material.opacity = 0.24 + Math.sin(cycle * Math.PI) * 0.68;
      });
      processingSpine.material.opacity = 0.15 + Math.abs(Math.sin(now * 0.0014 * activity)) * 0.14;
      scanPlane.position.y = Math.sin(now * 0.00072) * 3.35;
      scanPlane.material.opacity = 0.045 + Math.abs(Math.cos(now * 0.00072)) * 0.055;
      waves.forEach((wave) => {
        const cycle = (now * 0.00014 * activity + wave.userData.phase) % 1;
        wave.scale.setScalar(0.8 + cycle * 4.1);
        wave.material.opacity = (1 - cycle) * 0.075;
      });
      clusterMeshes.forEach((cluster, index) => {
        const selected = cluster === focusedCluster;
        const hovered = cluster === hoveredCluster;
        const scale = selected ? 1.85 : hovered ? 1.45 : 1 + Math.sin(now * 0.002 + index) * 0.12;
        cluster.scale.setScalar(scale);
        cluster.rotation.y += delta * 0.4;
      });
      if (network) network.group.rotation.z -= delta * 0.008 * activity;
    }

    updateNetwork(now, delta, activity);
    updateHover();
    renderer.render(scene, camera);

    if (!pixelCheckComplete && now > 800) {
      const gl = renderer.getContext();
      const size = 10;
      const pixels = new Uint8Array(size * size * 4);
      for (const xRatio of [0.25, 0.5, 0.75]) {
        for (const yRatio of [0.25, 0.5, 0.75]) {
          gl.readPixels(
            Math.max(0, Math.floor(renderer.domElement.width * xRatio - size / 2)),
            Math.max(0, Math.floor(renderer.domElement.height * yRatio - size / 2)),
            size,
            size,
            gl.RGBA,
            gl.UNSIGNED_BYTE,
            pixels,
          );
          if (pixels.some((value, index) => index % 4 !== 3 && value > 3)) {
            pixelCheckComplete = true;
            break;
          }
        }
        if (pixelCheckComplete) break;
      }
    }

    fpsFrames += 1;
    if (now - fpsWindow >= 1000) {
      const fps = Math.round((fpsFrames * 1000) / (now - fpsWindow));
      const profile = QUALITY[quality];
      canvas.dispatchEvent(new CustomEvent("auris-render-metrics", {
        detail: {
          fps,
          quality,
          nodes: profile.nodes,
          links: profile.links,
          pulses: profile.pulses,
          projection: viewMode.toUpperCase(),
          renderer: "THREE.JS / WEBGL",
          nonblank: pixelCheckComplete,
        },
      }));
      fpsWindow = now;
      fpsFrames = 0;
    }
    frameHandle = window.requestAnimationFrame(animate);
  }

  function setState(nextState) {
    state = STATE[nextState] ? nextState : "dormant";
    const colour = STATE[state].colour;
    coreMaterial.color.setHex(colour);
    coreMaterial.emissive.setHex(colour);
    amberLight.color.setHex(colour);
    processingSpine.material.color.setHex(colour);
    rings.forEach((ring, index) => {
      if (index !== 2 && index !== 6) ring.material.color.setHex(colour);
    });
  }

  function setAgents(data) {
    const online = data.filter((agent) => agent.status === "online").length;
    const agentsCluster = clusterMeshes.find((cluster) => cluster.userData.name === "agents");
    if (agentsCluster) {
      agentsCluster.userData.active = online > 0;
      agentsCluster.material.color.setHex(online > 0 ? 0x63e6ad : 0x35515e);
    }
  }

  function setViewMode(nextMode) {
    if (!["3d", "2d", "schematic"].includes(nextMode)) return;
    viewMode = nextMode;
    canvas.dataset.viewMode = nextMode;
    focusedCluster = null;
    targetCamera.set(0, nextMode === "schematic" ? 0.35 : 0.12, nextMode === "2d" ? 10.9 : 9.6);
    root.rotation.z = nextMode === "schematic" ? Math.PI / 12 : 0;
    root.scale.set(1, nextMode === "2d" ? 0.88 : 1, nextMode === "schematic" ? 0.55 : 1);
    rings.forEach((ring) => {
      ring.material.opacity = nextMode === "schematic" ? 0.09 : 0.16;
    });
    cages.forEach((cage, index) => {
      cage.material.opacity = nextMode === "schematic" ? 0.11 : index === 1 ? 0.055 : 0.07;
    });
    plinthRings.forEach((plinth, index) => {
      plinth.material.opacity = nextMode === "schematic" ? 0.2 : 0.16 - index * 0.018;
    });
    if (network) {
      network.linkMaterial.opacity = nextMode === "schematic" ? 0.28 : 0.135;
      network.nodeMaterial.opacity = nextMode === "schematic" ? 0.72 : 0.9;
    }
  }

  function focusCluster(name) {
    const cluster = clusterMeshes.find((item) => item.userData.name === name);
    focusedCluster = cluster || null;
    if (cluster) {
      const worldPosition = new THREE.Vector3();
      cluster.getWorldPosition(worldPosition);
      targetCamera.set(worldPosition.x * 0.32, worldPosition.y * 0.28, 7.35);
      canvas.dispatchEvent(new CustomEvent("auris-core-focus", {
        detail: {
          name: cluster.userData.name,
          label: cluster.userData.label,
          active: cluster.userData.active,
        },
      }));
    } else {
      targetCamera.set(0, 0.12, 9.6);
      canvas.dispatchEvent(new CustomEvent("auris-core-focus", { detail: null }));
    }
  }

  canvas.addEventListener("pointermove", (event) => {
    const rect = canvas.getBoundingClientRect();
    pointerX = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointerY = ((event.clientY - rect.top) / rect.height) * 2 - 1;
    pointer.set(pointerX, -pointerY);
    if (dragging && lastPointer) {
      dragX += event.clientX - lastPointer.x;
      dragY += event.clientY - lastPointer.y;
      lastPointer = { x: event.clientX, y: event.clientY };
    }
  });
  canvas.addEventListener("pointerleave", () => {
    pointerX = 0;
    pointerY = 0;
    pointer.set(2, 2);
    dragging = false;
    lastPointer = null;
  });
  canvas.addEventListener("pointerdown", (event) => {
    dragging = true;
    lastPointer = { x: event.clientX, y: event.clientY };
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointerup", (event) => {
    dragging = false;
    lastPointer = null;
    if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
  });
  canvas.addEventListener("click", () => {
    if (hoveredCluster) focusCluster(hoveredCluster.userData.name);
  });
  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    targetCamera.z = THREE.MathUtils.clamp(targetCamera.z + Math.sign(event.deltaY) * 0.45, 6.3, 12.8);
  }, { passive: false });

  const observer = new ResizeObserver(resize);
  observer.observe(canvas);
  buildNetwork(quality);
  resize();

  return {
    start() {
      if (!frameHandle) frameHandle = window.requestAnimationFrame(animate);
    },
    setState,
    setAgents,
    setQuality(nextQuality) {
      if (QUALITY[nextQuality] && nextQuality !== quality) buildNetwork(nextQuality);
    },
    setFocus(enabled) {
      focusedCluster = null;
      targetCamera.set(0, 0.12, enabled ? 7.2 : viewMode === "2d" ? 10.9 : 9.6);
    },
    setViewMode,
    focusCluster,
    destroy() {
      window.cancelAnimationFrame(frameHandle);
      observer.disconnect();
      disposeNetwork();
      root.traverse((object) => {
        object.geometry?.dispose?.();
        if (Array.isArray(object.material)) object.material.forEach((material) => material.dispose());
        else object.material?.dispose?.();
      });
      renderer.dispose();
    },
  };
}

function seededRandom(seed) {
  let value = seed >>> 0;
  return () => {
    value += 0x6d2b79f5;
    let result = value;
    result = Math.imul(result ^ (result >>> 15), result | 1);
    result ^= result + Math.imul(result ^ (result >>> 7), result | 61);
    return ((result ^ (result >>> 14)) >>> 0) / 4294967296;
  };
}

function inertCore() {
  return {
    start() {},
    setState() {},
    setAgents() {},
    setQuality() {},
    setFocus() {},
    setViewMode() {},
    focusCluster() {},
    destroy() {},
  };
}
