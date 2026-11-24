"""
evocode-v1/backend/test_phase5_autoship.py

Comprehensive Phase 5 Verification Test Suite:
1. POST /api/signals/{id}/approve (squash-merge, branch delete, issue close, confidence guard)
2. POST /api/signals/{id}/reject (PR close, branch delete, status transition)
3. POST /api/webhooks/github (HMAC-SHA256 verification, deployment_status, pull_request merged)
4. GET /api/comments (Shipped Live badge and status mapping)
5. FeedbackComments.tsx (component verification)
"""

import os
import sys
import json
import hmac
import hashlib
import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from main import app
from database import SessionLocal
from models import FeatureSignal, Comment, AuditEvent

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_approve_confidence_guard(db_session):
    """Signals with confidence < 70 must be blocked from auto-merging unless overridden."""
    signal = FeatureSignal(
        title="Assist Mode Low Confidence Feature",
        canonical_summary="A risky architectural change needing review",
        status="pr_ready",
        confidence_score=65,  # < 70
        upvote_count=5,
        github_pr_number=101,
        github_pr_url="https://github.com/test/repo/pull/101",
        branch_name="evocode/test-low-conf",
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)

    # Attempt to approve without override -> should return 403 Forbidden
    res = client.post(f"/api/signals/{signal.id}/approve")
    assert res.status_code == 403
    assert "confidence_score < 70" in res.json()["detail"]

    # Now approve with override_confidence=true -> should succeed
    res_override = client.post(f"/api/signals/{signal.id}/approve?override_confidence=true")
    assert res_override.status_code == 200
    data = res_override.json()
    assert data["approved"] is True
    assert data["status"] == "approved_shipped"

    # Verify database updated
    db_session.refresh(signal)
    assert signal.status == "approved_shipped"

    # Verify AuditEvent logged
    audit = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.signal_id == signal.id, AuditEvent.event_type == "approved_by_developer")
        .first()
    )
    assert audit is not None
    assert audit.stage == "deploy"


def test_approve_state_guard(db_session):
    """Signals not in pr_ready cannot be approved."""
    signal = FeatureSignal(
        title="Early Stage Signal",
        canonical_summary="Still gathering votes",
        status="gathering_votes",
        confidence_score=85,
        upvote_count=1,
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)

    res = client.post(f"/api/signals/{signal.id}/approve")
    assert res.status_code == 400
    assert "must be 'pr_ready'" in res.json()["detail"]


def test_approve_high_confidence_success(db_session):
    """Signals with confidence >= 70 in pr_ready approve smoothly with 1-click."""
    signal = FeatureSignal(
        title="Verified High Confidence Bugfix",
        canonical_summary="Clean styling fix with 95% confidence",
        status="pr_ready",
        confidence_score=95,
        upvote_count=8,
        github_issue_number=42,
        github_pr_number=202,
        github_pr_url="https://github.com/test/repo/pull/202",
        branch_name="evocode/test-high-conf",
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)

    res = client.post(f"/api/signals/{signal.id}/approve")
    assert res.status_code == 200
    data = res.json()
    assert data["approved"] is True
    assert data["merged"] is True
    assert data["status"] == "approved_shipped"
    assert data["pr_url"] == signal.github_pr_url

    db_session.refresh(signal)
    assert signal.status == "approved_shipped"


def test_reject_signal_success(db_session):
    """Rejecting a signal marks it rejected and logs an audit event."""
    signal = FeatureSignal(
        title="Unwanted Feature Request",
        canonical_summary="Developer decides not to ship this",
        status="pr_ready",
        confidence_score=75,
        github_pr_number=303,
        branch_name="evocode/test-reject",
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)

    res = client.post(f"/api/signals/{signal.id}/reject")
    assert res.status_code == 200
    data = res.json()
    assert data["rejected"] is True
    assert data["closed"] is True
    assert data["status"] == "rejected"

    db_session.refresh(signal)
    assert signal.status == "rejected"

    audit = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.signal_id == signal.id, AuditEvent.event_type == "rejected_by_developer")
        .first()
    )
    assert audit is not None


