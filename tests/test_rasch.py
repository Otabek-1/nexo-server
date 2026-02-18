from uuid import UUID

from app.services.rasch_service import estimate_rasch_1pl, theta_to_score_100


def test_rasch_estimation_orders_participants():
    # p1 strongest, p3 weakest
    submission_ids = [
        UUID("00000000-0000-0000-0000-000000000001"),
        UUID("00000000-0000-0000-0000-000000000002"),
        UUID("00000000-0000-0000-0000-000000000003"),
    ]
    item_ids = ["i1", "i2", "i3", "i4"]
    matrix = [
        [1, 1, 1, 1],
        [1, 0, 1, 0],
        [0, 0, 0, 0],
    ]

    est = estimate_rasch_1pl(submission_ids=submission_ids, item_ids=item_ids, matrix=matrix)
    theta_1 = est.theta_by_submission[submission_ids[0]]
    theta_2 = est.theta_by_submission[submission_ids[1]]
    theta_3 = est.theta_by_submission[submission_ids[2]]

    assert theta_1 > theta_2 > theta_3
    assert theta_to_score_100(theta_1) > theta_to_score_100(theta_2) > theta_to_score_100(theta_3)


def test_rasch_item_difficulty_direction():
    submission_ids = [
        UUID("10000000-0000-0000-0000-000000000001"),
        UUID("10000000-0000-0000-0000-000000000002"),
        UUID("10000000-0000-0000-0000-000000000003"),
    ]
    item_ids = ["easy", "hard"]
    matrix = [
        [1, 0],
        [1, 0],
        [1, 1],
    ]

    est = estimate_rasch_1pl(submission_ids=submission_ids, item_ids=item_ids, matrix=matrix)
    assert est.difficulty_by_item["hard"] > est.difficulty_by_item["easy"]

