import React from "react";

export const AnimatedShinyText = ({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) => {
  return (
    <div
      className={`inline-flex animate-shiny-text bg-clip-text text-transparent bg-[linear-gradient(110deg,#939393,45%,#fff,55%,#939393)] bg-[length:200%_100%] ${className}`}
    >
      {children}
    </div>
  );
};
