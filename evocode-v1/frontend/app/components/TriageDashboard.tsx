"use client";

/**
 * TriageDashboard.tsx — V2
 *
 * Fetches FeatureSignals live from GET /api/signals.
 * Zero hardcoded mock data. Shows clean loading/empty/error states.
 */

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { MagicCard } from "./ui/magic-card";
import { AnimatedShinyText } from "./ui/animated-shiny-text";
import { Spotlight } from "./ui/spotlight";
import { GooeyInput } from "./ui/gooey-input";
import { RefreshCw } from "lucide-react";

const BACKEND = "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────
interface Signal {
  id: number;
  title: string;
  canonical_summary: string;
  status: string;
  status_label: string;
  upvote_count: number;
  confidence_score: number | null;
  requires_human: boolean;
  route_path: string | null;
  github_pr_url: string | null;
  preview_url: string | null;
  created_at: string | null;
  updated_at: string | null;
}

// ── Status → badge color mapping ───────────────────────────────────────────
const statusDot: Record<string, string> = {
  gathering_votes:    "bg-blue-400",
  queued:             "bg-amber-400",
  planning:           "bg-amber-400",
  coding:             "bg-violet-400",
  verifying:          "bg-cyan-400",
  pr_ready:           "bg-indigo-400",
  approved_shipped:   "bg-emerald-500",
  assist_mode_blocked:"bg-orange-400",
  failed:             "bg-red-500",
  rejected:           "bg-zinc-500",
};

// Map V2 statuses to filter tab names
const filterMap: Record<string, string[]> = {
  All:       [],
  Active:    ["queued", "planning", "coding", "verifying"],
  "PR Ready": ["pr_ready"],
  Shipped:   ["approved_shipped"],
  "Assist Mode": ["assist_mode_blocked"],
  Failed:    ["failed", "rejected"],
  Collecting: ["gathering_votes"],
};

