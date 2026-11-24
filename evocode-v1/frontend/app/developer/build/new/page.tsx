"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { RippleButton } from "@/components/ui/ripple-button";
import { ArrowLeft, Sparkles } from "lucide-react";

const BACKEND = "http://localhost:8000";

export default function NewFeaturePage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) {
      setError("Title and description are required.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const res = await fetch(`${BACKEND}/api/report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          body: description,
          author: "Sri Hari",
          source_url: "https://github.com/evocode",
        }),
      });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data = await res.json();
      // Navigate to the build page for the new issue
      router.push(`/developer/build/${data.id ?? data.issue_id ?? "new"}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create feature. Is the backend running?");
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#0A0A0A] text-white font-sans flex items-center justify-center px-6">
      <div className="w-full max-w-xl">

        {/* Back */}
        <Link
          href="/developer/triage"
          className="inline-flex items-center gap-2 text-zinc-500 hover:text-white text-sm mb-10 transition-colors"
        >
          <ArrowLeft size={14} /> Back to Features
        </Link>

        <div className="border border-white/10 rounded-2xl bg-[#111111]/60 p-8 shadow-2xl backdrop-blur-xl">

          {/* Header */}
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
              <Sparkles size={18} className="text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold">New Feature Request</h1>
              <p className="text-zinc-500 text-sm mt-0.5">Submit a new issue to the AI pipeline</p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">

            {/* Title */}
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">Feature title</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Add dark mode to the portfolio"
                className="w-full bg-white/[0.03] border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-zinc-600 outline-none focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/20 transition-all hover:border-white/20"
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what needs to change, why, and any context..."
                rows={5}
                className="w-full bg-white/[0.03] border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-zinc-600 outline-none focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/20 transition-all hover:border-white/20 resize-none"
              />
            </div>

            {/* Error */}
            {error && (
              <div className="text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3">
                ⚠️ {error}
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center gap-3 pt-2">
              <RippleButton
                type="submit"
                disabled={submitting}
                rippleColor="#6366f1"
                className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm py-3 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? "Creating…" : "Create Feature →"}
              </RippleButton>
              <Link
                href="/developer/triage"
                className="px-5 py-3 rounded-xl border border-white/10 text-zinc-400 hover:text-white hover:border-white/20 text-sm font-medium transition-all"
              >
                Cancel
              </Link>
            </div>

          </form>
        </div>
      </div>
    </div>
  );
}
