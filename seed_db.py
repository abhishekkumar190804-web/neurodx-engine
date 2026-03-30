"""
seed_db.py
----------
Seeds the MongoDB `questions` collection with 20 realistic GRE-style questions.

Topics covered:
    - Algebra (4)
    - Geometry (4)
    - Arithmetic (3)
    - Data Analysis (3)
    - Vocabulary (3)
    - Reading Comprehension (3)

Difficulty ranges from 0.1 (easy) to 1.0 (hardest), distributed to cover
the full IRT scale so that the adaptive engine has questions at every level.

Usage:
    python seed_db.py

Note: This script is IDEMPOTENT — it drops and re-inserts all questions.
"""

import asyncio
import sys
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv
import os

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "gre_prep")

QUESTIONS: list[dict] = [
    # ── Algebra (difficulties: 0.2, 0.4, 0.65, 0.85) ──────────────────────
    {
        "text": "If 3x + 7 = 22, what is the value of x?",
        "options": ["A) 3", "B) 4", "C) 5", "D) 6", "E) 7"],
        "correct_answer": "C) 5",
        "topic": "Algebra",
        "difficulty": 0.2,
        "tags": ["linear equations", "basic algebra"],
    },
    {
        "text": (
            "If f(x) = 2x² − 3x + 1, what is f(4)?"
        ),
        "options": ["A) 17", "B) 21", "C) 25", "D) 29", "E) 33"],
        "correct_answer": "B) 21",
        "topic": "Algebra",
        "difficulty": 0.4,
        "tags": ["functions", "quadratic"],
    },
    {
        "text": (
            "The sum of two consecutive even integers is 106. "
            "What is the larger of the two integers?"
        ),
        "options": ["A) 50", "B) 52", "C) 54", "D) 56", "E) 58"],
        "correct_answer": "C) 54",
        "topic": "Algebra",
        "difficulty": 0.65,
        "tags": ["word problems", "consecutive integers"],
    },
    {
        "text": (
            "If |2x − 5| < 9, which of the following represents all possible "
            "values of x?"
        ),
        "options": [
            "A) −2 < x < 7",
            "B) −7 < x < 2",
            "C) x < −2 or x > 7",
            "D) −2 < x < 7 and x ≠ 5",
            "E) x > 7",
        ],
        "correct_answer": "A) −2 < x < 7",
        "topic": "Algebra",
        "difficulty": 0.85,
        "tags": ["absolute value", "inequalities"],
    },
    # ── Geometry (difficulties: 0.25, 0.45, 0.7, 0.95) ────────────────────
    {
        "text": (
            "A rectangle has a length of 12 and a width of 5. "
            "What is the length of its diagonal?"
        ),
        "options": ["A) 11", "B) 12", "C) 13", "D) 14", "E) 17"],
        "correct_answer": "C) 13",
        "topic": "Geometry",
        "difficulty": 0.25,
        "tags": ["Pythagorean theorem", "rectangles"],
    },
    {
        "text": (
            "The radius of circle O is 6. If arc AB subtends a central angle "
            "of 60°, what is the length of arc AB?"
        ),
        "options": ["A) 2π", "B) 3π", "C) 4π", "D) 6π", "E) 12π"],
        "correct_answer": "A) 2π",
        "topic": "Geometry",
        "difficulty": 0.45,
        "tags": ["circles", "arc length"],
    },
    {
        "text": (
            "Triangle ABC is inscribed in a circle of radius 5. If angle A = 90°, "
            "what is the length of side BC?"
        ),
        "options": ["A) 5", "B) 5√2", "C) 10", "D) 10√2", "E) 25"],
        "correct_answer": "C) 10",
        "topic": "Geometry",
        "difficulty": 0.7,
        "tags": ["inscribed angle theorem", "circles", "triangles"],
    },
    {
        "text": (
            "A right circular cone has a base radius of 3 and a slant height of 5. "
            "What is the volume of the cone?"
        ),
        "options": ["A) 12π", "B) 15π", "C) 16π", "D) 36π", "E) 45π"],
        "correct_answer": "A) 12π",
        "topic": "Geometry",
        "difficulty": 0.95,
        "tags": ["3D geometry", "cone", "volume"],
    },
    # ── Arithmetic (difficulties: 0.15, 0.35, 0.55) ───────────────────────
    {
        "text": "What is 15% of 240?",
        "options": ["A) 24", "B) 30", "C) 36", "D) 40", "E) 48"],
        "correct_answer": "C) 36",
        "topic": "Arithmetic",
        "difficulty": 0.15,
        "tags": ["percentages", "basic arithmetic"],
    },
    {
        "text": (
            "A store marks up an item by 40% and then offers a 20% discount "
            "on the marked-up price. What is the net percentage change from "
            "the original price?"
        ),
        "options": ["A) 8% loss", "B) 8% gain", "C) 12% gain", "D) 12% loss", "E) 20% gain"],
        "correct_answer": "C) 12% gain",
        "topic": "Arithmetic",
        "difficulty": 0.35,
        "tags": ["percentages", "successive changes"],
    },
    {
        "text": (
            "If the ratio of boys to girls in a class is 3:5 and there are "
            "40 students in total, how many boys are in the class?"
        ),
        "options": ["A) 10", "B) 12", "C) 15", "D) 24", "E) 25"],
        "correct_answer": "C) 15",
        "topic": "Arithmetic",
        "difficulty": 0.55,
        "tags": ["ratios", "proportions"],
    },
    # ── Data Analysis (difficulties: 0.3, 0.6, 0.8) ──────────────────────
    {
        "text": (
            "The mean of five numbers is 12. If one number is removed and the "
            "new mean is 11, what was the removed number?"
        ),
        "options": ["A) 14", "B) 15", "C) 16", "D) 17", "E) 18"],
        "correct_answer": "C) 16",
        "topic": "Data Analysis",
        "difficulty": 0.3,
        "tags": ["mean", "statistics"],
    },
    {
        "text": (
            "A dataset has the values: 4, 7, 7, 9, 11, 13, 13, 13, 20. "
            "Which measure of central tendency is greatest?"
        ),
        "options": [
            "A) Mean",
            "B) Median",
            "C) Mode",
            "D) Mean and Median are equal",
            "E) All three are equal",
        ],
        "correct_answer": "A) Mean",
        "topic": "Data Analysis",
        "difficulty": 0.6,
        "tags": ["mean", "median", "mode", "statistics"],
    },
    {
        "text": (
            "In a normal distribution with mean 500 and standard deviation 100, "
            "approximately what percentage of values fall between 400 and 600?"
        ),
        "options": ["A) 50%", "B) 68%", "C) 75%", "D) 95%", "E) 99.7%"],
        "correct_answer": "B) 68%",
        "topic": "Data Analysis",
        "difficulty": 0.8,
        "tags": ["normal distribution", "standard deviation", "statistics"],
    },
    # ── Vocabulary (difficulties: 0.2, 0.5, 0.75) ─────────────────────────
    {
        "text": (
            "The word GARRULOUS most nearly means:"
        ),
        "options": [
            "A) Silent and reserved",
            "B) Excessively talkative",
            "C) Deeply thoughtful",
            "D) Aggressively competitive",
            "E) Easily frightened",
        ],
        "correct_answer": "B) Excessively talkative",
        "topic": "Vocabulary",
        "difficulty": 0.2,
        "tags": ["GRE vocab", "adjectives"],
    },
    {
        "text": "The word EQUIVOCATE most nearly means:",
        "options": [
            "A) To speak clearly and directly",
            "B) To use ambiguous language to mislead",
            "C) To agree enthusiastically",
            "D) To calculate precisely",
            "E) To argue vehemently",
        ],
        "correct_answer": "B) To use ambiguous language to mislead",
        "topic": "Vocabulary",
        "difficulty": 0.5,
        "tags": ["GRE vocab", "verbs"],
    },
    {
        "text": "The word PELLUCID most nearly means:",
        "options": [
            "A) Turbid and murky",
            "B) Obstinately stubborn",
            "C) Translucently clear",
            "D) Excessively verbose",
            "E) Cautiously optimistic",
        ],
        "correct_answer": "C) Translucently clear",
        "topic": "Vocabulary",
        "difficulty": 0.75,
        "tags": ["GRE vocab", "high-frequency", "adjectives"],
    },
    # ── Reading Comprehension (difficulties: 0.4, 0.65, 0.9) ──────────────
    {
        "text": (
            "Passage: 'The resurgence of interest in stoic philosophy during the "
            "21st century can be attributed partly to its pragmatic approach to "
            "adversity and the widespread availability of ancient texts in "
            "translation.'\n\n"
            "The passage suggests that stoic philosophy's modern appeal is "
            "primarily due to:"
        ),
        "options": [
            "A) Its association with prestigious academic institutions",
            "B) Its practical approach to handling hardship and accessibility of texts",
            "C) Its rejection of modern psychological theories",
            "D) Its emphasis on emotional expression",
            "E) Its complex metaphysical framework",
        ],
        "correct_answer": (
            "B) Its practical approach to handling hardship and accessibility of texts"
        ),
        "topic": "Reading Comprehension",
        "difficulty": 0.4,
        "tags": ["main idea", "inference"],
    },
    {
        "text": (
            "Passage: 'While classical economists posited that markets self-correct "
            "efficiently, behavioral economists demonstrated that cognitive biases — "
            "such as loss aversion and anchoring — systematically distort economic "
            "decision-making in predictable ways.'\n\n"
            "The author's primary purpose in this passage is to:"
        ),
        "options": [
            "A) Refute the entire field of classical economics",
            "B) Contrast classical and behavioral economic assumptions about rationality",
            "C) Argue that cognitive biases should be ignored in policy decisions",
            "D) Praise the predictive accuracy of classical market models",
            "E) Describe the history of economic thought chronologically",
        ],
        "correct_answer": (
            "B) Contrast classical and behavioral economic assumptions about rationality"
        ),
        "topic": "Reading Comprehension",
        "difficulty": 0.65,
        "tags": ["author's purpose", "contrast structure"],
    },
    {
        "text": (
            "Passage: 'The paradox of tolerance, as articulated by Popper, holds that "
            "a tolerant society must be intolerant of intolerance itself — lest "
            "intolerant groups ultimately destroy the very openness that tolerated them. "
            "Critics of this view argue that any limit on tolerance sets a dangerous "
            "precedent for authoritarian suppression of dissent.'\n\n"
            "Which of the following best describes the relationship between Popper's "
            "view and that of his critics?"
        ),
        "options": [
            "A) They agree on ends but differ on means",
            "B) Popper's critics reject his conclusion as internally inconsistent",
            "C) The critics reinforce Popper's argument with additional evidence",
            "D) Both views advocate for unlimited free speech",
            "E) Popper advocates suppression while critics advocate tolerance",
        ],
        "correct_answer": "A) They agree on ends but differ on means",
        "topic": "Reading Comprehension",
        "difficulty": 0.9,
        "tags": ["logical structure", "critical reasoning", "philosophy"],
    },
]


def seed_database() -> None:
    """Connect to MongoDB and insert all GRE questions."""
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]

    print(f"Connected to MongoDB at {MONGODB_URI} | DB: {DB_NAME}")

    # Drop existing questions to ensure a clean, idempotent seed
    deleted = db.questions.delete_many({})
    print(f"  Cleared {deleted.deleted_count} existing question(s).")

    # Insert all questions
    result = db.questions.insert_many(QUESTIONS)
    print(f"  Inserted {len(result.inserted_ids)} questions successfully.")

    # Ensure indexes exist
    db.questions.create_index([("difficulty", ASCENDING)], name="difficulty_asc")
    db.questions.create_index([("topic", ASCENDING)], name="topic_asc")
    print("  Indexes verified: difficulty_asc, topic_asc")

    # Summary
    topics = db.questions.distinct("topic")
    print(f"\n  Topics in DB: {', '.join(sorted(topics))}")
    print(f"  Total questions: {db.questions.count_documents({})}")

    client.close()
    print("\nSeeding complete!")


if __name__ == "__main__":
    seed_database()
