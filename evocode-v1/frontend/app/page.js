"use client";

import React from "react";
import Link from "next/link";
import { Spotlight } from "./components/ui/spotlight";
import { BorderBeam } from "./components/ui/border-beam";

export default function Home() {
  return (
    <div className="relative flex flex-col min-h-screen w-full bg-[#050505] text-white font-sans overflow-hidden">
      
      {/* Multiple Spotlight Effects */}
      <Spotlight className="-top-40 left-0 md:left-20 md:-top-20" fill="white" />
      <Spotlight className="-top-40 left-[20%] md:left-[40%] md:-top-10" fill="purple" />
      <Spotlight className="-top-40 right-0 md:right-20 md:-top-20" fill="blue" />

      {/* Navigation */}
      <nav className="relative z-10 flex items-center justify-between px-8 py-6 max-w-7xl mx-auto w-full">
        <div className="flex items-center space-x-3 cursor-pointer hover:opacity-80 transition-opacity animate-pulse duration-1000">
          <div className="w-8 h-8 bg-zinc-800 rounded-md flex items-center justify-center">
            <div className="w-3 h-3 bg-white rounded-sm"></div>
          </div>
          <span className="font-bold text-lg tracking-widest text-white drop-shadow-sm">EVO-CODE</span>
        </div>
        <div className="hidden md:flex items-center space-x-8 text-sm font-medium text-zinc-400">
          <Link href="/developer/triage" className="hover:text-white transition-colors">Dashboard</Link>
          <Link href="/signup" className="hover:text-white transition-colors">Sign in</Link>
        </div>
      </nav>

      {/* Main Content */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-4 pt-20 pb-32 text-center max-w-5xl mx-auto w-full">
        
        {/* Floating Pill - Marquee */}
        <div className="mb-10 flex items-center justify-center w-full max-w-xl">
          <div className="relative flex overflow-hidden bg-[#111111] border border-white/5 rounded-full py-2.5 text-xs text-zinc-400 shadow-2xl backdrop-blur-sm w-full [mask-image:linear-gradient(to_right,transparent,black_10%,black_90%,transparent)]">
            
            {/* Animating Track */}
            <div className="flex w-max animate-marquee whitespace-nowrap hover:[animation-play-state:paused]">
              
              {/* Item Group 1 */}
              <div className="flex items-center justify-around pr-16 min-w-[100%]">
                <span className="ml-8">would love to see cross-post track...</span>
                
                <div className="flex items-center space-x-3 ml-4 pl-4 border-l border-white/10">
                  <span className="flex items-center"><span className="mr-1">♡</span> 3</span>
                  <span className="flex items-center"><span className="mr-1">⎋</span> 0</span>
                  <span className="flex items-center"><span className="mr-1">⇄</span> 2</span>
                </div>

                <div className="flex items-center ml-4 pl-4 border-l border-white/10">
                  <div className="w-5 h-5 rounded-full bg-zinc-700 flex items-center justify-center text-[8px] text-white mr-2">D</div>
                  <span className="text-zinc-300">@darkmode_260</span>
                </div>
                
                <span className="ml-8 text-zinc-500">·</span>
                <span className="ml-8 text-white font-medium">Shipped feature #11!</span>
                
                <div className="flex items-center space-x-3 ml-4 pl-4 border-l border-white/10">
                  <span className="flex items-center"><span className="mr-1">♡</span> 12</span>
                </div>
                
                <div className="flex items-center ml-4 pl-4 border-l border-white/10">
                  <div className="w-5 h-5 rounded-full bg-indigo-500 flex items-center justify-center text-[8px] text-white mr-2">A</div>
                  <span className="text-zinc-300">@alex_dev</span>
                </div>
              </div>
              
              {/* Item Group 2 (Duplicate) */}
              <div className="flex items-center justify-around pr-16 min-w-[100%]">
                <span className="ml-8">would love to see cross-post track...</span>
                
                <div className="flex items-center space-x-3 ml-4 pl-4 border-l border-white/10">
                  <span className="flex items-center"><span className="mr-1">♡</span> 3</span>
                  <span className="flex items-center"><span className="mr-1">⎋</span> 0</span>
                  <span className="flex items-center"><span className="mr-1">⇄</span> 2</span>
                </div>

                <div className="flex items-center ml-4 pl-4 border-l border-white/10">
                  <div className="w-5 h-5 rounded-full bg-zinc-700 flex items-center justify-center text-[8px] text-white mr-2">D</div>
                  <span className="text-zinc-300">@darkmode_260</span>
                </div>
                
                <span className="ml-8 text-zinc-500">·</span>
                <span className="ml-8 text-white font-medium">Shipped feature #11!</span>
                
                <div className="flex items-center space-x-3 ml-4 pl-4 border-l border-white/10">
                  <span className="flex items-center"><span className="mr-1">♡</span> 12</span>
                </div>
                
                <div className="flex items-center ml-4 pl-4 border-l border-white/10">
                  <div className="w-5 h-5 rounded-full bg-indigo-500 flex items-center justify-center text-[8px] text-white mr-2">A</div>
                  <span className="text-zinc-300">@alex_dev</span>
                </div>
              </div>
              
            </div>
          </div>
        </div>

        {/* Headline */}
        <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-8 leading-[1.1]">
          Automate feature delivery <br className="hidden md:block" />
          with your <span className="text-[#FFF5D1] drop-shadow-[0_0_15px_rgba(255,245,209,0.3)]">community</span>
        </h1>

        {/* Subheadline */}
        <p className="text-zinc-400 text-lg md:text-xl max-w-2xl mb-12 leading-relaxed">
          Capture the loudest signals, open issues, draft plans, and push PRs—without leaving your flow.
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row items-center space-y-4 sm:space-y-0 sm:space-x-6">
          <Link 
            href="/developer/triage"
            className="group relative overflow-hidden flex items-center text-sm font-semibold tracking-wider uppercase bg-transparent text-white border border-white/10 px-8 py-3.5 rounded-full hover:bg-white/5 transition-all"
          >
            View Dashboard 
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 ml-2 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
            <BorderBeam size={60} duration={4} delay={0} />
          </Link>
          
          <Link
            href="/signup"
            className="group relative overflow-hidden flex items-center text-sm font-semibold tracking-wider uppercase bg-transparent text-zinc-400 border border-transparent hover:border-white/10 rounded-full hover:text-white px-8 py-3.5 transition-colors"
          >
            Sign In
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 ml-2 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
            <BorderBeam size={60} duration={4} delay={2} />
          </Link>
        </div>
      </main>

    </div>
  );
}
