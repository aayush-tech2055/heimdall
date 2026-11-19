"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

/**
 * A decorative 3D "Bifrost" behind the sign-in page: glowing arcs in Heimdall's indigo and
 * gold, with drifting particles and a gentle tilt that follows the pointer. three.js is loaded
 * only here (dynamic import), the canvas is hidden from assistive technology, it pauses when
 * the tab is hidden, and with "reduce motion" on it draws a single still frame.
 */
export function BifrostScene() {
  const host = useRef<HTMLDivElement>(null);
  // Rendered into <body> so page-transition transforms cannot clip the fixed canvas.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let disposed = false;
    let cleanup = () => {};

    void import("three").then((THREE) => {
      if (disposed) return;
      const still = window.matchMedia(
        "(prefers-reduced-motion: reduce)",
      ).matches;
      const renderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: true,
      });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      el.appendChild(renderer.domElement);

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
      camera.position.set(0, 0, 10.5);

      const bridge = new THREE.Group();
      bridge.rotation.x = -0.35;
      bridge.position.set(0, -3.6, 0);
      scene.add(bridge);

      // Concentric arcs (half tori): navy → indigo → gold, like the Heimdall mark.
      const colors = [
        0x1e2a4a, 0x3730a3, 0x4f46e5, 0x6366f1, 0x818cf8, 0xe8b04b,
      ];
      const arcs = colors.map((color, i) => {
        const geo = new THREE.TorusGeometry(
          2.2 + i * 0.55,
          0.035 + (i === 5 ? 0.025 : 0),
          12,
          160,
          Math.PI,
        );
        const mat = new THREE.MeshBasicMaterial({
          color,
          transparent: true,
          opacity: i === 5 ? 0.85 : 0.55,
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.rotation.z = 0;
        bridge.add(mesh);
        return mesh;
      });

      // The watchful eye at the centre of the arcs.
      const eye = new THREE.Mesh(
        new THREE.SphereGeometry(0.22, 32, 32),
        new THREE.MeshBasicMaterial({ color: 0xe8b04b }),
      );
      bridge.add(eye);

      // Drifting particles along the bridge.
      const count = 420;
      const positions = new Float32Array(count * 3);
      const speeds = new Float32Array(count);
      for (let i = 0; i < count; i++) {
        const r = 2 + Math.random() * 3.6;
        const a = Math.random() * Math.PI;
        positions.set(
          [Math.cos(a) * r, Math.sin(a) * r, (Math.random() - 0.5) * 1.2],
          i * 3,
        );
        speeds[i] = 0.08 + Math.random() * 0.25;
      }
      const pGeo = new THREE.BufferGeometry();
      pGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      const particles = new THREE.Points(
        pGeo,
        new THREE.PointsMaterial({
          color: 0x6366f1,
          size: 0.045,
          transparent: true,
          opacity: 0.7,
          depthWrite: false,
        }),
      );
      bridge.add(particles);

      const resize = () => {
        const { clientWidth: w, clientHeight: h } = el;
        renderer.setSize(w, h, false);
        camera.aspect = w / Math.max(h, 1);
        camera.updateProjectionMatrix();
      };
      resize();
      const ro = new ResizeObserver(resize);
      ro.observe(el);

      let tx = 0;
      let ty = 0;
      const onMove = (e: PointerEvent) => {
        tx = (e.clientX / window.innerWidth - 0.5) * 0.3;
        ty = (e.clientY / window.innerHeight - 0.5) * 0.15;
      };
      window.addEventListener("pointermove", onMove);

      const clock = new THREE.Clock();
      let frame = 0;
      const draw = () => {
        const t = clock.getElapsedTime();
        arcs.forEach((arc, i) => {
          const m = arc.material as InstanceType<
            typeof THREE.MeshBasicMaterial
          >;
          m.opacity =
            (i === 5 ? 0.75 : 0.42) + Math.sin(t * 1.2 + i * 0.7) * 0.15;
        });
        eye.scale.setScalar(1 + Math.sin(t * 2) * 0.12);
        const pos = pGeo.attributes.position as InstanceType<
          typeof THREE.BufferAttribute
        >;
        for (let i = 0; i < count; i++) {
          const x = pos.getX(i);
          const y = pos.getY(i);
          const r = Math.hypot(x, y);
          let a = Math.atan2(y, x) - speeds[i] * 0.01;
          if (a < 0) a += Math.PI;
          pos.setXY(i, Math.cos(a) * r, Math.sin(a) * r);
        }
        pos.needsUpdate = true;
        bridge.rotation.y += (tx - bridge.rotation.y) * 0.04;
        bridge.rotation.x += (-0.35 + ty - bridge.rotation.x) * 0.04;
        renderer.render(scene, camera);
      };
      const loop = () => {
        draw();
        frame = requestAnimationFrame(loop);
      };
      const onVisibility = () => {
        cancelAnimationFrame(frame);
        if (!document.hidden && !still) loop();
      };
      document.addEventListener("visibilitychange", onVisibility);
      if (still) draw();
      else loop();

      cleanup = () => {
        cancelAnimationFrame(frame);
        ro.disconnect();
        window.removeEventListener("pointermove", onMove);
        document.removeEventListener("visibilitychange", onVisibility);
        scene.traverse((o) => {
          const mesh = o as InstanceType<typeof THREE.Mesh>;
          mesh.geometry?.dispose();
          const mat = mesh.material as { dispose?: () => void } | undefined;
          mat?.dispose?.();
        });
        renderer.dispose();
        renderer.domElement.remove();
      };
    });

    return () => {
      disposed = true;
      cleanup();
    };
  }, [mounted]);

  if (!mounted) return null;
  return createPortal(
    <div
      ref={host}
      aria-hidden
      className="hd-fade pointer-events-none fixed inset-0 -z-10 [&>canvas]:h-full [&>canvas]:w-full"
    />,
    document.body,
  );
}
