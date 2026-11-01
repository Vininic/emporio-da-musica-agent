import * as THREE from "three";
import { GLTFLoader } from "/static/vendor/three/loaders/GLTFLoader.js";
import { dressAsMaestro } from "/static/maestro.js";

const GESTURES = { wave: "Wave", yes: "Yes", no: "No", thumbs: "ThumbsUp" };
const IDLE_GESTURE_EVERY = [14, 26];
const IDLE_SPEED = 0.7;
const PORTRAIT_SIZE = 192;
const BEAT_SECONDS = 0.62;
const CONDUCT_PATTERN = [
  [0.0, -0.42],
  [0.34, -0.12],
  [-0.34, -0.08],
  [0.02, 0.42],
];

const scratchEuler = new THREE.Euler();
const scratchQuaternion = new THREE.Quaternion();
const worldA = new THREE.Vector3();
const worldB = new THREE.Vector3();
const delta = new THREE.Quaternion();
const parentWorld = new THREE.Quaternion();
const boneWorld = new THREE.Quaternion();
const identity = new THREE.Quaternion();

function ease(t) {
  return t * t * (3 - 2 * t);
}

function conductOffset(time) {
  const position = time / BEAT_SECONDS;
  const index = Math.floor(position) % CONDUCT_PATTERN.length;
  const next = CONDUCT_PATTERN[(index + 1) % CONDUCT_PATTERN.length];
  const current = CONDUCT_PATTERN[index];
  const t = ease(position - Math.floor(position));
  return [current[0] + (next[0] - current[0]) * t, current[1] + (next[1] - current[1]) * t];
}

function aimBone(bone, child, direction, weight) {
  bone.updateWorldMatrix(true, false);
  child.updateWorldMatrix(false, false);
  const from = worldB.setFromMatrixPosition(child.matrixWorld).sub(worldA.setFromMatrixPosition(bone.matrixWorld)).normalize();
  delta.setFromUnitVectors(from, direction);
  delta.slerp(identity, 1 - weight);
  bone.parent.getWorldQuaternion(parentWorld);
  bone.getWorldQuaternion(boneWorld);
  bone.quaternion.copy(parentWorld.invert().multiply(delta).multiply(boneWorld));
  bone.updateWorldMatrix(false, true);
}

export class Robot {
  constructor(canvas) {
    this.canvas = canvas;
    this.actions = {};
    this.mood = "idle";
    this.reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.pointer = { x: 0, y: 0 };
    this.look = { x: 0, y: 0 };
    this.conduct = 0;
    this.think = 0;
    this.elapsed = 0;
    this.nextGlance = 4;
    this.glance = 0;
    this.visible = true;
  }

