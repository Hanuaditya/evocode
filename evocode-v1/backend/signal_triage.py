"""
backend/signal_triage.py

Handles semantic clustering, vagueness detection, and build threshold orchestration
for user feedback comments in EvoCode V2.

Features:
- check_vagueness: evaluates user comments and generates 1-line clarification questions.
- cluster_comment_into_signal: matches comments into existing open FeatureSignals or creates new ones.
- merge_canonical_summary: synthesizes multiple user comments into one unified spec.
- trigger_autonomous_build: sets status=queued and records AuditEvent when threshold is crossed.
- Security: Wraps user comments in <user_comment>...</user_comment> XML delimiters to prevent prompt injection.
"""

import json
import logging
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks

from models import FeatureSignal, Comment, AuditEvent
from llm_router import call_with_fallback

logger = logging.getLogger("signal_triage")


# Common vague phrases for fast fallback
_VAGUE_PHRASES = {
    "fix it", "fix this", "it is broken", "broken", "bug", "error",
    "doesn't work", "not working", "help", "plz fix", "please fix",
    "bad", "wrong", "update it", "change it"
}


def check_vagueness(comment_body: str) -> Tuple[bool, Optional[str]]:
    """
    Checks if a user comment is too vague to be actionable.
    Returns:
        (is_vague: bool, clarification_reply: str | None)
    """
    clean_text = comment_body.strip()
    if not clean_text:
        return True, "Could you describe what behavior you expected to see?"

    # Fast heuristic check for short vague inputs
    lower_text = clean_text.lower().rstrip(".!?")
    if lower_text in _VAGUE_PHRASES or len(clean_text.split()) <= 2 and any(v in lower_text for v in ["fix", "broke", "bug", "error"]):
        return True, "Could you share more details on what specifically happened or what should be changed?"

    prompt = f"""You are a product triage assistant for a web application.
Evaluate whether the following user feedback comment is too vague to be actionable by a developer or AI coding agent.

An actionable comment gives a concrete bug, visual issue, or feature request (e.g. "add dark mode", "the checkout button is cut off", "site is too bright at night", "footer links are 404").
A vague comment gives almost zero detail (e.g. "fix this", "it doesn't work", "something is broken", "bad design", "fix bug").

User comment to evaluate:
<user_comment>
{clean_text}
</user_comment>

Respond strictly in valid JSON format:
{{
  "is_vague": true or false,
  "clarification_reply": "A concise, friendly 1-sentence question asking the user for specific details" or null
}}"""

    try:
        raw_resp = call_with_fallback(
            prompt=prompt,
            system_prompt="You analyze user feedback for clarity. Output JSON only.",
            purpose="triage",
            temperature=0.0,
        )
        # Parse JSON
        text = raw_resp.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        data = json.loads(text.strip())
        is_vague = bool(data.get("is_vague", False))
        clarification = data.get("clarification_reply") if is_vague else None
        return is_vague, clarification
    except Exception as e:
        logger.warning(f"[signal_triage] Vagueness check LLM call failed ({e}), using heuristic fallback")
        if len(clean_text.split()) <= 3 and any(w in lower_text for w in ["fix", "broke", "bug", "help", "bad", "error"]):
            return True, "Could you provide a few more details about what you'd like us to change or fix?"
        return False, None


def merge_canonical_summary(existing_summary: str, new_comment: str) -> str:
    """
    Synthesizes an existing signal's canonical summary with a new clustered user comment.
    """
    prompt = f"""You are synthesizing user feedback for a software feature or bug report.

Current canonical summary:
{existing_summary}

Additional user feedback:
<user_comment>
{new_comment}
</user_comment>

Produce a unified, concise canonical summary (1-3 sentences) capturing the core requirement and all relevant user perspectives without redundancy.
Output ONLY the merged summary text with no extra commentary."""

    try:
        merged = call_with_fallback(
            prompt=prompt,
            system_prompt="You synthesize software requirements. Return only the merged summary.",
            purpose="triage",
            temperature=0.0,
        )
        return merged.strip()
    except Exception as e:
        logger.warning(f"[signal_triage] merge_canonical_summary failed ({e}), appending new comment")
        return f"{existing_summary} | Additional note: {new_comment}"


