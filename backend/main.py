"""
FastAPI Main Application — NeuroDx Testing System
All API endpoints for session management, adaptive question delivery,
answer processing, and AI insight generation.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from bson import ObjectId

from backend.database import connect_db, close_db, get_db
from backend.models import (
    SessionStartResponse, QuestionOut, AnswerSubmit, AnswerResponse,
    SessionSummary, TopicPerformance, InsightsRequest, InsightsResponse,
    StudyStep
)
from backend.irt import (
    AbilityEstimator, select_next_question, ability_to_percentile
)
from backend.insights import generate_insights

# ─── App Configuration ────────────────────────────────────────────────────────

app = FastAPI(
    title="NeuroDx Testing System",
    description="AI-powered adaptive GRE practice using Item Response Theory",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_QUESTIONS = 10  # Questions per session
INITIAL_ABILITY = 0.0  # IRT ability score starting point (-3 to 3)

# ─── Lifecycle Events ─────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    await connect_db()
    print("🚀 NeuroDx Testing API is running!")


@app.on_event("shutdown")
async def shutdown_event():
    await close_db()


# ─── Helper Functions ─────────────────────────────────────────────────────────

def serialize_question(q: dict, question_number: int, total: int) -> QuestionOut:
    """Convert MongoDB doc to QuestionOut (hide correct_answer)."""
    return QuestionOut(
        id=str(q["_id"]),
        text=q["text"],
        options=q["options"],
        topic=q["topic"],
        tags=q.get("tags", []),
        difficulty=q["difficulty"],
        question_number=question_number,
        total_questions=total,
    )


def compute_topic_breakdown(responses: List[dict]) -> List[TopicPerformance]:
    """Aggregate per-topic accuracy from response history."""
    topic_stats: dict = {}
    for r in responses:
        topic = r.get("topic", "Unknown")
        if topic not in topic_stats:
            topic_stats[topic] = {"correct": 0, "total": 0}
        topic_stats[topic]["total"] += 1
        if r.get("correct"):
            topic_stats[topic]["correct"] += 1

    result = []
    for topic, stats in topic_stats.items():
        acc = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0
        result.append(TopicPerformance(
            topic=topic,
            correct=stats["correct"],
            total=stats["total"],
            accuracy=round(acc, 3),
        ))
    return sorted(result, key=lambda x: x.accuracy)   # weakest first


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """API health check."""
    db = get_db()
    question_count = await db.gre_questions.count_documents({})
    return {
        "status": "ok",
        "question_count": question_count,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/session/start", response_model=SessionStartResponse)
async def start_session():
    """
    Start a new adaptive test session.
    Initializes ability at 0.0 (baseline) and returns the first question.
    """
    db = get_db()
    session_id = str(uuid.uuid4())

    # Fetch all questions for selection
    all_questions = await db.gre_questions.find({}).to_list(length=None)
    if not all_questions:
        raise HTTPException(status_code=503, detail="No questions in database. Run seed_db.py first.")

    # Select first question near baseline difficulty 0.5
    first_q = select_next_question(INITIAL_ABILITY, all_questions, answered_ids=[])
    if not first_q:
        raise HTTPException(status_code=503, detail="Could not select first question.")

    # Create session document
    session_doc = {
        "session_id": session_id,
        "ability_score": INITIAL_ABILITY,
        "current_question_number": 1,
        "answered_ids": [str(first_q["_id"])],
        "response_history": [],
        "current_question_id": str(first_q["_id"]),
        "complete": False,
        "created_at": datetime.now(timezone.utc),
    }
    await db.user_sessions.insert_one(session_doc)

    return SessionStartResponse(
        session_id=session_id,
        message="Session started! Good luck on your GRE practice.",
        first_question=serialize_question(first_q, 1, MAX_QUESTIONS),
    )


@app.post("/answer", response_model=AnswerResponse)
async def submit_answer(payload: AnswerSubmit):
    """
    Submit an answer for the current question.
    Updates ability score via IRT and returns the next question (or completion).
    """
    db = get_db()

    # Load session
    session = await db.user_sessions.find_one({"session_id": payload.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.get("complete"):
        raise HTTPException(status_code=400, detail="Session already complete.")

    # Load question
    try:
        q_obj_id = ObjectId(payload.question_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid question_id format.")

    question = await db.gre_questions.find_one({"_id": q_obj_id})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    # Evaluate answer
    is_correct = payload.selected_answer.strip().upper() == question["correct_answer"].strip().upper()
    current_ability = session["ability_score"]

    # Record response for EAP
    response_entry = {
        "question_id": payload.question_id,
        "topic": question["topic"],
        "difficulty": question["difficulty"],
        "discrimination": question.get("discrimination", 1.0),
        "guessing": question.get("guessing", 0.2),
        "correct": is_correct,
        "selected": payload.selected_answer,
    }
    response_history = session.get("response_history", []) + [response_entry]

    # Update ability score using full EAP over response history
    new_ability = AbilityEstimator.update_ability(response_history, current_ability)

    # Determine direction
    delta = new_ability - current_ability
    if delta > 0.05:
        direction = "harder"
    elif delta < -0.05:
        direction = "easier"
    else:
        direction = "same"

    q_number = session["current_question_number"]
    is_last_question = q_number >= MAX_QUESTIONS

    # Prepare next question if not the last
    next_question_out: Optional[QuestionOut] = None
    if not is_last_question:
        all_questions = await db.gre_questions.find({}).to_list(length=None)
        answered_ids = session.get("answered_ids", []) + [payload.question_id]
        next_q = select_next_question(new_ability, all_questions, answered_ids)

        if next_q:
            next_q_id = str(next_q["_id"])
            next_question_out = serialize_question(next_q, q_number + 1, MAX_QUESTIONS)
            # Update session for next question
            await db.user_sessions.update_one(
                {"session_id": payload.session_id},
                {"$set": {
                    "ability_score": new_ability,
                    "current_question_number": q_number + 1,
                    "current_question_id": next_q_id,
                    "response_history": response_history,
                    "answered_ids": answered_ids + [next_q_id],
                }}
            )
        else:
            is_last_question = True

    if is_last_question:
        # Mark session complete
        await db.user_sessions.update_one(
            {"session_id": payload.session_id},
            {"$set": {
                "ability_score": new_ability,
                "response_history": response_history,
                "complete": True,
                "completed_at": datetime.now(timezone.utc),
            }}
        )

    return AnswerResponse(
        correct=is_correct,
        correct_answer=question["correct_answer"],
        explanation=question.get("explanation"),
        new_ability_score=round(new_ability, 4),
        difficulty_direction=direction,
        session_complete=is_last_question,
        next_question=next_question_out,
    )


@app.get("/session/{session_id}/summary", response_model=SessionSummary)
async def get_session_summary(session_id: str):
    """Get a complete summary of a finished session."""
    db = get_db()
    session = await db.user_sessions.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    history = session.get("response_history", [])
    total = len(history)
    correct_count = sum(1 for r in history if r.get("correct"))
    accuracy = correct_count / total if total > 0 else 0.0
    ability = session.get("ability_score", 0.0)

    topic_breakdown = compute_topic_breakdown(history)
    percentile = ability_to_percentile(ability)

    return SessionSummary(
        session_id=session_id,
        total_questions=total,
        correct_answers=correct_count,
        accuracy=round(accuracy, 4),
        final_ability_score=round(ability, 4),
        ability_percentile=percentile,
        topic_breakdown=topic_breakdown,
        questions_answered=history,
        created_at=session.get("created_at", datetime.now(timezone.utc)),
    )


@app.post("/insights")
async def get_ai_insights(payload: InsightsRequest):
    """
    Generate a personalized 3-step study plan using Gemini LLM.
    Works even without an API key (falls back to template-based insights).
    """
    db = get_db()
    session = await db.user_sessions.find_one({"session_id": payload.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    history = session.get("response_history", [])
    total = len(history)
    correct_count = sum(1 for r in history if r.get("correct"))
    accuracy = correct_count / total if total > 0 else 0.0
    ability = session.get("ability_score", 0.0)

    topic_breakdown_raw = compute_topic_breakdown(history)
    topic_breakdown_dicts = [
        {"topic": t.topic, "correct": t.correct, "total": t.total, "accuracy": t.accuracy}
        for t in topic_breakdown_raw
    ]

    session_data = {
        "session_id": payload.session_id,
        "total_questions": total,
        "correct_answers": correct_count,
        "accuracy": accuracy,
        "final_ability_score": ability,
        "topic_breakdown": topic_breakdown_dicts,
    }

    insights = await generate_insights(session_data)
    if not insights:
        raise HTTPException(status_code=500, detail="Failed to generate insights.")

    return insights




# ─── Static Files (Frontend) ──────────────────────────────────────────────────

import os
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")


    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "index.html"))
