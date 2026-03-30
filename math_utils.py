"""
math_utils.py
-------------
Item Response Theory (IRT) logic for the Adaptive GRE Prep Engine.

Implements the 1-Parameter Logistic (1PL) Rasch Model:
    P(correct | θ, β) = 1 / (1 + exp(-(θ - β)))

Where:
    θ (theta) = student ability estimate  [-3, 3] scale
    β (beta)  = item difficulty parameter [0.1, 1.0] → mapped to [-3, 3]
"""

import math
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Gradient ascent learning rate for MLE theta update
LEARNING_RATE: float = 0.3

# Convergence threshold; stop iterating when gradient is smaller than this
CONVERGENCE_THRESHOLD: float = 1e-4

# Maximum gradient ascent iterations per update call
MAX_ITERATIONS: int = 50

# Ability θ is clamped to this range (standard IRT scale)
THETA_MIN: float = -3.0
THETA_MAX: float = 3.0


def difficulty_to_beta(difficulty: float) -> float:
    """
    Map a question difficulty value [0.1, 1.0] to an IRT beta value [-3.0, 3.0].

    This linear transform aligns MongoDB's difficulty scale with the
    standard IRT logit scale used in the Rasch model.

    Args:
        difficulty: Question difficulty in [0.1, 1.0].

    Returns:
        Corresponding beta (item difficulty) in [-3.0, 3.0].
    """
    # Linear interpolation: 0.1 → -3.0, 1.0 → 3.0
    return -3.0 + (difficulty - 0.1) * (6.0 / 0.9)


def rasch_probability(theta: float, beta: float) -> float:
    """
    Compute the probability of a correct response using the Rasch (1PL IRT) model.

        P(correct | θ, β) = 1 / (1 + exp(-(θ - β)))

    Args:
        theta: Student ability estimate on the IRT logit scale.
        beta:  Item difficulty parameter on the IRT logit scale.

    Returns:
        Probability of a correct response in (0, 1).
    """
    try:
        return 1.0 / (1.0 + math.exp(-(theta - beta)))
    except OverflowError:
        # When (theta - beta) is very large negative, exp overflows → P ≈ 0
        return 0.0 if (theta - beta) < 0 else 1.0


def log_likelihood(theta: float, responses: list[dict[str, Any]]) -> float:
    """
    Compute the log-likelihood of the observed response vector given theta.

    L(θ) = Σ_i [ r_i * ln(P_i) + (1 - r_i) * ln(1 - P_i) ]

    Args:
        theta:     Current ability estimate.
        responses: List of dicts with keys 'difficulty' (float) and 'correct' (bool).

    Returns:
        Log-likelihood scalar value.
    """
    ll = 0.0
    for resp in responses:
        beta = difficulty_to_beta(resp["difficulty"])
        p = rasch_probability(theta, beta)
        # Clamp probabilities away from 0/1 to avoid log(0)
        p = max(1e-9, min(1 - 1e-9, p))
        if resp["correct"]:
            ll += math.log(p)
        else:
            ll += math.log(1.0 - p)
    return ll


def compute_gradient(theta: float, responses: list[dict[str, Any]]) -> float:
    """
    Compute the gradient of the log-likelihood with respect to theta.

    dL/dθ = Σ_i [ r_i - P_i(θ) ]

    For the Rasch model the gradient simplifies to the sum of residuals,
    since dP/dθ = P(1-P) and the chain rule yields exactly (r_i - P_i).

    Args:
        theta:     Current ability estimate.
        responses: List of response dicts (see log_likelihood for schema).

    Returns:
        Gradient scalar.
    """
    gradient = 0.0
    for resp in responses:
        beta = difficulty_to_beta(resp["difficulty"])
        p = rasch_probability(theta, beta)
        r = 1.0 if resp["correct"] else 0.0
        gradient += r - p
    return gradient


def update_theta(
    theta: float,
    responses: list[dict[str, Any]],
) -> float:
    """
    Update the student ability estimate θ using Maximum Likelihood Estimation (MLE)
    via gradient ascent on the Rasch model log-likelihood.

    Algorithm:
        Repeat until convergence or MAX_ITERATIONS:
            gradient = dL/dθ = Σ_i (r_i - P_i)
            θ ← clamp(θ + α * gradient, THETA_MIN, THETA_MAX)

    Special cases:
        - All correct  → θ nudged toward THETA_MAX
        - All incorrect → θ nudged toward THETA_MIN
        - Empty responses → θ unchanged

    Args:
        theta:     Current ability estimate.
        responses: Full response history with 'difficulty' and 'correct' keys.

    Returns:
        Updated theta value clamped to [THETA_MIN, THETA_MAX].
    """
    if not responses:
        return theta

    # Handle degenerate cases (all correct / all wrong) to avoid MLE instability
    all_correct = all(r["correct"] for r in responses)
    all_wrong = not any(r["correct"] for r in responses)

    if all_correct:
        # Nudge upward by 0.5, cannot do proper MLE without variance
        return min(THETA_MAX, theta + 0.5)
    if all_wrong:
        return max(THETA_MIN, theta - 0.5)

    current_theta = theta
    for iteration in range(MAX_ITERATIONS):
        gradient = compute_gradient(current_theta, responses)
        new_theta = current_theta + LEARNING_RATE * gradient
        # Clamp to valid IRT scale
        new_theta = max(THETA_MIN, min(THETA_MAX, new_theta))

        if abs(new_theta - current_theta) < CONVERGENCE_THRESHOLD:
            logger.debug(
                "Theta converged after %d iterations: %.4f → %.4f",
                iteration + 1,
                theta,
                new_theta,
            )
            return new_theta

        current_theta = new_theta

    logger.debug(
        "Theta update reached MAX_ITERATIONS (%d): %.4f → %.4f",
        MAX_ITERATIONS,
        theta,
        current_theta,
    )
    return current_theta


def select_target_difficulty(theta: float) -> float:
    """
    Convert the current theta estimate back to a target difficulty value
    for the next question query in MongoDB.

    Inverse of difficulty_to_beta():
        difficulty = 0.1 + (beta + 3.0) * (0.9 / 6.0)

    Args:
        theta: Current ability estimate in [THETA_MIN, THETA_MAX].

    Returns:
        Target question difficulty in [0.1, 1.0].
    """
    # β ≈ θ at the target difficulty (P = 0.5, maximally informative item)
    beta_target = theta
    difficulty = 0.1 + (beta_target + 3.0) * (0.9 / 6.0)
    # Clamp to valid difficulty range
    return max(0.1, min(1.0, difficulty))
