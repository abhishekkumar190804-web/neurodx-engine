"""
Pydantic models (schemas) for the NeuroDx Testing System.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ─── Question ────────────────────────────────────────────────────────────────

class QuestionOut(BaseModel):
    """Question returned to frontend (no correct_answer exposed)."""
    id: str
    text: str
    options: List[str]
    topic: str
    tags: List[str]
    difficulty: float
    question_number: int
    total_questions: int


# ─── Session ─────────────────────────────────────────────────────────────────

class SessionStartResponse(BaseModel):
    session_id: str
    message: str
    first_question: QuestionOut


class AnswerSubmit(BaseModel):
    session_id: str
    question_id: str
    selected_answer: str  # e.g. "A", "B", "C", "D", "E"


class AnswerResponse(BaseModel):
    correct: bool
    correct_answer: str
    explanation: Optional[str] = None
    new_ability_score: float
    difficulty_direction: str  # "harder", "easier", "same"
    session_complete: bool
    next_question: Optional[QuestionOut] = None


class TopicPerformance(BaseModel):
    topic: str
    correct: int
    total: int
    accuracy: float


class SessionSummary(BaseModel):
    session_id: str
    total_questions: int
    correct_answers: int
    accuracy: float
    final_ability_score: float
    ability_percentile: int
    topic_breakdown: List[TopicPerformance]
    questions_answered: List[Dict[str, Any]]
    created_at: datetime




# ─── AI Insights ─────────────────────────────────────────────────────────────

class InsightsRequest(BaseModel):
    session_id: str


class StudyStep(BaseModel):
    step_number: int
    title: str
    description: str
    resources: List[str]
    duration: str


class InsightsResponse(BaseModel):
    overall_assessment: str
    strengths: List[str]
    weaknesses: List[str]
    study_plan: List[StudyStep]
    motivational_message: str
