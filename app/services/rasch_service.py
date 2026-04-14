import math
from dataclasses import dataclass
from uuid import UUID


@dataclass
class RaschEstimate:
    theta_by_submission: dict[UUID, float]
    difficulty_by_item: dict[str, float]
    theta_se_by_submission: dict[UUID, float]
    item_se_by_item: dict[str, float]


@dataclass
class RaschItemStat:
    item_id: str
    correct_count: int
    incorrect_count: int
    total_count: int
    accuracy: float


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _normal_density(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _logsumexp(values: list[float]) -> float:
    if not values:
        return float("-inf")
    anchor = max(values)
    if not math.isfinite(anchor):
        return anchor
    return anchor + math.log(sum(math.exp(value - anchor) for value in values))


def _initial_item_difficulties(matrix: list[list[int]]) -> list[float]:
    if not matrix:
        return []
    n = len(matrix)
    k = len(matrix[0])
    adj = 0.5
    difficulties: list[float] = []
    for j in range(k):
        correct = sum(int(matrix[i][j]) for i in range(n))
        p = (correct + adj) / (n + 2 * adj)
        p = min(max(p, 1e-6), 1 - 1e-6)
        difficulties.append(math.log((1.0 - p) / p))
    mean_b = sum(difficulties) / len(difficulties)
    return [value - mean_b for value in difficulties]


def _quadrature_grid(size: int = 41, lower: float = -6.0, upper: float = 6.0) -> tuple[list[float], list[float]]:
    if size < 3:
        size = 3
    step = (upper - lower) / float(size - 1)
    nodes = [lower + step * index for index in range(size)]
    weights = [_normal_density(node) for node in nodes]
    total = sum(weights)
    normalized = [weight / total for weight in weights]
    return nodes, normalized


def _posterior_by_submission(
    matrix: list[list[int]],
    difficulties: list[float],
    nodes: list[float],
    weights: list[float],
) -> list[list[float]]:
    posterior: list[list[float]] = []
    for row in matrix:
        log_terms: list[float] = []
        for node, base_weight in zip(nodes, weights):
            log_prob = math.log(base_weight)
            for difficulty, response in zip(difficulties, row):
                p = _sigmoid(node - difficulty)
                log_prob += math.log(p if int(response) else 1.0 - p)
            log_terms.append(log_prob)

        log_total = _logsumexp(log_terms)
        posterior.append([math.exp(term - log_total) for term in log_terms])
    return posterior


def estimate_rasch_1pl(
    submission_ids: list[UUID],
    item_ids: list[str],
    matrix: list[list[int]],
    max_iter: int = 200,
    tol: float = 1e-5,
) -> RaschEstimate:
    if not submission_ids or not item_ids or not matrix:
        return RaschEstimate(
            theta_by_submission={},
            difficulty_by_item={},
            theta_se_by_submission={},
            item_se_by_item={},
        )

    n = len(submission_ids)
    k = len(item_ids)
    nodes, weights = _quadrature_grid()
    difficulties = _initial_item_difficulties(matrix)

    for _ in range(max_iter):
        posterior = _posterior_by_submission(matrix, difficulties, nodes, weights)
        max_change = 0.0

        for j in range(k):
            observed = sum(int(matrix[i][j]) for i in range(n))
            expected = 0.0
            information = 0.0
            for person_index in range(n):
                for prob, node in zip(posterior[person_index], nodes):
                    p = _sigmoid(node - difficulties[j])
                    expected += prob * p
                    information += prob * p * (1.0 - p)

            if information <= 1e-9:
                continue

            update = (observed - expected) / information
            difficulties[j] += update
            difficulties[j] = min(max(difficulties[j], -8.0), 8.0)
            max_change = max(max_change, abs(update))

        mean_b = sum(difficulties) / len(difficulties)
        difficulties = [value - mean_b for value in difficulties]

        if max_change < tol:
            break

    final_posterior = _posterior_by_submission(matrix, difficulties, nodes, weights)

    theta_by_submission: dict[UUID, float] = {}
    theta_se_by_submission: dict[UUID, float] = {}
    for index, submission_id in enumerate(submission_ids):
        probs = final_posterior[index]
        theta = sum(prob * node for prob, node in zip(probs, nodes))
        variance = sum(prob * ((node - theta) ** 2) for prob, node in zip(probs, nodes))
        theta_by_submission[submission_id] = theta
        theta_se_by_submission[submission_id] = math.sqrt(max(variance, 1e-12))

    item_se_by_item: dict[str, float] = {}
    for item_index, item_id in enumerate(item_ids):
        information = 0.0
        for person_index in range(n):
            for node_index, node in enumerate(nodes):
                post = final_posterior[person_index][node_index]
                p = _sigmoid(node - difficulties[item_index])
                information += post * p * (1.0 - p)
        item_se_by_item[item_id] = math.sqrt(1.0 / information) if information > 1e-9 else float("inf")

    difficulty_by_item = {item_ids[index]: difficulties[index] for index in range(k)}
    return RaschEstimate(
        theta_by_submission=theta_by_submission,
        difficulty_by_item=difficulty_by_item,
        theta_se_by_submission=theta_se_by_submission,
        item_se_by_item=item_se_by_item,
    )


def theta_to_score_100(theta: float) -> float:
    return max(0.0, min(100.0, 100.0 * _sigmoid(theta)))


def summarize_rasch_items(item_ids: list[str], matrix: list[list[int]]) -> list[RaschItemStat]:
    if not item_ids or not matrix:
        return []

    item_stats: list[RaschItemStat] = []
    total_rows = len(matrix)

    for index, item_id in enumerate(item_ids):
        correct_count = sum(1 for row in matrix if index < len(row) and int(row[index]) == 1)
        incorrect_count = max(total_rows - correct_count, 0)
        total_count = correct_count + incorrect_count
        accuracy = (correct_count / total_count) if total_count > 0 else 0.0
        item_stats.append(
            RaschItemStat(
                item_id=item_id,
                correct_count=correct_count,
                incorrect_count=incorrect_count,
                total_count=total_count,
                accuracy=accuracy,
            )
        )

    return item_stats
