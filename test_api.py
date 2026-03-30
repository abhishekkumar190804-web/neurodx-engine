"""
test_api.py
-----------
pytest test suite for the Adaptive GRE Prep API.

Tests:
    Unit  — math_utils IRT functions (Rasch model, MLE, difficulty mapping)
    Integration — FastAPI endpoints using TestClient with an in-memory MongoDB
                  (mongomock) so no real running MongoDB is needed.

Run:
    pytest test_api.py -v
"""

from __future__ import annotations

import math
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from models import StudyStep

# ---------------------------------------------------------------------------
# Unit tests — math_utils
# ---------------------------------------------------------------------------

class TestRaschProbability:
    """Tests for the 1PL Rasch model probability function."""

    def test_equal_theta_beta_gives_half(self):
        """When θ = β, P(correct) must equal exactly 0.5."""
        from math_utils import rasch_probability
        p = rasch_probability(theta=1.0, beta=1.0)
        assert abs(p - 0.5) < 1e-9

    def test_theta_much_greater_than_beta(self):
        """Very able student facing easy item → P close to 1."""
        from math_utils import rasch_probability
        p = rasch_probability(theta=3.0, beta=-3.0)
        assert p > 0.99

    def test_theta_much_less_than_beta(self):
        """Weak student facing very hard item → P close to 0."""
        from math_utils import rasch_probability
        p = rasch_probability(theta=-3.0, beta=3.0)
        assert p < 0.01

    def test_output_in_unit_interval(self):
        """P must always be in (0, 1)."""
        from math_utils import rasch_probability
        for theta in [-3, -1, 0, 1, 3]:
            for beta in [-3, -1, 0, 1, 3]:
                p = rasch_probability(theta, beta)
                assert 0.0 < p < 1.0, f"P={p} out of range for θ={theta}, β={beta}"


class TestDifficultyToBeta:
    """Tests for the difficulty → beta linear mapping."""

    def test_min_difficulty_maps_to_min_beta(self):
        from math_utils import difficulty_to_beta
        beta = difficulty_to_beta(0.1)
        assert abs(beta - (-3.0)) < 1e-6

    def test_max_difficulty_maps_to_max_beta(self):
        from math_utils import difficulty_to_beta
        beta = difficulty_to_beta(1.0)
        assert abs(beta - 3.0) < 1e-6

    def test_midpoint_maps_to_zero(self):
        """Difficulty 0.55 ≈ midpoint → beta ≈ 0."""
        from math_utils import difficulty_to_beta
        beta = difficulty_to_beta(0.55)
        assert abs(beta - 0.0) < 1e-4


class TestUpdateTheta:
    """Tests for the MLE gradient-ascent theta update."""

    def test_all_correct_increases_theta(self):
        from math_utils import update_theta
        responses = [
            {"difficulty": 0.4, "correct": True},
            {"difficulty": 0.5, "correct": True},
            {"difficulty": 0.6, "correct": True},
        ]
        new_theta = update_theta(0.5, responses)
        assert new_theta > 0.5, "All correct should increase ability estimate"

    def test_all_wrong_decreases_theta(self):
        from math_utils import update_theta
        responses = [
            {"difficulty": 0.4, "correct": False},
            {"difficulty": 0.5, "correct": False},
            {"difficulty": 0.6, "correct": False},
        ]
        new_theta = update_theta(0.5, responses)
        assert new_theta < 0.5, "All wrong should decrease ability estimate"

    def test_theta_clamped_to_valid_range(self):
        from math_utils import update_theta, THETA_MIN, THETA_MAX
        # Force theta toward ceiling
        responses = [{"difficulty": d, "correct": True} for d in [0.1] * 30]
        new_theta = update_theta(2.9, responses)
        assert THETA_MIN <= new_theta <= THETA_MAX

    def test_empty_responses_unchanged(self):
        from math_utils import update_theta
        assert update_theta(0.7, []) == 0.7

    def test_mixed_responses_converges(self):
        """Mixed correct/wrong → theta should land between min and max."""
        from math_utils import update_theta, THETA_MIN, THETA_MAX
        responses = [
            {"difficulty": 0.5, "correct": True},
            {"difficulty": 0.7, "correct": False},
            {"difficulty": 0.4, "correct": True},
            {"difficulty": 0.8, "correct": False},
        ]
        theta = update_theta(0.5, responses)
        assert THETA_MIN < theta < THETA_MAX


