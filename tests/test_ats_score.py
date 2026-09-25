"""Tests for AtsScoreService."""

from packages.domain.ats_score import AtsScoreService


def test_score_rewards_overlapping_keywords():
    svc = AtsScoreService()
    low = svc.score_text("cashier retail", "Senior Python engineer FastAPI PostgreSQL")
    high = svc.score_text(
        "Python FastAPI PostgreSQL engineer",
        "Senior Python engineer FastAPI PostgreSQL",
    )
    assert 0 <= low.score <= 100
    assert high.score > low.score
    assert "python" in [k.lower() for k in high.matched]


def test_does_not_require_invented_skills_in_resume():
    svc = AtsScoreService()
    result = svc.score_text("Python developer", "Requires Kubernetes expertise")
    assert "kubernetes" in [m.lower() for m in result.missing]
    assert result.score < 90


def test_preference_scoring_includes_skills():
    svc = AtsScoreService()
    result = svc.score_against_preferences(
        "Built APIs with Python and FastAPI",
        target_roles=["Backend Engineer"],
        skills=["Python", "FastAPI", "Kafka"],
    )
    assert "python" in [m.lower() for m in result.matched]
    assert "kafka" in [m.lower() for m in result.missing]
