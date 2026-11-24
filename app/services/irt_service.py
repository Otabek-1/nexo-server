import math
from dataclasses import dataclass
from uuid import UUID


@dataclass
class IRTEstimate:
    theta_by_submission: dict[UUID, float]
    theta_se_by_submission: dict[UUID, float]


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _logsumexp(values: list[float]) -> float:
    if not values:
        return float("-inf")
    anchor = max(values)
    return anchor + math.log(sum(math.exp(value - anchor) for value in values))


def theta_to_sat_section(theta: float) -> int:
    probability = _sigmoid(theta)
    return max(200, min(800, round(200 + 600 * probability)))


def theta_to_sat_total(theta_reading: float, theta_math: float) -> int:
    return theta_to_sat_section(theta_reading) + theta_to_sat_section(theta_math)


def estimate_2pl(
    submission_ids: list[UUID],
    item_ids: list[str],
    matrix: list[list[int]],
    difficulties: list[float],
    discriminations: list[float],
    guessing: list[float],
) -> IRTEstimate:
    if not submission_ids or not item_ids or not matrix:
        return IRTEstimate({}, {})

    nodes = [(-4.0 + index * 8.0 / 40) for index in range(41)]
    density = [math.exp(-0.5 * node * node) for node in nodes]
    weight_total = sum(density)
    weights = [value / weight_total for value in density]

    theta_by_submission: dict[UUID, float] = {}
    theta_se_by_submission: dict[UUID, float] = {}
    item_count = min(len(item_ids), len(difficulties), len(discriminations), len(guessing))

    for index, submission_id in enumerate(submission_ids):
        row = matrix[index] if index < len(matrix) else []
        log_terms: list[float] = []
        for node_index, node in enumerate(nodes):
            log_probability = math.log(max(weights[node_index], 1e-300))
            for item_index in range(item_count):
                if item_index >= len(row):
                    break
                difficulty = difficulties[item_index]
                discrimination = discriminations[item_index]
                c = guessing[item_index]
                probability = c + (1.0 - c) * _sigmoid(discrimination * (node - difficulty))
                probability = min(max(probability, 1e-9), 1.0 - 1e-9)
                log_probability += math.log(probability if row[item_index] else 1.0 - probability)
            log_terms.append(log_probability)

        log_total = _logsumexp(log_terms)
        posterior = [math.exp(term - log_total) for term in log_terms]
        theta = sum(probability * node for probability, node in zip(posterior, nodes))
        variance = sum(probability * ((node - theta) ** 2) for probability, node in zip(posterior, nodes))
        theta_by_submission[submission_id] = theta
        theta_se_by_submission[submission_id] = math.sqrt(max(variance, 1e-12))

    return IRTEstimate(
        theta_by_submission=theta_by_submission,
        theta_se_by_submission=theta_se_by_submission,
    )
