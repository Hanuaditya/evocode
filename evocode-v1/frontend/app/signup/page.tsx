"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { AnimatedList } from "@/components/ui/animated-list";

// ── EvoCode Activity Feed ───────────────────────────────────────────────
interface ActivityItem {
  name: string;
  description: string;
  icon: string;
  color: string;
  time: string;
}

const activities: ActivityItem[] = [
  { name: "New signal detected",     description: "@dev_hanu: The about section heading is wrong",   icon: "📡", color: "#ef4444", time: "15m ago" },
  { name: "Agent completed",         description: "Issue #13 patched & tests passed ✓",              icon: "🤖", color: "#8b5cf6", time: "12m ago" },
  { name: "Plan approved",           description: "Sri Hari approved the Grid Layout fix plan",       icon: "✅", color: "#10b981", time: "8m ago" },
  { name: "PR opened",               description: "evocode/fix-issue-15 → Remove Achievements",      icon: "🔀", color: "#06b6d4", time: "5m ago" },
  { name: "New feature request",     description: "@SriHari: Would love dark mode support!",         icon: "💬", color: "#6366f1", time: "2m ago" },
  { name: "PR merged",               description: "feat: Update About heading — merged to master",   icon: "🎉", color: "#00C9A7", time: "20m ago" },
  { name: "Code review",             description: "CodeRabbit: grid-cols-3 should be grid-cols-4",   icon: "🐰", color: "#f97316", time: "25m ago" },
  { name: "Feature shipped",         description: "Issue #11 deployed — heading updated live",       icon: "🚀", color: "#1E86FF", time: "30m ago" },
];

const allActivities = Array.from({ length: 3 }, () => activities).flat();

const ActivityCard = ({ name, description, icon, color, time }: ActivityItem) => (
  <div
    className={cn(
      "relative w-full max-w-[400px] cursor-pointer overflow-hidden rounded-2xl p-4",
      "transition-all duration-300 ease-out hover:scale-[1.02]",
      "bg-white/[0.03] backdrop-blur-xl border border-white/[0.08]",
      "hover:bg-white/[0.06] hover:border-white/[0.15]",
      "shadow-[0_8px_32px_0_rgba(0,0,0,0.4)]"
    )}
  >
    <div className="flex items-start gap-3.5">
      <div
        className="flex size-10 shrink-0 items-center justify-center rounded-xl transition-transform duration-300 hover:scale-110"
        style={{ 
          backgroundColor: color + "1A",
          border: `1.5px solid ${color}40`,
          boxShadow: `0 0 20px ${color}20`
        }}
      >
        <span className="text-lg">{icon}</span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <h4 className="font-semibold text-white text-sm truncate">{name}</h4>
          <span className="text-zinc-600 text-xs">·</span>
          <span className="text-zinc-500 text-xs font-medium">{time}</span>
        </div>
        <p className="text-zinc-400 text-xs leading-relaxed line-clamp-2">{description}</p>
      </div>
    </div>
  </div>
);