// ── Component ──────────────────────────────────────────────────────────────
export default function TriageDashboard() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState("All");

  const fetchSignals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${BACKEND}/api/signals?sort=recent`);
      if (!res.ok) throw new Error(`Backend returned ${res.status}`);
      const data: Signal[] = await res.json();
      setSignals(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not load signals");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSignals();
    // Auto-refresh every 15s while the page is open
    const id = setInterval(fetchSignals, 15_000);
    return () => clearInterval(id);
  }, [fetchSignals]);

  // ── Filter + search ───────────────────────────────────────────────────────
  const filteredSignals = signals.filter((s) => {
    const statusList = filterMap[activeFilter] ?? [];
    const matchesFilter = statusList.length === 0 || statusList.includes(s.status);
    const q = searchQuery.toLowerCase();
    const matchesSearch =
      !q ||
      s.title.toLowerCase().includes(q) ||
      (s.canonical_summary || "").toLowerCase().includes(q) ||
      (s.route_path || "").toLowerCase().includes(q);
    return matchesFilter && matchesSearch;
  });

  // ── Stat counts ───────────────────────────────────────────────────────────
  const activeCount = signals.filter((s) =>
    ["queued", "planning", "coding", "verifying"].includes(s.status)
  ).length;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen w-full bg-[#0A0A0A] text-white font-sans overflow-hidden relative">

      {/* Background lighting */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
        <Spotlight className="-top-40 left-0 md:-top-20 md:left-20" fill="white" />
        <Spotlight className="top-20 left-1/2 md:-top-10 md:left-1/2" fill="indigo" />
      </div>

      {/* ── Sidebar ──────────────────────────────────────────────────────── */}
      <aside className="relative z-10 w-64 border-r border-white/10 p-4 flex flex-col hidden md:flex bg-[#0A0A0A]/50 backdrop-blur-xl">
        <Link href="/" className="flex items-center space-x-2 mb-6 px-2 pt-2 group">
          <div className="w-6 h-6 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-md shadow-sm group-hover:scale-110 transition-transform duration-300" />
          <span className="font-bold text-lg tracking-widest text-white drop-shadow-sm">EVO-CODE</span>
        </Link>

        {/* Search */}
        <div className="px-2 mb-6">
          <GooeyInput placeholder="Search signals…" onSearch={setSearchQuery} />
        </div>

        <nav className="flex-1 space-y-1">
          <Link href="/" className="block px-3 py-2 text-sm font-medium text-zinc-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
            Home
          </Link>
          <Link href="/developer/triage" className="block px-3 py-2 text-sm font-medium text-white bg-white/10 rounded-lg transition-colors">
            Signals
          </Link>
          <Link href="/developer/build/new" className="block px-3 py-2 text-sm font-medium text-zinc-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
            + New Feature
          </Link>
          <Link href="/signup" className="block px-3 py-2 text-sm font-medium text-zinc-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
            Settings
          </Link>
        </nav>

        <div className="mt-auto pt-4 border-t border-white/10">
          <div className="flex items-center px-3 py-2">
            <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-xs font-bold mr-3">HA</div>
            <div className="text-sm font-medium text-zinc-300">Hanu Aditya</div>
          </div>
        </div>
      </aside>

      {/* ── Main content ─────────────────────────────────────────────────── */}
      <main className="relative z-10 flex-1 p-8 overflow-y-auto">
        <div className="max-w-7xl mx-auto">

          {/* Pill ticker */}
          <div className="z-10 flex mb-6">
            <div className="group rounded-full border border-white/10 bg-white/5 backdrop-blur-md text-sm text-white transition-all ease-in hover:cursor-pointer hover:bg-white/10">
              <AnimatedShinyText className="inline-flex items-center justify-center px-4 py-1.5 transition ease-out hover:duration-300">
                <span className="mr-3 px-2 py-0.5 rounded-full bg-white/10 text-[10px] uppercase tracking-wider font-semibold text-white">Live</span>
                <span className="text-gray-300">AI reads user comments and ships PRs automatically</span>
                <svg xmlns="http://www.w3.org/2000/svg" className="ml-2 h-3 w-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </AnimatedShinyText>
            </div>
          </div>

          <header className="flex flex-col md:flex-row md:items-start justify-between mb-8">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Signals & Automations</h1>
              <p className="text-zinc-400 mt-1">Live user feedback driving autonomous PR creation.</p>
            </div>

            <div className="flex items-center space-x-4 mt-6 md:mt-0">
              <div className="flex space-x-3 text-sm">
                <div className="flex flex-col items-center bg-zinc-900/50 border border-white/5 px-4 py-1.5 rounded-lg">
                  <span className="text-zinc-400 text-xs uppercase tracking-wider">Total</span>
                  <span className="font-semibold text-lg">{signals.length}</span>
                </div>
                <div className="flex flex-col items-center bg-zinc-900/50 border border-white/5 px-4 py-1.5 rounded-lg">
                  <span className="text-zinc-400 text-xs uppercase tracking-wider">Active</span>
                  <span className="font-semibold text-lg text-violet-400">{activeCount}</span>
                </div>
              </div>

              <button
                onClick={fetchSignals}
                className="p-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 transition-colors"
                title="Refresh"
              >
                <RefreshCw size={14} className={loading ? "animate-spin text-zinc-400" : "text-zinc-400"} />
              </button>

              <Link
                href="/developer/build/new"
                className="bg-white/10 hover:bg-white/20 border border-white/10 text-white font-medium text-sm px-4 py-2.5 rounded-lg transition-colors shadow-sm"
              >
                + New Feature
              </Link>
            </div>
          </header>

          {/* Filter tabs */}
          <div className="mb-4">
            <h2 className="text-xl font-semibold">All Signals</h2>
            <p className="text-zinc-400 text-sm mt-1">Filter by lifecycle and jump into details.</p>
          </div>
          <div className="flex flex-wrap gap-2 items-center border-b border-white/10 pb-4 mb-8">
            {Object.keys(filterMap).map((tab) => (
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

          {/* ── States: loading / error / empty / grid ──────────────────── */}
          {loading && (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4" />
              <p className="text-zinc-500 text-sm">Loading signals from backend…</p>
            </div>
          )}

          {!loading && error && (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <div className="text-4xl mb-3">⚡</div>
              <p className="text-red-400 text-sm font-medium">Failed to load signals</p>
              <p className="text-zinc-600 text-xs mt-1">{error}</p>
              <button
                onClick={fetchSignals}
                className="mt-4 text-xs text-zinc-400 hover:text-white border border-white/10 px-4 py-2 rounded-lg transition-colors"
              >
                Retry
              </button>
            </div>
          )}

          {!loading && !error && filteredSignals.length === 0 && (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <div className="text-4xl mb-3">{searchQuery ? "🔍" : "🤖"}</div>
              {searchQuery ? (
                <>
                  <p className="text-zinc-400 text-sm">No signals match <span className="text-white font-medium">&ldquo;{searchQuery}&rdquo;</span></p>
                  <p className="text-zinc-600 text-xs mt-1">Try a different search term</p>
                </>
              ) : (
                <>
                  <p className="text-zinc-400 text-sm">No signals yet</p>
                  <p className="text-zinc-600 text-xs mt-1">Post a comment on the target site to create the first signal</p>
                  <Link
                    href="/developer/build/new"
                    className="mt-4 text-xs text-indigo-400 hover:text-indigo-300 border border-indigo-500/30 px-4 py-2 rounded-lg transition-colors"
                  >
                    + Submit manually
                  </Link>
                </>
              )}
            </div>
          )}

          {!loading && !error && filteredSignals.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredSignals.map((signal) => (
                <Link href={`/developer/build/${signal.id}`} key={signal.id} className="block group">
                  <MagicCard
                    className="cursor-pointer h-full p-5 bg-[#111111]/80 border-white/10 group-hover:border-white/20"
                    gradientColor="#262626"
                  >
                    {/* Status badge */}
                    <div className="mb-4 flex items-center justify-between">
                      <div className="inline-flex items-center px-2 py-0.5 rounded-full border border-white/10 bg-white/5 text-[10px] font-bold tracking-wider text-zinc-300">
                        <div className={`w-1.5 h-1.5 rounded-full mr-1.5 ${statusDot[signal.status] ?? "bg-zinc-500"}`} />
                        {signal.status_label}
                      </div>
                      {signal.upvote_count > 0 && (
                        <span className="text-[10px] text-zinc-500 flex items-center gap-1">
                          ♡ {signal.upvote_count}
                        </span>
                      )}
                    </div>

                    {/* Title & summary */}
                    <h3 className="font-semibold text-white text-base leading-snug group-hover:text-indigo-300 transition-colors">
                      {signal.title}
                    </h3>
                    <div className="mt-2 flex-1">
                      <p className="text-zinc-400 text-sm line-clamp-3">
                        {signal.canonical_summary || "No description yet."}
                      </p>
                    </div>

                    {/* Footer */}
                    <div className="mt-6 pt-4 border-t border-white/5 flex items-center justify-between">
                      <span className="text-xs text-zinc-500 font-mono">
                        {signal.route_path ?? "/"}
                      </span>
                      <div className="flex items-center space-x-3 text-xs text-zinc-500">
                        {signal.confidence_score !== null && (
                          <span className={`font-medium ${
                            signal.confidence_score >= 70 ? "text-emerald-400" : "text-orange-400"
                          }`}>
                            {signal.confidence_score}% conf.
                          </span>
                        )}
                        {signal.github_pr_url && (
                          <span className="flex items-center gap-1 text-indigo-400">⎋ PR</span>
                        )}
                      </div>
                    </div>
                  </MagicCard>
                </Link>
              ))}
            </div>
          )}

        </div>
      </main>
    </div>
  );
}
