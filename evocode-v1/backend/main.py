import os
import asyncio
import time
import json
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from sse_starlette.sse import EventSourceResponse

# Import utilities and DB mapping
from database import create_all_tables, get_db, SessionLocal
from models import IssueReport, FeatureSignal, Comment, Upvote, AuditEvent
from signal_triage import check_vagueness, cluster_comment_into_signal, trigger_autonomous_build

from utils.github_manager import GitHubManager
from utils.streaming_callback import StreamingCallbackHandler
from utils.code_agent_with_tools import CodeAgentWithTools
from utils.agent_orchestrator import AgentOrchestrator
from utils.system_checks import check_npm_installed, check_node_installed, validate_project_structure, get_system_info
from utils.initialization import initialize_sandbox_environment
from utils.db_recovery import reset_specific_feature

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables at startup
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────
    logger.info("🚀 Starting EvoCode backend...")

    init_result = initialize_sandbox_environment()

    if init_result["success"]:
        logger.info("✅ Environment initialized successfully")
    else:
        logger.warning("⚠️  Environment initialization had issues:")
        for error in init_result["errors"]:
            logger.error(f"  - {error}")

    for warning in init_result.get("warnings", []):
        logger.warning(f"  - {warning}")

    # Create database tables
    create_all_tables()
    logger.info("✅ Server ready")

    yield
    # ── Shutdown ───────────────────────────────────────────────────────

# Initialize FastAPI instance
app = FastAPI(title="EvoCode V2 API", lifespan=lifespan)

# Add CORS Middleware — allow all local origins for demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # Must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# V1 Pydantic Schemas (kept intact for backward compat)
# ---------------------------------------------------------------------------

class BugReportRequest(BaseModel):
    bug_text: str
    file_path: str

class ExecuteRequest(BaseModel):
    approved_plan: str = ""   # Full markdown plan from the frontend textarea


# ---------------------------------------------------------------------------
# V2 Pydantic Schemas
# ---------------------------------------------------------------------------

class CommentCreateRequest(BaseModel):
    author_name: Optional[str] = "Anonymous"
    body: str
    route_path: Optional[str] = "/"
    console_errors: Optional[list] = []
    screenshot_base64: Optional[str] = None

class UpvoteRequest(BaseModel):
    voter_fingerprint: str   # hashed browser fingerprint — no PII


# -----------------
# Background Task
# -----------------
def run_orchestrator_background(issue_id: int, approved_plan: str = ""):
    """
    Background worker — uses the new AgentOrchestrator which chains:
      CodeAgentWithTools → SandboxRunner (npm test) → GitHubManager (branch + PR)
    Creates its own DB session so the HTTP request session is not held open.
    """
    github_token = os.getenv("GITHUB_TOKEN", "")
    repo_owner   = os.getenv("REPO_OWNER", "")
    repo_name    = os.getenv("REPO_NAME", "")

    github_manager = GitHubManager(github_token, repo_owner, repo_name)
    auth_result = github_manager.authenticate()
    if not auth_result["success"]:
        logger.error(f"[main] GitHub auth failed: {auth_result['error']}")

    db = SessionLocal()
    try:
        orchestrator = AgentOrchestrator(
            github_manager=github_manager,
            db_session=db,
        )
        result = orchestrator.process_issue(issue_id, approved_plan=approved_plan)
        logger.info(f"[main] Orchestrator finished for issue #{issue_id}: {result}")
    except Exception as exc:
        logger.error(f"[main] Orchestrator crashed for issue #{issue_id}: {exc}")
    finally:
        db.close()


# -----------------
# Core Endpoints
# -----------------

@app.get("/")
def get_root():
    """Root health endpoint indicating active server presence."""
    return {"status": "EvoCode V1 Running"}

@app.get("/health")
def health_check():
    """Standard generic health check returning 200 OK."""
    return {"status": "ok"}

