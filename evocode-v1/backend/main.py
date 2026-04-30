import os
import asyncio
import time
import json
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from sse_starlette.sse import EventSourceResponse

# Import utilities and DB mapping
from database import create_all_tables, get_db, SessionLocal
from models import IssueReport

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
app = FastAPI(title="EvoCode V1 API", lifespan=lifespan)

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request schema for Pydantic
class BugReportRequest(BaseModel):
    bug_text: str
    file_path: str

class ExecuteRequest(BaseModel):
    approved_plan: str = ""   # Full markdown plan from the frontend textarea


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

    planner_llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
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
        raw = response.content.strip()
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
