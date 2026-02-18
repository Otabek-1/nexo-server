import math
from dataclasses import dataclass
from uuid import UUID


@dataclass
class RaschEstimate:
    theta_by_submission: dict[UUID, float]
    difficulty_by_item: dict[str, float]


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _prox_init_theta(matrix: list[list[int]]) -> list[float]:
    if not matrix:
        return []
    k = max(1, len(matrix[0]))
    adj = 0.3
    thetas = []
    for row in matrix:
        raw = float(sum(row))
        p = (raw + adj) / (k + 2 * adj)
        p = max(1e-6, min(1 - 1e-6, p))
        thetas.append(math.log(p / (1 - p)))
    mean_theta = sum(thetas) / len(thetas)
    return [t - mean_theta for t in thetas]


def _prox_init_item_difficulty(matrix: list[list[int]]) -> list[float]:
    if not matrix:
        return []
    n = len(matrix)
    k = len(matrix[0])
    adj = 0.3
    difficulties: list[float] = []
    for j in range(k):
        col = sum(matrix[i][j] for i in range(n))
        p = (float(col) + adj) / (n + 2 * adj)
        p = max(1e-6, min(1 - 1e-6, p))
        difficulties.append(math.log((1 - p) / p))
    mean_b = sum(difficulties) / len(difficulties)
    return [b - mean_b for b in difficulties]


def estimate_rasch_1pl(
    submission_ids: list[UUID],
    item_ids: list[str],
    matrix: list[list[int]],
    max_iter: int = 40,
) -> RaschEstimate:
    if not submission_ids or not item_ids or not matrix:
        return RaschEstimate(theta_by_submission={}, difficulty_by_item={})

    n = len(submission_ids)
    k = len(item_ids)
    theta = _prox_init_theta(matrix)
    b = _prox_init_item_difficulty(matrix)

    for _ in range(max_iter):
        for i in range(n):
            grad = 0.0
            hess = 0.0
            for j in range(k):
                p = _sigmoid(theta[i] - b[j])
                grad += matrix[i][j] - p
                hess += p * (1 - p)
            if hess > 1e-9:
                theta[i] += grad / hess

        for j in range(k):
            grad = 0.0
            hess = 0.0
            for i in range(n):
                p = _sigmoid(theta[i] - b[j])
                grad += p - matrix[i][j]
                hess += p * (1 - p)
            if hess > 1e-9:
                b[j] += grad / hess

        mean_b = sum(b) / len(b)
        b = [x - mean_b for x in b]
        theta = [x - mean_b for x in theta]

    theta_by_submission = {submission_ids[i]: theta[i] for i in range(n)}
    difficulty_by_item = {item_ids[j]: b[j] for j in range(k)}
    return RaschEstimate(theta_by_submission=theta_by_submission, difficulty_by_item=difficulty_by_item)


def theta_to_score_100(theta: float) -> float:
    return max(0.0, min(100.0, 100.0 * _sigmoid(theta)))