  async start() {
    const renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: true,
      preserveDrawingBuffer: true,
    });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    this.renderer = renderer;

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(26, 1, 0.1, 100);
    this.camera.position.set(0, 2.9, 14.6);
    this.camera.lookAt(0, 2.45, 0);

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x2a2a30, 1.5));
    const key = new THREE.DirectionalLight(0xffffff, 2.2);
    key.position.set(2.5, 7, 6);
    this.scene.add(key);
    const rim = new THREE.DirectionalLight(0xffffff, 3.2);
    rim.position.set(-4, 4, -5);
    this.scene.add(rim);
    const rimRight = new THREE.DirectionalLight(0xffffff, 2.4);
    rimRight.position.set(5, 2, -4);
    this.scene.add(rimRight);

    const gltf = await new GLTFLoader().loadAsync("/static/assets/robot.glb");
    for (const clip of gltf.animations) {
      if (clip.name === "Idle") {
        clip.tracks = clip.tracks.filter((track) => track.name !== "Head.quaternion");
      }
    }
    this.model = gltf.scene;
    this.scene.add(this.model);
    this.bones = dressAsMaestro(this.model);
    this.bones.head.rotation.y = 0;
    this.face = this.#findFace();

    this.mixer = new THREE.AnimationMixer(this.model);
    for (const clip of gltf.animations) {
      const action = this.mixer.clipAction(clip);
      if (clip.name !== "Idle") {
        action.setLoop(THREE.LoopOnce);
        action.clampWhenFinished = true;
      }
      this.actions[clip.name] = action;
    }
    this.mixer.addEventListener("finished", () => this.#returnToIdle());
    this.actions.Idle.timeScale = IDLE_SPEED;
    this.current = this.actions.Idle;
    this.current.play();
    this.#scheduleIdleGesture();

    this.#resize();
    new ResizeObserver(() => this.#resize()).observe(this.canvas);
    addEventListener("pointermove", (event) => {
      this.pointer.x = (event.clientX / innerWidth) * 2 - 1;
      this.pointer.y = (event.clientY / innerHeight) * 2 - 1;
    });

    new IntersectionObserver(([entry]) => {
      this.visible = entry.isIntersecting;
    }).observe(this.canvas);

    this.lastFrame = performance.now();
    this.renderer.setAnimationLoop(() => this.#frame());
    this.canvas.classList.add("ready");
  }

  setMood(mood) {
    this.mood = mood;
    if (mood === "idle") this.#scheduleIdleGesture();
  }

  gesture(name) {
    const clip = GESTURES[name];
    if (!clip || !this.actions[clip] || this.oneShot) return;
    this.oneShot = true;
    this.#fadeTo(clip, 0.2);
    this.#express(name === "no" ? "Sad" : null);
  }

  portrait() {
    const box = new THREE.Box3();
    this.bones.head.traverse((node) => {
      if (node.isMesh) box.expandByObject(node);
    });
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const camera = new THREE.PerspectiveCamera(24, 1, 0.1, 100);
    const distance = (Math.max(size.x, size.y) * 0.56) / Math.tan(THREE.MathUtils.degToRad(12));
    camera.position.set(center.x, center.y + size.y * 0.04, center.z + distance);
    camera.lookAt(center);

    const target = new THREE.WebGLRenderTarget(PORTRAIT_SIZE, PORTRAIT_SIZE, { samples: 4, colorSpace: THREE.SRGBColorSpace });
    this.renderer.setRenderTarget(target);
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.clear();
    this.renderer.render(this.scene, camera);
    const pixels = new Uint8Array(PORTRAIT_SIZE * PORTRAIT_SIZE * 4);
    this.renderer.readRenderTargetPixels(target, 0, 0, PORTRAIT_SIZE, PORTRAIT_SIZE, pixels);
    this.renderer.setRenderTarget(null);
    target.dispose();

    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = PORTRAIT_SIZE;
    const context = canvas.getContext("2d");
    const image = context.createImageData(PORTRAIT_SIZE, PORTRAIT_SIZE);
    for (let row = 0; row < PORTRAIT_SIZE; row += 1) {
      const from = (PORTRAIT_SIZE - 1 - row) * PORTRAIT_SIZE * 4;
      image.data.set(pixels.subarray(from, from + PORTRAIT_SIZE * 4), row * PORTRAIT_SIZE * 4);
    }
    context.putImageData(image, 0, 0);
    return canvas.toDataURL("image/png");
  }

  #findFace() {
    let face = null;
    this.model.traverse((node) => {
      if (!face && node.isMesh && node.morphTargetDictionary?.Sad !== undefined) face = node;
    });
    return face;
  }

  #returnToIdle() {
    this.oneShot = false;
    this.#express(null);
    this.#fadeTo("Idle", 0.4);
    this.#scheduleIdleGesture();
  }

  #scheduleIdleGesture() {
    const [low, high] = IDLE_GESTURE_EVERY;
    this.nextGesture = this.elapsed + low + Math.random() * (high - low);
  }

  #express(name) {
    this.targetMorph = name ? this.face?.morphTargetDictionary?.[name] : null;
  }

  #fadeTo(name, duration = 0.35) {
    const next = this.actions[name];
    if (!next || next === this.current) return;
    next.reset().setEffectiveWeight(1).play();
    this.current?.crossFadeTo(next, duration, false);
    this.current = next;
  }

  #resize() {
    const { width, height } = this.canvas.getBoundingClientRect();
    if (!width || !height) return;
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  #frame() {
    const moment = performance.now();
    const delta = Math.min((moment - this.lastFrame) / 1000, 0.1);
    this.lastFrame = moment;
    if (document.hidden || !this.visible) return;

    if (!this.reduced) this.mixer.update(delta);
    this.elapsed += delta;
    if (this.elapsed > this.nextGlance) {
      this.glance = this.glance ? 0 : (Math.random() < 0.5 ? -1 : 1) * 0.3;
      this.nextGlance = this.elapsed + (this.glance ? 1.4 : 4 + Math.random() * 5);
    }
    if (this.mood === "idle" && !this.oneShot && this.elapsed > this.nextGesture) {
      this.gesture(Math.random() < 0.5 ? "yes" : "wave");
    }
    this.look.x += (this.pointer.x * 0.3 + this.glance - this.look.x) * 0.05;
    this.look.y += (this.pointer.y * 0.14 - this.look.y) * 0.05;
    const wanted = this.mood === "conducting" && !this.oneShot ? 1 : 0;
    this.conduct += (wanted - this.conduct) * 0.07;
    this.think += ((this.mood === "thinking" ? 1 : 0) - this.think) * 0.07;

    const influences = this.face?.morphTargetInfluences;
    if (influences && this.targetMorph != null) {
      influences[this.targetMorph] = Math.min(1, (influences[this.targetMorph] ?? 0) + 0.1);
    }

    const restore = this.reduced ? [] : this.#applyProceduralPose();
    this.renderer.render(this.scene, this.camera);
    for (const [bone, quaternion] of restore) bone.quaternion.copy(quaternion);
  }

  #applyProceduralPose() {
    const { head, armUpper, armLower, hand } = this.bones;
    const restore = [head, armUpper, armLower].map((bone) => [bone, bone.quaternion.clone()]);

    const nod = Math.sin(this.elapsed * 2.6) * 0.03;
    scratchEuler.set(this.look.y + this.think * (0.24 + nod), this.look.x + this.think * -0.32, this.think * 0.09);
    head.quaternion.multiply(scratchQuaternion.setFromEuler(scratchEuler));

    if (this.conduct > 0.01) {
      const [sideways, vertical] = conductOffset(this.elapsed);
      const upper = new THREE.Vector3(-0.86, -0.42 + vertical * 0.16, 0.36).normalize();
      const lower = new THREE.Vector3(-0.62 + sideways * 0.55, 0.1 + vertical * 0.55, 0.62).normalize();
      aimBone(armUpper, armLower, upper, this.conduct);
      aimBone(armLower, hand, lower, this.conduct);
    }
    return restore;
  }
}
