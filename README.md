# NeuroDx | AI-Driven Adaptive GRE Prep Engine

A production-quality **Computer Adaptive Testing (CAT)** API for GRE preparation, powered by:
- **FastAPI** — async REST API
- **MongoDB** (Motor) — question bank and session storage
- **1PL IRT / Rasch Model** — real-time ability estimation via MLE
- **Google Gemini** — personalized study plan generation

---

## Architecture

```
POST /sessions                → Create session (theta₀ = 0.5)
GET  /next-question/{id}      → Adaptive question (closest difficulty to theta)
POST /submit-answer           → Record response, run Rasch MLE theta update
POST /generate-plan           → LLM-powered 3-step study plan
GET  /sessions/{id}/status    → Session state
GET  /health                  → Liveness probe
```

### IRT: Rasch Model (1PL)

$$P(\text{correct} \mid \theta, \beta) = \frac{1}{1 + e^{-(\theta - \beta)}}$$

After each response, theta is updated via **gradient ascent MLE**:

$$\nabla\ell(\theta) = \sum_i [r_i - P_i(\theta)], \quad \theta \leftarrow \theta + \alpha \cdot \nabla\ell$$

with α = 0.3, convergence threshold = 1e-4, and θ clamped to [−3, 3].

---

## Quick Start

### 1. Prerequisites
- Python 3.11+
- MongoDB running locally (`mongod`) or an Atlas connection string

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
copy .env.example .env
# Edit .env — add MONGODB_URI and GEMINI_API_KEY
```

### 4. Seed the database (20 GRE questions)
```bash
python seed_db.py
```

### 5. Run the API
```bash
uvicorn main:app --reload
```
> Swagger UI: http://localhost:8000/docs  
> ReDoc: http://localhost:8000/redoc

---

## Example Workflow

```bash
# 1. Create session
curl -X POST http://localhost:8000/sessions

# 2. Get first question
curl http://localhost:8000/next-question/<session_id>

# 3. Submit answer
curl -X POST http://localhost:8000/submit-answer \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<id>","question_id":"<qid>","selected_answer":"C) 5"}'

# 4. Get study plan
curl -X POST http://localhost:8000/generate-plan \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<id>"}'
```

---

## Running Tests

```bash
pytest test_api.py -v
```

Test coverage:
- **Unit**: `rasch_probability`, `update_theta`, `difficulty_to_beta`, `select_target_difficulty`
- **Integration**: All 5 endpoints with mocked MongoDB (no DB required)

---

## Project Structure

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app + all endpoints |
| `database.py` | Motor async client, settings, index creation |
| `models.py` | Pydantic v2 schemas |
| `math_utils.py` | Rasch IRT — probability, MLE theta update |
| `llm_service.py` | Gemini API — Expert GRE Tutor prompt + fallback |
| `seed_db.py` | 20 GRE questions seeder (idempotent) |
| `test_api.py` | pytest unit + integration tests |

---

## MongoDB Indexes

Created automatically on startup:
```
db.questions.create_index([("difficulty", 1)])  # O(log n) adaptive queries
db.questions.create_index([("topic", 1)])
db.user_sessions.create_index([("session_id", 1)], unique=True)
```

---

## LLM Study Plan

The `/generate-plan` endpoint uses a formatted natural-language prompt (not raw JSON):

> *"The student attempted 10 questions. They failed 80% of Geometry questions but
> passed 90% of Algebra at difficulty 0.8. Final ability score (theta): 0.62 …"*

**Fallback**: If `GEMINI_API_KEY` is not set or the API call fails, a rule-based
plan is generated automatically — the endpoint never returns 500.