class TestSelectTargetDifficulty:
    """Tests for the inverse mapping theta → target difficulty."""

    def test_neutral_theta_gives_mid_difficulty(self):
        from math_utils import select_target_difficulty
        d = select_target_difficulty(0.0)
        assert abs(d - 0.55) < 0.01

    def test_high_theta_gives_high_difficulty(self):
        from math_utils import select_target_difficulty
        d = select_target_difficulty(2.5)
        assert d > 0.85

    def test_low_theta_gives_low_difficulty(self):
        from math_utils import select_target_difficulty
        d = select_target_difficulty(-2.5)
        assert d < 0.25

    def test_output_clamped_to_valid_range(self):
        from math_utils import select_target_difficulty
        for theta in [-3.0, 0.0, 3.0]:
            d = select_target_difficulty(theta)
            assert 0.1 <= d <= 1.0


# ---------------------------------------------------------------------------
# Integration tests — FastAPI endpoints
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """
    Provide a MagicMock that mimics Motor's async collection interface.
    We patch get_db() at the main module level so all endpoints use this mock.
    """
    db = MagicMock()

    # user_sessions collection
    db.user_sessions.find_one = AsyncMock()
    db.user_sessions.insert_one = AsyncMock()
    db.user_sessions.update_one = AsyncMock()

    # questions collection
    db.questions.find_one = AsyncMock()
    db.questions.aggregate = MagicMock()

    return db


SAMPLE_SESSION = {
    "session_id": "test-session-001",
    "current_ability_theta": 0.5,
    "seen_question_ids": [],
    "responses": [],
    "completed": False,
}

SAMPLE_QUESTION = {
    "_id": "507f1f77bcf86cd799439011",
    "text": "What is 2 + 2?",
    "options": ["A) 2", "B) 3", "C) 4", "D) 5", "E) 6"],
    "correct_answer": "C) 4",
    "topic": "Arithmetic",
    "difficulty": 0.15,
    "tags": ["basic"],
}


@pytest.fixture
def client(mock_db):
    """Create a FastAPI TestClient with all DB calls mocked."""
    with patch("main.get_db", return_value=mock_db), \
         patch("database.create_indexes", new_callable=AsyncMock), \
         patch("database.close_connection", new_callable=AsyncMock):
        from main import app
        with TestClient(app) as c:
            yield c, mock_db


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        c, _ = client
        resp = c.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestCreateSession:
    def test_creates_session_successfully(self, client):
        c, mock_db = client
        mock_db.user_sessions.insert_one.return_value = MagicMock()

        resp = c.post("/sessions")
        assert resp.status_code == 201
        data = resp.json()
        assert "session_id" in data
        assert data["initial_theta"] == 0.5
        mock_db.user_sessions.insert_one.assert_called_once()


class TestNextQuestion:
    def test_returns_question_for_valid_session(self, client):
        c, mock_db = client
        mock_db.user_sessions.find_one.return_value = dict(SAMPLE_SESSION)

        # Mock the aggregate pipeline
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[dict(SAMPLE_QUESTION)])
        mock_db.questions.aggregate.return_value = mock_cursor

        resp = c.get("/next-question/test-session-001")
        assert resp.status_code == 200
        data = resp.json()
        assert "question" in data
        assert data["question"]["topic"] == "Arithmetic"
        # Correct answer should NOT be in the response
        assert "correct_answer" not in data["question"]

    def test_404_for_unknown_session(self, client):
        c, mock_db = client
        mock_db.user_sessions.find_one.return_value = None

        resp = c.get("/next-question/nonexistent")
        assert resp.status_code == 404

    def test_409_for_completed_session(self, client):
        c, mock_db = client
        completed_session = {**SAMPLE_SESSION, "completed": True}
        mock_db.user_sessions.find_one.return_value = completed_session

        resp = c.get("/next-question/test-session-001")
        assert resp.status_code == 409

    def test_409_when_no_questions_left(self, client):
        c, mock_db = client
        mock_db.user_sessions.find_one.return_value = dict(SAMPLE_SESSION)
        mock_db.user_sessions.update_one.return_value = MagicMock()

        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_db.questions.aggregate.return_value = mock_cursor

        resp = c.get("/next-question/test-session-001")
        assert resp.status_code == 409


