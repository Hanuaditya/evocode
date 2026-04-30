"use client";

import React, { useEffect, useState } from "react";

interface ProgressPipelineProps {
  issueId: number;
  onComplete: (prUrl: string) => void;
}

const stepsConfig = [
  { id: "analyzing", label: "Analyzing Codebase" },
  { id: "writing", label: "Writing Code" },
  { id: "testing", label: "Running Sandbox Tests" },
  { id: "pr_creation", label: "Creating Pull Request" },
];

export default function ProgressPipeline({ issueId, onComplete }: ProgressPipelineProps) {
  const [currentStep, setCurrentStep] = useState<string>("analyzing");
  const [status, setStatus] = useState<string>("processing");

  useEffect(() => {
    let interval: NodeJS.Timeout;

    const pollStatus = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/api/issues/${issueId}/status`);
        if (!res.ok) return;
        const data = await res.json();

        if (data.current_step) setCurrentStep(data.current_step);
        if (data.status) setStatus(data.status);

        if (data.status === "completed" || data.status === "failed") {
          clearInterval(interval);
          if (data.status === "completed" && data.pr_url) {
            onComplete(data.pr_url);
          }
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    };

    pollStatus();
    interval = setInterval(pollStatus, 2000);

    return () => clearInterval(interval);
  }, [issueId, onComplete]);

  // Determine the index of the current step
  const currentIndex = stepsConfig.findIndex((s) => s.id === currentStep);

  return (
    <div className="w-full max-w-2xl mx-auto p-6 bg-[#18181b] rounded-xl border border-[#27272a] shadow-lg mb-8">
      <h3 className="text-lg font-semibold text-white mb-6">Execution Pipeline</h3>
      <div className="flex flex-col gap-6 relative">
        {/* Vertical line connecting steps */}
        <div className="absolute left-[15px] top-4 bottom-4 w-0.5 bg-[#3f3f46] -z-0"></div>

        {stepsConfig.map((step, index) => {
          const isPast =
            status === "completed" ||
            (currentIndex > index && status !== "failed") ||
            (status === "failed" && currentIndex > index);
          const isCurrent = currentIndex === index && status !== "completed" && status !== "failed";
          const isFailedCurrent = currentIndex === index && status === "failed";
          const isFuture = (currentIndex < index && status !== "completed") || (currentIndex === -1 && status !== "completed");

          return (
            <div key={step.id} className="flex items-center gap-5 relative z-10">
              <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full bg-[#18181b]">
                {isPast && (
                  <div className="w-7 h-7 rounded-full bg-green-500 flex items-center justify-center shadow-[0_0_10px_rgba(34,197,94,0.4)]">
                    <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                )}
                {isCurrent && (
                  <div className="w-7 h-7 rounded-full border-[3px] border-blue-500 border-t-transparent animate-spin shadow-[0_0_10px_rgba(59,130,246,0.3)]"></div>
                )}
                {isFailedCurrent && (
                  <div className="w-7 h-7 rounded-full bg-red-500 flex items-center justify-center shadow-[0_0_10px_rgba(239,68,68,0.4)]">
                    <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </div>
                )}
                {isFuture && (
                  <div className="w-7 h-7 rounded-full border-2 border-[#52525b] bg-[#18181b]"></div>
                )}
              </div>
              <div
                className={`font-medium tracking-wide ${
                  isPast ? "text-green-400" : isCurrent ? "text-blue-400" : isFailedCurrent ? "text-red-400" : "text-gray-500"
                }`}
              >
                {step.label}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
