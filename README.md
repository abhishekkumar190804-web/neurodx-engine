# NeuroDx Testing System

An AI-powered adaptive application for GRE practice that adjusts question difficulty in real-time based on your performance, and generates personalized study plans.

## 🚀 How to Run the Project

### Prerequisites

- Python 3.9+
- MongoDB installed and running locally on port 27017
- An OpenAI API Key

### Setup Instructions

1. **Clone the repository** and navigate to the project directory.

2. **Install Backend Dependencies**:

   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Configure Environment Variables**:
   Create a `.env` file in the `backend/` directory with:

   ```env
   MONGO_URI=mongodb://localhost:27017
   OPENAI_API_KEY=your_actual_api_key_here
   ```

4. **Seed the Database**:
   Populate MongoDB with the initial question bank.

   ```bash
   python backend/seed_db.py
   ```

5. **Run the Backend Server**:
   Start the FastAPI app.

   ```bash
   python -m uvicorn backend.main:app --port 8000 --reload
   ```

6. **Access the Application**:
   Open a web browser and navigate directly to the backend URL, which serves the frontend:
   `http://localhost:8000/`

---

## 🧠 Adaptive Algorithm Logic

The adaptive engine is built strictly upon **Item Response Theory (IRT)**, using a Bayesian updating methodology known as **Expected A Posteriori (EAP)**.

1. **Starting Point**: Every test-taker begins with an initial "Ability Score" (θ) of `0.0` (considered the statistical average/baseline in IRT).
2. **The Adaptive Loop**:
   - When a student tackles a question, the system evaluates their response.
   - If they get it correct, their estimated ability (θ) increases, and the algorithm deliberately selects the next question whose known difficulty ($b$) is slightly above their new ability score.
   - If they get it wrong, their ability drops, and the system selects an easier question.
3. **Continuous Re-Estimation**: The student's ability isn't just a running average. After _every single response_, the Bayesian EAP estimator recalculates their true ability based on their entire response history in that session.

By adjusting in real-time, the system finds the exact skill level of the user much faster and with greater precision than a static test.

---

## 📖 API Documentation

The backend exposes a REST API powered by FastAPI.

- **`GET /health`**
  Checks whether the API is running and counts the available database questions.

- **`POST /session/start`**
  Initializes a new testing session and returns the unique `session_id` along with the first adaptive question.
  - _Response_: `{ session_id, message, first_question }`

- **`POST /answer`**
  Submits an answer to the current question, runs the IRT calculation to update ability, and determines the next question.
  - _Payload_: `{ session_id, question_id, selected_answer }`
  - _Response_: `{ correct, correct_answer, new_ability_score, difficulty_direction, session_complete, next_question }`

- **`GET /session/{session_id}/summary`**
  Retrieves the final breakdown of a completed session, including overall accuracy, percentile performance, and per-topic analysis.

- **`POST /insights`**
  Sends the final session data to an LLM (OpenAI) to generate the personalized 3-step study plan.
  - _Payload_: `{ session_id }`
  - _Response_: AI-generated `{ overall_assessment, strengths, weaknesses, study_plan, motivational_message }`

---

## 🤖 AI Log

**How AI was leveraged:**

- **Code Generation Context**: Used advanced code generation tools to quickly scaffold the entire FastAPI backend, define Pydantic data models, and implement the initial CSS logic for the glassmorphic frontend screens.
- **Algorithm Generation**: Tasked AI with writing the specialized NumPy code required for the Bayesian Expected A Posteriori (EAP) ability estimation within the IRT engine.
- **Data Creation**: Used AI models to instantly generate JSON blobs of 25 high-quality, GRE-style questions spanning multiple topics, automatically assigning them strict difficulties between 0.1 and 1.0.

**Challenges the AI couldn't inherently solve on the first try:**

- **Asynchronous Execution Flows**: Getting the AI to cleanly serialize specific database queries sequentially while serving static HTML files through the FastAPI router required manual architectural steering.
- **Deep CSS UI Bugs**: While the AI built an impressive layout rapidly, a persistent automatic-scrolling "jerk" bug on the results screen required stepping outside of pure code generation and deeply debugging DOM screen-transition layout logics manually.
- **Model Hallucinations with "Fake" DB logic**: The AI occasionally attempted to use non-standard MongoDB aggregation methods for fetching questions which had to be repeatedly steered back to simpler motor-layer queries to reduce async runtime complexity.

---

## 🌍 Deployment Options

Since this is a FastAPI application with a MongoDB backend, here is the recommended deployment strategy:

### 1. Database (MongoDB Atlas)

- Create a free cluster on [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
- Get your connection string (e.g., `mongodb+srv://<user>:<password>@cluster0...`).
- Replace the local `MONGO_URI` in your `.env` file with this string.

### 2. Application Hosting (Render, Railway, or Heroku)

The easiest way to deploy the FastAPI backend and frontend is using a PaaS (Platform as a Service) like **Render**:

1. Push your code to a GitHub repository.
2. Create a new **Web Service** on Render and connect your repository.
3. Use the following build and run commands:
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. In the Render dashboard, add your **Environment Variables**:
   - `MONGO_URI` (your Atlas connection string)
   - `OPENAI_API_KEY` (your OpenAI key)

_(Since the frontend files are served directly by FastAPI from the `/frontend` and `/static` folders, deploying the backend as described above will automatically deploy the frontend as well!)_
