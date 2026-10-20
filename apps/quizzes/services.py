import random

from django.db import transaction

from apps.questions.models import PATHWAY_CHOICES, Question
from apps.subjects.models import Topic

from .models import Quiz, QuizQuestion


def generate_mock_exam(subject, question_count, time_limit_minutes, topics=None):
    if question_count <= 0:
        raise ValueError("Question count must be greater than zero.")
    if time_limit_minutes is not None and time_limit_minutes <= 0:
        raise ValueError("Time limit must be greater than zero.")

    selected_topics = Topic.objects.filter(subject=subject, is_active=True)
    if topics is not None:
        selected_topic_ids = [topic.pk for topic in topics]
        selected_topics = selected_topics.filter(pk__in=selected_topic_ids)

    weighted_topics = [topic for topic in selected_topics if topic.exam_weight > 0]
    total_weight = sum(topic.exam_weight for topic in weighted_topics)
    if not total_weight:
        raise ValueError("The subject has no active topics with a positive exam weight.")

    # Largest-remainder allocation so the targets sum to question_count; ties go to the lower pk.
    shares = {t.pk: question_count * t.exam_weight / total_weight for t in weighted_topics}
    targets = {pk: int(share) for pk, share in shares.items()}
    by_remainder = sorted(shares, key=lambda pk: (targets[pk] - shares[pk], pk))
    for pk in by_remainder[: question_count - sum(targets.values())]:
        targets[pk] += 1

    sampled_questions = []
    topic_counts = {}
    for topic in weighted_topics:
        target_count = targets[topic.pk]
        questions = list(
            Question.objects.filter(
                subject=subject,
                topic=topic,
                is_active=True,
            ).order_by("?")[:target_count]
        )
        sampled_questions.extend(questions)
        topic_counts[topic.pk] = len(questions)

    if not sampled_questions:
        raise ValueError("No active questions are available for the selected topics.")

    random.shuffle(sampled_questions)
    with transaction.atomic():
        quiz = Quiz.objects.create(
            subject=subject,
            title=f"{subject.code} Mock Exam",
            description="Timed, subject-wide exam practice.",
            is_mock=True,
            time_limit_minutes=time_limit_minutes,
        )
        QuizQuestion.objects.bulk_create([
            QuizQuestion(quiz=quiz, question=question, order=order)
            for order, question in enumerate(sampled_questions)
        ])
    return quiz, topic_counts


FORMATS_BY_DIFFICULTY = {
    "easy": {Question.FORMAT_MULTIPLE_CHOICE},
    "medium": {Question.FORMAT_TRUE_FALSE, Question.FORMAT_MULTIPLE_CHOICE, Question.FORMAT_SHORT_ANSWER},
    "hard": {Question.FORMAT_WORDED},
}
DEFAULT_COUNTS = {"easy": 10, "medium": 10, "hard": 5}


def generate_lesson_quizzes(topic, lesson, counts, pathway="", allow_partial=False):
    """Create one inactive practice quiz per requested difficulty from the lesson's question bank.

    counts maps difficulty to question count. Raises ValueError on any shortage unless allow_partial.
    Quizzes start inactive so a teacher can preview them before switching them on.
    """
    if lesson.subject_id != topic.subject_id:
        raise ValueError("The lesson and topic belong to different subjects.")
    counts = {difficulty: count for difficulty, count in counts.items() if count}
    if not counts:
        raise ValueError("Ask for at least one question.")
    if any(difficulty not in FORMATS_BY_DIFFICULTY or count < 0 for difficulty, count in counts.items()):
        raise ValueError("Counts must be positive and keyed by easy, medium or hard.")
    if pathway and pathway not in dict(PATHWAY_CHOICES):
        raise ValueError(f"Unknown pathway '{pathway}'.")

    picked, shortages = {}, []
    for difficulty in FORMATS_BY_DIFFICULTY:
        if difficulty not in counts:
            continue
        questions = Question.objects.filter(
            topic=topic,
            lesson=lesson,
            is_active=True,
            difficulty=difficulty,
            format__in=FORMATS_BY_DIFFICULTY[difficulty],
        )
        if pathway:
            questions = questions.filter(**{f"for_{pathway}": True})
        picked[difficulty] = list(questions.order_by("?")[: counts[difficulty]])
        if len(picked[difficulty]) < counts[difficulty]:
            shortages.append(f"{difficulty.title()}: {len(picked[difficulty])} of {counts[difficulty]} eligible")
    if shortages and not allow_partial:
        raise ValueError("Not enough questions. " + "; ".join(shortages) + ".")
    picked = {difficulty: questions for difficulty, questions in picked.items() if questions}
    if not picked:
        raise ValueError("No eligible questions for this topic and lesson.")

    quizzes = []
    with transaction.atomic():
        for difficulty, questions in picked.items():
            quiz = Quiz.objects.create(
                subject=lesson.subject,
                topic=topic,
                lesson=lesson,
                title=f"{lesson.title}: {difficulty.title()}",
                difficulty=difficulty,
                pathway=pathway,
                is_active=False,
            )
            QuizQuestion.objects.bulk_create([
                QuizQuestion(quiz=quiz, question=question, order=order)
                for order, question in enumerate(questions)
            ])
            quizzes.append(quiz)
    return quizzes, shortages
