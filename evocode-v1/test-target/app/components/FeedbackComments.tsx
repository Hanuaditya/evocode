"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";

interface CommentItem {
  id: number;
  signal_id: number | null;
  author_name: string;
  body: string;
  route_path: string | null;
  upvotes: number;
  is_ai_clarification: boolean;
  signal_status: string | null;
  raw_status?: string | null;
  pr_url?: string | null;
  preview_url?: string | null;
  created_at: string | null;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_EVOCODE_BACKEND || "http://localhost:8000";

export default function FeedbackComments() {
  const [comments, setComments] = useState<CommentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [authorName, setAuthorName] = useState("");
  const [commentBody, setCommentBody] = useState("");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [aiReply, setAiReply] = useState<string | null>(null);
  const [voterFingerprint, setVoterFingerprint] = useState<string>("");

  const consoleErrorsRef = useRef<string[]>([]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      let fp = localStorage.getItem("evocode_voter_fp");
      if (!fp) {
        fp = "voter_" + Math.random().toString(36).substring(2, 12) + "_" + Date.now().toString(36);
        localStorage.setItem("evocode_voter_fp", fp);
      }
      setVoterFingerprint(fp);

      const originalConsoleError = console.error;
      console.error = (...args: unknown[]) => {
        try {
          const serialized = args.map((a) => (typeof a === "object" ? JSON.stringify(a) : String(a))).join(" ");
          consoleErrorsRef.current.push(serialized.slice(0, 300));
          if (consoleErrorsRef.current.length > 5) consoleErrorsRef.current.shift();
        } catch {}
        originalConsoleError.apply(console, args);
      };

      const errorHandler = (event: ErrorEvent) => {
        try {
          consoleErrorsRef.current.push(`${event.message} at ${event.filename}:${event.lineno}`);
          if (consoleErrorsRef.current.length > 5) consoleErrorsRef.current.shift();
        } catch {}
      };

      window.addEventListener("error", errorHandler);
      return () => {
        console.error = originalConsoleError;
        window.removeEventListener("error", errorHandler);
      };
    }
  }, []);

  const fetchComments = useCallback(async () => {
    setLoading(true);
    try {
      const currentRoute = typeof window !== "undefined" ? window.location.pathname || "/" : "/";
      const res = await fetch(`${BACKEND_URL}/api/comments?route=${encodeURIComponent(currentRoute)}`);
      if (res.ok) {
        const data: CommentItem[] = await res.json();
        setComments(data);
      }
    } catch {
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchComments();
    const interval = setInterval(fetchComments, 10000);
    return () => clearInterval(interval);
  }, [fetchComments]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentBody.trim() || !authorName.trim()) return;

    setSubmitting(true);
    setStatusMessage(null);
    setAiReply(null);

    const currentRoute = typeof window !== "undefined" ? window.location.pathname || "/" : "/";
    try {
      const res = await fetch(`${BACKEND_URL}/api/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          author_name: authorName.trim(),
          body: commentBody.trim(),
          route_path: currentRoute,
          console_errors: consoleErrorsRef.current,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setCommentBody("");
        setStatusMessage("Comment submitted! EvoCode is triaging your request.");
        if (data.ai_reply) {
          setAiReply(data.ai_reply);
        }
        await fetchComments();
      } else {
        setStatusMessage("Could not submit comment. Please check your backend.");
      }
    } catch {
      setStatusMessage("Backend server appears unreachable. Make sure EvoCode backend is running.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpvote = async (commentId: number) => {
    if (!voterFingerprint) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/comments/${commentId}/upvote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voter_fingerprint: voterFingerprint }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.triggered_build) {
          setStatusMessage("⚡ Threshold reached! EvoCode autonomous build job has been triggered!");
        }
        await fetchComments();
      }
    } catch {}
  };

  return (
    <section className="w-full px-[8%] md:px-[12%] py-12 border-t border-gray-200 dark:border-white/10" id="feedback">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20 mb-3">
            <span>⚡ Community-Driven Engineering</span>
          </div>
          <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
            Community Comments & Live Upvotes
          </h2>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400 max-w-xl mx-auto">
            Suggest improvements or report bugs. Upvoted features automatically trigger the EvoCode autonomous pipeline
            to build, verify, and ship live!
          </p>
        </div>

        <form onSubmit={handleSubmit} className="mb-10 p-6 rounded-2xl bg-gray-50 dark:bg-[#121212] border border-gray-200 dark:border-white/10 shadow-sm">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Your Name</label>
              <input
                type="text"
                placeholder="Jane Developer"
                value={authorName}
                onChange={(e) => setAuthorName(e.target.value)}
                required
                className="w-full px-3.5 py-2.5 text-sm rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-black/40 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Current Page</label>
              <input
                type="text"
                disabled
                value={typeof window !== "undefined" ? window.location.pathname || "/" : "/"}
                className="w-full px-3.5 py-2.5 text-sm rounded-lg border border-gray-200 dark:border-white/5 bg-gray-100 dark:bg-white/5 text-gray-500 font-mono"
              />
            </div>
          </div>

          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
              Feedback / Feature Request / Bug
            </label>
            <textarea
              rows={3}
              placeholder="e.g. Add dark mode toggle or fix mobile responsive layout on project cards..."
              value={commentBody}
              onChange={(e) => setCommentBody(e.target.value)}
              required
              className="w-full px-3.5 py-2.5 text-sm rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-black/40 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <span className="text-xs text-gray-500 dark:text-gray-400">
              💡 Telemetry (route path & console state) is attached silently to assist AI diagnosis.
            </span>
            <button
              type="submit"
              disabled={submitting}
              className="w-full sm:w-auto px-6 py-2.5 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors disabled:opacity-50 shadow"
            >
              {submitting ? "Submitting…" : "Post Comment"}
            </button>
          </div>

          {statusMessage && (
            <div className="mt-4 p-3 rounded-lg bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800/40 text-xs text-indigo-700 dark:text-indigo-300">
              {statusMessage}
            </div>
          )}
          {aiReply && (
            <div className="mt-3 p-3.5 rounded-lg bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800/40 text-xs text-purple-700 dark:text-purple-300 flex items-start gap-2">
              <span className="font-bold shrink-0">🤖 EvoCode AI Reply:</span>
              <span>{aiReply}</span>
            </div>
          )}
        </form>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900 dark:text-white">Recent Feedback & Signals</h3>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {comments.length} {comments.length === 1 ? "comment" : "comments"}
            </span>
          </div>

          {loading && comments.length === 0 && (
            <div className="text-center py-8 text-xs text-gray-500">Loading community comments…</div>
          )}

          {!loading && comments.length === 0 && (
            <div className="text-center py-8 text-xs text-gray-500 dark:text-gray-400 border border-dashed border-gray-200 dark:border-white/10 rounded-xl">
              No comments yet on this page. Be the first to share feedback!
            </div>
          )}

          {comments.map((c) => {
            const isShipped =
              c.signal_status === "Shipped Live" ||
              c.raw_status === "approved_shipped" ||
              c.signal_status === "approved_shipped";
            const isPrReady = c.signal_status === "PR Ready" || c.raw_status === "pr_ready";
            const isBuilding =
              c.signal_status === "AI Building" ||
              c.signal_status === "AI Coding" ||
              c.signal_status === "AI Planning" ||
              c.raw_status === "coding" ||
              c.raw_status === "planning" ||
              c.raw_status === "queued" ||
              c.raw_status === "verifying";

            return (
              <div
                key={c.id}
                className="p-4 rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-[#111111]/70 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2 mb-1.5">
                    <span className="text-xs font-bold text-gray-900 dark:text-white">{c.author_name}</span>
                    <span className="text-[11px] text-gray-400">
                      {c.created_at ? new Date(c.created_at).toLocaleDateString() : ""}
                    </span>

                    {/* PHASE 5: SHIPPED LIVE BADGE */}
                    {isShipped ? (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                        <svg className="w-3.5 h-3.5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                        </svg>
                        Shipped Live
                        {c.pr_url && (
                          <a
                            href={c.pr_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="ml-1 underline hover:text-emerald-300"
                            title="View merged GitHub Pull Request"
                          >
                            PR ↗
                          </a>
                        )}
                      </span>
                    ) : isPrReady ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 border border-indigo-500/30">
                        PR Ready
                        {c.pr_url && (
                          <a href={c.pr_url} target="_blank" rel="noopener noreferrer" className="ml-1 underline hover:text-indigo-300">
                            ↗
                          </a>
                        )}
                      </span>
                    ) : isBuilding ? (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                        AI Building
                      </span>
                    ) : c.signal_status ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 dark:bg-white/5 text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-white/10">
                        {c.signal_status}
                      </span>
                    ) : null}
                  </div>

                  <p className="text-sm text-gray-800 dark:text-zinc-200">{c.body}</p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() => handleUpvote(c.id)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-200 dark:border-white/10 hover:border-indigo-500/50 hover:bg-indigo-50 dark:hover:bg-indigo-950/20 text-gray-700 dark:text-gray-300 transition-colors"
                  >
                    <svg className="w-3.5 h-3.5 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                    </svg>
                    <span>{c.upvotes}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
