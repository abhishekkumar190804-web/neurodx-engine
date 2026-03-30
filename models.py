"""
models.py
---------
Pydantic v2 request/response schemas for the Adaptive GRE Prep API.

All IDs are serialized as strings (MongoDB ObjectId → str). FastAPI
automatically uses these schemas for request validation, OpenAPI docs,
and response serialization.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Question schemas
# ---------------------------------------------------------------------------


class QuestionOut(BaseModel):
    """A GRE question returned to the client (correct answer is hidden)."""

    id: str = Field(..., description="MongoDB ObjectId as string")
    text: str = Field(..., description="The question text")
    options: list[str] = Field(..., description="Answer choices (A, B, C, D, E)")
    topic: str = Field(..., description="GRE topic area")
    difficulty: float = Field(..., ge=0.1, le=1.0, description="IRT difficulty [0.1, 1.0]")
    tags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Session schemas
# ---------------------------------------------------------------------------


class SessionCreateResponse(BaseModel):
    """Response after creating a new adaptive testing session."""

    session_id: str = Field(..., description="Unique session identifier (UUID)")
    message: str = "Session created. Call /next-question/{session_id} to begin."
    initial_theta: float = Field(0.5, description="Starting ability estimate")


class SessionStatusResponse(BaseModel):
    """Current state of a session."""

    session_id: str
    current_ability_theta: float
    questions_answered: int
    completed: bool


# ---------------------------------------------------------------------------
# Next-question schemas
# ---------------------------------------------------------------------------


class NextQuestionResponse(BaseModel):
    """
    Returned by GET /next-question/{session_id}.
    Includes the question and current session metadata.
    """

    question: QuestionOut
    current_theta: float = Field(..., description="Current ability estimate")
    questions_answered: int = Field(..., description="How many questions done so far")


# ---------------------------------------------------------------------------
# Submit-answer schemas
# ---------------------------------------------------------------------------


class SubmitAnswerRequest(BaseModel):
    """Payload for POST /submit-answer."""

    session_id: str = Field(..., description="Active session ID")
    question_id: str = Field(..., description="The ObjectId of the answered question")
    selected_answer: str = Field(..., description="The answer choice submitted by the user")

    @field_validator("selected_answer")
    @classmethod
    def strip_answer(cls, v: str) -> str:
        return v.strip()


class SubmitAnswerResponse(BaseModel):
    """Response after submitting an answer; reveals correctness and new theta."""

    correct: bool
    correct_answer: str
    previous_theta: float
    updated_theta: float
    theta_delta: float = Field(..., description="Change in ability estimate")
    questions_answered: int
    session_completed: bool = False
    message: str = ""


# ---------------------------------------------------------------------------
# Generate-plan schemas
# ---------------------------------------------------------------------------


class GeneratePlanRequest(BaseModel):
    """Payload for POST /generate-plan."""

    session_id: str = Field(..., description="Completed or in-progress session ID")
    max_questions_override: Optional[int] = Field(
        None,
        description="Override the question limit; useful for testing",
    )


class StudyStep(BaseModel):
    """A single step in the personalized 3-step study plan."""

    step: int = Field(..., ge=1, le=3)
    focus: str = Field(..., description="Primary focus area for this step")
    action: str = Field(..., description="Concrete action the student should take")
    resource: str = Field(..., description="Recommended resource or practice type")


class GeneratePlanResponse(BaseModel):
    """Response from the LLM-powered study plan generator."""

    session_id: str
    final_theta: float
    performance_summary: str
    steps: list[StudyStep]
    raw_llm_output: Optional[str] = None
