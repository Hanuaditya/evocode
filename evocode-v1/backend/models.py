from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

# Import Base from database module
from database import Base

class IssueReport(Base):
    __tablename__ = "issue_reports"

    id = Column(Integer, primary_key=True, index=True)
    bug_text = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    status = Column(String, default="pending", index=True) # pending, planned, processing, completed, failed
    current_step = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    proposed_plan = Column(Text, nullable=True)        # AI-generated Markdown plan
    confidence_score = Column(Integer, nullable=True)  # 0-100 from Gemini
    requires_human = Column(Boolean, default=False)    # True when confidence < 70
    last_heartbeat = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Bidirectional relationships
    fix_attempts = relationship("FixAttempt", back_populates="issue_report", cascade="all, delete-orphan")
    pull_request = relationship("PullRequest", back_populates="issue_report", uselist=False, cascade="all, delete-orphan")


class FixAttempt(Base):
    __tablename__ = "fix_attempts"

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issue_reports.id"))
    attempt_number = Column(Integer)
    generated_code = Column(String)
    test_passed = Column(Boolean, default=False)
    error_logs = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Back reference to IssueReport
    issue_report = relationship("IssueReport", back_populates="fix_attempts")


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True, index=True)
    # unique=True enforces a 1-to-1 relationship between IssueReport and PullRequest
    issue_id = Column(Integer, ForeignKey("issue_reports.id"), unique=True)
    pr_url = Column(String)
    branch_name = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Back reference to IssueReport
    issue_report = relationship("IssueReport", back_populates="pull_request")
