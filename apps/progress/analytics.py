# apps/progress/analytics.py
from django.utils import timezone

from .models import QuizAnswer, QuizAttempt

MIN_EVIDENCE = 5
ANSWER_HALF_LIFE_DAYS = 14
TOPIC_READINESS_WEIGHT = 0.7
MOCK_READINESS_WEIGHT = 0.3

def topic_mastery(user, subject):
    now = timezone.now()
    answer_rows = QuizAnswer.objects.filter(
        attempt__user=user,
        attempt__completed_at__isnull=False,
        question__subject=subject,
    ).values_list(
        "question__topic_id",
        "question__topic__name",
        "is_correct",
        "attempt__completed_at",
    )
    totals = {}
    for topic_id, topic_name, is_correct, completed_at in answer_rows:
        age_days = max((now - completed_at).total_seconds() / 86400, 0)
        answer_weight = 0.5 ** (age_days / ANSWER_HALF_LIFE_DAYS)
        topic = totals.setdefault(topic_id, {
            "name": topic_name,
            "weighted_total": 0.0,
            "weighted_correct": 0.0,
            "n": 0,
        })
        topic["weighted_total"] += answer_weight
        topic["weighted_correct"] += answer_weight * int(is_correct)
        topic["n"] += 1

    results = {}
    for topic_id, topic in totals.items():
        accuracy = topic["weighted_correct"] / topic["weighted_total"]
        results[topic_id] = {
            "name": topic["name"],
            "accuracy": accuracy,
            "accuracy_percent": round(accuracy * 100),
            "n": topic["n"],
            "enough_data": topic["n"] >= MIN_EVIDENCE,
        }
    return results


def difficulty_breakdown(user, subject):
    now = timezone.now()
    answer_rows = QuizAnswer.objects.filter(
        attempt__user=user,
        attempt__completed_at__isnull=False,
        question__subject=subject,
    ).values_list(
        "question__difficulty",
        "is_correct",
        "attempt__completed_at",
    )
    totals = {
        difficulty: {"weighted_total": 0.0, "weighted_correct": 0.0, "n": 0}
        for difficulty in ("easy", "medium", "hard")
    }
    for difficulty, is_correct, completed_at in answer_rows:
        age_days = max((now - completed_at).total_seconds() / 86400, 0)
        answer_weight = 0.5 ** (age_days / ANSWER_HALF_LIFE_DAYS)
        band = totals.setdefault(
            difficulty,
            {"weighted_total": 0.0, "weighted_correct": 0.0, "n": 0},
        )
        band["weighted_total"] += answer_weight
        band["weighted_correct"] += answer_weight * int(is_correct)
        band["n"] += 1

    results = {}
    for difficulty, band in totals.items():
        accuracy = (
            band["weighted_correct"] / band["weighted_total"]
            if band["weighted_total"]
            else None
        )
        results[difficulty] = {
            "accuracy": accuracy,
            "accuracy_percent": round(accuracy * 100) if accuracy is not None else None,
            "n": band["n"],
            "enough_data": band["n"] >= MIN_EVIDENCE,
        }
    return results


def mock_time_analytics(user, subject):
    durations = list(
        QuizAttempt.objects.filter(
            user=user,
            quiz__subject=subject,
            quiz__is_mock=True,
            completed_at__isnull=False,
            time_taken_seconds__isnull=False,
        ).values_list("time_taken_seconds", flat=True)
    )
    total_seconds = sum(durations)
    return {
        "count": len(durations),
        "total_seconds": total_seconds,
        "average_seconds": round(total_seconds / len(durations)) if durations else None,
    }


def estimated_readiness(topics, topic_results, mock_attempt=None):
    total_exam_weight = sum(topic.exam_weight for topic in topics)
    known_topics = [
        topic for topic in topics
        if topic.exam_weight > 0
        and topic_results.get(topic.id, {}).get("enough_data", False)
    ]
    known_exam_weight = sum(topic.exam_weight for topic in known_topics)
    confidence_percent = round(
        known_exam_weight * 100 / total_exam_weight
    ) if total_exam_weight else 0

    if not known_exam_weight:
        return {
            "available": False,
            "confidence_percent": confidence_percent,
            "mock_attempt": mock_attempt,
        }

    topic_score = sum(
        topic.exam_weight * topic_results[topic.id]["accuracy"]
        for topic in known_topics
    ) / known_exam_weight
    score = topic_score
    if mock_attempt is not None:
        score = (
            TOPIC_READINESS_WEIGHT * topic_score
            + MOCK_READINESS_WEIGHT * mock_attempt.percentage / 100
        )
    score_percent = round(score * 100)
    if score_percent < 50:
        band = "Not ready"
    elif score_percent < 75:
        band = "Building"
    else:
        band = "Likely ready"
    return {
        "available": True,
        "score_percent": score_percent,
        "band": band,
        "confidence_percent": confidence_percent,
        "mock_attempt": mock_attempt,
    }