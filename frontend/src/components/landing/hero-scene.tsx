"use client";

import { useEffect, useRef } from "react";

/**
 * The home page hero: a 3D "Bifrost" on black. Glowing arcs in several colours, a field of
 * white stars, a gold eye at the centre. It tilts towards the pointer and turns and recedes
 * as the page scrolls. three.js loads only here; the canvas is decorative (aria-hidden),
 * pauses when off screen or the tab is hidden, and draws one still frame for reduced motion.
 */
export function HeroScene() {
  const host = useRef<HTMLDivElement>(null);

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
      scene.fog = new THREE.Fog(0x000000, 9, 22);
      const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
      camera.position.set(0, 0.4, 11);

      const bridge = new THREE.Group();
      bridge.position.set(0, -3.2, 0);
      bridge.rotation.x = -0.42;
      scene.add(bridge);

      const colors = [
        0xffffff, 0xa5b4fc, 0x6366f1, 0x22d3ee, 0x34d399, 0xf472b6, 0xf5b544,
      ];
      const arcs = colors.map((color, i) => {
        const mesh = new THREE.Mesh(
          new THREE.TorusGeometry(
            2 + i * 0.62,
            i === colors.length - 1 ? 0.06 : 0.032,
            16,
            200,
            Math.PI,
          ),
          new THREE.MeshBasicMaterial({
            color,
            transparent: true,
            opacity: 0.6,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
          }),
        );
        bridge.add(mesh);
        return mesh;
      });

      const eye = new THREE.Mesh(
        new THREE.SphereGeometry(0.26, 32, 32),
        new THREE.MeshBasicMaterial({ color: 0xf5b544 }),
      );
      bridge.add(eye);
      const halo = new THREE.Mesh(
        new THREE.RingGeometry(0.4, 0.46, 64),
        new THREE.MeshBasicMaterial({
          color: 0xf5b544,
          transparent: true,
          opacity: 0.5,
          side: THREE.DoubleSide,
        }),
      );
      bridge.add(halo);

      // Stars: a wide field behind, and particles travelling along the arcs.
      const starCount = 900;
      const star = new Float32Array(starCount * 3);
      for (let i = 0; i < starCount; i++) {
        star.set(
          [
            (Math.random() - 0.5) * 40,
            (Math.random() - 0.3) * 22,
            -Math.random() * 18,
          ],
          i * 3,
        );
      }
      const starGeo = new THREE.BufferGeometry();
      starGeo.setAttribute("position", new THREE.BufferAttribute(star, 3));
      const stars = new THREE.Points(
        starGeo,
        new THREE.PointsMaterial({
          color: 0xffffff,
          size: 0.035,
          transparent: true,
          opacity: 0.55,
          depthWrite: false,
        }),
      );
      scene.add(stars);

      const flowCount = 520;
      const flow = new Float32Array(flowCount * 3);
      const speed = new Float32Array(flowCount);
      for (let i = 0; i < flowCount; i++) {
        const r = 2 + Math.random() * 3.9;
        const a = Math.random() * Math.PI;
        flow.set(
          [Math.cos(a) * r, Math.sin(a) * r, (Math.random() - 0.5) * 0.8],
          i * 3,
        );
        speed[i] = 0.1 + Math.random() * 0.35;
      }
      const flowGeo = new THREE.BufferGeometry();
      flowGeo.setAttribute("position", new THREE.BufferAttribute(flow, 3));
      const particles = new THREE.Points(
        flowGeo,
        new THREE.PointsMaterial({
          color: 0xc7d2fe,
          size: 0.05,
          transparent: true,
          opacity: 0.9,
          blending: THREE.AdditiveBlending,
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
        tx = (e.clientX / window.innerWidth - 0.5) * 0.4;
        ty = (e.clientY / window.innerHeight - 0.5) * 0.2;
      };
      window.addEventListener("pointermove", onMove);

      let visible = true;
      const io = new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting;
      });
      io.observe(el);

      const clock = new THREE.Clock();
      let frame = 0;
      const draw = () => {
        const t = clock.getElapsedTime();
        const scroll = Math.min(window.scrollY / window.innerHeight, 1.2);
        arcs.forEach((arc, i) => {
          const m = arc.material as InstanceType<
            typeof THREE.MeshBasicMaterial
          >;
          m.opacity = 0.42 + Math.sin(t * 1.3 + i * 0.6) * 0.22;
        });
        eye.scale.setScalar(1 + Math.sin(t * 2.2) * 0.14);
        halo.scale.setScalar(1 + ((t * 0.6) % 1) * 1.6);
        (
          halo.material as InstanceType<typeof THREE.MeshBasicMaterial>
        ).opacity = 0.5 * (1 - ((t * 0.6) % 1));
        const pos = flowGeo.attributes.position as InstanceType<
          typeof THREE.BufferAttribute
        >;
        for (let i = 0; i < flowCount; i++) {
          const x = pos.getX(i);
          const y = pos.getY(i);
          const r = Math.hypot(x, y);
          let a = Math.atan2(y, x) - speed[i] * 0.012;
          if (a < 0) a += Math.PI;
          pos.setXY(i, Math.cos(a) * r, Math.sin(a) * r);
        }
        pos.needsUpdate = true;
        stars.rotation.y = t * 0.01;
        bridge.rotation.y += (tx + scroll * 0.6 - bridge.rotation.y) * 0.05;
        bridge.rotation.x +=
          (-0.42 + ty - scroll * 0.35 - bridge.rotation.x) * 0.05;
        camera.position.z = 11 + scroll * 4;
        renderer.render(scene, camera);
      };
      const loop = () => {
        if (visible && !document.hidden) draw();
        frame = requestAnimationFrame(loop);
      };
      if (still) draw();
      else loop();

      cleanup = () => {
        cancelAnimationFrame(frame);
        ro.disconnect();
        io.disconnect();
        window.removeEventListener("pointermove", onMove);
        scene.traverse((o) => {
          const mesh = o as InstanceType<typeof THREE.Mesh>;
          mesh.geometry?.dispose();
          (mesh.material as { dispose?: () => void } | undefined)?.dispose?.();
        });
        renderer.dispose();
        renderer.domElement.remove();
      };
    });

    return () => {
      disposed = true;
      cleanup();
    };
  }, []);

  return (
    <div
      ref={host}
      aria-hidden
      className="pointer-events-none absolute inset-0 [&>canvas]:h-full [&>canvas]:w-full"
    />
  );
}
