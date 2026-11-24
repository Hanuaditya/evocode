"use client";

/**
 * app/developer/build/[id]/page.tsx — V2
 *
 * Fetches signal details live from GET /api/signals/{id}.
 * Preserves the full V1 two-step build workflow (Plan → Approve & Execute).
 * Adds Confidence Score badge, Assist Mode lock, PR link, and live Vercel preview.
 * Zero hardcoded mock ticket data.
 */

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Check,
  Sparkles,
  GitPullRequest,
  Plus,
  Loader2,
  ExternalLink,
  AlertTriangle,
  MessageCircle,
  ArrowLeft,
  RefreshCw,
  ThumbsUp,
  Eye,
  ShieldCheck,
} from "lucide-react";
import EvidenceReview from "@/components/EvidenceReview";
import AssistModePanel from "@/components/AssistModePanel";
import { RippleButton } from "@/components/ui/ripple-button";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

const BACKEND = "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────
interface Comment {
  id: number;
  author_name: string;
  body: string;
  route_path: string | null;
  upvotes: number;
  is_ai_clarification: boolean;
  created_at: string | null;
}

interface AuditEvent {
  id: number;
  stage: string;
  event_type: string;
  payload: Record<string, unknown> | null;
  created_at: string | null;
}

interface SignalDetail {
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
  plan_markdown: string | null;
  strategy_guide: string | null;
  diff_patch: string | null;
  github_issue_number: number | null;
  github_pr_number: number | null;
  branch_name: string | null;
  error_message: string | null;
  current_step: string | null;
  execution_mode: string;
  comments: Comment[];
  audit_events: AuditEvent[];
  fix_attempts: { attempt_number: number; ast_passed: boolean; tests_passed: boolean; error_log: string | null }[];
}

// ── Pipeline stage states ──────────────────────────────────────────────────
type Stage = "idle" | "creating" | "planning" | "plan_ready" | "executing" | "done" | "error";

// ── Confidence Score badge ─────────────────────────────────────────────────
function ConfidenceBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  const color = score >= 70 ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
                            : "text-orange-400 border-orange-500/30 bg-orange-500/10";
  return (
    <span className={`text-xs font-semibold px-3 py-1 rounded-full border ${color}`}>
      {score >= 70 ? "✓" : "⚠"} {score}% confidence
    </span>
  );
}

