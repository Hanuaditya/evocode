"use client";

import React, { useState } from "react";

export function MagicCard({
  children,
  className = "",
  gradientColor = "#262626",
}: {
  children: React.ReactNode;
  className?: string;
  gradientColor?: string;
}) {
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      onMouseMove={(e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        setMousePosition({
          x: e.clientX - rect.left,
          y: e.clientY - rect.top,
        });
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`relative overflow-hidden rounded-xl border transition-all ${className}`}
    >
      <div
        className="pointer-events-none absolute -inset-px rounded-xl opacity-0 transition-opacity duration-300"
        style={{
          opacity: isHovered ? 1 : 0,
          background: `radial-gradient(600px circle at ${mousePosition.x}px ${mousePosition.y}px, ${gradientColor}, transparent 40%)`,
        }}
      />
      <div className="relative z-10 flex h-full flex-col">{children}</div>
    </div>
  );
}
