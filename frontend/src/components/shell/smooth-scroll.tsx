"use client";

import "lenis/dist/lenis.css";

import { ReactLenis } from "lenis/react";
import { useEffect, useState } from "react";

/** Smooth, eased page scrolling (Lenis). Off for people who prefer reduced motion.
 * Inner scroll panels opt out with `data-lenis-prevent` and keep native scrolling. */
export function SmoothScroll({ children }: { children: React.ReactNode }) {
  const [reduced, setReduced] = useState(true);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const on = () => setReduced(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  if (reduced) return <>{children}</>;
  return (
    <ReactLenis
      root
      options={{ lerp: 0.09, smoothWheel: true, anchors: { offset: -72 } }}
    >
      {children}
    </ReactLenis>
  );
}
