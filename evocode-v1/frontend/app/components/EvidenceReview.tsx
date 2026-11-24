"use client";

/**
 * app/components/EvidenceReview.tsx — EvoCode V2
 *
 * Renders the four-quadrant Evidence Review panel:
 * - Where: Target route, branch, affected files
 * - Why: Clustered user comments, vote count, synthesized requirement
 * - When: Chronological audit events timeline
 * - Proof: Before / After screenshots, git diff, and live Vercel Preview URL
 */

import React, { useState } from "react";
import {
  ExternalLink,
  MapPin,
  HelpCircle,
  Clock,
  ShieldCheck,
  CheckCircle2,
  FileCode,
  GitBranch,
  Eye,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

interface CommentItem {
  id: number;
  author_name: string;
  body: string;
  upvotes: number;
  created_at: string | null;
}

interface AuditItem {
  id: number;
  stage: string;
  event_type: string;
  payload: Record<string, unknown> | null;
  created_at: string | null;
}

export interface SignalEvidence {
  id: number;
  title: string;
  canonical_summary: string;
  route_path: string | null;
  branch_name: string | null;
  github_pr_url: string | null;
  preview_url: string | null;
  confidence_score: number | null;
  diff_patch: string | null;
  before_img_path: string | null;
  after_img_path: string | null;
  visual_verdict: string | null;
  comments: CommentItem[];
  audit_events: AuditItem[];
}

export default function EvidenceReview({ signal }: { signal: SignalEvidence }) {
  const [showDiff, setShowDiff] = useState(false);

  return (
    <div className="space-y-6">
      {/* Vercel Live Preview Pill banner (if preview_url exists) */}
      {signal.preview_url ? (
        <div className="flex items-center justify-between p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-300">
          <div className="flex items-center gap-3">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-emerald-400">Vercel Preview Deployed</p>
              <p className="text-xs text-emerald-300/80 mt-0.5">Live staging deployment ready for verification.</p>
            </div>
          </div>
          <a
            href={signal.preview_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs font-semibold bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-200 px-4 py-2 rounded-lg transition-colors"
          >
            Open Live Preview <ExternalLink size={13} />
          </a>
        </div>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 1. WHERE */}
        <div className="border border-white/10 rounded-xl bg-[#111111]/60 p-5">
          <div className="flex items-center gap-2 mb-3 text-xs font-bold text-zinc-400 uppercase tracking-wider">
            <MapPin size={14} className="text-indigo-400" />
            Where — Location Context
          </div>
          <div className="space-y-3 text-xs">
            <div>
              <span className="text-zinc-500 block mb-1">Target Route</span>
              <span className="font-mono text-zinc-200 bg-black/40 border border-white/5 px-2.5 py-1 rounded inline-block">
                {signal.route_path || "/"}
              </span>
            </div>
            {signal.branch_name && (
              <div>
                <span className="text-zinc-500 block mb-1">Feature Branch</span>
                <span className="font-mono text-zinc-200 bg-black/40 border border-white/5 px-2.5 py-1 rounded inline-flex items-center gap-1.5">
                  <GitBranch size={12} className="text-purple-400" />
                  {signal.branch_name}
                </span>
              </div>
            )}
            {signal.github_pr_url && (
              <div>
                <span className="text-zinc-500 block mb-1">Pull Request</span>
                <a
                  href={signal.github_pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-indigo-400 hover:text-indigo-300 inline-flex items-center gap-1"
                >
                  View on GitHub <ExternalLink size={11} />
                </a>
              </div>
            )}
          </div>
        </div>

        {/* 2. WHY */}
        <div className="border border-white/10 rounded-xl bg-[#111111]/60 p-5">
          <div className="flex items-center gap-2 mb-3 text-xs font-bold text-zinc-400 uppercase tracking-wider">
            <HelpCircle size={14} className="text-amber-400" />
            Why — Clustered User Voice
          </div>
          <div className="space-y-3">
            <div className="bg-black/40 border border-white/5 p-3 rounded-lg">
              <span className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1 font-semibold">
                Synthesized Canonical Summary
              </span>
              <p className="text-xs text-zinc-200 leading-relaxed">
                {signal.canonical_summary || signal.title}
              </p>
            </div>
            <div className="space-y-1.5 max-h-36 overflow-y-auto">
              <span className="text-[10px] text-zinc-500 uppercase tracking-wider block font-semibold">
                Underlying User Comments ({signal.comments.length})
              </span>
              {signal.comments.slice(0, 4).map((c) => (
                <div key={c.id} className="text-xs text-zinc-400 border-l-2 border-indigo-500/40 pl-2 py-0.5">
                  <span className="text-zinc-300 font-medium">{c.author_name}:</span> &ldquo;{c.body}&rdquo;
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 3. WHEN */}
        <div className="border border-white/10 rounded-xl bg-[#111111]/60 p-5">
          <div className="flex items-center gap-2 mb-3 text-xs font-bold text-zinc-400 uppercase tracking-wider">
            <Clock size={14} className="text-blue-400" />
            When — Audit Trail
          </div>
          <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
            {signal.audit_events.length === 0 ? (
              <p className="text-xs text-zinc-500">No audit events recorded yet.</p>
            ) : (
              signal.audit_events.map((evt) => (
                <div key={evt.id} className="flex items-start gap-2.5 text-xs text-zinc-400">
                  <span className="font-mono text-[10px] text-zinc-600 shrink-0 mt-0.5">
                    {evt.created_at ? new Date(evt.created_at).toLocaleTimeString() : "--:--"}
                  </span>
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-mono border border-white/10 bg-white/5 text-zinc-300 shrink-0">
                    {evt.stage}
                  </span>
                  <span className="text-zinc-300 truncate">{evt.event_type}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* 4. PROOF */}
        <div className="border border-white/10 rounded-xl bg-[#111111]/60 p-5">
          <div className="flex items-center gap-2 mb-3 text-xs font-bold text-zinc-400 uppercase tracking-wider">
            <ShieldCheck size={14} className="text-emerald-400" />
            Proof — Verification Evidence
          </div>
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-400">Confidence:</span>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${
                (signal.confidence_score ?? 0) >= 70
                  ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
                  : "text-orange-400 border-orange-500/30 bg-orange-500/10"
              }`}>
                {signal.confidence_score ?? "--"}%
              </span>
            </div>

            {/* Before / After Preview Images or Placeholders */}
            <div className="grid grid-cols-2 gap-2 text-center text-xs">
              <div className="border border-white/5 bg-black/40 rounded-lg p-3 overflow-hidden">
                <span className="text-zinc-500 block text-[10px] uppercase font-semibold mb-1">Before Change</span>
                {signal.before_img_path ? (
                  <img
                    src={`http://localhost:8000/${signal.before_img_path.replace(/\\/g, "/")}`}
                    alt="Before change"
                    className="w-full h-24 object-cover rounded border border-white/10"
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = "none";
                    }}
                  />
                ) : (
                  <div className="h-16 flex items-center justify-center text-zinc-600 font-mono text-[11px] bg-zinc-900/40 rounded border border-dashed border-zinc-800">
                    Original Build
                  </div>
                )}
              </div>
              <div className="border border-white/5 bg-black/40 rounded-lg p-3 overflow-hidden">
                <span className="text-zinc-500 block text-[10px] uppercase font-semibold mb-1">After Change</span>
                {signal.after_img_path ? (
                  <img
                    src={`http://localhost:8000/${signal.after_img_path.replace(/\\/g, "/")}`}
                    alt="After change"
                    className="w-full h-24 object-cover rounded border border-white/10"
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = "none";
                    }}
                  />
                ) : (
                  <div className="h-16 flex items-center justify-center text-emerald-400/80 font-mono text-[11px] bg-emerald-950/20 rounded border border-dashed border-emerald-900/40">
                    Verified Clean
                  </div>
                )}
              </div>
            </div>

            {/* Visual Verifier Critique / Verdict */}
            {signal.visual_verdict && (
              <div className="p-2.5 rounded-lg bg-emerald-950/20 border border-emerald-500/20 text-[11px] text-emerald-300">
                <span className="font-semibold block text-[10px] uppercase text-emerald-400 mb-0.5">Visual Verifier Verdict:</span>
                {signal.visual_verdict}
              </div>
            )}

            {/* Diff Accordion Toggle */}
            {signal.diff_patch && (
              <div>
                <button
                  onClick={() => setShowDiff(!showDiff)}
                  className="w-full flex items-center justify-between text-xs text-zinc-400 hover:text-white border border-white/10 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 transition-colors"
                >
                  <span className="flex items-center gap-1.5">
                    <FileCode size={12} /> Inspect Git Diff Patch
                  </span>
                  {showDiff ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>
                {showDiff && (
                  <pre className="mt-2 text-[10px] font-mono text-zinc-300 bg-black/70 border border-white/10 rounded-lg p-3 overflow-x-auto max-h-48 whitespace-pre">
                    {signal.diff_patch}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