def cluster_comment_into_signal(comment_body: str, route_path: str, db: Session) -> FeatureSignal:
    """
    Finds semantically matching open FeatureSignals or creates a new one.
    """
    clean_text = comment_body.strip()
    route = route_path.strip() if route_path else "/"

    # Fetch open signals currently gathering votes or queued
    open_signals: List[FeatureSignal] = (
        db.query(FeatureSignal)
        .filter(FeatureSignal.status.in_(["gathering_votes", "queued"]))
        .order_by(FeatureSignal.created_at.desc())
        .limit(10)
        .all()
    )

    if not open_signals:
        logger.info(f"[signal_triage] No open signals found. Creating new signal for route: {route}")
        title = _generate_signal_title(clean_text)
        signal = FeatureSignal(
            title=title,
            canonical_summary=clean_text,
            route_path=route,
            status="gathering_votes",
            upvote_count=0,
        )
        db.add(signal)
        db.flush()
        return signal

    # Fast keyword clustering against open signals
    words = [w.lower() for w in clean_text.split() if len(w) > 3]
    stopwords = {"this", "that", "with", "from", "have", "make", "need", "please", "page", "site", "look", "should", "could"}
    meaningful = [w for w in words if w not in stopwords]

    if meaningful and open_signals:
        for s in open_signals:
            sig_text = f"{s.title} {s.canonical_summary or ''}".lower()
            if any(w in sig_text for w in meaningful):
                logger.info(f"[signal_triage] Fast matched comment into Signal #{s.id} ('{s.title}')")
                if s.canonical_summary and clean_text.lower() not in s.canonical_summary.lower():
                    s.canonical_summary = f"{s.canonical_summary} | {clean_text}"
                return s

    # Immediate new FeatureSignal creation — fast & responsive for demo
    title = clean_text[:50].capitalize() if len(clean_text) <= 50 else clean_text[:47].capitalize() + "…"
    new_signal = FeatureSignal(
        title=title,
        canonical_summary=clean_text,
        route_path=route,
        status="gathering_votes",
        upvote_count=0,
    )
    db.add(new_signal)
    db.flush()
    logger.info(f"[signal_triage] Created new Signal #{new_signal.id}: '{new_signal.title}'")
    return new_signal


def _generate_signal_title(comment_body: str) -> str:
    """
    Generates a concise title (under 60 chars) from a user comment.
    """
    clean_text = comment_body.strip()
    if len(clean_text) <= 50:
        return clean_text.capitalize()

    prompt = f"""Generate a concise, professional feature ticket title (max 7 words, under 50 characters) summarizing this user request:
<user_comment>
{clean_text}
</user_comment>
Return ONLY the title text."""

    try:
        title = call_with_fallback(
            prompt=prompt,
            system_prompt="You write concise issue titles. Return only the title.",
            purpose="triage",
            temperature=0.0,
        )
        cleaned = title.strip().strip('"').strip("'")
        if len(cleaned) > 60:
            cleaned = cleaned[:57] + "…"
        return cleaned or clean_text[:50]
    except Exception:
        return clean_text[:50] + "…"


def trigger_autonomous_build(
    signal_id: int,
    db: Session,
    background_tasks: Optional[BackgroundTasks] = None
) -> bool:
    """
    Transitions a signal from gathering_votes to queued when the upvote threshold is reached.
    Logs an AuditEvent. In Phase 3, wires up full agent orchestrator execution.
    """
    signal = db.query(FeatureSignal).filter(FeatureSignal.id == signal_id).first()
    if not signal:
        return False

    if signal.status != "gathering_votes":
        logger.info(f"[signal_triage] Signal #{signal_id} is already in state '{signal.status}', skipping trigger")
        return False

    signal.status = "queued"
    audit = AuditEvent(
        signal_id=signal.id,
        stage="triage",
        event_type="threshold_reached",
        payload_json=json.dumps({
            "upvote_count": signal.upvote_count,
            "title": signal.title,
            "status": "queued"
        }),
    )
    db.add(audit)
    db.commit()
    logger.info(f"[signal_triage] Signal #{signal.id} reached upvote threshold → status changed to queued")

    # In Phase 3, we add:
    # if background_tasks:
    #     background_tasks.add_task(run_signal_orchestrator, signal.id)

    return True
