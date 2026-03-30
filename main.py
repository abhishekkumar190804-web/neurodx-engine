"""
main.py
-------
Adaptive GRE Prep API — FastAPI application.

Endpoints:
    POST   /sessions                        Create a new adaptive session
    GET    /next-question/{session_id}      Get the next adapted question
    POST   /submit-answer                   Submit an answer, update theta
    POST   /generate-plan                   Generate LLM-powered study plan
    GET    /sessions/{session_id}/status    View session status

Architecture:
    - Async Motor client for all MongoDB I/O (non-blocking)
    - IRT theta updates via math_utils.update_theta() (Rasch MLE)
    - Study plans via llm_service.generate_study_plan() (Gemini)
    - Full Pydantic v2 schema validation on all endpoints
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

from bson import ObjectId
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

from database import create_indexes, close_connection, get_db
from llm_service import generate_study_plan
from math_utils import update_theta, select_target_difficulty
from models import (
    GeneratePlanRequest,
    GeneratePlanResponse,
    NextQuestionResponse,
    QuestionOut,
    SessionCreateResponse,
    SessionStatusResponse,
    StudyStep,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INITIAL_THETA: float = 0.5          # Starting ability estimate (neutral)
MAX_QUESTIONS_PER_SESSION: int = 20  # A full adaptive GRE session


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create MongoDB indexes on startup; close connection on shutdown."""
    logger.info("Starting up — creating MongoDB indexes…")
    await create_indexes()
    yield
    logger.info("Shutting down — closing MongoDB connection…")
    await close_connection()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Adaptive GRE Prep API",
    description=(
        "A Computer Adaptive Testing engine for GRE preparation. "
        "Uses 1PL IRT (Rasch Model) for real-time ability estimation "
        "and Google Gemini for personalized study plans."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _oid(id_str: str) -> ObjectId:
    """Convert a string to a MongoDB ObjectId with a clean error."""
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid ObjectId: '{id_str}'",
        )


def _question_to_out(doc: dict[str, Any]) -> QuestionOut:
    """Convert a raw MongoDB question document to the API response model."""
    return QuestionOut(
        id=str(doc["_id"]),
        text=doc["text"],
        options=doc["options"],
        topic=doc["topic"],
        difficulty=doc["difficulty"],
        tags=doc.get("tags", []),
    )


async def _get_session_or_404(session_id: str) -> dict[str, Any]:
    """Fetch a session document or raise HTTP 404."""
    db = get_db()
    session = await db.user_sessions.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return session


