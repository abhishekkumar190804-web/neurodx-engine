"""
Item Response Theory (IRT) — 3-Parameter Logistic Model
Handles adaptive ability estimation and question selection.
"""
import math
import numpy as np
from typing import List, Dict, Any, Optional


# ─── IRT 3PL Model ───────────────────────────────────────────────────────────

def irt_probability(ability: float, difficulty: float,
                    discrimination: float = 1.0,
                    guessing: float = 0.0) -> float:
    """
    P(θ | a, b, c) = c + (1-c) / (1 + exp(-a*(θ - b)))
    
    θ = ability  (maps to difficulty 0.1-1.0 via normalization)
    b = difficulty (converted from [0.1, 1.0] → [-3, 3] scale)
    a = discrimination parameter
    c = guessing parameter
    """
    # Convert difficulty from [0.1, 1.0] scale to [-3, 3] IRT scale
    b = (difficulty - 0.55) * 6.0  # center around 0
    exponent = -discrimination * (ability - b)
    exponent = max(-500, min(500, exponent))  # prevent overflow
    prob = guessing + (1.0 - guessing) / (1.0 + math.exp(exponent))
    return prob


def ability_to_difficulty(ability: float) -> float:
    """Convert IRT ability score [-3, 3] to difficulty [0.1, 1.0]."""
    # Normalize: ability [-3, 3] → difficulty [0.1, 1.0]
    normalized = (ability + 3.0) / 6.0          # → [0, 1]
    return max(0.1, min(1.0, 0.1 + normalized * 0.9))


def difficulty_to_ability(difficulty: float) -> float:
    """Convert difficulty [0.1, 1.0] back to IRT ability [-3, 3]."""
    normalized = (difficulty - 0.1) / 0.9        # → [0, 1]
    return normalized * 6.0 - 3.0


# ─── Ability Estimator (EAP — Expected A Posteriori) ─────────────────────────

class AbilityEstimator:
    """
    Bayesian ability estimator using Expected A Posteriori (EAP) method.
    Updates the student's ability score after each response.
    """

    ABILITY_POINTS = np.linspace(-3, 3, 61)           # Quadrature points
    PRIOR_MEAN = 0.0
    PRIOR_SD = 1.0

    @classmethod
    def compute_prior(cls) -> np.ndarray:
        """Normal prior N(0, 1) over ability range."""
        prior = np.exp(-0.5 * ((cls.ABILITY_POINTS - cls.PRIOR_MEAN) / cls.PRIOR_SD) ** 2)
        return prior / prior.sum()

    @classmethod
    def update_ability(
        cls,
        response_history: List[Dict[str, Any]],
        current_ability: float
    ) -> float:
        """
        EAP update: integrate posterior over ability quadrature points.
        
        Args:
            response_history: list of {correct, difficulty, discrimination, guessing}
            current_ability:  current ability estimate (for fallback)
        
        Returns:
            Updated ability estimate on [-3, 3] scale.
        """
        if not response_history:
            return current_ability

        prior = cls.compute_prior()
        likelihood = np.ones(len(cls.ABILITY_POINTS))

        for resp in response_history:
            correct = resp.get("correct", False)
            difficulty = resp.get("difficulty", 0.5)
            disc = resp.get("discrimination", 1.0)
            guess = resp.get("guessing", 0.0)

            for i, theta in enumerate(cls.ABILITY_POINTS):
                p = irt_probability(theta, difficulty, disc, guess)
                p = max(1e-9, min(1 - 1e-9, p))
                likelihood[i] *= p if correct else (1 - p)

        posterior = prior * likelihood
        total = posterior.sum()
        if total < 1e-15:
            return current_ability      # avoid division by zero

        posterior /= total
        eap = float(np.dot(cls.ABILITY_POINTS, posterior))
        return max(-3.0, min(3.0, eap))

    @classmethod
    def simple_update(cls, current_ability: float, correct: bool,
                      difficulty: float, learning_rate: float = 0.3) -> float:
        """
        Simple adaptive update (used for quick approximation between EAP calls).
        Moves ability up on correct, down on incorrect, weighted by surprise.
        """
        prob = irt_probability(current_ability, difficulty)
        if correct:
            delta = learning_rate * (1.0 - prob)   # big jump if unexpected correct
        else:
            delta = -learning_rate * prob           # big drop if unexpected wrong
        new_ability = current_ability + delta
        return max(-3.0, min(3.0, new_ability))


# ─── Question Selector ────────────────────────────────────────────────────────

def select_next_question(
    current_ability: float,
    questions: List[Dict[str, Any]],
    answered_ids: List[str]
) -> Optional[Dict[str, Any]]:
    """
    Select the next question whose difficulty is closest to the
    student's current *target difficulty* derived from their ability.
    
    Strategy:
      1. Filter out already-answered questions.
      2. Compute target difficulty from ability.
      3. Return the question minimizing |difficulty - target_difficulty|.
      4. Add small random noise to avoid always picking the same question.
    """
    available = [q for q in questions if str(q["_id"]) not in answered_ids]
    if not available:
        return None

    target_difficulty = ability_to_difficulty(current_ability)

    # Score each question: primarily by difficulty proximity, tiny random noise
    rng = np.random.default_rng()
    scored = []
    for q in available:
        diff_gap = abs(q["difficulty"] - target_difficulty)
        noise = rng.uniform(0, 0.02)   # small tiebreaker
        scored.append((diff_gap + noise, q))

    scored.sort(key=lambda x: x[0])
    return scored[0][1]


# ─── Ability Percentile Estimator ─────────────────────────────────────────────

def ability_to_percentile(ability: float) -> int:
    """
    Map IRT ability [-3, 3] to approximate percentile using normal CDF.
    Ability 0.0 → 50th percentile, ±3 → ~0th/100th.
    """
    from scipy.stats import norm
    percentile = int(norm.cdf(ability, loc=0, scale=1) * 100)
    return max(1, min(99, percentile))
