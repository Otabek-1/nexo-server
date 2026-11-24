from uuid import UUID

from app.services.irt_service import estimate_2pl, theta_to_sat_section, theta_to_sat_total


def test_irt_orders_ability_by_correct_responses():
    ids = [
        UUID("20000000-0000-0000-0000-000000000001"),
        UUID("20000000-0000-0000-0000-000000000002"),
        UUID("20000000-0000-0000-0000-000000000003"),
    ]
    estimate = estimate_2pl(
        submission_ids=ids,
        item_ids=["q1", "q2", "q3"],
        matrix=[[1, 1, 1], [1, 0, 0], [0, 0, 0]],
        difficulties=[-1.0, 0.0, 1.0],
        discriminations=[1.0, 1.0, 1.0],
        guessing=[0.0, 0.0, 0.0],
    )
    assert estimate.theta_by_submission[ids[0]] > estimate.theta_by_submission[ids[1]] > estimate.theta_by_submission[ids[2]]


def test_sat_section_and_total_scores_are_bounded():
    section = theta_to_sat_section(0)
    total = theta_to_sat_total(-1, 1)
    assert 200 <= section <= 800
    assert 400 <= total <= 1600