async def _get_next_question(
    session: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Query MongoDB for the maximally informative next question.

    Strategy:
        - Target difficulty ≈ current theta (P=0.5 → maximum Fisher information)
        - Exclude all questions already seen in this session
        - Sort by |difficulty - target| ascending → pick smallest gap

    Returns None if no unseen questions remain.
    """
    db = get_db()
    seen_ids = [_oid(qid) for qid in session.get("seen_question_ids", [])]
    target_difficulty = select_target_difficulty(session["current_ability_theta"])

    logger.info(
        "session=%s | theta=%.3f | target_difficulty=%.3f | seen=%d",
        session["session_id"],
        session["current_ability_theta"],
        target_difficulty,
        len(seen_ids),
    )

    # MongoDB aggregation: compute abs(difficulty - target), sort ascending
    pipeline = [
        {"$match": {"_id": {"$nin": seen_ids}}},
        {
            "$addFields": {
                "diff_gap": {
                    "$abs": {"$subtract": ["$difficulty", target_difficulty]}
                }
            }
        },
        {"$sort": {"diff_gap": 1}},
        {"$limit": 1},
    ]

    cursor = db.questions.aggregate(pipeline)
    results = await cursor.to_list(length=1)
    return results[0] if results else None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/sessions",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new adaptive testing session",
    tags=["Sessions"],
)
async def create_session() -> SessionCreateResponse:
    """
    Initialize a new GRE adaptive testing session.

    Returns a unique `session_id` to use in subsequent calls.
    The session starts with theta = 0.5 (neutral ability estimate).
    """
    db = get_db()
    session_id = str(uuid.uuid4())
    session_doc = {
        "session_id": session_id,
        "current_ability_theta": INITIAL_THETA,
        "seen_question_ids": [],
        "responses": [],        # Full response history for IRT + LLM
        "completed": False,
    }
    await db.user_sessions.insert_one(session_doc)
    logger.info("Created session: %s", session_id)

    return SessionCreateResponse(
        session_id=session_id,
        initial_theta=INITIAL_THETA,
    )


@app.get(
    "/next-question/{session_id}",
    response_model=NextQuestionResponse,
    summary="Get the next adaptive question",
    tags=["Adaptive Testing"],
)
async def next_question(session_id: str) -> NextQuestionResponse:
    """
    Return the next GRE question adapted to the student's current ability.

    The question is selected so that its difficulty is closest to the
    current theta estimate (maximum Fisher information criterion).

    Raises:
        404: Session not found.
        409: Session already completed or no more questions available.
    """
    session = await _get_session_or_404(session_id)

    if session["completed"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is already completed. Call /generate-plan to get your study plan.",
        )

    if len(session.get("seen_question_ids", [])) >= MAX_QUESTIONS_PER_SESSION:
        # Auto-mark as completed
        db = get_db()
        await db.user_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"completed": True}},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Maximum of {MAX_QUESTIONS_PER_SESSION} questions reached. "
                "Session completed. Call /generate-plan."
            ),
        )

    question_doc = await _get_next_question(session)

    if question_doc is None:
        # All questions exhausted before hitting the limit
        db = get_db()
        await db.user_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"completed": True}},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No more questions available. Session completed. Call /generate-plan.",
        )

    return NextQuestionResponse(
        question=_question_to_out(question_doc),
        current_theta=session["current_ability_theta"],
        questions_answered=len(session.get("seen_question_ids", [])),
    )


@app.post(
    "/submit-answer",
    response_model=SubmitAnswerResponse,
    summary="Submit an answer and update ability estimate",
    tags=["Adaptive Testing"],
)
async def submit_answer(payload: SubmitAnswerRequest) -> SubmitAnswerResponse:
    """
    Record the student's answer to a question and update their theta.

    Process:
    1. Validate the session and question.
    2. Determine correctness.
    3. Run Rasch MLE gradient ascent to update theta.
    4. Persist the response and new theta to MongoDB.
    5. Return correctness, new theta, and session status.

    Raises:
        404: Session or question not found.
        409: Session already completed, or question already answered.
    """
    db = get_db()
    session = await _get_session_or_404(payload.session_id)

    if session["completed"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot submit answers to a completed session.",
        )

    # Guard: question must not have been seen already
    if payload.question_id in session.get("seen_question_ids", []):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Question '{payload.question_id}' has already been answered in this session.",
        )

    # Fetch the question to validate and get metadata
    question_doc = await db.questions.find_one({"_id": _oid(payload.question_id)})
    if not question_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question '{payload.question_id}' not found.",
        )

    correct_answer: str = question_doc["correct_answer"]
    is_correct = payload.selected_answer.strip() == correct_answer.strip()
    previous_theta = session["current_ability_theta"]

    # Build the full response record (used by IRT update and LLM)
    response_record = {
        "question_id": payload.question_id,
        "correct": is_correct,
        "difficulty": question_doc["difficulty"],
        "topic": question_doc["topic"],
    }

    # Compute new responses list (existing + this one)
    all_responses = session.get("responses", []) + [response_record]

    # Run MLE theta update on full response history
    new_theta = update_theta(previous_theta, all_responses)
    theta_delta = round(new_theta - previous_theta, 4)

    questions_answered = len(session.get("seen_question_ids", [])) + 1
    session_completed = questions_answered >= MAX_QUESTIONS_PER_SESSION

    # Persist update to MongoDB
    await db.user_sessions.update_one(
        {"session_id": payload.session_id},
        {
            "$push": {
                "seen_question_ids": payload.question_id,
                "responses": response_record,
            },
            "$set": {
                "current_ability_theta": new_theta,
                "completed": session_completed,
            },
        },
    )

    logger.info(
        "session=%s | q=%s | correct=%s | theta %.3f → %.3f (Δ=%.4f)",
        payload.session_id,
        payload.question_id,
        is_correct,
        previous_theta,
        new_theta,
        theta_delta,
    )

    msg = ""
    if session_completed:
        msg = "Session complete! Call POST /generate-plan with your session_id."

    return SubmitAnswerResponse(
        correct=is_correct,
        correct_answer=correct_answer,
        previous_theta=round(previous_theta, 4),
        updated_theta=round(new_theta, 4),
        theta_delta=theta_delta,
        questions_answered=questions_answered,
        session_completed=session_completed,
        message=msg,
    )


@app.post(
    "/generate-plan",
    response_model=GeneratePlanResponse,
    summary="Generate a personalized LLM study plan",
    tags=["Study Plan"],
)
async def generate_plan(payload: GeneratePlanRequest) -> GeneratePlanResponse:
    """
    Analyze the session history and generate a personalized 3-step GRE study plan.

    Uses Google Gemini with an "Expert GRE Tutor" persona. If the LLM API is
    unavailable, a rule-based fallback plan is returned automatically.

    The session does NOT need to be completed to call this endpoint.

    Raises:
        404: Session not found.
        400: Session has no responses yet.
    """
    session = await _get_session_or_404(payload.session_id)
    responses = session.get("responses", [])

    if not responses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No responses found in this session. Answer at least one question first.",
        )

    final_theta = session["current_ability_theta"]
    logger.info(
        "Generating study plan for session=%s | theta=%.3f | responses=%d",
        payload.session_id,
        final_theta,
        len(responses),
    )

    performance_summary, steps, raw_output = await generate_study_plan(
        responses=responses,
        final_theta=final_theta,
    )

    return GeneratePlanResponse(
        session_id=payload.session_id,
        final_theta=round(final_theta, 4),
        performance_summary=performance_summary,
        steps=steps,
        raw_llm_output=raw_output,
    )


@app.get(
    "/sessions/{session_id}/status",
    response_model=SessionStatusResponse,
    summary="View current session status",
    tags=["Sessions"],
)
async def session_status(session_id: str) -> SessionStatusResponse:
    """Return the current status of an adaptive testing session."""
    session = await _get_session_or_404(session_id)
    return SessionStatusResponse(
        session_id=session_id,
        current_ability_theta=round(session["current_ability_theta"], 4),
        questions_answered=len(session.get("seen_question_ids", [])),
        completed=session["completed"],
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Meta"])
async def health_check() -> JSONResponse:
    """Liveness probe — returns 200 OK if the server is running."""
    return JSONResponse({"status": "ok", "version": app.version})
