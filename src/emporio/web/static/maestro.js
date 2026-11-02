import * as THREE from "three";

const COAT = 0x17181d;
const COAT_DEEP = 0x101116;
const TROUSERS = 0x131418;
const PORCELAIN = 0xdcdcd8;
const STEEL = 0x34363d;
const SHIRT = 0xf4f4f1;
const WIG = 0xecebe6;
const LEATHER = 0x0b0b0e;
const CORK = 0x8a6a3c;
const EYE = 0x08090c;
const GOLD = 0xd9b44a;

function surface(color, roughness = 0.55, metalness = 0.05, extra = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness, metalness, flatShading: true, ...extra });
}

const SKIN = {
  Torso: { Main: () => surface(COAT, 0.5, 0.1), Grey: () => surface(COAT_DEEP, 0.6) },
  ShoulderL_1: { Main: () => surface(COAT, 0.5, 0.1) },
  ShoulderR_1: { Main: () => surface(COAT, 0.5, 0.1) },
  ArmL: { Main: () => surface(COAT, 0.5, 0.1) },
  ArmR: { Main: () => surface(COAT, 0.5, 0.1) },
  HandL: { Main: () => surface(COAT, 0.5, 0.1), Grey: () => surface(SHIRT, 0.7) },
  HandR: { Main: () => surface(COAT, 0.5, 0.1), Grey: () => surface(SHIRT, 0.7) },
  LegL: { Main: () => surface(TROUSERS, 0.65) },
  LegR: { Main: () => surface(TROUSERS, 0.65) },
  LowerLegL_1: { Main: () => surface(TROUSERS, 0.65) },
  LowerLegR_1: { Main: () => surface(TROUSERS, 0.65) },
  FootL_1: { Grey: () => surface(LEATHER, 0.22, 0.55) },
  FootR_1: { Grey: () => surface(LEATHER, 0.22, 0.55) },
  Head_1: {
    Main: () => surface(PORCELAIN, 0.42, 0.15),
    Grey: () => surface(STEEL, 0.45, 0.4),
    Black: () => surface(EYE, 0.55, 0, { flatShading: false }),
  },
};

function skinOwner(mesh) {
  let node = mesh;
  while (node) {
    if (SKIN[node.name]) return SKIN[node.name];
    node = node.parent;
  }
  return null;
}

function reskin(model) {
  model.traverse((node) => {
    if (!node.isMesh) return;
    const owner = skinOwner(node);
    const make = owner?.[node.material.name];
    if (!make) return;
    const material = make();
    material.name = node.material.name;
    node.material = material;
    node.castShadow = true;
  });
}

function bone(model, name) {
  let found = null;
  model.traverse((node) => {
    if (!found && node.isBone && node.name === name) found = node;
  });
  return found;
}

function worldOf(node) {
  return node.getWorldPosition(new THREE.Vector3());
}

function meshBounds(model, name) {
  const box = new THREE.Box3();
  model.traverse((node) => {
    if (node.name === name) box.expandByObject(node);
  });
  return box;
}

function pieceOn(parent, geometry, material, position, rotation = [0, 0, 0], scale = [1, 1, 1]) {
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.set(...position);
  mesh.rotation.set(...rotation);
  mesh.scale.set(...scale);
  mesh.updateMatrixWorld(true);
  parent.attach(mesh);
  return mesh;
}

function addWig(model, headBone) {
  const box = meshBounds(model, "Head_1");
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const hair = new THREE.MeshStandardMaterial({ color: WIG, roughness: 0.9, metalness: 0 });
  const sideX = size.x / 2;

  const crown = new THREE.SphereGeometry(size.x * 0.5, 28, 18);
  pieceOn(headBone, crown, hair, [center.x, center.y + size.y * 0.3, center.z - size.z * 0.2], [0, 0, 0], [1.02, 0.56, 0.8]);

  const roll = new THREE.CapsuleGeometry(size.y * 0.12, size.z * 0.12, 6, 14);
  for (const side of [-1, 1]) {
    for (let row = 0; row < 3; row += 1) {
      const y = center.y + size.y * (0.26 - row * 0.235);
      pieceOn(headBone, roll, hair, [center.x + side * (sideX + size.y * 0.03), y, center.z - size.z * 0.2], [Math.PI / 2, 0, 0]);
    }
  }
}

function addTailcoat(model, torsoBone) {
  const box = meshBounds(model, "Torso");
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const frontZ = box.max.z;

  const shirt = surface(SHIRT, 0.75);
  const bow = surface(GOLD, 0.35, 0.6);

  const collar = new THREE.CylinderGeometry(size.x * 0.13, size.x * 0.16, size.y * 0.16, 12);
  pieceOn(torsoBone, collar, shirt, [center.x, box.max.y - size.y * 0.06, center.z]);

  const halfWidth = size.x * 0.19;
  const halfHeight = size.y * 0.27;
  const front = new THREE.ShapeGeometry(
    new THREE.Shape([new THREE.Vector2(-halfWidth, halfHeight), new THREE.Vector2(0, -halfHeight), new THREE.Vector2(halfWidth, halfHeight)]),
  );
  pieceOn(torsoBone, front, new THREE.MeshStandardMaterial({ color: SHIRT, roughness: 0.75, side: THREE.DoubleSide }), [center.x, center.y + size.y * 0.08, frontZ + size.z * 0.012], [-0.06, 0, 0]);

  const wing = new THREE.ConeGeometry(size.x * 0.1, size.x * 0.22, 4);
  const neckY = box.max.y - size.y * 0.2;
  pieceOn(torsoBone, wing, bow, [center.x - size.x * 0.105, neckY, frontZ - size.z * 0.1], [0, 0, -Math.PI / 2]);
  pieceOn(torsoBone, wing, bow, [center.x + size.x * 0.105, neckY, frontZ - size.z * 0.1], [0, 0, Math.PI / 2]);
}

function addBaton(model, hand, forearm) {
  const reference = meshBounds(model, "Head_1").getSize(new THREE.Vector3()).x;
  const length = reference * 0.6;
  const group = new THREE.Group();
  const stick = new THREE.Mesh(
    new THREE.CylinderGeometry(reference * 0.008, reference * 0.019, length, 8),
    surface(0xf6f6f2, 0.4, 0),
  );
  stick.position.y = length / 2;
  const grip = new THREE.Mesh(new THREE.SphereGeometry(reference * 0.04, 10, 8), surface(CORK, 0.8));
  grip.scale.set(1, 1.5, 1);
  group.add(stick, grip);

  const palm = worldOf(hand);
  const along = palm.clone().sub(worldOf(forearm)).normalize().multiplyScalar(0.55);
  along.add(new THREE.Vector3(-0.42, 0.05, 0.6)).normalize();
  group.position.copy(palm);
  group.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), along);
  group.updateMatrixWorld(true);
  hand.attach(group);
}

export function dressAsMaestro(model) {
  model.updateMatrixWorld(true);
  reskin(model);
  const head = bone(model, "Head");
  const torso = bone(model, "Torso_1");
  const hand = bone(model, "Palm2R") ?? bone(model, "LowerArmR");
  addWig(model, head);
  addTailcoat(model, torso);
  addBaton(model, hand, bone(model, "LowerArmR"));
  return { head, armUpper: bone(model, "UpperArmR"), armLower: bone(model, "LowerArmR"), hand };
}