@app.post("/api/report")
def submit_bug_report(report: BugReportRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Accepts a BugReportRequest payload, saves it to the SQLite IssueReport table,
    triggers the background orchestrator, and immediately returns the tracked issue reference.
    """
    db_issue = IssueReport(
        bug_text=report.bug_text,
        file_path=report.file_path,
        status="pending"   # Sit in DB — do NOT auto-execute. Developer reviews first.
    )
    
    db.add(db_issue)
    db.commit()
    db.refresh(db_issue)
    
    return {"issue_id": db_issue.id, "status": "pending"}

@app.get("/api/issues/{issue_id}/status")
def get_issue_status(issue_id: int, db: Session = Depends(get_db)):
    """
    Queries the database and returns the current status of the requested issue.
    """
    db_issue = db.query(IssueReport).filter(IssueReport.id == issue_id).first()
    
    if db_issue is None:
        raise HTTPException(status_code=404, detail=f"Issue {issue_id} not found")
        
    pr_url = None
    if hasattr(db_issue, "pull_request") and db_issue.pull_request:
        pr_url = db_issue.pull_request.pr_url
        
    return {
        "status": db_issue.status,
        "current_step": db_issue.current_step,
        "error_message": db_issue.error_message,
        "pr_url": pr_url
    }


@app.get("/api/features/{feature_id}")
def get_feature(feature_id: int, db: Session = Depends(get_db)):
    """
    Returns full details for a single feature/issue by ID.
    """
    feature = db.query(IssueReport).filter(IssueReport.id == feature_id).first()
    if not feature:
        raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

    pr_url = None
    if feature.pull_request:
        pr_url = feature.pull_request.pr_url

    # Use the AI-generated plan from DB, fall back to template for old issues
    plan_markdown = feature.proposed_plan or (
        f"# PLAN.md: Feature #{feature.id}\n\n"
        f"## 1. Summary\n{feature.bug_text}\n\n"
        f"## 2. Files to Modify\n- `{feature.file_path}`\n\n"
        f"## 3. Implementation Steps\n"
        f"Read `{feature.file_path}` first to understand the current structure, "
        f"then apply the requested changes while preserving all existing code style and logic."
    )

    return {
        "id": feature.id,
        "bug_text": feature.bug_text,
        "file_path": feature.file_path,
        "status": feature.status,
        "current_step": feature.current_step,
        "error_message": feature.error_message,
        "last_heartbeat": feature.last_heartbeat.isoformat() if feature.last_heartbeat else None,
        "created_at": feature.created_at.isoformat() if feature.created_at else None,
        "pr_url": pr_url,
        "attempts": [
            {
                "attempt_number": a.attempt_number,
                "test_passed": a.test_passed,
                "error_logs": a.error_logs,
                "agent_logs": getattr(a, "agent_logs", None)
            } for a in feature.fix_attempts
        ],
        "plan_markdown": plan_markdown,
        "confidence_score": feature.confidence_score if feature.confidence_score is not None else 92,
        "requires_human": feature.requires_human or False,
        "is_critical": feature.requires_human or False,
    }


@app.post("/api/issues/{issue_id}/plan")
def generate_plan(issue_id: int, db: Session = Depends(get_db)):
    """
    Step 1 of the 2-step workflow.
    Calls Gemini to produce a structured implementation plan + confidence score.
    Saves result to the database. Does NOT start the coding agent.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage
    import json as _json

    issue = db.query(IssueReport).filter(IssueReport.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail=f"Issue {issue_id} not found")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not set")

    model_name = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-3.5-flash")
    planner_llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.2,
        convert_system_message_to_human=True,
    )

    planning_prompt = f"""You are a senior software engineer triaging a code change request.

ISSUE DESCRIPTION:
{issue.bug_text}

TARGET FILE: {issue.file_path}

Generate a structured implementation plan and return ONLY a valid JSON object with no markdown fencing.
The JSON must have exactly these keys:
- "implementation_plan": A detailed Markdown plan with sections for Summary, Files to Modify, and Step-by-Step Instructions.
- "confidence_score": An integer from 0 to 100.
  - 90+ if it is a simple text, label, or CSS-only change.
  - 70-89 if it requires understanding component logic or props.
  - Below 70 if it requires changes to multiple files, business logic, or APIs.
- "requires_human": Boolean. Set to true if confidence_score < 70.

Return ONLY the raw JSON object. No explanation. No markdown."""

    try:
        response = planner_llm.invoke([HumanMessage(content=planning_prompt)])
        if isinstance(response.content, list):
            raw = "".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in response.content]).strip()
        else:
            raw = str(response.content).strip()
        # Strip any accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        plan_data = _json.loads(raw)
    except Exception as exc:
        logger.error(f"[plan] Gemini planning failed: {exc}")
        # Fallback: minimal plan if Gemini fails
        plan_data = {
            "implementation_plan": (
                f"# Plan for Issue #{issue.id}\n\n"
                f"## Task\n{issue.bug_text}\n\n"
                f"## Target File\n`{issue.file_path}`\n\n"
                f"## Steps\n1. Read the file.\n2. Apply the change.\n3. Write it back."
            ),
            "confidence_score": 85,
            "requires_human": False,
        }

    # Persist to DB
    issue.proposed_plan    = plan_data["implementation_plan"]
    issue.confidence_score = int(plan_data.get("confidence_score", 85))
    issue.requires_human   = bool(plan_data.get("requires_human", False))
    issue.status           = "planned"
    db.commit()

    logger.info(f"[plan] Issue #{issue_id} plan generated. Confidence: {issue.confidence_score}")
    return {
        "plan_markdown":   issue.proposed_plan,
        "confidence_score": issue.confidence_score,
        "requires_human":  issue.requires_human,
    }


