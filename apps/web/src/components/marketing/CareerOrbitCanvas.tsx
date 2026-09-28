"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

const NODE_COUNT = 5;
const ORBIT_RADIUS = 2.35;

function createGlowMaterial(color: THREE.ColorRepresentation, emissiveIntensity = 0.35) {
  return new THREE.MeshPhysicalMaterial({
    color,
    emissive: new THREE.Color(color),
    emissiveIntensity,
    metalness: 0.15,
    roughness: 0.35,
    clearcoat: 0.6,
    clearcoatRoughness: 0.2,
  });
}

export function CareerOrbitCanvas() {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const hostEl = hostRef.current;
    if (!hostEl) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 40);
    camera.position.set(0, 0.4, 7.2);

    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
    });
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    hostEl.appendChild(renderer.domElement);

    const root = new THREE.Group();
    scene.add(root);

    const core = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.55, 2),
      createGlowMaterial("#5551ff", 0.45),
    );
    root.add(core);

    const orbitRing = new THREE.Mesh(
      new THREE.TorusGeometry(ORBIT_RADIUS, 0.018, 12, 128),
      new THREE.MeshBasicMaterial({
        color: 0x94a3b8,
        transparent: true,
        opacity: 0.35,
      }),
    );
    orbitRing.rotation.x = Math.PI / 2.35;
    root.add(orbitRing);

    const nodes: THREE.Mesh[] = [];
    const nodeColors = ["#e85d4c", "#5551ff", "#0ea5e9", "#10b981", "#f59e0b"];

    for (let i = 0; i < NODE_COUNT; i += 1) {
      const angle = (i / NODE_COUNT) * Math.PI * 2;
      const node = new THREE.Mesh(
        new THREE.SphereGeometry(0.22, 24, 24),
        createGlowMaterial(nodeColors[i % nodeColors.length], 0.28),
      );
      node.position.set(
        Math.cos(angle) * ORBIT_RADIUS,
        Math.sin(angle * 0.6) * 0.35,
        Math.sin(angle) * ORBIT_RADIUS,
      );
      root.add(node);
      nodes.push(node);

      const link = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(0, 0, 0),
          node.position.clone(),
        ]),
        new THREE.LineBasicMaterial({
          color: 0x64748b,
          transparent: true,
          opacity: 0.22,
        }),
      );
      root.add(link);
    }

    const ambient = new THREE.AmbientLight(0xffffff, 0.55);
    const key = new THREE.DirectionalLight(0xffffff, 1.1);
    key.position.set(4, 6, 5);
    const fill = new THREE.DirectionalLight(0x5551ff, 0.35);
    fill.position.set(-5, -2, 3);
    scene.add(ambient, key, fill);

    let frameId = 0;
    let pointerX = 0;
    let pointerY = 0;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function onPointerMove(event: PointerEvent) {
      const el = hostRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      pointerX = ((event.clientX - rect.left) / rect.width - 0.5) * 2;
      pointerY = ((event.clientY - rect.top) / rect.height - 0.5) * 2;
    }

    function resize() {
      const el = hostRef.current;
      if (!el) return;
      const { clientWidth, clientHeight } = el;
      if (clientWidth === 0 || clientHeight === 0) return;
      camera.aspect = clientWidth / clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(clientWidth, clientHeight, false);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    }

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(hostEl);
    resize();
    hostEl.addEventListener("pointermove", onPointerMove);

    const start = performance.now();
    function tick(now: number) {
      frameId = requestAnimationFrame(tick);
      const t = (now - start) * 0.001;

      if (!reducedMotion) {
        root.rotation.y = t * 0.22 + pointerX * 0.12;
        root.rotation.x = pointerY * 0.08;
        core.rotation.y = t * 0.4;
        nodes.forEach((node, index) => {
          const angle = (index / NODE_COUNT) * Math.PI * 2 + t * 0.35;
          node.position.set(
            Math.cos(angle) * ORBIT_RADIUS,
            Math.sin(angle * 0.6 + t) * 0.35,
            Math.sin(angle) * ORBIT_RADIUS,
          );
        });
      }

      renderer.render(scene, camera);
    }
    frameId = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(frameId);
      hostEl.removeEventListener("pointermove", onPointerMove);
      resizeObserver.disconnect();
      renderer.dispose();
      hostEl.removeChild(renderer.domElement);
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          object.geometry.dispose();
          const mat = object.material;
          if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
          else mat.dispose();
        }
      });
    };
  }, []);

  return (
    <div
      ref={hostRef}
      className="pointer-events-none absolute inset-0 sm:pointer-events-auto"
      aria-hidden
    />
  );
}
