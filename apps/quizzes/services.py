import random

from apps.questions.models import Question
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

    sampled_questions = []
    topic_counts = {}
    for topic in weighted_topics:
        target_count = round(question_count * topic.exam_weight / total_weight)
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
