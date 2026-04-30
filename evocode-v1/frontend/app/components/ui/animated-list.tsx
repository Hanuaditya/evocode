"use client";

import React, { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface AnimatedListProps {
  className?: string;
  children: React.ReactNode;
  delay?: number;
}

export function AnimatedList({ className, children, delay = 1000 }: AnimatedListProps) {
  const [index, setIndex] = useState(0);
  const childrenArray = React.Children.toArray(children);

  useEffect(() => {
    const interval = setInterval(() => {
      setIndex((prev) => (prev + 1) % childrenArray.length);
    }, delay);
    return () => clearInterval(interval);
  }, [childrenArray.length, delay]);

  const itemsToShow = childrenArray.slice(0, index + 1).reverse();

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {itemsToShow.map((item, i) => (
        <AnimatedListItem key={(item as React.ReactElement).key ?? i}>
          {item}
        </AnimatedListItem>
      ))}
    </div>
  );
}

function AnimatedListItem({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="animate-slide-in"
      style={{ opacity: 0 }}
    >
      {children}
    </div>
  );
}
