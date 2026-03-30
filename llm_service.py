"""
llm_service.py
--------------
LLM-powered GRE Study Plan generator using Google Gemini.

The service:
1. Analyzes the session response history (topics, accuracy, difficulty).
2. Builds a rich, human-readable prompt instead of sending raw JSON.
3. Calls the Gemini API with an Expert GRE Tutor system prompt.
4. Parses the structured 3-step plan from the response.

Fallback: If the LLM call fails, a rule-based fallback plan is generated
          from the same analytics data so the endpoint never returns 500.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any

import google.generativeai as genai

from database import settings
from models import StudyStep

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — defines the LLM persona
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are an Expert GRE Tutor with 15 years of experience \
coaching students from all academic backgrounds. You specialize in adaptive \
learning strategies, score improvement through targeted practice, and \
psychological confidence-building.

Your task is to analyze a student's GRE adaptive test session and produce \
a precise, actionable 3-step study plan in valid JSON format.

ALWAYS respond with ONLY a JSON object in this exact schema (no markdown, \
no prose outside the JSON):
{
  "performance_summary": "One-sentence summary of the student's performance.",
  "steps": [
    {
      "step": 1,
      "focus": "Topic or skill area",
      "action": "Specific, measurable action the student should take",
      "resource": "Recommended book, app, or practice type"
    },
    {
      "step": 2,
      ...
    },
    {
      "step": 3,
      ...
    }
  ]
}"""


# ---------------------------------------------------------------------------
# Analytics helpers
# ---------------------------------------------------------------------------

