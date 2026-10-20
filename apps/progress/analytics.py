# apps/progress/analytics.py
from collections import defaultdict

from django.utils import timezone

from .models import QuizAnswer, QuizAttempt, TopicMasteryStat

MIN_EVIDENCE = 5
ANSWER_HALF_LIFE_DAYS = 14
TOPIC_READINESS_WEIGHT = 0.7
MOCK_READINESS_WEIGHT = 0.3


def _decay(start, end):
    """Weight multiplier for evidence that is (end - start) older than it was."""
    return 0.5 ** (max((end - start).total_seconds() / 86400, 0) / ANSWER_HALF_LIFE_DAYS)


def record_attempt(attempt):
    """Fold a completed attempt's answers into the user's mastery totals (call once per attempt)."""
    fresh = defaultdict(lambda: [0, 0])
    for topic_id, difficulty, is_correct in QuizAnswer.objects.filter(attempt=attempt).values_list(
        "question__topic_id", "question__difficulty", "is_correct"
    ):
        fresh[topic_id, difficulty][0] += 1
        fresh[topic_id, difficulty][1] += int(is_correct)
    stats = {
        (stat.topic_id, stat.difficulty): stat
        for stat in TopicMasteryStat.objects.select_for_update().filter(
            user_id=attempt.user_id, topic_id__in={topic_id for topic_id, _ in fresh}
        )
    }
    for (topic_id, difficulty), (answered, correct) in fresh.items():
        stat = stats.get((topic_id, difficulty)) or TopicMasteryStat(
            user_id=attempt.user_id, topic_id=topic_id, difficulty=difficulty, updated_at=attempt.completed_at
        )
        # Bring old totals and the new answers to the later of the two moments, then add.
        at = max(stat.updated_at, attempt.completed_at)
        old, new = _decay(stat.updated_at, at), _decay(attempt.completed_at, at)
        stat.weighted_total = stat.weighted_total * old + answered * new
        stat.weighted_correct = stat.weighted_correct * old + correct * new
        stat.n += answered
        stat.updated_at = at
        stat.save()


def mastery_rows(user, subject):
    """One query for a subject's mastery totals; pass to topic_mastery/difficulty_breakdown to share it."""
    return list(TopicMasteryStat.objects.filter(user=user, topic__subject=subject).values_list(
        "topic_id", "topic__name", "difficulty", "weighted_total", "weighted_correct", "n", "updated_at"
    ))


def topic_mastery(user, subject, rows=None):
    now = timezone.now()
    totals = {}
    for topic_id, topic_name, _, weighted_total, weighted_correct, n, updated_at in (
        mastery_rows(user, subject) if rows is None else rows
    ):
        factor = _decay(updated_at, now)
        topic = totals.setdefault(topic_id, {
            "name": topic_name,
            "weighted_total": 0.0,
            "weighted_correct": 0.0,
            "n": 0,
        })
        topic["weighted_total"] += weighted_total * factor
        topic["weighted_correct"] += weighted_correct * factor
        topic["n"] += n

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


def difficulty_breakdown(user, subject, rows=None):
    now = timezone.now()
    totals = {
        difficulty: {"weighted_total": 0.0, "weighted_correct": 0.0, "n": 0}
        for difficulty in ("easy", "medium", "hard")
    }
    for _, _, difficulty, weighted_total, weighted_correct, n, updated_at in (
        mastery_rows(user, subject) if rows is None else rows
    ):
        factor = _decay(updated_at, now)
        band = totals.setdefault(
            difficulty,
            {"weighted_total": 0.0, "weighted_correct": 0.0, "n": 0},
        )
        band["weighted_total"] += weighted_total * factor
        band["weighted_correct"] += weighted_correct * factor
        band["n"] += n

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