class TestSubmitAnswer:
    def test_correct_answer_increases_theta(self, client):
        c, mock_db = client
        mock_db.user_sessions.find_one.return_value = dict(SAMPLE_SESSION)
        mock_db.questions.find_one.return_value = dict(SAMPLE_QUESTION)
        mock_db.user_sessions.update_one.return_value = MagicMock()

        payload = {
            "session_id": "test-session-001",
            "question_id": "507f1f77bcf86cd799439011",
            "selected_answer": "C) 4",
        }
        resp = c.post("/submit-answer", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["correct"] is True
        assert data["correct_answer"] == "C) 4"
        assert data["updated_theta"] > data["previous_theta"]

    def test_wrong_answer_decreases_theta(self, client):
        c, mock_db = client
        mock_db.user_sessions.find_one.return_value = dict(SAMPLE_SESSION)
        mock_db.questions.find_one.return_value = dict(SAMPLE_QUESTION)
        mock_db.user_sessions.update_one.return_value = MagicMock()

        payload = {
            "session_id": "test-session-001",
            "question_id": "507f1f77bcf86cd799439011",
            "selected_answer": "A) 2",
        }
        resp = c.post("/submit-answer", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["correct"] is False
        assert data["updated_theta"] < data["previous_theta"]

    def test_404_for_unknown_session(self, client):
        c, mock_db = client
        mock_db.user_sessions.find_one.return_value = None

        payload = {
            "session_id": "bad-session",
            "question_id": "507f1f77bcf86cd799439011",
            "selected_answer": "C) 4",
        }
        resp = c.post("/submit-answer", json=payload)
        assert resp.status_code == 404

    def test_409_for_duplicate_question(self, client):
        c, mock_db = client
        session_with_seen = {
            **SAMPLE_SESSION,
            "seen_question_ids": ["507f1f77bcf86cd799439011"],
        }
        mock_db.user_sessions.find_one.return_value = session_with_seen

        payload = {
            "session_id": "test-session-001",
            "question_id": "507f1f77bcf86cd799439011",
            "selected_answer": "C) 4",
        }
        resp = c.post("/submit-answer", json=payload)
        assert resp.status_code == 409


class TestGeneratePlan:
    def test_plan_generated_with_responses(self, client):
        c, mock_db = client
        session_with_responses = {
            **SAMPLE_SESSION,
            "responses": [
                {"question_id": "abc", "correct": True, "difficulty": 0.4, "topic": "Algebra"},
                {"question_id": "def", "correct": False, "difficulty": 0.7, "topic": "Geometry"},
            ],
            "current_ability_theta": 0.6,
        }
        mock_db.user_sessions.find_one.return_value = session_with_responses

        # Mock LLM to be unavailable (GEMINI_API_KEY not set → fallback plan)
        with patch("main.generate_study_plan", new_callable=AsyncMock) as mock_plan:
            mock_plan.return_value = (
                "Student performed moderately.",
                [
                    StudyStep(step=1, focus="Geometry", action="Practice 30 problems", resource="Manhattan Prep"),
                    StudyStep(step=2, focus="Mixed", action="Timed test", resource="ETS Official"),
                    StudyStep(step=3, focus="Algebra", action="Daily warmup", resource="Magoosh"),
                ],
                None,
            )
            resp = c.post("/generate-plan", json={"session_id": "test-session-001"})

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["steps"]) == 3
        assert data["final_theta"] == 0.6

    def test_400_for_empty_session(self, client):
        c, mock_db = client
        mock_db.user_sessions.find_one.return_value = dict(SAMPLE_SESSION)  # No responses

        resp = c.post("/generate-plan", json={"session_id": "test-session-001"})
        assert resp.status_code == 400
