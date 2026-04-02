"""
MongoDB Question Seeder — 25 GRE-style questions with IRT parameters.
Run: python -m backend.seed_db
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "gre_adaptive")

GRE_QUESTIONS = [
    # ── ALGEBRA (Quantitative) ────────────────────────────────────────────────
    {
        "text": "If 3x + 7 = 22, what is the value of 6x − 5?",
        "options": ["A) 20", "B) 25", "C) 30", "D) 35", "E) 40"],
        "correct_answer": "B",
        "difficulty": 0.2,
        "topic": "Algebra",
        "tags": ["linear equations", "basic"],
        "discrimination": 0.9,
        "guessing": 0.2,
    },
    {
        "text": "What are the roots of the equation x² − 5x + 6 = 0?",
        "options": ["A) 1 and 6", "B) 2 and 3", "C) −2 and −3", "D) 1 and −6", "E) −1 and 6"],
        "correct_answer": "B",
        "difficulty": 0.3,
        "topic": "Algebra",
        "tags": ["quadratic", "factoring"],
        "discrimination": 1.0,
        "guessing": 0.2,
    },
    {
        "text": "If f(x) = 2x² − 3x + 1, what is f(−2)?",
        "options": ["A) 15", "B) 10", "C) 3", "D) 11", "E) −3"],
        "correct_answer": "A",
        "difficulty": 0.4,
        "topic": "Algebra",
        "tags": ["functions", "substitution"],
        "discrimination": 1.1,
        "guessing": 0.2,
    },
    {
        "text": "For all real x, if |2x − 4| < 6, which of the following must be true?",
        "options": ["A) −1 < x < 5", "B) −1 < x < 4", "C) 1 < x < 7", "D) x > −1", "E) x < 5"],
        "correct_answer": "A",
        "difficulty": 0.65,
        "topic": "Algebra",
        "tags": ["absolute value", "inequalities"],
        "discrimination": 1.3,
        "guessing": 0.2,
    },
    {
        "text": "If log₂(x) + log₂(x−2) = 3, what is the value of x?",
        "options": ["A) 2", "B) 3", "C) 4", "D) 5", "E) 6"],
        "correct_answer": "C",
        "difficulty": 0.8,
        "topic": "Algebra",
        "tags": ["logarithms", "advanced"],
        "discrimination": 1.4,
        "guessing": 0.2,
    },

    # ── GEOMETRY (Quantitative) ───────────────────────────────────────────────
    {
        "text": "A rectangle has perimeter 36 cm and length 10 cm. What is its area?",
        "options": ["A) 72 cm²", "B) 80 cm²", "C) 90 cm²", "D) 64 cm²", "E) 56 cm²"],
        "correct_answer": "B",
        "difficulty": 0.2,
        "topic": "Geometry",
        "tags": ["perimeter", "area", "rectangle"],
        "discrimination": 0.9,
        "guessing": 0.2,
    },
    {
        "text": "In a right triangle, the two legs measure 6 and 8. What is the hypotenuse?",
        "options": ["A) 9", "B) 10", "C) 11", "D) 12", "E) 14"],
        "correct_answer": "B",
        "difficulty": 0.25,
        "topic": "Geometry",
        "tags": ["Pythagorean theorem", "right triangle"],
        "discrimination": 0.95,
        "guessing": 0.2,
    },
    {
        "text": "A circle has an area of 49π. What is its circumference?",
        "options": ["A) 7π", "B) 14π", "C) 21π", "D) 28π", "E) 49π"],
        "correct_answer": "B",
        "difficulty": 0.45,
        "topic": "Geometry",
        "tags": ["circle", "circumference", "area"],
        "discrimination": 1.1,
        "guessing": 0.2,
    },
    {
        "text": "Two parallel lines are cut by a transversal. If one interior angle is 65°, what is the co-interior (same-side interior) angle?",
        "options": ["A) 65°", "B) 115°", "C) 25°", "D) 130°", "E) 90°"],
        "correct_answer": "B",
        "difficulty": 0.55,
        "topic": "Geometry",
        "tags": ["parallel lines", "transversal", "angles"],
        "discrimination": 1.2,
        "guessing": 0.2,
    },
    {
        "text": "A cone has radius 3 and height 4. What is its volume? (V = ⅓πr²h)",
        "options": ["A) 12π", "B) 16π", "C) 24π", "D) 36π", "E) 48π"],
        "correct_answer": "A",
        "difficulty": 0.7,
        "topic": "Geometry",
        "tags": ["cone", "volume", "3D"],
        "discrimination": 1.3,
        "guessing": 0.2,
    },

    # ── STATISTICS & DATA ANALYSIS ────────────────────────────────────────────
    {
        "text": "The mean of five numbers is 12. If four of the numbers are 8, 11, 15, and 16, what is the fifth number?",
        "options": ["A) 8", "B) 10", "C) 12", "D) 14", "E) 10"],
        "correct_answer": "B",
        "difficulty": 0.3,
        "topic": "Statistics",
        "tags": ["mean", "average"],
        "discrimination": 1.0,
        "guessing": 0.2,
    },
    {
        "text": "A data set has values: 4, 7, 7, 9, 12, 12, 12, 15. What is the mode?",
        "options": ["A) 7", "B) 9", "C) 12", "D) 15", "E) 10"],
        "correct_answer": "C",
        "difficulty": 0.15,
        "topic": "Statistics",
        "tags": ["mode", "basic statistics"],
        "discrimination": 0.85,
        "guessing": 0.2,
    },
    {
        "text": "In a normal distribution, approximately what percentage of data falls within 2 standard deviations of the mean?",
        "options": ["A) 50%", "B) 68%", "C) 90%", "D) 95%", "E) 99%"],
        "correct_answer": "D",
        "difficulty": 0.6,
        "topic": "Statistics",
        "tags": ["normal distribution", "standard deviation"],
        "discrimination": 1.2,
        "guessing": 0.2,
    },
    {
        "text": "If P(A) = 0.4 and P(B) = 0.3 and A and B are independent events, what is P(A ∩ B)?",
        "options": ["A) 0.70", "B) 0.12", "C) 0.07", "D) 0.58", "E) 0.40"],
        "correct_answer": "B",
        "difficulty": 0.5,
        "topic": "Statistics",
        "tags": ["probability", "independent events"],
        "discrimination": 1.15,
        "guessing": 0.2,
    },

    # ── NUMBER THEORY ─────────────────────────────────────────────────────────
    {
        "text": "What is the greatest common divisor (GCD) of 48 and 180?",
        "options": ["A) 6", "B) 12", "C) 24", "D) 36", "E) 18"],
        "correct_answer": "B",
        "difficulty": 0.35,
        "topic": "Number Theory",
        "tags": ["GCD", "factors"],
        "discrimination": 1.05,
        "guessing": 0.2,
    },
    {
        "text": "How many prime numbers exist between 50 and 70?",
        "options": ["A) 3", "B) 4", "C) 5", "D) 6", "E) 2"],
        "correct_answer": "B",
        "difficulty": 0.55,
        "topic": "Number Theory",
        "tags": ["prime numbers", "counting"],
        "discrimination": 1.1,
        "guessing": 0.2,
    },

    # ── VOCABULARY (Verbal) ───────────────────────────────────────────────────
    {
        "text": "Choose the word most similar in meaning to LACONIC:",
        "options": ["A) Talkative", "B) Brief", "C) Melancholy", "D) Energetic", "E) Confused"],
        "correct_answer": "B",
        "difficulty": 0.3,
        "topic": "Vocabulary",
        "tags": ["synonyms", "adjective"],
        "discrimination": 1.0,
        "guessing": 0.2,
    },
    {
        "text": "Choose the word most opposite in meaning to OBSTINATE:",
        "options": ["A) Stubborn", "B) Persistent", "C) Pliable", "D) Rigid", "E) Tenacious"],
        "correct_answer": "C",
        "difficulty": 0.45,
        "topic": "Vocabulary",
        "tags": ["antonyms", "adjective"],
        "discrimination": 1.1,
        "guessing": 0.2,
    },
    {
        "text": "The scientist's findings were so RECONDITE that only specialists could appreciate their significance. RECONDITE most nearly means:",
        "options": ["A) Widely known", "B) Abstruse", "C) Transparent", "D) Simplistic", "E) Experimental"],
        "correct_answer": "B",
        "difficulty": 0.75,
        "topic": "Vocabulary",
        "tags": ["context clue", "advanced vocabulary"],
        "discrimination": 1.35,
        "guessing": 0.2,
    },

    # ── TEXT COMPLETION (Verbal) ──────────────────────────────────────────────
    {
        "text": "Despite the professor's _______ reputation, students found her lectures surprisingly engaging.\n\nBlank: (i)",
        "options": ["A) pedantic", "B) boring", "C) stimulating", "D) controversial", "E) nonexistent"],
        "correct_answer": "A",
        "difficulty": 0.5,
        "topic": "Text Completion",
        "tags": ["blank fill", "verbal reasoning"],
        "discrimination": 1.1,
        "guessing": 0.2,
    },
    {
        "text": "The diplomat's remarks were deliberately _______, allowing all parties to interpret them favorably.\n\nBlank: (i)",
        "options": ["A) candid", "B) ambiguous", "C) harsh", "D) specific", "E) accusatory"],
        "correct_answer": "B",
        "difficulty": 0.6,
        "topic": "Text Completion",
        "tags": ["blank fill", "context"],
        "discrimination": 1.2,
        "guessing": 0.2,
    },

    # ── READING COMPREHENSION (Verbal) ───────────────────────────────────────
    {
        "text": "The passage suggests that the author views technological determinism primarily as:\n\n[Passage excerpt]: 'While convenient, deterministic frameworks oversimplify the complex, bidirectional relationship between society and technology.'",
        "options": ["A) A useful explanatory tool", "B) An overly reductive model", "C) The dominant academic view", "D) An empirically proven theory", "E) A politically motivated concept"],
        "correct_answer": "B",
        "difficulty": 0.65,
        "topic": "Reading Comprehension",
        "tags": ["inference", "author's view"],
        "discrimination": 1.25,
        "guessing": 0.2,
    },
    {
        "text": "Which of the following best describes the primary purpose of the passage?\n\n[Passage excerpt]: 'Critics of classical music's concert decorum argue that enforced silence alienates younger audiences and perpetuates social exclusivity, ultimately threatening the art form's survival.'",
        "options": ["A) To celebrate concert traditions", "B) To argue for loosening concert norms", "C) To analyze youth demographics", "D) To compare music formats", "E) To defend classical music's popularity"],
        "correct_answer": "B",
        "difficulty": 0.55,
        "topic": "Reading Comprehension",
        "tags": ["primary purpose", "passage analysis"],
        "discrimination": 1.15,
        "guessing": 0.2,
    },

    # ── SENTENCE EQUIVALENCE (Verbal) ─────────────────────────────────────────
    {
        "text": "The new policy was seen as _______ by most stakeholders, who felt it addressed their core concerns without imposing unnecessary burdens.\n\nSelect TWO answer choices that create sentences alike in meaning.",
        "options": ["A) equitable", "B) draconian", "C) judicious", "D) capricious", "E) onerous", "F) balanced"],
        "correct_answer": "C",
        "difficulty": 0.8,
        "topic": "Sentence Equivalence",
        "tags": ["two correct", "sentence equivalence"],
        "discrimination": 1.4,
        "guessing": 0.15,
    },
    {
        "text": "The mathematician's proof, though _______, contained a subtle flaw that eluded detection for decades.\n\nSelect TWO answer choices that create sentences alike in meaning.",
        "options": ["A) superficial", "B) rigorous", "C) meticulous", "D) approximate", "E) flawed", "F) speculative"],
        "correct_answer": "B",
        "difficulty": 0.85,
        "topic": "Sentence Equivalence",
        "tags": ["two correct", "advanced verbal"],
        "discrimination": 1.45,
        "guessing": 0.15,
    },
]


async def seed():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    # Drop and re-seed questions collection
    await db.gre_questions.drop()
    result = await db.gre_questions.insert_many(GRE_QUESTIONS)
    count = len(result.inserted_ids)
    print(f"✅ Seeded {count} GRE questions into '{DB_NAME}.gre_questions'")

    # Verify topics
    topics = await db.gre_questions.distinct("topic")
    print(f"📚 Topics covered: {', '.join(sorted(topics))}")

    # Verify difficulty range
    easy = await db.gre_questions.count_documents({"difficulty": {"$lt": 0.4}})
    med = await db.gre_questions.count_documents({"difficulty": {"$gte": 0.4, "$lt": 0.7}})
    hard = await db.gre_questions.count_documents({"difficulty": {"$gte": 0.7}})
    print(f"📊 Difficulty spread — Easy: {easy}, Medium: {med}, Hard: {hard}")

    # Ensure user_sessions collection exists
    if "user_sessions" not in await db.list_collection_names():
        await db.create_collection("user_sessions")
    print("✅ 'user_sessions' collection ready")

    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
