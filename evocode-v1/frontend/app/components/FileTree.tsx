"use client";

import React, {
  useState,
  useEffect,
  useCallback,
  useRef,
  createContext,
  useContext,
} from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type FileStatus =
  | "idle"      // untouched — gray
  | "reading"   // agent is reading — yellow pulse
  | "writing"   // agent is writing — cyan pulse
  | "modified"  // successfully written — green
  | "error";    // tool_error occurred — red

export interface FileNode {
  name: string;
  path: string;          // relative from repo root
  type: "file" | "folder";
  extension?: string;    // e.g. "jsx", "ts", "css"
  children?: FileNode[];
  lastModified?: string; // ISO string
}

export interface FileDiff {
  path: string;
  before: string;
  after: string;
}

interface FileTreeProps {
  /** Tree structure to render */
  tree: FileNode[];
  /** Live status map: path → FileStatus */
  fileStatuses?: Record<string, FileStatus>;
  /** Called when user clicks a file */
  onFileClick?: (node: FileNode) => void;
  /** Called when user wants to revert a file */
  onRevert?: (node: FileNode) => void;
  /** Optional diff data to show in modal */
  diffs?: Record<string, FileDiff>;
  /** API base URL for polling */
  apiBase?: string;
  /** Compact mode (smaller padding) */
  compact?: boolean;
}

// ---------------------------------------------------------------------------
// Context for shared state inside the tree
// ---------------------------------------------------------------------------

interface TreeCtx {
  fileStatuses: Record<string, FileStatus>;
  flashingFiles: Set<string>;
  diffs: Record<string, FileDiff>;
  onFileClick: (node: FileNode) => void;
  onRevert: (node: FileNode) => void;
  compact: boolean;
}

const TreeContext = createContext<TreeCtx>({
  fileStatuses: {},
  flashingFiles: new Set(),
  diffs: {},
  onFileClick: () => {},
  onRevert: () => {},
  compact: false,
});

// ---------------------------------------------------------------------------
// File type → icon + colour
// ---------------------------------------------------------------------------

const EXT_META: Record<string, { icon: string; color: string }> = {
  jsx:   { icon: "⚛", color: "#61dafb" },
  tsx:   { icon: "⚛", color: "#61dafb" },
  ts:    { icon: "🔷", color: "#3b82f6" },
  js:    { icon: "🟨", color: "#fbbf24" },
  css:   { icon: "🎨", color: "#c084fc" },
  scss:  { icon: "🎨", color: "#ec4899" },
  json:  { icon: "{ }", color: "#f97316" },
  md:    { icon: "📝", color: "#94a3b8" },
  py:    { icon: "🐍", color: "#4ade80" },
  html:  { icon: "🌐", color: "#fb923c" },
  svg:   { icon: "🖼", color: "#a78bfa" },
  env:   { icon: "🔐", color: "#6b7280" },
  gitignore: { icon: "🚫", color: "#6b7280" },
};


function getFileMeta(name: string, extension?: string) {
  const ext = extension ?? name.split(".").pop() ?? "";
  return EXT_META[ext] ?? { icon: "📄", color: "#94a3b8" };
}

// ---------------------------------------------------------------------------
// Status → styling
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<
  FileStatus,
  { bg: string; border: string; textColor: string; label: string }
> = {
  idle:     { bg: "transparent",    border: "transparent",  textColor: "#9ca3af", label: "" },
  reading:  { bg: "#7c3aed22",      border: "#7c3aed",      textColor: "#c4b5fd", label: "reading" },
  writing:  { bg: "#0e7490aa",      border: "#22d3ee",      textColor: "#67e8f9", label: "writing" },
  modified: { bg: "#14532d66",      border: "#22c55e",      textColor: "#4ade80", label: "modified" },
  error:    { bg: "#450a0a66",      border: "#ef4444",      textColor: "#f87171", label: "error" },
};

// ---------------------------------------------------------------------------
// Context menu
// ---------------------------------------------------------------------------

interface ContextMenu {
  x: number;
  y: number;
  node: FileNode;
}

