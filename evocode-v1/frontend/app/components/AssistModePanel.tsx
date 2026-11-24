"use client";

/**
 * app/components/AssistModePanel.tsx — EvoCode V2
 *
 * Rendered when confidence_score < 70 or requires_human is true.
 * Locks autonomous merge and provides the Architectural Strategy Guide.
 */

import React from "react";
import { AlertTriangle, ShieldAlert, Code2, CheckCircle2 } from "lucide-react";

interface AssistModePanelProps {
  guide: string | null;
  confidenceScore: number | null;
  onEditPlan?: () => void;
}

export default function AssistModePanel({
  guide,
  confidenceScore,
  onEditPlan,
}: AssistModePanelProps) {
  return (
    <div className="border border-amber-500/30 rounded-xl bg-amber-500/5 p-6 shadow-xl mb-6">
      <div className="flex items-start gap-3.5 mb-4">
        <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 shrink-0">
          <ShieldAlert size={20} />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-amber-300">
              Assist Mode Activated — Autonomous Merge Locked
            </h3>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-300 font-semibold">
              Confidence: {confidenceScore ?? 0}% &lt; 70% threshold
            </span>
          </div>
          <p className="text-xs text-amber-200/70 mt-1.5 leading-relaxed">
            EvoCode detected a high-impact architectural change (e.g., authentication, database mutations, payments, or multi-file edits).
            Autonomous merging has been locked as a safety guardrail. Review the step-by-step strategy guide below.
          </p>
        </div>
      </div>

      {guide && (
        <div className="mt-4 bg-[#0A0A0A] border border-white/10 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-mono font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
              <Code2 size={13} className="text-amber-400" /> Architectural Strategy Guide
            </span>
          </div>
          <div className="text-xs text-zinc-300 font-mono leading-relaxed max-h-72 overflow-y-auto whitespace-pre-wrap">
            {guide}
          </div>
        </div>
      )}

      {onEditPlan && (
        <div className="mt-4 flex justify-end">
          <button
            onClick={onEditPlan}
            className="text-xs font-semibold px-4 py-2 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-200 transition-colors"
          >
            Edit Implementation Plan
          </button>
        </div>
      )}
    </div>
  );
}
