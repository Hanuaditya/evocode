"use client";

import React, { useState, useEffect } from "react";

export default function BugReportWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [bugText, setBugText] = useState("");
  const [filePath, setFilePath] = useState("src/checkout.js"); 
  const [status, setStatus] = useState("idle"); // idle, submitting, polling, completed, failed
  const [issueId, setIssueId] = useState(null);
  const [prUrl, setPrUrl] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus("submitting");
    setErrorMsg("");

    try {
      const response = await fetch("http://127.0.0.1:8000/api/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bug_text: bugText, file_path: filePath })
      });

      if (!response.ok) throw new Error("Failed to submit bug report.");

      const data = await response.json();
      setIssueId(data.issue_id);
      setStatus("polling");
    } catch (err) {
      setErrorMsg(err.message || "Network Error: Could not reach backend.");
      setStatus("idle");
    }
  };

  useEffect(() => {
    let interval;
    if (status === "polling" && issueId) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`http://127.0.0.1:8000/api/issues/${issueId}/status`);
          if (res.ok) {
            const data = await res.json();
            
            if (data.status === "completed") {
              setStatus("completed");
              setPrUrl(data.pr_url || "https://github.com/");
              clearInterval(interval);
            } else if (data.status === "failed") {
              setStatus("failed");
              setErrorMsg("The AI failed to resolve the issue after maximum attempts.");
              clearInterval(interval);
            } else if (data.status === "pending" || data.status === "planned") {
              // Now that we have Human-in-the-Loop, it stays pending until human approval
              setStatus("pending_review");
              clearInterval(interval);
            }
          }
        } catch (e) {
          console.error("Polling error:", e);
        }
      }, 3000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [status, issueId]);

  return (
    <>
      {/* Floating Button */}
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-50 p-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full shadow-2xl transition-transform hover:scale-110 flex items-center justify-center focus:outline-none focus:ring-4 focus:ring-indigo-300"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      </button>

      {/* Modal Overlay */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-60 backdrop-blur-sm transition-opacity p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-lg p-6 relative animate-fade-in-up">
            
            {/* Close Button */}
            <button 
              onClick={() => { 
                setIsOpen(false); 
                if (status === "completed" || status === "failed") {
                  setStatus("idle"); 
                  setIssueId(null); 
                  setBugText(""); 
                }
              }}
              className="absolute top-4 right-4 text-gray-500 hover:text-gray-800 dark:hover:text-gray-200 focus:outline-none transition-colors"
            >
               <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
               </svg>
            </button>

            <h2 className="text-2xl font-bold mb-5 text-gray-800 dark:text-gray-100 flex items-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 mr-2 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Report an Issue
            </h2>

            {status === "idle" || status === "failed" ? (
              <form onSubmit={handleSubmit} className="flex flex-col space-y-5">
                {errorMsg && (
                   <div className="p-3 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800 rounded-lg text-sm font-medium">
                     {errorMsg}
                   </div>
                )}
                
                <div className="flex flex-col">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Target File</label>
                  <select 
                    value={filePath} 
                    onChange={(e) => setFilePath(e.target.value)}
                    className="p-3 border border-gray-300 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800 text-gray-800 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500 outline-none transition"
                  >
                    <option value="app/components/About.jsx">app/components/About.jsx</option>
                    <option value="app/components/Header.jsx">app/components/Header.jsx</option>
                    <option value="app/components/Footer.jsx">app/components/Footer.jsx</option>
                    <option value="app/components/Navbar.jsx">app/components/Navbar.jsx</option>
                    <option value="app/components/Services.jsx">app/components/Services.jsx</option>
                  </select>
                </div>

                <div className="flex flex-col">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Request Details</label>
                  <textarea 
                    rows="4"
                    value={bugText}
                    onChange={(e) => setBugText(e.target.value)}
                    placeholder="Describe the bug or feature clearly... e.g. 'Add a cool gradient to the hero text' or 'Fix the checkout crash'"
                    className="p-3 border border-gray-300 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800 text-gray-800 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500 outline-none transition resize-none placeholder-gray-400"
                    required
                  ></textarea>
                </div>

                <button 
                  type="submit" 
                  className="mt-2 w-full p-3.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-bold text-lg transition shadow-md"
                >
                  Generate Fix
                </button>
              </form>
            ) : status === "submitting" || status === "polling" ? (
              <div className="flex flex-col items-center justify-center py-12 space-y-6">
                <div className="w-14 h-14 border-4 border-indigo-100 dark:border-gray-700 border-t-indigo-600 rounded-full animate-spin"></div>
                <div className="text-center">
                  <h3 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-1">EvoCode is operating...</h3>
                  <p className="text-md text-gray-500 dark:text-gray-400 max-w-xs mx-auto">
                    {status === "submitting" 
                      ? "Transmitting payload to backend..." 
                      : "The AI Agent is currently orchestrating the fix and executing sandbox tests."}
                  </p>
                </div>
              </div>
            ) : status === "pending_review" ? (
              <div className="flex flex-col items-center justify-center py-8 space-y-5 animate-fade-in-up">
                <div className="w-16 h-16 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400 rounded-full flex items-center justify-center shadow-inner">
                   <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                     <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                   </svg>
                </div>
                <div className="text-center">
                  <h3 className="text-2xl font-bold text-gray-800 dark:text-gray-100 mb-2">Issue Logged!</h3>
                  <p className="text-gray-600 dark:text-gray-300">
                    Your bug report has been received. Because Human-in-the-Loop triage is enabled, it is waiting for your review.
                  </p>
                </div>
                <a 
                  href={`http://localhost:3001/developer/build/${issueId}`} 
                  target="_blank" 
                  rel="noreferrer"
                  className="inline-flex items-center mt-2 px-8 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-lg transition shadow-lg"
                >
                  Review AI Plan & Execute
                </a>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 space-y-5 animate-fade-in-up">
                <div className="w-20 h-20 bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400 rounded-full flex items-center justify-center shadow-inner">
                   <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                     <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                   </svg>
                </div>
                <div className="text-center">
                  <h3 className="text-2xl font-bold text-gray-800 dark:text-gray-100 mb-2">Fix Deployed!</h3>
                  <p className="text-gray-600 dark:text-gray-300">
                    The AI successfully generated a patch, passed the isolated test suite, and pushed a branch to GitHub.
                  </p>
                </div>
                {prUrl && (
                  <a 
                    href={prUrl} 
                    target="_blank" 
                    rel="noreferrer"
                    className="inline-flex items-center mt-2 px-8 py-3 bg-gray-900 dark:bg-indigo-600 text-white font-semibold rounded-lg hover:bg-gray-800 dark:hover:bg-indigo-500 transition shadow-lg"
                  >
                    View Pull Request
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 ml-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
