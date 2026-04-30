"use client";

import React, { useState } from "react";
import Link from "next/link";
import { MagicCard } from "./ui/magic-card";
import { AnimatedShinyText } from "./ui/animated-shiny-text";
import { Spotlight } from "./ui/spotlight";
import { GooeyInput } from "./ui/gooey-input";

// 2. Define the REAL Data Interface & State
const tickets = [
  { 
    id: 11, 
    title: "Update About Component Heading", 
    description: "Change the main heading text from 'About me' to 'About Hanu Aditya' while preserving Tailwind classes.", 
    status: "COMPLETED", 
    color: "bg-emerald-500",
    timestamp: "Last: 2026-04-26T01:15:00Z"
  },
  { 
    id: 12, 
    title: "Add Achievements Section", 
    description: "Add a new section dedicated to 'Achievements' matching the existing grid layout and styling.", 
    status: "COMPLETED", 
    color: "bg-emerald-500",
    timestamp: "Last: 2026-04-26T01:25:00Z"
  },
  { 
    id: 13, 
    title: "Grid Layout Fix for Achievements", 
    description: "Update grid-cols-3 to lg:grid-cols-4 to fix the orphan card layout caught by CodeRabbit review.", 
    status: "PENDING", 
    color: "bg-blue-500",
    timestamp: "Last: 2026-04-26T01:30:00Z"
  },
  { 
    id: 14, 
    title: "Implement Dark Mode Theme", 
    description: "Implement a dark mode theme option to reduce eye strain and enhance readability for users.", 
    status: "DRAFT", 
    color: "bg-zinc-500",
    timestamp: "Last: 2026-04-26T01:30:44Z"
  },
  { 
    id: 15, 
    title: "Remove Achievements Section", 
    description: "Remove the Achievements section entirely from the portfolio page and revert the grid back to lg:grid-cols-3 to keep the layout clean.", 
    status: "COMPLETED", 
    color: "bg-emerald-500",
    timestamp: "Last: 2026-04-26T02:35:00Z"
  }
];