@app.post("/api/issues/{issue_id}/execute")
def execute_issue(
    issue_id: int,
    body: ExecuteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Step 2 of the 2-step workflow.
    Accepts the (possibly edited) plan from the frontend and fires the coding agent.
    """
    issue = db.query(IssueReport).filter(IssueReport.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail=f"Issue {issue_id} not found")

    if issue.status in ("processing", "completed"):
        raise HTTPException(
            status_code=400,
            detail=f"Issue is already in terminal state: {issue.status}"
        )

    # Save the final (possibly edited) plan back to DB
    if body.approved_plan:
        issue.proposed_plan = body.approved_plan

    issue.status = "approved"
    db.commit()

    approved_plan = issue.proposed_plan or ""

    # Fire the orchestrator with the approved plan
    background_tasks.add_task(
        run_orchestrator_background, issue_id, approved_plan=approved_plan
    )

    return {"status": "processing", "message": "Agent execution started. Poll /api/issues/{id}/status for updates."}

@app.post("/api/features/{feature_id}/reset")
def reset_feature(feature_id: int):
    """Resets a stuck feature to failed state so it can be retried."""
    result = reset_specific_feature(feature_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@app.get("/api/issues/{issue_id}/execute/stream")
async def stream_agent_execution(issue_id: int, db: Session = Depends(get_db)):
    issue = db.query(IssueReport).filter(IssueReport.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail=f"Issue {issue_id} not found")

    queue = asyncio.Queue()
    callback_handler = StreamingCallbackHandler(queue)
    agent = CodeAgentWithTools()

    build_plan = (
        f"# PLAN.md: Feature #{issue.id}\n\n"
        f"## 1. Summary\n{issue.bug_text}\n\n"
        f"## 2. Files to Modify\n- `{issue.file_path}`\n\n"
        f"## 3. Implementation Steps\n"
        f"Read `{issue.file_path}` first to understand the current structure, "
        f"then apply the requested changes while preserving all existing code style and logic."
    )

    async def event_generator():
        task = asyncio.create_task(
            agent.fix_with_context_streaming(
                bug_description=issue.bug_text,
                target_file_path=issue.file_path,
                build_plan=build_plan,
                callback_handler=callback_handler
            )
        )

        while True:
            payload = await queue.get()
            yield f"data: {json.dumps(payload)}\n\n"
            
            payload_type = payload.get("type")
            if payload_type in ("done", "error", "complete"):
                break
                
        await task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.post("/api/features/{feature_id}/force-stop")
def force_stop_feature(feature_id: int):
    """Force stops a feature (same as reset, just explicit intent)."""
    result = reset_specific_feature(feature_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@app.get("/api/features")
def list_features(db: Session = Depends(get_db)):
    """List all features/issues for the developer dashboard."""
    features = db.query(IssueReport).order_by(IssueReport.created_at.desc()).all()
    return [
        {
            "id": f.id,
            "bug_text": f.bug_text[:120],
            "file_path": f.file_path,
            "status": f.status,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in features
    ]


@app.get("/api/features/{feature_id}/execute/stream")
async def execute_stream(feature_id: int, db: Session = Depends(get_db)):
    """
    Server-Sent Events endpoint that streams live agent execution updates
    for the given feature_id. The client receives real-time log messages,
    LLM tokens, tool calls, and a final completion or error event.
    """

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()

        try:
            # 1. Load the IssueReport used as the feature request
            feature = db.query(IssueReport).filter(IssueReport.id == feature_id).first()

            if not feature:
                yield {
                    "event": "error",
                    "data": json.dumps({"message": f"Feature {feature_id} not found"}),
                }
                return

            if feature.status not in ("pending", "processing", "approved"):
                yield {
                    "event": "error",
                    "data": json.dumps(
                        {"message": f"Feature has status '{feature.status}' — cannot execute."}
                    ),
                }
                return

            # 2. Send initial handshake to the client
            yield {
                "event": "status",
                "data": json.dumps({"message": "🚀 Starting execution..."}),
            }

            # 3. Wire up the streaming callback → queue
            callback_handler = StreamingCallbackHandler(queue=queue)

            # 4. Define the async agent task (runs concurrently)
            async def run_agent():
                try:
                    agent = CodeAgentWithTools()

                    result = await agent.fix_with_context_streaming(
                        bug_description=feature.bug_text,
                        target_file_path=feature.file_path,
                        build_plan=None,  # extend with BuildPlan model in V2
                        callback_handler=callback_handler,
                    )

                    await queue.put({"type": "complete", "result": result})

                except Exception as exc:
                    await queue.put({"type": "error", "message": str(exc)})

            # 5. Launch the agent as a background asyncio task
            agent_task = asyncio.create_task(run_agent())

            # 6. Drain the queue and forward every message as an SSE event
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=1.0)

                    if message.get("type") == "complete":
                        yield {
                            "event": "complete",
                            "data": json.dumps(
                                {
                                    "message": "✅ Execution complete",
                                    "result": message.get("result"),
                                }
                            ),
                        }
                        break

                    elif message.get("type") == "error":
                        yield {
                            "event": "error",
                            "data": json.dumps({"message": message.get("message", "Unknown error")}),
                        }
                        break

                    elif message.get("type") == "done":
                        # Sentinel from StreamingCallbackHandler.on_agent_finish
                        break

                    else:
                        yield {
                            "event": "log",
                            "data": json.dumps(message),
                        }

                except asyncio.TimeoutError:
                    # Keep the connection alive while the agent is still working
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps({"timestamp": time.time()}),
                    }

                # Bail out if the agent task itself crashed before sending a message
                if agent_task.done() and not agent_task.cancelled():
                    exc = agent_task.exception()
                    if exc:
                        yield {
                            "event": "error",
                            "data": json.dumps({"message": str(exc)}),
                        }
                        break

        except Exception as exc:
            yield {
                "event": "error",
                "data": json.dumps({"message": f"Server error: {exc}"}),
            }

    return EventSourceResponse(event_generator())


@app.get("/api/debug/sandbox-status")
async def get_sandbox_status():
    """
    Returns diagnostic information about the sandbox environment
    """
    try:
        project_path = os.getenv("REPO_PATH", "../evocode-test-target")
        
        return {
            "status": "ok",
            "system": get_system_info(project_path),
            "npm_installed": check_npm_installed(),
            "node_installed": check_node_installed(),
            "project": validate_project_structure(project_path),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }



# ===========================================================================
# V2 API ROUTES — FeatureSignals, Comments, Upvotes
# ===========================================================================

# ---------------------------------------------------------------------------
# Helper: map FeatureSignal status to human-readable badge
# ---------------------------------------------------------------------------
_STATUS_LABEL = {
    "gathering_votes":    "Gathering Votes",
    "queued":             "Queued",
    "planning":           "AI Planning",
    "coding":             "AI Coding",
    "verifying":          "Verifying",
    "pr_ready":           "PR Ready",
    "approved_shipped":   "Shipped Live",
    "assist_mode_blocked":"Assist Mode",
    "failed":             "Failed",
    "rejected":           "Rejected",
}

def _signal_summary(s: FeatureSignal) -> dict:
    return {
        "id":               s.id,
        "title":            s.title,
        "canonical_summary": s.canonical_summary or "",
        "status":           s.status,
        "status_label":     _STATUS_LABEL.get(s.status, s.status),
        "upvote_count":     s.upvote_count,
        "confidence_score": s.confidence_score,
        "requires_human":   s.requires_human,
        "route_path":       s.route_path,
        "github_pr_url":    s.github_pr_url,
        "preview_url":      s.preview_url,
        "created_at":       s.created_at.isoformat() if s.created_at else None,
        "updated_at":       s.updated_at.isoformat() if s.updated_at else None,
    }


# ---------------------------------------------------------------------------
# GET /api/signals  — List all signals (replaces hardcoded tickets array)
# ---------------------------------------------------------------------------
@app.get("/api/signals")
def list_signals(
    status: Optional[str] = Query(None, description="Filter by status"),
    sort:   Optional[str] = Query("recent", description="trending | recent"),
    db: Session = Depends(get_db),
):
    """
    Returns all FeatureSignals for the EvoCode Dashboard.
    Replaces the old hardcoded const tickets = [...] array.
    """
    q = db.query(FeatureSignal)
    if status:
        q = q.filter(FeatureSignal.status == status)
    if sort == "trending":
        q = q.order_by(FeatureSignal.upvote_count.desc())
    else:
        q = q.order_by(FeatureSignal.created_at.desc())
    signals = q.all()
    return [_signal_summary(s) for s in signals]


# ---------------------------------------------------------------------------
# GET /api/signals/{id}  — Full signal detail for the Build/Review page
# ---------------------------------------------------------------------------
@app.get("/api/signals/{signal_id}")
def get_signal(signal_id: int, db: Session = Depends(get_db)):
    """
    Full signal details: clustered comments, plan_markdown, diff_patch,
    before/after images, preview_url, audit_events, fix_attempts.
    """
    s = db.query(FeatureSignal).filter(FeatureSignal.id == signal_id).first()
    if not s:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    comments = [
        {
            "id":                 c.id,
            "author_name":        c.author_name,
            "body":               c.body,
            "route_path":         c.route_path,
            "is_ai_clarification": c.is_ai_clarification,
            "upvotes":            c.upvotes,
            "created_at":         c.created_at.isoformat() if c.created_at else None,
        }
        for c in s.comments
    ]

    audit_events = [
        {
            "id":          e.id,
            "stage":       e.stage,
            "event_type":  e.event_type,
            "payload":     json.loads(e.payload_json) if e.payload_json else None,
            "created_at":  e.created_at.isoformat() if e.created_at else None,
        }
        for e in sorted(s.audit_events, key=lambda x: x.created_at or datetime.min)
    ]

    fix_attempts = [
        {
            "attempt_number": a.attempt_number,
            "ast_passed":     a.ast_passed,
            "tests_passed":   a.tests_passed,
            "visual_passed":  a.visual_passed,
            "error_log":      a.error_log,
            "created_at":     a.created_at.isoformat() if a.created_at else None,
        }
        for a in s.v2_fix_attempts
    ]

    return {
        **_signal_summary(s),
        "plan_markdown":       s.plan_markdown,
        "strategy_guide":      s.strategy_guide,
        "diff_patch":          s.diff_patch,
        "before_img_path":     s.before_img_path,
        "after_img_path":      s.after_img_path,
        "visual_verdict":      json.loads(s.visual_verdict) if s.visual_verdict else None,
        "github_issue_number": s.github_issue_number,
        "github_pr_number":    s.github_pr_number,
        "branch_name":         s.branch_name,
        "current_step":        s.current_step,
        "error_message":       s.error_message,
        "execution_mode":      s.execution_mode,
        "tokens_used":         s.tokens_used,
        "latency_ms":          s.latency_ms,
        "comments":            comments,
        "audit_events":        audit_events,
        "fix_attempts":        fix_attempts,
    }


# ---------------------------------------------------------------------------
# GET /api/signals/{id}/stream  — SSE stream for LiveTerminal
# ---------------------------------------------------------------------------
@app.get("/api/signals/{signal_id}/stream")
async def stream_signal(signal_id: int, db: Session = Depends(get_db)):
    """
    Server-Sent Events stream for the LiveTerminal component.
    Replays existing AuditEvents and then keeps the connection alive
    while the agent is running (polling DB every 2s for new events).
    """
    signal = db.query(FeatureSignal).filter(FeatureSignal.id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    seen_ids: set = set()

    async def event_generator():
        # Yield initial status
        yield {
            "event": "status",
            "data":  json.dumps({"message": f"Streaming signal #{signal_id}", "status": signal.status}),
        }

        terminal_statuses = {"approved_shipped", "failed", "rejected", "assist_mode_blocked"}
        while True:
            # Fresh session per tick to pick up commits from background workers
            tick_db = SessionLocal()
            try:
                sig = tick_db.query(FeatureSignal).filter(FeatureSignal.id == signal_id).first()
                if not sig:
                    break

                new_events = (
                    tick_db.query(AuditEvent)
                    .filter(AuditEvent.signal_id == signal_id)
                    .filter(AuditEvent.id.notin_(seen_ids) if seen_ids else True)
                    .order_by(AuditEvent.created_at)
                    .all()
                )
                for ev in new_events:
                    seen_ids.add(ev.id)
                    yield {
                        "event": "log",
                        "data":  json.dumps({
                            "type":       ev.event_type,
                            "stage":      ev.stage,
                            "payload":    json.loads(ev.payload_json) if ev.payload_json else None,
                            "created_at": ev.created_at.isoformat() if ev.created_at else None,
                        }),
                    }

                if sig.status in terminal_statuses:
                    yield {
                        "event": "complete",
                        "data":  json.dumps({"status": sig.status, "pr_url": sig.github_pr_url}),
                    }
                    break

                yield {
                    "event": "heartbeat",
                    "data":  json.dumps({"timestamp": time.time(), "status": sig.status}),
                }
            finally:
                tick_db.close()

            await asyncio.sleep(2)

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# POST /api/comments  — Receive a comment from the target website
# ---------------------------------------------------------------------------
def _run_triage_in_background(comment_id: int, signal_id: int, body: str, route_path: str, author_name: str):
    """Background task: LLM vagueness check + AI clarification storage (non-blocking)."""
    try:
        db = SessionLocal()
        is_vague, ai_reply = check_vagueness(body)

        # Store AI clarification reply if vague
        if is_vague and ai_reply:
            ai_comment = Comment(
                signal_id=signal_id,
                author_name="EvoCode AI",
                body=ai_reply,
                route_path=route_path,
                is_ai_clarification=True,
            )
            db.add(ai_comment)

        # Update audit event with vagueness result
        audit = AuditEvent(
            signal_id=signal_id,
            stage="triage",
            event_type="vagueness_check",
            payload_json=json.dumps({
                "author": author_name,
                "route": route_path,
                "is_vague": is_vague,
                "has_ai_reply": bool(ai_reply),
                "comment_id": comment_id,
            }),
        )
        db.add(audit)
        db.commit()
        db.close()
        logger.info(f"[triage_bg] Comment {comment_id} triage complete — is_vague={is_vague}")
    except Exception as e:
        logger.warning(f"[triage_bg] Background triage failed for comment {comment_id}: {e}")
        try:
            db.close()
        except Exception:
            pass


@app.post("/api/comments")
def create_comment(req: CommentCreateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Receives a comment from the embedded FeedbackComments widget on the
    target website. Immediately creates a signal + comment and returns fast.
    LLM vagueness check runs in the background.
    """
    # 1. Fast keyword-based signal clustering (no LLM) — immediate response
    signal = cluster_comment_into_signal(req.body, req.route_path or "/", db)

    # 2. Store the user comment immediately
    console_errors_json = json.dumps(req.console_errors) if req.console_errors else None
    comment = Comment(
        signal_id=signal.id,
        author_name=req.author_name or "Anonymous",
        body=req.body,
        route_path=req.route_path,
        console_errors_json=console_errors_json,
        is_ai_clarification=False,
    )
    db.add(comment)

    # 3. Log audit event immediately
    audit = AuditEvent(
        signal_id=signal.id,
        stage="triage",
        event_type="comment_received",
        payload_json=json.dumps({
            "author": req.author_name,
            "route": req.route_path,
            "comment_body_preview": req.body[:80],
        }),
    )
    db.add(audit)
    db.commit()
    db.refresh(comment)
    db.refresh(signal)

    # 4. Run LLM vagueness check in background (non-blocking)
    background_tasks.add_task(
        _run_triage_in_background,
        comment.id, signal.id, req.body, req.route_path or "/", req.author_name or "Anonymous"
    )

    return {
        "comment_id":    comment.id,
        "signal_id":     signal.id,
        "signal_status": signal.status,
        "upvote_count":  signal.upvote_count,
        "ai_reply":      None,   # Will be posted async by background triage
        "is_vague":      False,  # Determined async
    }


# ---------------------------------------------------------------------------
# GET /api/comments  — List comments for a route (used by FeedbackComments widget)
# ---------------------------------------------------------------------------
@app.get("/api/comments")
def list_comments(route: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """
    Returns comments for a given route_path, with their linked FeatureSignal status.
    Used by the embedded FeedbackComments widget on the target website.
    """
    q = db.query(Comment)
    if route:
        q = q.filter(Comment.route_path == route)
    comments = q.order_by(Comment.created_at.desc()).limit(50).all()

    result = []
    for c in comments:
        signal_status = None
        raw_status = None
        pr_url = None
        preview_url = None
        if c.signal_id:
            sig = db.query(FeatureSignal).filter(FeatureSignal.id == c.signal_id).first()
            if sig:
                signal_status = _STATUS_LABEL.get(sig.status, sig.status)
                raw_status = sig.status
                pr_url = sig.github_pr_url
                preview_url = sig.preview_url
        result.append({
            "id":                 c.id,
            "signal_id":          c.signal_id,
            "author_name":        c.author_name,
            "body":               c.body,
            "route_path":         c.route_path,
            "upvotes":            c.upvotes,
            "is_ai_clarification": c.is_ai_clarification,
            "signal_status":      signal_status,
            "raw_status":         raw_status,
            "pr_url":             pr_url,
            "preview_url":        preview_url,
            "created_at":         c.created_at.isoformat() if c.created_at else None,
        })
    return result


# ---------------------------------------------------------------------------
# POST /api/comments/{id}/upvote  — Upvote a comment / signal
# ---------------------------------------------------------------------------
@app.post("/api/comments/{comment_id}/upvote")
def upvote_comment(comment_id: int, req: UpvoteRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Increments the signal's upvote_count. Prevents duplicate votes via
    voter_fingerprint unique constraint. Triggers autonomous build if
    upvote_count >= UPVOTE_THRESHOLD and status == gathering_votes.
    """
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment or not comment.signal_id:
        raise HTTPException(status_code=404, detail="Comment or linked signal not found")

    signal = db.query(FeatureSignal).filter(FeatureSignal.id == comment.signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    # Check for duplicate vote
    existing_vote = (
        db.query(Upvote)
        .filter(Upvote.signal_id == signal.id)
        .filter(Upvote.voter_fingerprint == req.voter_fingerprint)
        .first()
    )
    if existing_vote:
        return {
            "signal_id":    signal.id,
            "upvote_count": signal.upvote_count,
            "triggered_build": False,
            "status":       signal.status,
            "message":      "Already voted",
        }

    # Record vote
    vote = Upvote(
        signal_id=signal.id,
        comment_id=comment_id,
        voter_fingerprint=req.voter_fingerprint,
    )
    db.add(vote)
    signal.upvote_count = (signal.upvote_count or 0) + 1
    comment.upvotes = (comment.upvotes or 0) + 1

    upvote_threshold = int(os.getenv("UPVOTE_THRESHOLD", "1"))
    triggered_build = False

    if signal.upvote_count >= upvote_threshold and signal.status == "gathering_votes":
        triggered_build = trigger_autonomous_build(signal.id, db, background_tasks)

    db.commit()

    return {
        "signal_id":       signal.id,
        "upvote_count":    signal.upvote_count,
        "triggered_build": triggered_build,
        "status":          signal.status,
    }


# ---------------------------------------------------------------------------
# POST /api/signals/{id}/approve  — One-click Approve & Ship (Phase 5)
# ---------------------------------------------------------------------------
@app.post("/api/signals/{signal_id}/approve")
def approve_signal(
    signal_id: int,
    override_confidence: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Squash-merges the PR, deletes the feature branch, marks approved_shipped.
    Verifies confidence_score >= 70 unless override_confidence is True.
    """
    signal = db.query(FeatureSignal).filter(FeatureSignal.id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    if signal.status != "pr_ready":
        raise HTTPException(status_code=400, detail=f"Signal is in state '{signal.status}', must be 'pr_ready' to approve")

    if (signal.confidence_score or 0) < 70 and not override_confidence:
        raise HTTPException(status_code=403, detail="Auto-merge blocked: confidence_score < 70. Manual review required.")

    # Call GitHubManager to squash merge and delete branch
    merge_sha = None
    gh_token = os.getenv("GITHUB_TOKEN")
    gh_owner = os.getenv("REPO_OWNER")
    gh_name = os.getenv("REPO_NAME")

    if gh_token and gh_owner and gh_name and signal.github_pr_number:
        try:
            gh = GitHubManager(gh_token, gh_owner, gh_name)
            auth_res = gh.authenticate()
            if auth_res.get("success"):
                merge_res = gh.merge_pull_request(
                    signal.github_pr_number,
                    commit_title=f"Merge PR #{signal.github_pr_number}: {signal.title}"
                )
                if merge_res.get("success"):
                    merge_sha = merge_res.get("data", {}).get("sha")
                if signal.branch_name:
                    gh.delete_branch(signal.branch_name)
                if signal.github_issue_number:
                    gh.close_issue(signal.github_issue_number, comment=f"Auto-closed by EvoCode: Closes #{signal.github_issue_number} upon squash-merging PR #{signal.github_pr_number}")
            else:
                logger.warning(f"[approve_signal] GitHub auth notice: {auth_res.get('error')}. Proceeding with state transition.")
        except Exception as e:
            logger.warning(f"[approve_signal] GitHub merge call notice: {e}. Marking approved in database.")

    signal.status = "approved_shipped"
    db.add(AuditEvent(
        signal_id=signal.id,
        stage="deploy",
        event_type="approved_by_developer",
        payload_json=json.dumps({"pr_url": signal.github_pr_url, "merge_sha": merge_sha, "branch": signal.branch_name}),
    ))
    db.commit()
    return {
        "approved": True,
        "merged": True,
        "merge_sha": merge_sha,
        "pr_url": signal.github_pr_url,
        "status": signal.status
    }


# ---------------------------------------------------------------------------
# POST /api/signals/{id}/reject  — Reject a PR
# ---------------------------------------------------------------------------
@app.post("/api/signals/{signal_id}/reject")
def reject_signal(signal_id: int, db: Session = Depends(get_db)):
    """
    Closes the PR and deletes the branch. Full GitHub integration in Phase 5.
    """
    signal = db.query(FeatureSignal).filter(FeatureSignal.id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    gh_token = os.getenv("GITHUB_TOKEN")
    gh_owner = os.getenv("REPO_OWNER")
    gh_name = os.getenv("REPO_NAME")

    if gh_token and gh_owner and gh_name and signal.github_pr_number:
        try:
            gh = GitHubManager(gh_token, gh_owner, gh_name)
            if gh.authenticate().get("success"):
                gh.close_pull_request(signal.github_pr_number)
                if signal.branch_name:
                    gh.delete_branch(signal.branch_name)
                if signal.github_issue_number:
                    gh.close_issue(signal.github_issue_number, comment=f"EvoCode: PR #{signal.github_pr_number} was rejected by developer.")
        except Exception as e:
            logger.warning(f"[reject_signal] GitHub reject notice: {e}")

    signal.status = "rejected"
    db.add(AuditEvent(
        signal_id=signal.id,
        stage="deploy",
        event_type="rejected_by_developer",
        payload_json=json.dumps({"pr_url": signal.github_pr_url}),
    ))
    db.commit()
    return {"rejected": True, "closed": True, "status": signal.status}


# ---------------------------------------------------------------------------
# POST /api/signals/{id}/retry  — Re-queue with edited plan
# ---------------------------------------------------------------------------
@app.post("/api/signals/{signal_id}/retry")
def retry_signal(signal_id: int, plan_markdown: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Accepts an edited plan_markdown, resets status to queued, re-runs orchestrator.
    """
    signal = db.query(FeatureSignal).filter(FeatureSignal.id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    if plan_markdown:
        signal.plan_markdown = plan_markdown
    signal.status = "queued"
    signal.error_message = None
    db.add(AuditEvent(
        signal_id=signal.id,
        stage="triage",
        event_type="retried_by_developer",
        payload_json=json.dumps({"new_plan_provided": bool(plan_markdown)}),
    ))
    db.commit()
    return {"queued": True, "signal_id": signal.id}


# ---------------------------------------------------------------------------
# POST /api/webhooks/github  — Production Deployment Webhook (Phase 5)
# ---------------------------------------------------------------------------
@app.post("/api/webhooks/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Webhook endpoint listening for GitHub/Vercel deployment events.
    Verifies HMAC-SHA256 signature when secret is configured.
    On deployment_status with state == 'success' and environment == 'Production',
    marks matching FeatureSignal as 'approved_shipped' / production deployed.
    """
    raw_body = await request.body()

    # Signature verification
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if secret and secret != "your_webhook_secret_here" and x_hub_signature_256:
        import hmac
        import hashlib
        computed = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(computed, x_hub_signature_256):
            raise HTTPException(status_code=401, detail="Invalid HMAC-SHA256 webhook signature")

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception:
        payload = {}

    event_type = x_github_event or payload.get("event")
    logger.info(f"[webhook] Received GitHub webhook event: {event_type}")

    # GitHub ping handshake
    if event_type == "ping":
        return {"status": "ok", "message": "pong"}

    # Process pull_request merged event
    if event_type == "pull_request" or "pull_request" in payload:
        pr_data = payload.get("pull_request", {})
        action = payload.get("action")
        is_merged = pr_data.get("merged", False)
        pr_number = pr_data.get("number")
        if (action == "closed" and is_merged) or is_merged:
            matched_signal = None
            if pr_number:
                matched_signal = db.query(FeatureSignal).filter(FeatureSignal.github_pr_number == pr_number).first()
            if not matched_signal and pr_data.get("head", {}).get("ref"):
                head_ref = pr_data["head"]["ref"]
                matched_signal = db.query(FeatureSignal).filter(FeatureSignal.branch_name.contains(head_ref)).first()
            if matched_signal:
                matched_signal.status = "approved_shipped"
                db.add(AuditEvent(
                    signal_id=matched_signal.id,
                    stage="deploy",
                    event_type="pr_merged_on_github",
                    payload_json=json.dumps({"pr_number": pr_number, "action": action, "merged": True}),
                ))
                db.commit()
                logger.info(f"[webhook] Signal #{matched_signal.id} marked approved_shipped via pull_request webhook")
                return {"status": "ok", "signal_id": matched_signal.id, "shipped": True}

    # Process deployment_status event
    if event_type == "deployment_status" or "deployment_status" in payload:
        dep_status = payload.get("deployment_status", {})
        deployment = payload.get("deployment", {})
        state = dep_status.get("state")
        environment = deployment.get("environment", "").lower()
        ref = deployment.get("ref", "")
        target_url = dep_status.get("target_url") or dep_status.get("environment_url")

        logger.info(f"[webhook] Deployment status: state={state}, env={environment}, ref={ref}")

        if state == "success":
            matched_signal = None
            if ref:
                matched_signal = (
                    db.query(FeatureSignal)
                    .filter(FeatureSignal.branch_name.contains(ref))
                    .order_by(FeatureSignal.id.desc())
                    .first()
                )

            if not matched_signal:
                matched_signal = (
                    db.query(FeatureSignal)
                    .filter(FeatureSignal.status.in_(["pr_ready", "approved_shipped"]))
                    .order_by(FeatureSignal.updated_at.desc())
                    .first()
                )

            if matched_signal:
                matched_signal.status = "approved_shipped"
                if target_url:
                    matched_signal.preview_url = target_url
                db.add(AuditEvent(
                    signal_id=matched_signal.id,
                    stage="deploy",
                    event_type="production_deployment_success",
                    payload_json=json.dumps({
                        "environment": environment,
                        "url": target_url,
                        "ref": ref
                    }),
                ))
                db.commit()
                logger.info(f"[webhook] Signal #{matched_signal.id} marked approved_shipped via deployment webhook")
                return {"status": "ok", "signal_id": matched_signal.id, "shipped": True}

    return {"status": "ok", "message": f"Event {event_type} received"}
