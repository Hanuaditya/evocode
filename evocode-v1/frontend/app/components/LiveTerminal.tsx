"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type LogType =
  | "tool_start"
  | "tool_end"
  | "tool_error"
  | "token"
  | "llm_start"
  | "llm_end"
  | "chain_start"
  | "chain_end"
  | "chain_error"
  | "agent_action"
  | "agent_finish"
  | "status"
  | "heartbeat"
  | "log"
  | "complete"
  | "error"
  | "done"
  | "info";

interface LogEntry {
  id: string;
  type: LogType;
  message: string;
  timestamp: string;
  raw?: Record<string, unknown>;
}

interface ExecutionResult {
  success: boolean;
  output: string;
  error: string | null;
}

interface LiveTerminalProps {
  featureId: number;
  onComplete?: (result: ExecutionResult) => void;
  /** Backend base URL — defaults to http://127.0.0.1:8000 */
  apiBase?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const now = () =>
  new Date().toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

const uid = () => Math.random().toString(36).slice(2, 9);

/** Map a log type to a terminal colour class */
const typeColor = (type: LogType): string => {
  switch (type) {
    case "tool_start":
      return "#fbbf24"; // amber
    case "tool_end":
    case "agent_finish":
      return "#4ade80"; // green
    case "tool_error":
    case "chain_error":
    case "error":
      return "#f87171"; // red
    case "llm_start":
    case "token":
      return "#67e8f9"; // cyan
    case "agent_action":
      return "#c084fc"; // purple
    case "chain_start":
    case "chain_end":
      return "#93c5fd"; // blue
    case "status":
      return "#ffffff"; // white
    case "heartbeat":
      return "#374151"; // dim gray (nearly invisible)
    case "done":
      return "#4ade80";
    default:
      return "#e2e8f0"; // light
  }
};

/** Prefix glyph per type */
const typeGlyph = (type: LogType): string => {
  switch (type) {
    case "tool_start":    return "⚡";
    case "tool_end":      return "✅";
    case "tool_error":    return "💥";
    case "llm_start":     return "🤖";
    case "token":         return "·";
    case "chain_start":   return "🧠";
    case "chain_end":     return "✨";
    case "chain_error":   return "🔥";
    case "agent_action":  return "💭";
    case "agent_finish":  return "🎉";
    case "status":        return "🚀";
    case "error":         return "❌";
    case "heartbeat":     return "♡";
    case "done":          return "🏁";
    default:              return "›";
  }
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function LiveTerminal({
  featureId,
  onComplete,
  apiBase = "http://127.0.0.1:8000",
}: LiveTerminalProps) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [tokenBuffer, setTokenBuffer] = useState("");

  const terminalRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);

  // ------ helpers -------- //

  const addLog = useCallback((type: LogType, message: string, raw?: Record<string, unknown>) => {
    setLogs((prev) => [
      ...prev,
      { id: uid(), type, message, timestamp: now(), raw },
    ]);
  }, []);

  // Auto-scroll to bottom whenever logs update
  useEffect(() => {
    const el = terminalRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs, tokenBuffer]);

  // ------ SSE connection -------- //

  useEffect(() => {
    if (!featureId) return;

    const url = `${apiBase}/api/features/${featureId}/execute/stream`;
    addLog("status", `Connecting to execution stream for feature #${featureId}…`);
    setIsRunning(true);
    setError(null);
    setResult(null);
    setLogs([]);
    setTokenBuffer("");

    const es = new EventSource(url);
    esRef.current = es;

    // Generic message (no event type)
    es.onmessage = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as Record<string, unknown>;
        const msg = (data.message as string) || JSON.stringify(data);
        addLog("info", msg, data);
      } catch {
        addLog("info", e.data);
      }
    };

    // Typed events from the backend
    const typedEvents: LogType[] = [
      "log", "status", "heartbeat", "error", "complete", "done",
    ];