// ── Main Sign Up Page ────────────────────────────────────────────────────
export default function SignUpPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [focusedInput, setFocusedInput] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email || !password) {
      alert("Please fill in all fields.");
      return;
    }
    setSubmitting(true);
    // Simulate a brief signup then redirect to the dashboard
    setTimeout(() => router.push("/developer/triage"), 800);
  };

  return (
    <div className="flex min-h-screen w-full bg-[#0A0A0A] text-white font-sans overflow-hidden">

      {/* ── Left Panel: Sign Up Form ──────────────────────────────────── */}
      <div className="flex flex-col justify-center w-full max-w-[560px] px-10 lg:px-16 py-16 shrink-0 relative z-10">

        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 mb-16 group w-fit">
          <div className="relative w-8 h-8 bg-gradient-to-br from-white to-zinc-300 rounded-lg flex items-center justify-center shadow-lg transition-transform duration-300 group-hover:scale-110">
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500 to-purple-600 opacity-0 group-hover:opacity-100 rounded-lg transition-opacity duration-300" />
            <svg className="w-4 h-4 text-black relative z-10" fill="currentColor" viewBox="0 0 24 24">
              <path d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <span className="font-bold text-lg tracking-wider bg-gradient-to-r from-white to-zinc-400 bg-clip-text text-transparent">
            EVOCODE
          </span>
        </Link>

        {/* Header */}
        <div className="mb-10">
          <h1 className="text-4xl font-bold mb-3 bg-gradient-to-br from-white via-white to-zinc-400 bg-clip-text text-transparent">
            Create your account
          </h1>
          <p className="text-zinc-500 text-base leading-relaxed max-w-md">
            Automate feature delivery from community signals — no setup required.
          </p>
        </div>

        {/* Form */}
        <form className="flex flex-col gap-5" onSubmit={handleSubmit}>

          {/* Full Name */}
          <div className="group">
            <label className="block text-sm font-medium mb-2 text-zinc-300 transition-colors duration-200 group-focus-within:text-white">
              Full name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onFocus={() => setFocusedInput("name")}
              onBlur={() => setFocusedInput(null)}
              placeholder="Hanu Aditya"
              className={cn(
                "w-full bg-white/[0.03] border rounded-xl px-4 py-3.5 text-sm text-white placeholder:text-zinc-600",
                "outline-none transition-all duration-300",
                "hover:bg-white/[0.05] hover:border-white/20",
                focusedInput === "name"
                  ? "border-indigo-500/60 bg-white/[0.06] shadow-[0_0_0_3px_rgba(99,102,241,0.1)]"
                  : "border-white/10"
              )}
            />
          </div>

          {/* Email */}
          <div className="group">
            <label className="block text-sm font-medium mb-2 text-zinc-300 transition-colors duration-200 group-focus-within:text-white">
              Email address
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onFocus={() => setFocusedInput("email")}
              onBlur={() => setFocusedInput(null)}
              placeholder="you@yourdomain.com"
              className={cn(
                "w-full bg-white/[0.03] border rounded-xl px-4 py-3.5 text-sm text-white placeholder:text-zinc-600",
                "outline-none transition-all duration-300",
                "hover:bg-white/[0.05] hover:border-white/20",
                focusedInput === "email"
                  ? "border-indigo-500/60 bg-white/[0.06] shadow-[0_0_0_3px_rgba(99,102,241,0.1)]"
                  : "border-white/10"
              )}
            />
          </div>

          {/* Password */}
          <div className="group">
            <label className="block text-sm font-medium mb-2 text-zinc-300 transition-colors duration-200 group-focus-within:text-white">
              Password <span className="text-red-400">*</span>
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onFocus={() => setFocusedInput("password")}
              onBlur={() => setFocusedInput(null)}
              placeholder="Create a strong password"
              className={cn(
                "w-full bg-white/[0.03] border rounded-xl px-4 py-3.5 text-sm text-white placeholder:text-zinc-600",
                "outline-none transition-all duration-300",
                "hover:bg-white/[0.05] hover:border-white/20",
                focusedInput === "password"
                  ? "border-indigo-500/60 bg-white/[0.06] shadow-[0_0_0_3px_rgba(99,102,241,0.1)]"
                  : "border-white/10"
              )}
            />
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={submitting}
            className={cn(
              "w-full relative overflow-hidden group",
              "bg-white text-black font-semibold text-sm py-3.5 rounded-xl mt-2",
              "transition-all duration-300",
              "hover:shadow-[0_0_30px_rgba(255,255,255,0.2)]",
              "disabled:opacity-70 disabled:cursor-not-allowed"
            )}
          >
            <span className="relative z-10 group-hover:text-white transition-colors duration-300">
              {submitting ? "Creating account…" : "Create account"}
            </span>
            <div className="absolute inset-0 bg-gradient-to-r from-indigo-600 to-purple-600 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
          </button>
        </form>

        {/* Divider */}
        <div className="flex items-center gap-4 my-7">
          <div className="flex-1 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
          <span className="text-xs text-zinc-500 font-medium">or continue with</span>
          <div className="flex-1 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
        </div>

        {/* OAuth Buttons */}
        <div className="grid grid-cols-3 gap-3">
          {/* Google */}
          <button className="flex items-center justify-center gap-2.5 bg-white/[0.03] hover:bg-white/[0.08] border border-white/10 hover:border-white/20 rounded-xl py-3.5 transition-all duration-300 group">
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            <span className="text-zinc-300 text-xs font-medium group-hover:text-white transition-colors">Google</span>
          </button>

          {/* GitHub */}
          <button className="flex items-center justify-center gap-2.5 bg-white/[0.03] hover:bg-white/[0.08] border border-white/10 hover:border-white/20 rounded-xl py-3.5 transition-all duration-300 group">
            <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
            </svg>
            <span className="text-zinc-300 text-xs font-medium group-hover:text-white transition-colors">GitHub</span>
          </button>

          {/* Apple */}
          <button className="flex items-center justify-center gap-2.5 bg-white/[0.03] hover:bg-white/[0.08] border border-white/10 hover:border-white/20 rounded-xl py-3.5 transition-all duration-300 group">
            <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09l.01-.01zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z"/>
            </svg>
            <span className="text-zinc-300 text-xs font-medium group-hover:text-white transition-colors">Apple</span>
          </button>
        </div>

        {/* Footer Link */}
        <p className="text-center text-sm text-zinc-500 mt-8">
          Already have an account?{" "}
          <Link
            href="/"
            className="text-indigo-400 hover:text-indigo-300 font-semibold transition-colors duration-200 hover:underline underline-offset-2"
          >
            Sign in
          </Link>
        </p>
      </div>

      {/* ── Right Panel: Animated Activity Feed ─────────────────────── */}
      <div className="hidden lg:flex flex-1 relative overflow-hidden">

        {/* Base gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-[#1a1a1a] via-[#0f0f0f] to-[#0A0A0A]" />

        {/* Accent orbs */}
        <div className="absolute top-20 right-20 w-[500px] h-[500px] bg-indigo-600/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-20 left-20 w-[400px] h-[400px] bg-purple-600/10 rounded-full blur-[100px]" />

        {/* Subtle grid */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `
              linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)
            `,
            backgroundSize: "50px 50px",
          }}
        />

        {/* Activity Feed */}
        <div className="absolute inset-0 flex flex-col justify-start pt-20 px-12 overflow-hidden">
          <AnimatedList delay={2000} className="gap-4">
            {allActivities.map((item, idx) => (
              <ActivityCard {...item} key={idx} />
            ))}
          </AnimatedList>

          {/* Bottom fade */}
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-[#0A0A0A] via-[#0A0A0A]/80 to-transparent" />
        </div>

        {/* Bottom: Tags + Testimonial */}
        <div className="absolute bottom-10 left-12 right-12 z-20">
          <div className="flex flex-wrap gap-2 mb-5">
            <span className="px-4 py-1.5 rounded-full bg-white/[0.05] backdrop-blur-xl border border-white/10 text-xs font-semibold text-white">Open Source</span>
            <span className="px-4 py-1.5 rounded-full bg-white/[0.05] backdrop-blur-xl border border-white/10 text-xs font-semibold text-white">AI Agents</span>
            <span className="px-4 py-1.5 rounded-full bg-gradient-to-r from-indigo-500/20 to-purple-500/20 backdrop-blur-xl border border-indigo-400/20 text-xs font-semibold text-indigo-200">Automated PRs</span>
          </div>

          <div className="bg-white/[0.03] backdrop-blur-2xl border border-white/10 rounded-2xl p-6 shadow-[0_20px_70px_-10px_rgba(0,0,0,0.5)] hover:border-white/20 transition-all duration-300">
            {/* Stars */}
            <div className="flex items-center gap-0.5 mb-3">
              {[...Array(5)].map((_, i) => (
                <svg key={i} className="w-3.5 h-3.5 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
                </svg>
              ))}
            </div>
            <p className="text-white text-sm font-medium leading-relaxed mb-4">
              &ldquo;EvoCode shipped a PR from a tweet in under 4 minutes. What used to take our team a full sprint is now fully automated.&rdquo;
            </p>
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-xs shadow-lg">
                SH
              </div>
              <div>
                <p className="text-white text-sm font-semibold">Sri Hari</p>
                <p className="text-zinc-500 text-xs">Lead Engineer, EvoCode</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
