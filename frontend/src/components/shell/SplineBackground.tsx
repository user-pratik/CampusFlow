"use client";

import dynamic from "next/dynamic";

const Spline = dynamic(() => import("@splinetool/react-spline"), {
  ssr: false,
  loading: () => <div className="w-full h-full bg-slate-950" />,
});

export default function SplineBackground() {
  return (
    <div className="fixed inset-0 -z-10 bg-slate-950 pointer-events-none">
      <Spline scene="https://prod.spline.design/vj1TYPlzimq3o6mk/scene.splinecode" />
    </div>
  );
}