// ---------------------------------------------------------------------------
// Diff Modal
// ---------------------------------------------------------------------------

function DiffModal({
  diff,
  onClose,
}: {
  diff: FileDiff;
  onClose: () => void;
}) {
  const beforeLines = diff.before.split("\n");
  const afterLines = diff.after.split("\n");

  return (
    <div style={ms.overlay} onClick={onClose}>
      <div style={ms.modal} onClick={(e) => e.stopPropagation()}>
        <div style={ms.header}>
          <span style={ms.title}>📄 {diff.path}</span>
          <button onClick={onClose} style={ms.closeBtn}>✕</button>
        </div>
        <div style={ms.diffGrid}>
          {/* Before */}
          <div>
            <div style={ms.diffLabel("before")}>BEFORE</div>
            <pre style={ms.diffPre}>
              {beforeLines.map((line, i) => (
                <div
                  key={i}
                  style={{
                    ...ms.diffLine,
                    background: !afterLines[i] || line !== afterLines[i]
                      ? "#450a0a55"
                      : "transparent",
                    color: !afterLines[i] || line !== afterLines[i]
                      ? "#fca5a5"
                      : "#94a3b8",
                  }}
                >
                  <span style={ms.lineNum}>{i + 1}</span>
                  {line}
                </div>
              ))}
            </pre>
          </div>
          {/* After */}
          <div>
            <div style={ms.diffLabel("after")}>AFTER</div>
            <pre style={ms.diffPre}>
              {afterLines.map((line, i) => (
                <div
                  key={i}
                  style={{
                    ...ms.diffLine,
                    background: !beforeLines[i] || line !== beforeLines[i]
                      ? "#14532d55"
                      : "transparent",
                    color: !beforeLines[i] || line !== beforeLines[i]
                      ? "#86efac"
                      : "#94a3b8",
                  }}
                >
                  <span style={ms.lineNum}>{i + 1}</span>
                  {line}
                </div>
              ))}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

const ms = {
  overlay: {
    position: "fixed" as const,
    inset: 0,
    background: "rgba(0,0,0,0.75)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 9999,
  },
  modal: {
    background: "#0f172a",
    border: "1px solid #1e293b",
    borderRadius: "0.75rem",
    width: "min(90vw, 960px)",
    maxHeight: "80vh",
    display: "flex",
    flexDirection: "column" as const,
    overflow: "hidden",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "0.75rem 1rem",
    borderBottom: "1px solid #1e293b",
    background: "#1e293b",
  },
  title: {
    fontFamily: "monospace",
    fontSize: "0.85rem",
    color: "#e2e8f0",
    fontWeight: 600,
  },
  closeBtn: {
    background: "transparent",
    border: "none",
    color: "#6b7280",
    cursor: "pointer",
    fontSize: "1rem",
    padding: "0.2rem 0.4rem",
  },
  diffGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    overflow: "auto",
    flex: 1,
  },
  diffLabel: (side: "before" | "after"): React.CSSProperties => ({
    padding: "0.3rem 0.75rem",
    fontSize: "0.7rem",
    fontWeight: 700,
    letterSpacing: "0.1em",
    background: side === "before" ? "#1c0606" : "#052e16",
    color: side === "before" ? "#f87171" : "#4ade80",
    borderBottom: `1px solid ${side === "before" ? "#450a0a" : "#14532d"}`,
  }),
  diffPre: {
    margin: 0,
    padding: 0,
    fontFamily: "'Fira Code', monospace",
    fontSize: "0.75rem",
    overflowX: "auto" as const,
  },
  diffLine: {
    display: "flex",
    gap: "0.75rem",
    padding: "0.05rem 0.5rem",
    whiteSpace: "pre" as const,
  },
  lineNum: {
    color: "#374151",
    userSelect: "none" as const,
    minWidth: "2rem",
    textAlign: "right" as const,
    flexShrink: 0,
  },
};

// ---------------------------------------------------------------------------
// Single file row
// ---------------------------------------------------------------------------

function FileRow({ node, depth }: { node: FileNode; depth: number }) {
  const ctx = useContext(TreeContext);
  const status = ctx.fileStatuses[node.path] ?? "idle";
  const isFlashing = ctx.flashingFiles.has(node.path);
  const hasDiff = !!ctx.diffs[node.path];
  const [hovered, setHovered] = useState(false);
  const statusStyle = STATUS_STYLES[status];
  const { icon, color } = getFileMeta(node.name, node.extension);

  const handleClick = () => ctx.onFileClick(node);

  const [ctxMenu, setCtxMenu] = useState<{ x: number; y: number } | null>(null);

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    setCtxMenu({ x: e.clientX, y: e.clientY });
  };

  const closeCtxMenu = useCallback(() => setCtxMenu(null), []);

  useEffect(() => {
    if (ctxMenu) {
      window.addEventListener("click", closeCtxMenu);
      return () => window.removeEventListener("click", closeCtxMenu);
    }
  }, [ctxMenu, closeCtxMenu]);

  const padding = ctx.compact
    ? `0.2rem 0.5rem 0.2rem ${1 + depth * 1}rem`
    : `0.35rem 0.75rem 0.35rem ${1 + depth * 1.2}rem`;

  return (
    <>
      <div
        onClick={handleClick}
        onContextMenu={handleContextMenu}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        title={
          node.lastModified
            ? `Last modified: ${new Date(node.lastModified).toLocaleString()}`
            : node.path
        }
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.4rem",
          padding,
          cursor: "pointer",
          borderRadius: "0.25rem",
          margin: "0.05rem 0.25rem",
          background: isFlashing
            ? "#1a3a1a"
            : hovered
            ? "#1e293b"
            : statusStyle.bg,
          border: `1px solid ${isFlashing ? "#22c55e" : statusStyle.border}`,
          transition: "background 0.3s, border-color 0.3s",
          animation: isFlashing ? "fileFlash 0.6s ease-in-out" : undefined,
        }}
      >
        {/* File type icon */}
        <span style={{ fontSize: ctx.compact ? "0.75rem" : "0.85rem", color }}>
          {icon}
        </span>

        {/* File name */}
        <span
          style={{
            fontSize: ctx.compact ? "0.72rem" : "0.78rem",
            color: statusStyle.textColor !== "#9ca3af" ? statusStyle.textColor : "#cbd5e1",
            fontFamily: "monospace",
            flex: 1,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {node.name}
        </span>

        {/* Status badge */}
        {status !== "idle" && (
          <span
            style={{
              fontSize: "0.6rem",
              padding: "0.1rem 0.35rem",
              borderRadius: "9999px",
              background: statusStyle.border + "33",
              color: statusStyle.textColor,
              fontWeight: 700,
              letterSpacing: "0.04em",
              flexShrink: 0,
              animation:
                status === "reading" || status === "writing"
                  ? "statusPulse 1.2s ease-in-out infinite"
                  : undefined,
            }}
          >
            {statusStyle.label}
          </span>
        )}

        {/* Diff indicator */}
        {hasDiff && (
          <span style={{ fontSize: "0.65rem", color: "#6366f1" }} title="Diff available">
            ≠
          </span>
        )}
      </div>

      {/* Context menu */}
      {ctxMenu && (
        <div
          style={{
            position: "fixed",
            top: ctxMenu.y,
            left: ctxMenu.x,
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "0.5rem",
            zIndex: 9998,
            minWidth: "160px",
            overflow: "hidden",
            boxShadow: "0 10px 30px rgba(0,0,0,0.5)",
          }}
        >
          {[
            { label: "📄 View Diff", action: () => ctx.onFileClick(node) },
            { label: "↩ Revert Changes", action: () => ctx.onRevert(node) },
          ].map(({ label, action }) => (
            <button
              key={label}
              onClick={() => { action(); closeCtxMenu(); }}
              style={{
                display: "block",
                width: "100%",
                padding: "0.5rem 0.75rem",
                background: "transparent",
                border: "none",
                color: "#e2e8f0",
                textAlign: "left",
                cursor: "pointer",
                fontSize: "0.78rem",
              }}
              onMouseEnter={(e) =>
                ((e.target as HTMLElement).style.background = "#334155")
              }
              onMouseLeave={(e) =>
                ((e.target as HTMLElement).style.background = "transparent")
              }
            >
              {label}
            </button>
          ))}
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Folder row (recursive)
// ---------------------------------------------------------------------------

function FolderRow({ node, depth }: { node: FileNode; depth: number }) {
  const ctx = useContext(TreeContext);
  const [open, setOpen] = useState(depth < 2); // auto-expand top levels
  const [hovered, setHovered] = useState(false);

  // Check if any child has a non-idle status (bubble up indicator)
  const hasActiveChild = useCallback(
    (n: FileNode): boolean => {
      if (n.type === "file") return (ctx.fileStatuses[n.path] ?? "idle") !== "idle";
      return (n.children ?? []).some(hasActiveChild);
    },
    [ctx.fileStatuses]
  );

  const active = hasActiveChild(node);

  const padding = ctx.compact
    ? `0.2rem 0.5rem 0.2rem ${1 + depth * 1}rem`
    : `0.35rem 0.75rem 0.35rem ${1 + depth * 1.2}rem`;

  return (
    <>
      <div
        onClick={() => setOpen((v) => !v)}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.4rem",
          padding,
          cursor: "pointer",
          borderRadius: "0.25rem",
          margin: "0.05rem 0.25rem",
          background: hovered ? "#1e293b" : "transparent",
          transition: "background 0.15s",
        }}
      >
        <span style={{ fontSize: "0.75rem", color: "#6b7280", width: "0.8rem" }}>
          {open ? "▾" : "▸"}
        </span>
        <span style={{ fontSize: ctx.compact ? "0.75rem" : "0.85rem" }}>📁</span>
        <span
          style={{
            fontSize: ctx.compact ? "0.72rem" : "0.78rem",
            color: "#94a3b8",
            fontFamily: "monospace",
            fontWeight: 600,
            flex: 1,
          }}
        >
          {node.name}
        </span>
        {active && !open && (
          <span
            style={{
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              background: "#fbbf24",
              animation: "statusPulse 1.2s ease-in-out infinite",
              flexShrink: 0,
            }}
          />
        )}
      </div>

      {open && (
        <div>
          {(node.children ?? []).map((child) =>
            child.type === "folder" ? (
              <FolderRow key={child.path} node={child} depth={depth + 1} />
            ) : (
              <FileRow key={child.path} node={child} depth={depth + 1} />
            )
          )}
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Root component
// ---------------------------------------------------------------------------

export default function FileTree({
  tree,
  fileStatuses = {},
  onFileClick,
  onRevert,
  diffs = {},
  compact = false,
}: FileTreeProps) {
  // Track files that recently changed (for flash animation)
  const [flashingFiles, setFlashingFiles] = useState<Set<string>>(new Set());
  const prevStatuses = useRef<Record<string, FileStatus>>({});

  // Diff modal
  const [activeDiff, setActiveDiff] = useState<FileDiff | null>(null);

  // Detect transitions → modified, trigger flash
  useEffect(() => {
    const newly: string[] = [];
    for (const [path, status] of Object.entries(fileStatuses)) {
      if (status === "modified" && prevStatuses.current[path] !== "modified") {
        newly.push(path);
      }
    }
    if (newly.length > 0) {
      setFlashingFiles((prev) => {
        const next = new Set(prev);
        newly.forEach((p) => next.add(p));
        return next;
      });
      // Remove flash after animation completes
      const t = setTimeout(() => {
        setFlashingFiles((prev) => {
          const next = new Set(prev);
          newly.forEach((p) => next.delete(p));
          return next;
        });
      }, 3000);
      return () => clearTimeout(t);
    }
    prevStatuses.current = { ...fileStatuses };
  }, [fileStatuses]);

  const handleFileClick = useCallback(
    (node: FileNode) => {
      const diff = diffs[node.path];
      if (diff) setActiveDiff(diff);
      onFileClick?.(node);
    },
    [diffs, onFileClick]
  );

  const handleRevert = useCallback(
    (node: FileNode) => {
      onRevert?.(node);
    },
    [onRevert]
  );

  const ctxValue: TreeCtx = {
    fileStatuses,
    flashingFiles,
    diffs,
    onFileClick: handleFileClick,
    onRevert: handleRevert,
    compact,
  };

  return (
    <TreeContext.Provider value={ctxValue}>
      {/* Keyframe styles injected once */}
      <style>{`
        @keyframes fileFlash {
          0%   { background: #14532d; box-shadow: 0 0 12px #22c55e88; }
          60%  { background: #14532d99; box-shadow: 0 0 6px #22c55e44; }
          100% { background: transparent; box-shadow: none; }
        }
        @keyframes statusPulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.35; }
        }
      `}</style>

      <div
        style={{
          background: "#0a0f1a",
          border: "1px solid #1e293b",
          borderRadius: "0.75rem",
          overflow: "hidden",
          fontFamily: "system-ui, sans-serif",
          userSelect: "none",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0.6rem 0.75rem",
            background: "#111827",
            borderBottom: "1px solid #1e293b",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <span style={{ fontSize: "0.8rem" }}>📁</span>
            <span
              style={{
                fontSize: "0.72rem",
                fontWeight: 700,
                letterSpacing: "0.1em",
                color: "#64748b",
                textTransform: "uppercase",
              }}
            >
              Repository
            </span>
          </div>

          {/* Legend */}
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            {(["reading", "writing", "modified", "error"] as FileStatus[]).map((s) => (
              <span
                key={s}
                style={{
                  fontSize: "0.58rem",
                  color: STATUS_STYLES[s].textColor,
                  opacity: 0.8,
                  letterSpacing: "0.03em",
                }}
              >
                ● {s}
              </span>
            ))}
          </div>
        </div>

        {/* Tree body */}
        <div
          style={{
            maxHeight: compact ? "300px" : "500px",
            overflowY: "auto",
            padding: "0.4rem 0",
          }}
        >
          {tree.length === 0 ? (
            <div
              style={{
                padding: "2rem",
                textAlign: "center",
                color: "#374151",
                fontSize: "0.8rem",
              }}
            >
              No files loaded
            </div>
          ) : (
            tree.map((node) =>
              node.type === "folder" ? (
                <FolderRow key={node.path} node={node} depth={0} />
              ) : (
                <FileRow key={node.path} node={node} depth={0} />
              )
            )
          )}
        </div>
      </div>

      {/* Diff modal */}
      {activeDiff && (
        <DiffModal diff={activeDiff} onClose={() => setActiveDiff(null)} />
      )}
    </TreeContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Utility: derive fileStatuses from SSE log events
// Call this in a parent component that owns the SSE stream
// ---------------------------------------------------------------------------

export function deriveStatusesFromLogs(
  logs: Array<{ type: string; raw?: Record<string, unknown> }>
): Record<string, FileStatus> {
  const statuses: Record<string, FileStatus> = {};

  for (const log of logs) {
    const tool = log.raw?.tool as string | undefined;
    const input = (log.raw?.tool_input ?? log.raw?.data ?? "") as string;

    // Try to extract a filepath from the tool input string
    const pathMatch = input.match(/['"]([^'"]+\.\w+)['"]/);
    const filePath = pathMatch?.[1];

    if (!filePath) continue;

    if (log.type === "tool_start") {
      if (tool === "read_file")  statuses[filePath] = "reading";
      if (tool === "write_file") statuses[filePath] = "writing";
    }
    if (log.type === "tool_end") {
      // After a write the file is modified; after a read stay idle
      if (statuses[filePath] === "writing") statuses[filePath] = "modified";
      if (statuses[filePath] === "reading") statuses[filePath] = "idle";
    }
    if (log.type === "tool_error") {
      statuses[filePath] = "error";
    }
  }

  return statuses;
}
