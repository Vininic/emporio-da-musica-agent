import * as THREE from "three";
import { GLTFLoader } from "/static/vendor/three/loaders/GLTFLoader.js";

const LOOPING = new Set(["Idle", "Walking", "Sitting", "Dance"]);
const GESTURES = { wave: "Wave", yes: "Yes", no: "No", thumbs: "ThumbsUp", dance: "Dance" };

export class Robot {
  constructor(canvas) {
    this.canvas = canvas;
    this.actions = {};
    this.base = "Idle";
    this.reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.pointer = { x: 0, y: 0 };
    this.lookX = 0;
    this.lookY = 0;
  }

  async start() {
    const renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer = renderer;

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
    this.camera.position.set(0, 3.1, 12.5);
    this.camera.lookAt(0, 2.45, 0);

    this.scene.add(new THREE.HemisphereLight(0xdfe6ff, 0x0b0f1c, 1.5));
    const key = new THREE.DirectionalLight(0xffffff, 2.2);
    key.position.set(3, 6, 5);
    this.scene.add(key);
    const rim = new THREE.DirectionalLight(0x4a69c7, 3.2);
    rim.position.set(-4, 3, -4);
    this.scene.add(rim);

    const gltf = await new GLTFLoader().loadAsync("/static/assets/robot.glb");
    this.model = gltf.scene;
    this.model.rotation.y = 0;
    this.scene.add(this.model);
    this.head = this.model.getObjectByName("Head");
    this.face = this.model.getObjectByName("Head_4");

    this.mixer = new THREE.AnimationMixer(this.model);
    for (const clip of gltf.animations) {
      const action = this.mixer.clipAction(clip);
      if (!LOOPING.has(clip.name)) {
        action.setLoop(THREE.LoopOnce);
        action.clampWhenFinished = true;
      }
      this.actions[clip.name] = action;
    }
    this.mixer.addEventListener("finished", () => this.#returnToBase());
    this.current = this.actions[this.base];
    this.current.play();

    this.#resize();
    new ResizeObserver(() => this.#resize()).observe(this.canvas);
    addEventListener("pointermove", (event) => {
      this.pointer.x = (event.clientX / innerWidth) * 2 - 1;
      this.pointer.y = (event.clientY / innerHeight) * 2 - 1;
    });

    this.lastFrame = performance.now();
    this.renderer.setAnimationLoop(() => this.#frame());
    this.canvas.classList.add("ready");
  }

  setBase(name) {
    if (this.base === name) return;
    this.base = name;
    if (!this.oneShot) this.#fadeTo(name);
  }

  gesture(name) {
    const clip = GESTURES[name];
    if (!clip || !this.actions[clip]) return;
    if (LOOPING.has(clip)) {
      this.setBase(clip);
      return;
    }
    this.oneShot = true;
    this.#fadeTo(clip, 0.2);
    this.#express(name === "no" ? "Sad" : null);
  }

  #returnToBase() {
    this.oneShot = false;
    this.#express(null);
    this.#fadeTo(this.base, 0.4);
  }

  #express(name) {
    const face = this.face;
    if (!face?.morphTargetDictionary) return;
    this.targetMorph = name ? face.morphTargetDictionary[name] : null;
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
    if (document.hidden) return;
    if (!this.reduced) this.mixer.update(delta);

    this.lookX += (this.pointer.x * 0.5 - this.lookX) * 0.06;
    this.lookY += (this.pointer.y * 0.25 - this.lookY) * 0.06;
    if (this.head && !this.reduced) {
      this.head.rotation.y += this.lookX;
      this.head.rotation.x += this.lookY;
    }

    const influences = this.face?.morphTargetInfluences;
    if (influences) {
      for (let i = 0; i < influences.length; i += 1) {
        const target = i === this.targetMorph ? 1 : 0;
        influences[i] += (target - influences[i]) * 0.12;
      }
    }
    this.renderer.render(this.scene, this.camera);
  }
}