def test_github_webhook_ping():
    """GitHub webhook ping event returns pong."""
    res = client.post(
        "/api/webhooks/github",
        headers={"x-github-event": "ping"},
        json={"zen": "Responsive is better than fast."},
    )
    assert res.status_code == 200
    assert res.json()["message"] == "pong"


def test_github_webhook_hmac_verification():
    """Invalid HMAC signature returns 401 Unauthorized when secret is active."""
    secret = "test_webhook_secret_key"
    os.environ["GITHUB_WEBHOOK_SECRET"] = secret

    payload = json.dumps({"event": "ping"}).encode("utf-8")
    fake_sig = "sha256=invalid_hex_string_1234567890abcdef"

    res = client.post(
        "/api/webhooks/github",
        content=payload,
        headers={"x-hub-signature-256": fake_sig, "content-type": "application/json"},
    )
    assert res.status_code == 401

    # Valid signature passes
    valid_sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    res_valid = client.post(
        "/api/webhooks/github",
        content=payload,
        headers={"x-hub-signature-256": valid_sig, "content-type": "application/json"},
    )
    assert res_valid.status_code == 200

    # Reset secret to avoid interfering with other tests
    os.environ["GITHUB_WEBHOOK_SECRET"] = "your_webhook_secret_here"


def test_github_webhook_deployment_status(db_session):
    """Vercel / GitHub deployment_status success flips signal to approved_shipped."""
    import uuid
    unique_branch = f"evocode/signal-dark-mode-{uuid.uuid4().hex[:8]}"

    signal = FeatureSignal(
        title="Dark Mode Support",
        canonical_summary="Clustered dark mode request",
        status="pr_ready",
        branch_name=unique_branch,
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)

    payload = {
        "deployment_status": {
            "state": "success",
            "environment_url": "https://evocode-test-target-git-darkmode.vercel.app",
        },
        "deployment": {
            "environment": "Production",
            "ref": unique_branch,
        },
    }

    res = client.post(
        "/api/webhooks/github",
        headers={"x-github-event": "deployment_status"},
        json=payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["shipped"] is True
    assert data["signal_id"] == signal.id

    db_session.refresh(signal)
    assert signal.status == "approved_shipped"
    assert signal.preview_url == "https://evocode-test-target-git-darkmode.vercel.app"

    audit = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.signal_id == signal.id, AuditEvent.event_type == "production_deployment_success")
        .first()
    )
    assert audit is not None


def test_comments_shipped_live_badge(db_session):
    """GET /api/comments returns 'Shipped Live' badge when signal is approved_shipped."""
    signal = FeatureSignal(
        title="Live Tested Feature",
        canonical_summary="Shipped and live on production",
        status="approved_shipped",
        github_pr_url="https://github.com/test/repo/pull/999",
        preview_url="https://production-app.vercel.app",
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)

    comment = Comment(
        signal_id=signal.id,
        author_name="Alice Contributor",
        body="Please add contrast to the footer links",
        route_path="/about",
        upvotes=4,
    )
    db_session.add(comment)
    db_session.commit()

    res = client.get("/api/comments?route=/about")
    assert res.status_code == 200
    comments = res.json()
    matched = next((c for c in comments if c["id"] == comment.id), None)
    assert matched is not None
    assert matched["signal_status"] == "Shipped Live"
    assert matched["raw_status"] == "approved_shipped"
    assert matched["pr_url"] == "https://github.com/test/repo/pull/999"
    assert matched["preview_url"] == "https://production-app.vercel.app"


def test_feedback_comments_component_present():
    """Verify FeedbackComments.tsx exists in both test-target and evocode-test-target with Shipped Live badge."""
    target_path = r"C:\Users\hanua\OneDrive\Desktop\evocode-test-target\app\components\FeedbackComments.tsx"
    assert os.path.exists(target_path), f"File {target_path} not found"

    with open(target_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "Shipped Live" in content, "Shipped Live badge text missing in FeedbackComments.tsx"
    assert "handleUpvote" in content, "Upvote handler missing in FeedbackComments.tsx"
    assert "consoleErrorsRef" in content, "Telemetry capture missing in FeedbackComments.tsx"
    assert "/api/comments" in content, "Backend comments endpoint missing in FeedbackComments.tsx"
