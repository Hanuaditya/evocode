"use client";

import React, { useState, useRef } from "react";
import { Search, X } from "lucide-react";

interface GooeyInputProps {
  placeholder?: string;
  onSearch?: (value: string) => void;
  className?: string;
}

export function GooeyInput({ placeholder = "Search...", onSearch, className = "" }: GooeyInputProps) {
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValue(e.target.value);
    onSearch?.(e.target.value);
  };

  const handleClear = () => {
    setValue("");
    onSearch?.("");
    inputRef.current?.focus();
  };

  return (
    <div
      className={`relative flex items-center group ${className}`}
      style={{ filter: focused ? "url(#gooey-filter)" : "none" }}
    >
      {/* SVG filter for gooey effect */}
      <svg width="0" height="0" style={{ position: "absolute" }}>
        <defs>
          <filter id="gooey-filter" x="-20%" y="-50%" width="140%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="blur" />
            <feColorMatrix
              in="blur"
              mode="matrix"
              values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 22 -9"
              result="gooey"
            />
            <feComposite in="SourceGraphic" in2="gooey" operator="atop" />
          </filter>
        </defs>
      </svg>

      {/* Search icon blob */}
      <div
        className={`absolute left-0 flex items-center justify-center rounded-full transition-all duration-500 ${
          focused
            ? "w-9 h-9 bg-white/15 left-0.5"
            : "w-8 h-8 bg-white/10 left-1"
        }`}
      >
        <Search size={13} className="text-zinc-400" />
      </div>

      {/* Input field */}
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={handleChange}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder={placeholder}
        className={`w-full pl-9 pr-7 py-2 text-xs bg-white/5 rounded-full border transition-all duration-300 outline-none text-zinc-300 placeholder:text-zinc-600 ${
          focused
            ? "border-indigo-500/40 bg-white/8 shadow-[0_0_12px_rgba(99,102,241,0.15)] pl-10"
            : "border-white/10 hover:border-white/20"
        }`}
      />

      {/* Clear button */}
      {value && (
        <button
          onClick={handleClear}
          className="absolute right-2 text-zinc-600 hover:text-zinc-300 transition-colors"
        >
          <X size={11} />
        </button>
      )}
    </div>
  );
}