export default function TriageDashboard() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState("All");

  const filteredTickets = tickets.filter((t) => {
    const matchesSearch =
      t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter =
      activeFilter === "All" ||
      t.status.toLowerCase() === activeFilter.toLowerCase();
    return matchesSearch && matchesFilter;
  });

  return (
    // 3. Page Layout
    <div className="flex h-screen w-full bg-[#0A0A0A] text-white font-sans overflow-hidden relative">
      
      {/* Premium Background Lighting */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
        <Spotlight 
          className="-top-40 left-0 md:-top-20 md:left-20 animate-[spotlight-breathe_8s_ease-in-out_infinite]" 
          fill="white" 
        />
        <Spotlight 
          className="top-20 left-1/2 md:-top-10 md:left-1/2 animate-[spotlight-breathe_12s_ease-in-out_infinite]" 
          fill="indigo" 
        />
      </div>

      {/* Sidebar */}
      <aside className="relative z-10 w-64 border-r border-white/10 p-4 flex flex-col hidden md:flex bg-[#0A0A0A]/50 backdrop-blur-xl">
        <Link href="/" className="flex items-center space-x-2 mb-6 px-2 pt-2 group">
          <div className="w-6 h-6 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-md shadow-sm group-hover:scale-110 transition-transform duration-300"></div>
          <span className="font-bold text-lg tracking-widest text-white drop-shadow-sm group-hover:translate-x-1 transition-transform duration-300">EVO-CODE</span>
        </Link>

        {/* Search */}
        <div className="px-2 mb-6">
          <GooeyInput
            placeholder="Search features..."
            onSearch={setSearchQuery}
          />
        </div>
        
        <nav className="flex-1 space-y-1">
          <Link href="/" className="block px-3 py-2 text-sm font-medium text-zinc-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
            Home
          </Link>
          <Link href="/developer/triage" className="block px-3 py-2 text-sm font-medium text-white bg-white/10 rounded-lg transition-colors">
            Features
          </Link>
          <button
            onClick={() => alert("Automations coming soon! 🚀")}
            className="w-full text-left block px-3 py-2 text-sm font-medium text-zinc-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
          >
            Automations
          </button>
          <Link href="/signup" className="block px-3 py-2 text-sm font-medium text-zinc-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
            Settings
          </Link>
        </nav>
        
        <div className="mt-auto pt-4 border-t border-white/10">
          <div className="flex items-center px-3 py-2">
            <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-xs font-bold mr-3">
              HA
            </div>
            <div className="text-sm font-medium text-zinc-300">Hanu Aditya</div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="relative z-10 flex-1 p-8 overflow-y-auto">
        <div className="max-w-7xl mx-auto">
          
          {/* 4. Main Content Header & Filters */}
          <div className="mb-8">
            
            {/* The Pill Ticker */}
            <div className="z-10 flex mb-6">
              <div className="group rounded-full border border-white/10 bg-white/5 backdrop-blur-md text-sm text-white transition-all ease-in hover:cursor-pointer hover:bg-white/10">
                <AnimatedShinyText className="inline-flex items-center justify-center px-4 py-1.5 transition ease-out hover:duration-300">
                  <span className="mr-3 px-2 py-0.5 rounded-full bg-white/10 text-[10px] uppercase tracking-wider font-semibold text-white">
                    New
                  </span>
                  <span className="text-gray-300">Would love to see cross-post track...</span>
                  <svg xmlns="http://www.w3.org/2000/svg" className="ml-2 h-3 w-3 text-gray-400 transition-transform duration-300 ease-in-out group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </AnimatedShinyText>
              </div>
            </div>

            <header className="flex flex-col md:flex-row md:items-start justify-between mb-8">
              <div>
                <h1 className="text-3xl font-bold tracking-tight">Automations & signals</h1>
                <p className="text-zinc-400 mt-1">Snapshot of everything running right now.</p>
              </div>
              
              <div className="flex items-center space-x-4 mt-6 md:mt-0">
                <div className="flex space-x-3 text-sm">
                  <div className="flex flex-col items-center bg-zinc-900/50 border border-white/5 px-4 py-1.5 rounded-lg">
                    <span className="text-zinc-400 text-xs uppercase tracking-wider">Features</span>
                    <span className="font-semibold text-lg">10</span>
                  </div>
                  <div className="flex flex-col items-center bg-zinc-900/50 border border-white/5 px-4 py-1.5 rounded-lg">
                    <span className="text-zinc-400 text-xs uppercase tracking-wider">Signals</span>
                    <span className="font-semibold text-lg">20</span>
                  </div>
                </div>
                <Link
                  href="/developer/build/new"
                  className="bg-white/10 hover:bg-white/20 border border-white/10 text-white font-medium text-sm px-4 py-2.5 rounded-lg transition-colors shadow-sm h-full flex items-center"
                >
                  + New Feature
                </Link>
              </div>
            </header>

            <div>
              <div className="mb-4">
                <h2 className="text-xl font-semibold">All Features</h2>
                <p className="text-zinc-400 text-sm mt-1">Filter by lifecycle and jump into details.</p>
              </div>
              
              <div className="flex flex-wrap gap-2 items-center border-b border-white/10 pb-4">
                {["All", "Active", "Pending", "Draft", "Paused", "Completed", "Failed"].map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveFilter(tab)}
                    className={`text-sm px-3 py-1.5 rounded-full transition-colors ${
                      activeFilter === tab
                        ? "bg-white/10 text-white border border-white/10 font-medium"
                        : "text-zinc-500 hover:text-zinc-300 hover:bg-white/5"
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* 5. The Magic Card Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-8">
            {filteredTickets.length === 0 ? (
              <div className="col-span-3 flex flex-col items-center justify-center py-20 text-center">
                <div className="text-4xl mb-3">🔍</div>
                <p className="text-zinc-400 text-sm">No features match <span className="text-white font-medium">&ldquo;{searchQuery}&rdquo;</span></p>
                <p className="text-zinc-600 text-xs mt-1">Try a different search term</p>
              </div>
            ) : (
              filteredTickets.map((ticket) => (
                <Link href={`/developer/build/${ticket.id}`} key={ticket.id} className="block group">
                  <MagicCard 
                    className="cursor-pointer h-full p-5 bg-[#111111]/80 border-white/10 group-hover:border-white/20" 
                    gradientColor="#262626"
                  >
                    {/* Top: Status Badge */}
                    <div className="mb-4">
                      <div className={`inline-flex items-center px-2 py-0.5 rounded-full border border-white/10 bg-white/5 text-[10px] font-bold tracking-wider text-zinc-300`}>
                        <div className={`w-1.5 h-1.5 rounded-full mr-1.5 ${ticket.color}`}></div>
                        {ticket.status}
                      </div>
                    </div>

                    {/* Middle: Title & Description */}
                    <h3 className="font-semibold text-white text-base leading-snug group-hover:text-indigo-300 transition-colors">
                      {ticket.title}
                    </h3>
                    <div className="mt-2 flex-1">
                      <p className="text-zinc-400 text-sm line-clamp-3">
                        {ticket.description}
                      </p>
                    </div>

                    {/* Bottom: Timestamp & Metrics */}
                    <div className="mt-6 pt-4 border-t border-white/5 flex items-center justify-between">
                      <span className="text-xs text-zinc-500 font-mono">{ticket.timestamp}</span>
                      <div className="flex items-center space-x-3 text-xs text-zinc-500">
                        <span className="flex items-center"><span className="mr-1">📄</span> 1</span>
                        <span className="flex items-center"><span className="mr-1">♡</span> 1</span>
                        <span className="flex items-center"><span className="mr-1">⎋</span> 0</span>
                      </div>
                    </div>
                  </MagicCard>
                </Link>
              ))
            )}
          </div>
          
        </div>
      </main>
    </div>
  );
}
