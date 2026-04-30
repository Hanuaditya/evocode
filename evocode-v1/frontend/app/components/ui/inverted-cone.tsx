"use client";

import React from "react";

export function InvertedCone() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none z-0 flex justify-center">
      {/* Outer soft glow */}
      <div 
        className="absolute top-0 w-[1000px] h-[800px] origin-top animate-[cone-breathe_7s_ease-in-out_infinite]"
        style={{
          background: 'conic-gradient(from 0deg at 50% 0%, transparent 130deg, rgba(255,255,255,0.15) 180deg, transparent 230deg)',
          filter: 'blur(50px)',
        }}
      />
      
      {/* Inner bright core */}
      <div 
        className="absolute top-0 w-[600px] h-[600px] origin-top animate-[cone-breathe_5s_ease-in-out_infinite]"
        style={{
          background: 'conic-gradient(from 0deg at 50% 0%, transparent 150deg, rgba(255,255,255,0.25) 180deg, transparent 210deg)',
          filter: 'blur(40px)',
        }}
      />
    </div>
  );
}
