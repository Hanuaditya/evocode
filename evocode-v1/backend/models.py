"""
backend/models.py

V2 schema: Adds FeatureSignal, Comment, Upvote, AuditEvent tables.
Keeps IssueReport, FixAttempt, PullRequest for V1 backward-compatibility
(all 7 existing GitHub PRs stay intact in the DB).
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, Text,
    DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from database import Base


# ---------------------------------------------------------------------------
# V1 tables (kept intact for backward compatibility)
# ---------------------------------------------------------------------------

class IssueReport(Base):
    __tablename__ = "issue_reports"

    id               = Column(Integer, primary_key=True, index=True)
    bug_text         = Column(String, nullable=False)
    file_path        = Column(String, nullable=False)
    status           = Column(String, default="pending", index=True)
    current_step     = Column(String, nullable=True)
    error_message    = Column(String, nullable=True)
    proposed_plan    = Column(Text, nullable=True)
    confidence_score = Column(Integer, nullable=True)
    requires_human   = Column(Boolean, default=False)
    last_heartbeat   = Column(DateTime, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    fix_attempts = relationship("FixAttempt", back_populates="issue_report", cascade="all, delete-orphan")
    pull_request = relationship("PullRequest", back_populates="issue_report", uselist=False, cascade="all, delete-orphan")


class FixAttempt(Base):
    __tablename__ = "fix_attempts"

    id             = Column(Integer, primary_key=True, index=True)
    issue_id       = Column(Integer, ForeignKey("issue_reports.id"))
    attempt_number = Column(Integer)
    generated_code = Column(String)
    test_passed    = Column(Boolean, default=False)
    error_logs     = Column(String)
    created_at     = Column(DateTime, default=datetime.utcnow)

    issue_report = relationship("IssueReport", back_populates="fix_attempts")


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id          = Column(Integer, primary_key=True, index=True)
    issue_id    = Column(Integer, ForeignKey("issue_reports.id"), unique=True)
    pr_url      = Column(String)
    branch_name = Column(String)
    status      = Column(String, default="pending")
    created_at  = Column(DateTime, default=datetime.utcnow)

    issue_report = relationship("IssueReport", back_populates="pull_request")


# ---------------------------------------------------------------------------
# V2 tables
# ---------------------------------------------------------------------------

class FeatureSignal(Base):
    """
    Master entity that tracks a clustered user request from vote-gathering
    all the way through live production deployment.

    Status lifecycle:
      gathering_votes → queued → planning → coding → verifying
      → pr_ready → approved_shipped
      (error branches: assist_mode_blocked, failed, rejected)
    """
    __tablename__ = "feature_signals"

    id                  = Column(Integer, primary_key=True, index=True)
    title               = Column(String, nullable=False)
    canonical_summary   = Column(Text, nullable=True)       # AI-merged summary of clustered comments
    status              = Column(String, default="gathering_votes", index=True)
    execution_mode      = Column(String, default="autonomous_pr")  # autonomous_pr | plan_gate
    upvote_count        = Column(Integer, default=0)
    route_path          = Column(String, nullable=True)     # e.g. /pricing, /about

    # Planning output
    confidence_score    = Column(Integer, nullable=True)    # 0–100
    requires_human      = Column(Boolean, default=False)    # True when score < 70
    plan_markdown       = Column(Text, nullable=True)
    strategy_guide      = Column(Text, nullable=True)       # Only for assist_mode_blocked

    # Execution output
    diff_patch          = Column(Text, nullable=True)
    github_issue_number = Column(Integer, nullable=True)
    github_pr_number    = Column(Integer, nullable=True)
    github_pr_url       = Column(String, nullable=True)
    branch_name         = Column(String, nullable=True)
    preview_url         = Column(String, nullable=True)     # Vercel Preview URL

    # Visual verification
    before_img_path     = Column(String, nullable=True)
    after_img_path      = Column(String, nullable=True)
    visual_verdict      = Column(Text, nullable=True)       # JSON from Gemini Vision Judge

    # Telemetry
    tokens_used         = Column(Integer, default=0)
    latency_ms          = Column(Integer, default=0)
    error_message       = Column(String, nullable=True)
    current_step        = Column(String, nullable=True)
    last_heartbeat      = Column(DateTime, nullable=True)

    created_at          = Column(DateTime, default=datetime.utcnow)
    updated_at          = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    comments     = relationship("Comment", back_populates="signal", cascade="all, delete-orphan")
    upvotes      = relationship("Upvote", back_populates="signal", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="signal", cascade="all, delete-orphan")
    v2_fix_attempts = relationship("V2FixAttempt", back_populates="signal", cascade="all, delete-orphan")


class Comment(Base):
    """
    Raw user comment from the target website, plus optional AI clarification reply.
    """
    __tablename__ = "comments"

    id                   = Column(Integer, primary_key=True, index=True)
    signal_id            = Column(Integer, ForeignKey("feature_signals.id"), nullable=True, index=True)
    author_name          = Column(String, nullable=False, default="Anonymous")
    body                 = Column(Text, nullable=False)
    route_path           = Column(String, nullable=True)        # window.location.pathname
    console_errors_json  = Column(Text, nullable=True)          # JSON array of console errors
    screenshot_url       = Column(String, nullable=True)
    is_ai_clarification  = Column(Boolean, default=False)
    upvotes              = Column(Integer, default=0)
    created_at           = Column(DateTime, default=datetime.utcnow)

    signal = relationship("FeatureSignal", back_populates="comments")


class Upvote(Base):
    """
    Tracks unique upvotes per signal to prevent spam.
    voter_fingerprint is a hashed browser identifier (no PII stored).
    """
    __tablename__ = "upvotes"
    __table_args__ = (
        UniqueConstraint("signal_id", "voter_fingerprint", name="uq_signal_voter"),
    )

    id               = Column(Integer, primary_key=True, index=True)
    signal_id        = Column(Integer, ForeignKey("feature_signals.id"), nullable=False, index=True)
    comment_id       = Column(Integer, ForeignKey("comments.id"), nullable=True)
    voter_fingerprint = Column(String, nullable=False)
    created_at       = Column(DateTime, default=datetime.utcnow)

    signal = relationship("FeatureSignal", back_populates="upvotes")


class AuditEvent(Base):
    """
    Append-only timestamped log powering the 'When' panel in the dashboard
    and the SSE replay stream.
    """
    __tablename__ = "audit_events"

    id           = Column(Integer, primary_key=True, index=True)
    signal_id    = Column(Integer, ForeignKey("feature_signals.id"), nullable=False, index=True)
    stage        = Column(String, nullable=False)   # triage | plan | code | ast | test | visual | pr | deploy
    event_type   = Column(String, nullable=False)   # e.g. llm_call, tool_start, test_pass
    payload_json = Column(Text, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)

    signal = relationship("FeatureSignal", back_populates="audit_events")


class V2FixAttempt(Base):
    """
    Tracks self-healing retry loop diagnostics for FeatureSignal executions.
    (Separate from V1 FixAttempt to avoid schema conflicts.)
    """
    __tablename__ = "v2_fix_attempts"

    id             = Column(Integer, primary_key=True, index=True)
    signal_id      = Column(Integer, ForeignKey("feature_signals.id"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)   # 1–3
    ast_passed     = Column(Boolean, default=False)
    tests_passed   = Column(Boolean, default=False)
    visual_passed  = Column(Boolean, default=False)
    error_log      = Column(Text, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)

    signal = relationship("FeatureSignal", back_populates="v2_fix_attempts")