def _compute_session_analytics(responses: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Derive key performance metrics from the raw response history.

    Args:
        responses: List of response dicts containing:
            - question_id (str)
            - correct (bool)
            - difficulty (float)
            - topic (str)

    Returns:
        Analytics dict with per-topic breakdown and global stats.
    """
    topic_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"correct": 0, "total": 0, "difficulties": []}
    )

    difficulties_seen: list[float] = []

    for r in responses:
        topic = r.get("topic", "Unknown")
        topic_stats[topic]["total"] += 1
        if r.get("correct"):
            topic_stats[topic]["correct"] += 1
        diff = r.get("difficulty", 0.5)
        topic_stats[topic]["difficulties"].append(diff)
        difficulties_seen.append(diff)

    # Compute per-topic accuracy and average difficulty
    topic_summary: list[dict[str, Any]] = []
    for topic, stats in topic_stats.items():
        accuracy = stats["correct"] / stats["total"] if stats["total"] else 0
        avg_diff = (
            sum(stats["difficulties"]) / len(stats["difficulties"])
            if stats["difficulties"]
            else 0.5
        )
        topic_summary.append(
            {
                "topic": topic,
                "accuracy_pct": round(accuracy * 100, 1),
                "avg_difficulty": round(avg_diff, 2),
                "questions_attempted": stats["total"],
            }
        )

    global_accuracy = (
        sum(1 for r in responses if r.get("correct")) / len(responses)
        if responses
        else 0
    )
    avg_difficulty_reached = (
        sum(difficulties_seen) / len(difficulties_seen) if difficulties_seen else 0.5
    )

    return {
        "total_questions": len(responses),
        "global_accuracy_pct": round(global_accuracy * 100, 1),
        "avg_difficulty_reached": round(avg_difficulty_reached, 2),
        "topic_breakdown": sorted(
            topic_summary, key=lambda x: x["accuracy_pct"]
        ),  # weakest topics first
    }


def _build_user_prompt(
    analytics: dict[str, Any], final_theta: float
) -> str:
    """
    Convert analytics into a rich, human-readable prompt for the LLM.

    This avoids dumping raw JSON at the model; instead it presents the
    data as a natural-language briefing that the tutor persona can act on.
    """
    lines = [
        f"The student completed {analytics['total_questions']} adaptive GRE questions.",
        f"Overall accuracy: {analytics['global_accuracy_pct']}%.",
        f"Average difficulty level reached: {analytics['avg_difficulty_reached']:.2f} (scale 0.1–1.0).",
        f"Final ability score (theta on IRT scale): {final_theta:.3f} (scale −3 to +3).",
        "",
        "Per-topic performance breakdown (sorted weakest → strongest):",
    ]

    for t in analytics["topic_breakdown"]:
        strength = (
            "strong" if t["accuracy_pct"] >= 70
            else "moderate" if t["accuracy_pct"] >= 50
            else "weak"
        )
        lines.append(
            f"  • {t['topic']}: {t['accuracy_pct']}% accuracy at avg difficulty "
            f"{t['avg_difficulty']} ({t['questions_attempted']} questions) — {strength}"
        )

    lines += [
        "",
        "Based on this data, create a targeted 3-step study plan.",
        "Prioritize the student's weakest topics while maintaining strength in areas they excel.",
        "Steps should be concrete, time-bound, and reference specific GRE prep resources.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fallback plan generator (rule-based, no LLM required)
# ---------------------------------------------------------------------------

def _fallback_plan(
    analytics: dict[str, Any], final_theta: float
) -> tuple[str, list[StudyStep]]:
    """Generate a basic study plan without LLM when the API call fails."""
    breakdown = analytics["topic_breakdown"]
    weakest = breakdown[0]["topic"] if breakdown else "Quantitative Reasoning"
    strongest = breakdown[-1]["topic"] if len(breakdown) > 1 else "Verbal Reasoning"

    summary = (
        f"Student scored {analytics['global_accuracy_pct']}% overall "
        f"(theta={final_theta:.2f}); needs focus on {weakest}."
    )

    steps = [
        StudyStep(
            step=1,
            focus=weakest,
            action=f"Complete 30 targeted practice problems on {weakest} "
                   f"starting at medium difficulty, reviewing every wrong answer.",
            resource="Manhattan Prep GRE Strategy Guide (topic-specific volume)",
        ),
        StudyStep(
            step=2,
            focus="Mixed Practice",
            action="Take two full-length timed section practice tests focusing "
                   "on time management and question skipping strategy.",
            resource="ETS Official GRE Practice Tests (free on ets.org)",
        ),
        StudyStep(
            step=3,
            focus=strongest,
            action=f"Maintain your strength in {strongest} with 15-minute "
                   f"daily warm-up sessions to solidify your score ceiling.",
            resource="Magoosh GRE — Daily Practice Questions",
        ),
    ]

    return summary, steps


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_study_plan(
    responses: list[dict[str, Any]],
    final_theta: float,
) -> tuple[str, list[StudyStep], str | None]:
    """
    Generate a personalized 3-step GRE study plan.

    Args:
        responses:   Full session response history (with topic, difficulty, correct).
        final_theta: Final ability estimate from IRT.

    Returns:
        Tuple of (performance_summary, list[StudyStep], raw_llm_output | None).
        raw_llm_output is None when the fallback plan is used.
    """
    analytics = _compute_session_analytics(responses)
    user_prompt = _build_user_prompt(analytics, final_theta)

    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY not set — using fallback plan generator.")
        summary, steps = _fallback_plan(analytics, final_theta)
        return summary, steps, None

    try:
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=SYSTEM_PROMPT,
        )

        response = model.generate_content(user_prompt)
        raw_text: str = response.text.strip()

        # Strip markdown code fences if present
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

        plan_data = json.loads(raw_text)
        performance_summary: str = plan_data.get(
            "performance_summary", "Study plan generated."
        )
        steps = [StudyStep(**s) for s in plan_data["steps"]]

        return performance_summary, steps, raw_text

    except json.JSONDecodeError as exc:
        logger.error("Failed to parse LLM JSON response: %s", exc)
        summary, steps = _fallback_plan(analytics, final_theta)
        return summary, steps, None

    except Exception as exc:  # noqa: BLE001
        logger.error("LLM API call failed: %s", exc)
        summary, steps = _fallback_plan(analytics, final_theta)
        return summary, steps, None
