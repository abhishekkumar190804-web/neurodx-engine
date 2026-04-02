"""
AI Insights Module — OpenAI integration for personalized GRE study plans.
"""
import os
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def _build_prompt(session_data: Dict[str, Any]) -> str:
    """Build a structured prompt from session performance data."""
    accuracy = session_data.get("accuracy", 0)
    ability = session_data.get("final_ability_score", 0.0)
    topics = session_data.get("topic_breakdown", [])
    total = session_data.get("total_questions", 10)
    correct = session_data.get("correct_answers", 0)

    weak_topics = [t for t in topics if t.get("accuracy", 1.0) < 0.5]
    strong_topics = [t for t in topics if t.get("accuracy", 0.0) >= 0.7]

    weak_str = ", ".join([f"{t['topic']} ({int(t['accuracy']*100)}%)" for t in weak_topics]) or "None identified"
    strong_str = ", ".join([f"{t['topic']} ({int(t['accuracy']*100)}%)" for t in strong_topics]) or "None identified"

    return f"""You are an expert GRE tutor providing a personalized study plan.

STUDENT PERFORMANCE DATA:
- Total Questions: {total}
- Correct Answers: {correct}
- Overall Accuracy: {int(accuracy * 100)}%
- IRT Ability Score: {ability:.2f} (scale: -3 to +3, where 0 = average GRE test-taker)
- Strong Topics: {strong_str}
- Weak Topics: {weak_str}

Based on this data, provide a PERSONALIZED 3-STEP STUDY PLAN in the following JSON format exactly:

{{
  "overall_assessment": "2-3 sentence overall assessment of the student's performance",
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "study_plan": [
    {{
      "step_number": 1,
      "title": "Step title (focus on biggest weakness)",
      "description": "Detailed 2-3 sentence description of what to study and how",
      "resources": ["Specific book/resource 1", "Specific book/resource 2"],
      "duration": "e.g., 1 week, 3 days"
    }},
    {{
      "step_number": 2,
      "title": "Step title",
      "description": "Detailed description",
      "resources": ["Resource 1", "Resource 2"],
      "duration": "timeframe"
    }},
    {{
      "step_number": 3,
      "title": "Step title (integration/practice)",
      "description": "Detailed description",
      "resources": ["Resource 1", "Resource 2"],
      "duration": "timeframe"
    }}
  ],
  "motivational_message": "An encouraging, personalized 1-2 sentence message"
}}

Respond ONLY with valid JSON. No markdown, no extra text."""


async def generate_insights(session_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Call OpenAI API to generate personalized study plan.
    Falls back to template-based insights if API key is unavailable.
    """
    if not OPENAI_API_KEY or OPENAI_API_KEY == "your_openai_api_key_here":
        return _fallback_insights(session_data)

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        prompt = _build_prompt(session_data)
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert GRE tutor. Always respond with valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )

        raw_text = response.choices[0].message.content.strip()
        parsed = json.loads(raw_text)
        return parsed

    except Exception as e:
        print(f"⚠️ OpenAI API error: {e}. Falling back to template insights.")
        return _fallback_insights(session_data)


def _fallback_insights(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """Template-based insights when the OpenAI key is unavailable."""
    accuracy = session_data.get("accuracy", 0)
    ability = session_data.get("final_ability_score", 0.0)
    topics = session_data.get("topic_breakdown", [])
    weak_topics = [t["topic"] for t in topics if t.get("accuracy", 1.0) < 0.5]
    strong_topics = [t["topic"] for t in topics if t.get("accuracy", 0.0) >= 0.7]
    level = "beginner" if ability < -1 else "intermediate" if ability < 1 else "advanced"

    return {
        "overall_assessment": (
            f"You achieved {int(accuracy*100)}% accuracy with an IRT ability score of {ability:.2f}, "
            f"placing you in the {level} range. "
            f"{'Your performance shows solid foundational skills.' if accuracy > 0.6 else 'Consistent practice will significantly improve your score.'}"
        ),
        "strengths": strong_topics if strong_topics else ["Keep practicing to identify your strengths"],
        "weaknesses": weak_topics if weak_topics else ["General test-taking strategy and timing"],
        "study_plan": [
            {
                "step_number": 1,
                "title": f"Targeted Review: {weak_topics[0] if weak_topics else 'Core GRE Concepts'}",
                "description": (
                    f"Focus on {', '.join(weak_topics[:2]) if weak_topics else 'foundational GRE concepts'}. "
                    "Work through problem sets systematically, reviewing each mistake carefully. "
                    "Spend 30–45 minutes daily on concept review and practice problems."
                ),
                "resources": [
                    "Manhattan Prep GRE Strategy Guides",
                    "ETS Official GRE Super Power Pack",
                ],
                "duration": "1 week",
            },
            {
                "step_number": 2,
                "title": "Timed Practice Sessions",
                "description": (
                    "Begin timed practice to simulate real test conditions. "
                    "Complete full-length section quizzes and track your accuracy by topic. "
                    "Focus on pacing — approximately 1.5 minutes per Quant question."
                ),
                "resources": [
                    "Magoosh GRE Premium (adaptive practice)",
                    "Princeton Review GRE 1,007 Practice Questions",
                ],
                "duration": "1 week",
            },
            {
                "step_number": 3,
                "title": "Full-Length Mock Tests & Analysis",
                "description": (
                    "Take 2–3 full-length GRE practice tests under real conditions. "
                    "After each test, spend equal time reviewing mistakes. "
                    "Focus final days on vocabulary flashcards and formula sheets."
                ),
                "resources": [
                    "ETS PowerPrep II (official free tests)",
                    "Kaplan GRE Prep + Practice Tests",
                ],
                "duration": "5–7 days",
            },
        ],
        "motivational_message": (
            f"You're building real momentum! With targeted focus on "
            f"{weak_topics[0] if weak_topics else 'your areas for improvement'}, "
            "you'll see a significant score increase. Stay consistent and trust the process!"
        ),
    }