// ── Main Page Component ────────────────────────────────────────────────────
export default function IssueDetailPage({ params }: { params: { id: string } }) {
  const signalId = params.id; // could be a numeric V2 signal ID

  // ── Live signal data ──────────────────────────────────────────────────────
  const [signal, setSignal] = useState<SignalDetail | null>(null);
  const [signalLoading, setSignalLoading] = useState(true);
  const [signalError, setSignalError] = useState<string | null>(null);

  // ── Build pipeline state (V1 workflow preserved) ──────────────────────────
  const [stage, setStage] = useState<Stage>("idle");
  const [backendIssueId, setBackendIssueId] = useState<number | null>(null);
  const [planText, setPlanText] = useState("");
  const [activeTab, setActiveTab] = useState<"edit" | "preview">("edit");
  const [prUrl, setPrUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<"build" | "evidence" | "comments" | "audit">("build");

  // ── Fetch signal from live API ─────────────────────────────────────────────
  const fetchSignal = useCallback(async () => {
    if (!signalId || signalId === "new") return;
    setSignalLoading(true);
    setSignalError(null);
    try {
      const res = await fetch(`${BACKEND}/api/signals/${signalId}`);
      if (!res.ok) throw new Error(`Signal not found (${res.status})`);
      const data: SignalDetail = await res.json();
      setSignal(data);
      // Pre-fill plan textarea if a plan already exists in DB
      if (data.plan_markdown && !planText) {
        setPlanText(data.plan_markdown);
      }
      // If signal is already completed, reflect that in stage
      if (data.status === "approved_shipped" && stage === "idle") {
        setStage("done");
        setPrUrl(data.github_pr_url);
      }
    } catch (err: unknown) {
      setSignalError(err instanceof Error ? err.message : "Failed to load signal");
    } finally {
      setSignalLoading(false);
    }
  }, [signalId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchSignal();
  }, [fetchSignal]);

  // ── Determine if this is a V2 signal (numeric id exists in /api/signals) ──
  const isV2Signal = signal !== null;

  // ── Fallback title/description when signal isn't found yet ────────────────
  const displayTitle = signal?.title ?? `Feature #${signalId}`;
  const displayDesc  = signal?.canonical_summary ?? "Loading feature details…";
  const isAssistMode = (signal?.confidence_score ?? 100) < 70 && signal?.requires_human;

  // ── Step 1: Create issue on backend + generate plan ───────────────────────
  const handleBuildClick = async () => {
    setStage("creating");
    setErrorMsg(null);

    try {
      // 1a. Create the issue in the DB
      const reportRes = await fetch(`${BACKEND}/api/report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bug_text: signal?.canonical_summary ?? displayDesc,
          file_path: "app/page.js", // Master layout file controlling global dark mode state
        }),
      });
      if (!reportRes.ok) throw new Error("Failed to create issue on backend");
      const { issue_id } = await reportRes.json();
      setBackendIssueId(issue_id);
      setStage("planning");

      // 1b. Ask Gemini to write the implementation plan
      const planRes = await fetch(`${BACKEND}/api/issues/${issue_id}/plan`, {
        method: "POST",
      });
      if (!planRes.ok) throw new Error("Failed to generate plan");
      const { plan_markdown } = await planRes.json();
      setPlanText(plan_markdown);
      setStage("plan_ready");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Unknown error");
      setStage("error");
    }
  };

  // ── Step 2: Approve plan → fire the agent → poll for PR ──────────────────
  const handleApproveClick = async () => {
    if (!backendIssueId) return;
    setStage("executing");
    setErrorMsg(null);

    try {
      const execRes = await fetch(`${BACKEND}/api/issues/${backendIssueId}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved_plan: planText }),
      });
      if (!execRes.ok) throw new Error("Failed to start execution");

      // Poll every 5s
      const poll = async () => {
        const statusRes = await fetch(`${BACKEND}/api/issues/${backendIssueId}/status`);
        const data = await statusRes.json();
        if (data.status === "completed") {
          setPrUrl(data.pr_url || null);
          setStage("done");
        } else if (data.status === "failed") {
          setErrorMsg(data.error_message || "Agent failed");
          setStage("error");
        } else {
          setTimeout(poll, 5000);
        }
      };
      setTimeout(poll, 5000);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Unknown error");
      setStage("error");
    }
  };

  // ── Step 3: V2 One-Click Auto-Ship & Reject (Phase 5) ────────────────────
  const [shippingLoading, setShippingLoading] = useState(false);
  const [rejectingLoading, setRejectingLoading] = useState(false);
  const [shipMessage, setShipMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleApproveAndShip = async (override = false) => {
    if (!signalId) return;
    setShippingLoading(true);
    setShipMessage(null);
    try {
      const res = await fetch(`${BACKEND}/api/signals/${signalId}/approve?override_confidence=${override}`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Failed to approve signal" }));
        throw new Error(err.detail || `Server error (${res.status})`);
      }
      const data = await res.json();
      setShipMessage({
        type: "success",
        text: `✓ Squash-merged PR, auto-closed issue, deleted branch, and marked Shipped Live! (SHA: ${data.merge_sha ? data.merge_sha.slice(0, 7) : "verified"})`,
      });
      await fetchSignal();
    } catch (err: unknown) {
      setShipMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Approval failed",
      });
    } finally {
      setShippingLoading(false);
    }
  };

  const handleRejectAndClose = async () => {
    if (!signalId) return;
    setRejectingLoading(true);
    setShipMessage(null);
    try {
      const res = await fetch(`${BACKEND}/api/signals/${signalId}/reject`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Failed to reject signal" }));
        throw new Error(err.detail || `Server error (${res.status})`);
      }
      setShipMessage({
        type: "success",
        text: "Closed Pull Request and deleted feature branch.",
      });
      await fetchSignal();
    } catch (err: unknown) {
      setShipMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Rejection failed",
      });
    } finally {
      setRejectingLoading(false);
    }
  };

  // ── Derived pipeline helpers ──────────────────────────────────────────────
  const isBuilding = stage === "creating" || stage === "planning";
  const planReady  = ["plan_ready", "executing", "done"].includes(stage);

  const pipelineLabel =
    stage === "idle"       ? "PENDING"      :
    stage === "creating"   ? "PROVISIONING" :
    stage === "planning"   ? "PLANNING"     :
    stage === "plan_ready" ? `ISSUE #${backendIssueId}` :
    stage === "executing"  ? "EXECUTING"    :
    stage === "done"       ? "DONE"         :
    "ERROR";

  // ── Loading / error state for signal fetch ────────────────────────────────
  if (signalLoading) {
    return (
      <div className="flex h-screen w-full bg-[#0A0A0A] text-white items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-zinc-500 text-sm">Loading signal…</p>
        </div>
      </div>
    );
  }

  if (signalError && !signal) {
    return (
      <div className="flex h-screen w-full bg-[#0A0A0A] text-white items-center justify-center">
        <div className="text-center max-w-md">
          <div className="text-4xl mb-4">⚡</div>
          <p className="text-red-400 font-medium mb-2">Signal not found</p>
          <p className="text-zinc-500 text-sm mb-6">{signalError}</p>
          <Link href="/developer/triage" className="text-xs text-indigo-400 hover:text-indigo-300 border border-indigo-500/30 px-4 py-2 rounded-lg">
            ← Back to dashboard
          </Link>
        </div>
      </div>
    );
  }

  // ── Main render ───────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen w-full bg-[#0A0A0A] text-white font-sans overflow-hidden">

      {/* ── Sidebar ────────────────────────────────────────────────────── */}
      <div className="w-64 border-r border-white/10 p-4 flex flex-col bg-transparent relative z-10">
        <div className="flex items-center justify-between mb-8">
          <Link href="/developer/triage" className="font-bold tracking-widest text-white flex items-center group">
            <div className="w-6 h-6 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-md mr-2 group-hover:scale-110 transition-transform" />
            EVO-CODE
          </Link>
        </div>
        <div className="space-y-1">
          <div className="text-xs font-semibold text-zinc-500 tracking-wider mb-2 px-3">SIGNALS</div>
          <Link href="/developer/triage" className="block text-sm text-white bg-white/10 px-3 py-2 rounded-md">All Signals</Link>
          <Link href="/developer/triage?filter=Completed" className="block text-sm text-zinc-400 px-3 py-2 hover:text-white rounded-md hover:bg-white/5 transition-colors">Shipped</Link>
          <Link href="/signup" className="block text-sm text-zinc-400 px-3 py-2 hover:text-white rounded-md hover:bg-white/5 transition-colors">Settings</Link>
        </div>
      </div>

      {/* ── Main content ─────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-10 relative z-10">
        <div className="max-w-5xl mx-auto">

          {/* Breadcrumb */}
          <Breadcrumb className="mb-6">
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink asChild>
                  <Link href="/" className="text-zinc-500 hover:text-white transition-colors">Home</Link>
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbLink asChild>
                  <Link href="/developer/triage" className="text-zinc-500 hover:text-white transition-colors">Signals</Link>
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage className="text-zinc-300">{displayTitle}</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>

          {/* Header */}
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-2">
              <span className="text-xs font-bold tracking-widest text-zinc-500">SIGNAL #{signal?.id}</span>
              {signal && <ConfidenceBadge score={signal.confidence_score} />}
              {signal?.upvote_count != null && signal.upvote_count > 0 && (
                <span className="text-xs text-zinc-500 flex items-center gap-1">
                  <ThumbsUp size={11} /> {signal.upvote_count} votes
                </span>
              )}
              <button onClick={fetchSignal} className="ml-auto p-1.5 rounded-md hover:bg-white/5 transition-colors">
                <RefreshCw size={12} className="text-zinc-500" />
              </button>
            </div>
            <h1 className="text-3xl font-semibold mt-2">{displayTitle}</h1>
            <p className="text-zinc-400 mt-2 text-sm max-w-3xl">{displayDesc}</p>
            {signal?.route_path && (
              <p className="text-zinc-600 text-xs mt-1 font-mono">{signal.route_path}</p>
            )}
          </div>

          {/* ── Phase 5: One-Click Production Auto-Ship Gate ───────────────── */}
          {signal?.status === "pr_ready" && (
            <div className="mb-8 p-5 rounded-xl border border-indigo-500/40 bg-gradient-to-r from-indigo-950/40 via-purple-950/20 to-black/60 shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                  </span>
                  <span className="text-xs font-bold uppercase tracking-wider text-emerald-400">
                    Autonomous PR Ready for Deployment
                  </span>
                </div>
                <p className="text-sm text-zinc-300">
                  Tests, build, and visual verifier have passed. Inspect evidence and ship with one click.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={handleRejectAndClose}
                  disabled={rejectingLoading || shippingLoading}
                  className="px-4 py-2 rounded-lg text-xs font-semibold border border-red-500/30 hover:border-red-500/50 bg-red-500/10 hover:bg-red-500/20 text-red-300 transition-colors disabled:opacity-50"
                >
                  {rejectingLoading ? "Closing…" : "Reject & Close"}
                </button>

                {(signal.confidence_score ?? 0) < 70 ? (
                  <button
                    onClick={() => handleApproveAndShip(true)}
                    disabled={shippingLoading || rejectingLoading}
                    className="px-5 py-2 rounded-lg text-xs font-bold bg-amber-600 hover:bg-amber-500 text-white shadow-lg transition-all disabled:opacity-50 flex items-center gap-1.5"
                    title="Confidence score < 70 requires manual override"
                  >
                    {shippingLoading ? (
                      <span className="flex items-center gap-1.5"><Loader2 size={13} className="animate-spin" /> Shipping…</span>
                    ) : (
                      <span>Override & Ship 🚀</span>
                    )}
                  </button>
                ) : (
                  <button
                    onClick={() => handleApproveAndShip(false)}
                    disabled={shippingLoading || rejectingLoading}
                    className="px-5 py-2 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-950/50 transition-all disabled:opacity-50 flex items-center gap-1.5"
                  >
                    {shippingLoading ? (
                      <span className="flex items-center gap-1.5"><Loader2 size={13} className="animate-spin" /> Shipping…</span>
                    ) : (
                      <span>Approve & Ship 🚀</span>
                    )}
                  </button>
                )}
              </div>
            </div>
          )}

          {signal?.status === "approved_shipped" && (
            <div className="mb-8 p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <Check size={18} className="text-emerald-400" />
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-emerald-400">Shipped Live to Production</p>
                  <p className="text-xs text-emerald-300/80 mt-0.5">
                    PR squash-merged, remote branch deleted, and live badges updated.
                  </p>
                </div>
              </div>
              {signal.github_pr_url && (
                <a
                  href={signal.github_pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs font-semibold underline hover:text-emerald-200"
                >
                  View Merged PR ↗
                </a>
              )}
            </div>
          )}

          {signal?.status === "rejected" && (
            <div className="mb-8 p-4 rounded-xl border border-zinc-700 bg-zinc-900/60 text-zinc-400 flex items-center gap-2.5">
              <AlertTriangle size={18} className="text-zinc-500" />
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-zinc-300">Signal Rejected</p>
                <p className="text-xs text-zinc-500 mt-0.5">Pull Request closed and feature branch deleted.</p>
              </div>
            </div>
          )}

          {shipMessage && (
            <div
              className={`mb-8 p-3.5 rounded-xl border text-xs ${
                shipMessage.type === "success"
                  ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                  : "bg-red-500/10 border-red-500/30 text-red-300"
              }`}
            >
              {shipMessage.text}
            </div>
          )}

          {/* Section tabs */}
          <div className="flex gap-2 border-b border-white/10 pb-4 mb-6">
            {(["build", "evidence", "comments", "audit"] as const).map((sec) => (
              <button
                key={sec}
                onClick={() => setActiveSection(sec)}
                className={`text-sm px-4 py-1.5 rounded-full transition-colors capitalize ${
                  activeSection === sec
                    ? "bg-white/10 text-white font-medium"
                    : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {sec === "build"    && <span className="flex items-center gap-1.5"><GitPullRequest size={12} />{sec}</span>}
                {sec === "evidence" && <span className="flex items-center gap-1.5"><ShieldCheck size={12} />Evidence Review</span>}
                {sec === "comments" && <span className="flex items-center gap-1.5"><MessageCircle size={12} />Comments ({signal?.comments.length ?? 0})</span>}
                {sec === "audit"    && <span className="flex items-center gap-1.5"><Eye size={12} />Audit Log ({signal?.audit_events.length ?? 0})</span>}
              </button>
            ))}
          </div>

          {/* ═══════════════════ BUILD TAB ══════════════════════════════ */}
          {activeSection === "build" && (
            <>
              {/* Assist Mode Panel */}
              {isAssistMode && signal?.strategy_guide && (
                <AssistModePanel
                  guide={signal.strategy_guide}
                  confidenceScore={signal.confidence_score}
                />
              )}

              {/* Build Pipeline Card */}
              <div className="border border-white/10 rounded-xl bg-[#111111]/50 p-6 shadow-xl">
                <div className="flex justify-between items-center border-b border-white/5 pb-4">
                  <div>
                    <h2 className="text-xs font-bold tracking-widest text-zinc-500">BUILD PIPELINE</h2>
                    <p className="text-sm text-zinc-400 mt-1">Plan → Approve → Agent codes → PR opened.</p>
                  </div>
                  <div className={`text-xs font-semibold px-3 py-1 rounded-full border ${
                    stage === "error" ? "text-red-400 border-red-500/30 bg-red-500/10" :
                    stage === "done"  ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10" :
                    "text-zinc-400 border-white/10 bg-white/5"
                  }`}>
                    {pipelineLabel}
                  </div>
                </div>

                {/* Idle: show BUILD button (locked if assist mode) */}
                {stage === "idle" && (
                  isAssistMode ? (
                    <div className="mt-6 flex items-center gap-3 text-sm text-orange-400">
                      <AlertTriangle size={16} />
                      Execution locked — confidence score below 70. Review the Assist Mode guide above.
                    </div>
                  ) : (
                    <RippleButton
                      onClick={handleBuildClick}
                      rippleColor="#6366f1"
                      className="mt-6 text-sm font-medium text-zinc-400 hover:text-white bg-white/5 hover:bg-white/10 border border-white/10 px-4 py-2 rounded-md transition-all"
                    >
                      <Plus size={16} className="mr-2 inline" /> BUILD
                    </RippleButton>
                  )
                )}

                {/* Building state */}
                {isBuilding && (
                  <div className="mt-6 flex items-center text-sm text-zinc-400">
                    <Loader2 size={16} className="mr-3 animate-spin" />
                    {stage === "creating" ? "Creating issue on backend…" : "Gemini is writing your implementation plan…"}
                  </div>
                )}

                {/* Error state */}
                {stage === "error" && (
                  <div className="mt-6 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-4">
                    ⚠️ {errorMsg}
                  </div>
                )}

                {/* Step stepper */}
                {planReady && (
                  <div className="flex items-center justify-between w-full mt-6">
                    <div className="flex-1 flex items-center p-4 rounded-xl border border-white/10 bg-white/[0.02] opacity-70">
                      <div className="h-8 w-8 rounded-full bg-emerald-500/10 flex items-center justify-center mr-4 border border-emerald-500/20">
                        <Check size={16} className="text-emerald-500" />
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-white">Issue created</div>
                        <div className="text-xs text-zinc-500 mt-0.5">#{backendIssueId} in DB</div>
                      </div>
                    </div>

                    <div className="w-6 h-[1px] bg-white/10 mx-2" />

                    <div className={`flex-1 flex items-center p-4 rounded-xl border transition-all ${
                      stage === "plan_ready" ? "border-zinc-600 bg-zinc-800/40" : "border-white/10 bg-white/[0.02] opacity-70"
                    }`}>
                      <div className="h-8 w-8 rounded-full bg-amber-500/10 flex items-center justify-center mr-4 border border-amber-500/20">
                        {stage === "plan_ready" ? <Sparkles size={16} className="text-amber-500" /> : <Check size={16} className="text-emerald-500" />}
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-white">Plan ready</div>
                        <div className="text-xs text-zinc-400 mt-0.5">Review & approve below</div>
                      </div>
                    </div>

                    <div className="w-6 h-[1px] bg-white/10 mx-2" />

                    <div className={`flex-1 flex items-center p-4 rounded-xl border transition-all ${
                      stage === "done"      ? "border-emerald-500/30 bg-emerald-500/5" :
                      stage === "executing" ? "border-zinc-600 bg-zinc-800/40" :
                      "border-white/5 bg-transparent opacity-40 grayscale"
                    }`}>
                      <div className="h-8 w-8 rounded-full bg-white/5 flex items-center justify-center mr-4 border border-white/10">
                        {stage === "executing" ? <Loader2 size={16} className="text-zinc-400 animate-spin" /> :
                         stage === "done"      ? <Check size={16} className="text-emerald-400" /> :
                         <GitPullRequest size={16} className="text-zinc-400" />}
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-white">PR opened</div>
                        <div className="text-xs text-zinc-500 mt-0.5">
                          {stage === "executing" ? "Agent is coding…" : "Review & merge"}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* PR link (once done) */}
              {(stage === "done" || signal?.github_pr_url) && (prUrl ?? signal?.github_pr_url) && (
                <a
                  href={(prUrl ?? signal?.github_pr_url)!}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-4 flex items-center gap-2 text-sm font-medium text-emerald-400 hover:text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 px-4 py-3 rounded-xl transition-colors"
                >
                  <GitPullRequest size={16} /> View Pull Request on GitHub
                  <ExternalLink size={13} className="ml-auto" />
                </a>
              )}

              {/* Vercel Preview URL */}
              {signal?.preview_url && (
                <a
                  href={signal.preview_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 flex items-center gap-2 text-sm font-medium text-indigo-400 hover:text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 px-4 py-3 rounded-xl transition-colors"
                >
                  <Eye size={16} /> Open Vercel Preview
                  <ExternalLink size={13} className="ml-auto" />
                </a>
              )}

              {/* Plan Review (editable textarea) */}
              {planReady && (
                <div className="mt-6 border border-white/10 rounded-xl bg-[#111111]/50 p-6 shadow-xl">
                  <div className="flex justify-between items-center mb-6">
                    <div>
                      <h2 className="text-xs font-bold tracking-widest text-zinc-500">PLAN REVIEW</h2>
                      <p className="text-sm text-zinc-400 mt-1">Edit the plan and approve to execute.</p>
                    </div>
                    <RippleButton
                      onClick={handleApproveClick}
                      disabled={stage !== "plan_ready"}
                      rippleColor="#818cf8"
                      className={`px-4 py-2 rounded-md text-xs font-semibold border transition-all ${
                        stage === "plan_ready"
                          ? "border-indigo-500/40 bg-indigo-500/20 text-indigo-300 hover:bg-indigo-500/30"
                          : "border-white/10 bg-white/5 text-zinc-500 cursor-not-allowed"
                      }`}
                    >
                      {stage === "executing" ? (
                        <span className="flex items-center gap-2"><Loader2 size={12} className="animate-spin" />EXECUTING…</span>
                      ) : stage === "done" ? "✓ APPROVED" : "APPROVE PLAN"}
                    </RippleButton>
                  </div>

                  <div className="flex space-x-2 mb-4 border-b border-white/10 pb-2">
                    {(["edit", "preview"] as const).map((t) => (
                      <button
                        key={t}
                        onClick={() => setActiveTab(t)}
                        className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-colors ${activeTab === t ? "bg-white text-black" : "text-zinc-500 hover:text-white"}`}
                      >
                        {t.charAt(0).toUpperCase() + t.slice(1)}
                      </button>
                    ))}
                  </div>

                  {activeTab === "edit" ? (
                    <textarea
                      className="w-full bg-[#0A0A0A] border border-white/5 rounded-lg p-6 font-mono text-xs text-zinc-300 h-[280px] overflow-y-auto leading-relaxed focus:outline-none focus:border-indigo-500/50 resize-none"
                      value={planText}
                      onChange={(e) => setPlanText(e.target.value)}
                      disabled={stage !== "plan_ready"}
                    />
                  ) : (
                    <div className="bg-[#0A0A0A] border border-white/5 rounded-lg p-6 text-sm text-zinc-200 h-[280px] overflow-y-auto leading-relaxed">
                      {planText.split("\n").map((line, i) => {
                        if (line.startsWith("# "))  return <h1 key={i} className="text-xl font-bold text-white mb-3">{line.substring(2)}</h1>;
                        if (line.startsWith("## ")) return <h2 key={i} className="text-sm font-bold text-white mt-4 mb-2 uppercase tracking-wider text-indigo-300">{line.substring(3)}</h2>;
                        if (line.startsWith("- "))  return <li key={i} className="ml-4 list-disc text-zinc-400 mb-1 font-mono text-xs">{line.substring(2)}</li>;
                        if (line.trim() === "")      return <br key={i} />;
                        return <p key={i} className="mb-2 text-zinc-300 text-sm">{line}</p>;
                      })}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {/* ═══════════════════ EVIDENCE REVIEW TAB ════════════════════ */}
          {activeSection === "evidence" && signal && (
            <EvidenceReview signal={signal as any} />
          )}

          {/* ═══════════════════ COMMENTS TAB ═══════════════════════════ */}
          {activeSection === "comments" && (
            <div className="border border-white/10 rounded-xl bg-[#111111]/50 p-6 shadow-xl">
              <h2 className="text-xs font-bold tracking-widest text-zinc-500 mb-6">USER COMMENTS</h2>
              {!signal?.comments.length ? (
                <p className="text-zinc-500 text-sm">No comments yet for this signal.</p>
              ) : (
                <div className="space-y-4">
                  {signal.comments.map((c) => (
                    <div key={c.id} className={`flex gap-3 ${c.is_ai_clarification ? "opacity-70" : ""}`}>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${
                        c.is_ai_clarification ? "bg-indigo-500/20 text-indigo-300" : "bg-zinc-800 text-zinc-300"
                      }`}>
                        {c.is_ai_clarification ? "🤖" : c.author_name.charAt(0).toUpperCase()}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-medium text-white">{c.author_name}</span>
                          {c.is_ai_clarification && <span className="text-[9px] bg-indigo-500/20 text-indigo-300 px-1.5 py-0.5 rounded-full">AI Reply</span>}
                          <span className="text-zinc-600 text-xs ml-auto">{c.created_at ? new Date(c.created_at).toLocaleString() : ""}</span>
                        </div>
                        <p className="text-sm text-zinc-300">{c.body}</p>
                        {c.upvotes > 0 && <p className="text-xs text-zinc-600 mt-1">♡ {c.upvotes}</p>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ═══════════════════ AUDIT LOG TAB ══════════════════════════ */}
          {activeSection === "audit" && (
            <div className="border border-white/10 rounded-xl bg-[#111111]/50 p-6 shadow-xl">
              <h2 className="text-xs font-bold tracking-widest text-zinc-500 mb-6">AUDIT LOG — WHEN</h2>
              {!signal?.audit_events.length ? (
                <p className="text-zinc-500 text-sm">No audit events recorded yet.</p>
              ) : (
                <div className="space-y-3">
                  {signal.audit_events.map((ev) => (
                    <div key={ev.id} className="flex items-start gap-3 text-xs font-mono">
                      <span className="text-zinc-600 shrink-0 w-20">{ev.created_at ? new Date(ev.created_at).toLocaleTimeString() : ""}</span>
                      <span className={`shrink-0 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${
                        ev.stage === "triage" ? "bg-blue-500/20 text-blue-300" :
                        ev.stage === "plan"   ? "bg-amber-500/20 text-amber-300" :
                        ev.stage === "code"   ? "bg-violet-500/20 text-violet-300" :
                        ev.stage === "test"   ? "bg-cyan-500/20 text-cyan-300" :
                        ev.stage === "pr"     ? "bg-indigo-500/20 text-indigo-300" :
                        ev.stage === "deploy" ? "bg-emerald-500/20 text-emerald-300" :
                        "bg-zinc-800 text-zinc-400"
                      }`}>{ev.stage}</span>
                      <span className="text-zinc-300">{ev.event_type}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