    typedEvents.forEach((evtName) => {
      es.addEventListener(evtName, (e: Event) => {
        const me = e as MessageEvent;
        try {
          const data = JSON.parse(me.data) as Record<string, unknown>;

          if (evtName === "complete") {
            const execResult = (data.result ?? { success: true, output: "", error: null }) as ExecutionResult;
            addLog("done", (data.message as string) || "Execution complete");
            setResult(execResult);
            setIsRunning(false);
            es.close();
            onComplete?.(execResult);
            return;
          }

          if (evtName === "error") {
            const errMsg = (data.message as string) || "Unknown server error";
            addLog("error", errMsg, data);
            setError(errMsg);
            setIsRunning(false);
            es.close();
            return;
          }

          if (evtName === "heartbeat") {
            // Show a subtle heartbeat tick but don't flood the log
            addLog("heartbeat", "♡ keepalive", data);
            return;
          }

          // Generic "log" event — sub-type is in data.type
          const subType = (data.type as LogType) || "info";

          if (subType === "token") {
            // Accumulate tokens into a live buffer instead of one entry per token
            setTokenBuffer((prev) => prev + ((data.data as string) ?? ""));
            return;
          }

          // Flush token buffer when a non-token message arrives
          setTokenBuffer((prev) => {
            if (prev) {
              addLog("token", prev);
              return "";
            }
            return prev;
          });

          const msg = (data.message as string) || JSON.stringify(data);
          addLog(subType, msg, data);

        } catch {
          addLog("info", me.data);
        }
      });
    });

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) return; // already closed cleanly
      addLog("error", "SSE connection lost. The backend may have restarted.");
      setError("Connection lost");
      setIsRunning(false);
      es.close();
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [featureId, apiBase]);

  // ------ Render -------- //

  return (
    <div style={styles.wrapper}>
      {/* ── Header bar ── */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.dot("#ef4444")} />
          <span style={styles.dot("#fbbf24")} />
          <span style={styles.dot("#4ade80")} />
          <span style={styles.headerTitle}>EvoCode Agent — Feature #{featureId}</span>
        </div>
        <div style={styles.headerRight}>
          {isRunning && (
            <span style={styles.pulsingBadge}>
              <span style={styles.pulsingDot} />
              RUNNING
            </span>
          )}
          {result?.success && !isRunning && (
            <span style={{ ...styles.badge, background: "#14532d", color: "#4ade80" }}>
              ✅ COMPLETE
            </span>
          )}
          {error && !isRunning && (
            <span style={{ ...styles.badge, background: "#450a0a", color: "#f87171" }}>
              ❌ FAILED
            </span>
          )}
        </div>
      </div>

      {/* ── Terminal body ── */}
      <div ref={terminalRef} style={styles.terminal}>
        {logs.map((log) => (
          <div
            key={log.id}
            style={{
              ...styles.logLine,
              color: typeColor(log.type),
              // hide noisy heartbeat lines with low opacity
              opacity: log.type === "heartbeat" ? 0.25 : 1,
            }}
          >
            <span style={styles.timestamp}>{log.timestamp}</span>
            <span style={styles.glyph}>{typeGlyph(log.type)}</span>
            <span style={styles.message}>{log.message}</span>
          </div>
        ))}

        {/* Live token stream */}
        {tokenBuffer && (
          <div style={{ ...styles.logLine, color: typeColor("token") }}>
            <span style={styles.timestamp}>{now()}</span>
            <span style={styles.glyph}>·</span>
            <span style={styles.message}>{tokenBuffer}</span>
            <span style={styles.cursor}>▌</span>
          </div>
        )}

        {/* Empty state */}
        {logs.length === 0 && !isRunning && (
          <div style={{ color: "#4b5563", fontStyle: "italic" }}>
            Waiting to connect…
          </div>
        )}
      </div>

      {/* ── Result panel ── */}
      {result && (
        <div style={styles.resultPanel(result.success)}>
          <div style={styles.resultTitle}>
            {result.success ? "✅ Execution Successful" : "❌ Execution Failed"}
          </div>
          {result.output && (
            <pre style={styles.resultOutput}>{result.output}</pre>
          )}
          {result.error && (
            <pre style={{ ...styles.resultOutput, color: "#f87171" }}>
              {result.error}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Styles (inline — no Tailwind dependency)
// ---------------------------------------------------------------------------

const styles = {
  wrapper: {
    fontFamily: "'Fira Code', 'Cascadia Code', Consolas, Monaco, monospace",
    background: "#0a0a0a",
    border: "1px solid #1f2937",
    borderRadius: "0.75rem",
    overflow: "hidden",
    boxShadow: "0 25px 50px rgba(0,0,0,0.6)",
  } as React.CSSProperties,

  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0.6rem 1rem",
    background: "#111827",
    borderBottom: "1px solid #1f2937",
  } as React.CSSProperties,

  headerLeft: {
    display: "flex",
    alignItems: "center",
    gap: "0.4rem",
  } as React.CSSProperties,

  headerTitle: {
    color: "#9ca3af",
    fontSize: "0.78rem",
    marginLeft: "0.5rem",
    letterSpacing: "0.05em",
  } as React.CSSProperties,

  headerRight: {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
  } as React.CSSProperties,

  dot: (color: string): React.CSSProperties => ({
    width: "0.65rem",
    height: "0.65rem",
    borderRadius: "50%",
    background: color,
    display: "inline-block",
  }),

  badge: {
    fontSize: "0.7rem",
    padding: "0.15rem 0.5rem",
    borderRadius: "9999px",
    fontWeight: 700,
    letterSpacing: "0.05em",
  } as React.CSSProperties,

  pulsingBadge: {
    display: "flex",
    alignItems: "center",
    gap: "0.35rem",
    fontSize: "0.7rem",
    color: "#4ade80",
    fontWeight: 700,
    letterSpacing: "0.05em",
  } as React.CSSProperties,

  pulsingDot: {
    width: "0.5rem",
    height: "0.5rem",
    borderRadius: "50%",
    background: "#4ade80",
    animation: "pulse 1.5s ease-in-out infinite",
    display: "inline-block",
  } as React.CSSProperties,

  terminal: {
    height: "420px",
    overflowY: "auto",
    padding: "1rem",
    background: "#0a0a0a",
    color: "#e2e8f0",
    fontSize: "0.82rem",
    lineHeight: "1.7",
    scrollBehavior: "smooth",
  } as React.CSSProperties,

  logLine: {
    display: "flex",
    gap: "0.5rem",
    alignItems: "flex-start",
    marginBottom: "0.1rem",
    wordBreak: "break-word",
  } as React.CSSProperties,

  timestamp: {
    color: "#374151",
    flexShrink: 0,
    fontSize: "0.72rem",
    paddingTop: "0.1rem",
  } as React.CSSProperties,

  glyph: {
    flexShrink: 0,
    width: "1.2rem",
    textAlign: "center" as const,
  } as React.CSSProperties,

  message: {
    flex: 1,
    whiteSpace: "pre-wrap",
  } as React.CSSProperties,

  cursor: {
    animation: "blink 1s step-end infinite",
    color: "#67e8f9",
  } as React.CSSProperties,

  resultPanel: (success: boolean): React.CSSProperties => ({
    borderTop: `1px solid ${success ? "#14532d" : "#450a0a"}`,
    background: success ? "#052e16" : "#1c0606",
    padding: "1rem",
  }),

  resultTitle: {
    fontWeight: 700,
    marginBottom: "0.5rem",
    fontSize: "0.85rem",
  } as React.CSSProperties,

  resultOutput: {
    fontSize: "0.78rem",
    color: "#d1fae5",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    margin: 0,
    maxHeight: "180px",
    overflowY: "auto",
  } as React.CSSProperties,
};
