"use client";

import React, { useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface RippleButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  rippleColor?: string;
  duration?: string;
  children: React.ReactNode;
}

export function RippleButton({
  className,
  children,
  rippleColor = "#ffffff",
  duration = "600ms",
  onClick,
  disabled,
  ...props
}: RippleButtonProps) {
  const [ripples, setRipples] = useState<{ x: number; y: number; id: number }[]>([]);
  const ref = useRef<HTMLButtonElement>(null);

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (disabled) return;
    const button = ref.current;
    if (!button) return;
    const rect = button.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const id = Date.now();
    setRipples((prev) => [...prev, { x, y, id }]);
    setTimeout(() => setRipples((prev) => prev.filter((r) => r.id !== id)), 700);
    onClick?.(e);
  };

  return (
    <button
      ref={ref}
      className={cn(
        "relative overflow-hidden inline-flex items-center justify-center gap-2 select-none transition-all active:scale-95",
        disabled && "opacity-50 cursor-not-allowed",
        className
      )}
      onClick={handleClick}
      disabled={disabled}
      {...props}
    >
      {ripples.map((ripple) => (
        <span
          key={ripple.id}
          className="absolute rounded-full pointer-events-none animate-[ripple_600ms_ease-out_forwards]"
          style={{
            left: ripple.x - 50,
            top: ripple.y - 50,
            width: 100,
            height: 100,
            background: rippleColor,
            opacity: 0.3,
            animationDuration: duration,
          }}
        />
      ))}
      {children}
    </button>
  );
}
