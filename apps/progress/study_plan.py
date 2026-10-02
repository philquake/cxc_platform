from datetime import date, timedelta
from math import ceil

from django.db import transaction
from django.utils import timezone

from apps.lessons.models import Lesson
from apps.questions.models import Question
from apps.quizzes.models import Quiz

from .analytics import topic_mastery
from .models import (
	FlashcardState,
	LessonProgress,
	MistakeReview,
	QuizAnswer,
	StudyPlan,
	StudyPlanItem,
)

MAX_LESSONS_PER_DAY = 3
QUIZ_INTERVAL = 4


def _lesson_topics(lessons, subject):
	lesson_ids = [lesson.id for lesson in lessons]
	topics_by_lesson = {}
	for lesson_id, topic_id in Question.objects.filter(
		lesson_id__in=lesson_ids,
		is_active=True,
		topic__is_active=True,
	).order_by("lesson_id", "id").values_list("lesson_id", "topic_id"):
		topics_by_lesson.setdefault(lesson_id, topic_id)

	for lesson_id, topic_id in Quiz.objects.filter(
		lesson_id__in=lesson_ids,
		is_active=True,
		lesson__is_active=True,
		topic__is_active=True,
	).order_by("lesson_id", "id").values_list("lesson_id", "topic_id"):
		topics_by_lesson.setdefault(lesson_id, topic_id)

	fallback_topic_id = subject.topics.filter(is_active=True).order_by("name").values_list(
		"id", flat=True
	).first()
	return {
		lesson.id: topics_by_lesson.get(lesson.id, fallback_topic_id)
		for lesson in lessons
	}


def _review_topic_ids(user, subject):
	mistake_topic_ids = set(
		MistakeReview.objects.filter(
			user=user,
			resolved=False,
			question__subject=subject,
			question__is_active=True,
		).values_list("question__topic_id", flat=True)
	)
	wrong_answer_topic_ids = set(
		QuizAnswer.objects.filter(
			attempt__user=user,
			attempt__completed_at__isnull=False,
			question__subject=subject,
			question__is_active=True,
			is_correct=False,
		).values_list("question__topic_id", flat=True)
	)
	return mistake_topic_ids | wrong_answer_topic_ids


def generate_plan(user, subject, target_date: date):
	"""Replace the user's active plan for a subject and return the new plan."""
	today = timezone.localdate()
	if target_date <= today:
		raise ValueError("Target date must be in the future.")

	lessons = list(
		Lesson.objects.filter(subject=subject, is_active=True).order_by(
			"lesson_number", "section_number", "id"
		)
	)
	completed_lesson_ids = set(
		LessonProgress.objects.filter(
			user=user,
			completed=True,
			lesson__subject=subject,
		).values_list("lesson_id", flat=True)
	)
	remaining_lessons = [
		lesson for lesson in lessons if lesson.id not in completed_lesson_ids
	]
	lesson_topic_ids = _lesson_topics(remaining_lessons, subject)
	mastery = topic_mastery(user, subject)
	topics = {
		topic.id: topic
		for topic in subject.topics.filter(is_active=True)
	}

	def lesson_priority(lesson):
		topic_id = lesson_topic_ids[lesson.id]
		topic = topics.get(topic_id)
		if topic is None:
			return 1.0
		result = mastery.get(topic_id)
		if not result or not result["enough_data"]:
			return float(topic.exam_weight)
		return topic.exam_weight * (1 - result["accuracy"])

	remaining_lessons.sort(
		key=lambda lesson: (
			-lesson_priority(lesson),
			lesson.lesson_number,
			lesson.id,
		)
	)

	days_available = (target_date - today).days
	lessons_per_day = min(
		MAX_LESSONS_PER_DAY,
		ceil(len(remaining_lessons) / days_available),
	) if remaining_lessons else 0
	wrong_topic_ids = _review_topic_ids(user, subject)
	quiz_topic_ids = set(
		Quiz.objects.filter(
			subject=subject,
			is_active=True,
			lesson__is_active=True,
		topic__is_active=True,
		).values_list("topic_id", flat=True)
	)

	rows = []
	lesson_index = 0
	day_offset = 0
	while lesson_index < len(remaining_lessons):
		scheduled_date = today + timedelta(days=day_offset)
		order = 0
		for _ in range(lessons_per_day):
			if lesson_index >= len(remaining_lessons):
				break
			lesson = remaining_lessons[lesson_index]
			topic_id = lesson_topic_ids[lesson.id]
			rows.append({
				"item_type": StudyPlanItem.LESSON,
				"lesson": lesson,
				"topic_id": topic_id,
				"scheduled_date": scheduled_date,
				"order": order,
			})
			order += 1
			if topic_id:
				rows.append({
					"item_type": StudyPlanItem.FLASHCARD_REVIEW,
					"topic_id": topic_id,
					"scheduled_date": scheduled_date,
					"order": order,
				})
				order += 1
				if topic_id in wrong_topic_ids:
					rows.append({
						"item_type": StudyPlanItem.MISTAKE_REVIEW,
						"topic_id": topic_id,
						"scheduled_date": scheduled_date,
						"order": order,
					})
					order += 1
			lesson_index += 1
			if lesson_index % QUIZ_INTERVAL == 0 and topic_id in quiz_topic_ids:
				rows.append({
					"item_type": StudyPlanItem.QUIZ,
					"topic_id": topic_id,
					"scheduled_date": scheduled_date,
					"order": order,
				})
				order += 1
		day_offset += 1

	with transaction.atomic():
		StudyPlan.objects.filter(
			user=user,
			subject=subject,
			is_active=True,
		).update(is_active=False)
		plan = StudyPlan.objects.create(
			user=user,
			subject=subject,
			target_date=target_date,
		)
		StudyPlanItem.objects.bulk_create([
			StudyPlanItem(plan=plan, **row)
			for row in rows
		])
	return plan


def due_flashcard_count(user, topic, scheduled_date):
	return FlashcardState.objects.filter(
		user=user,
		question__topic=topic,
		question__is_active=True,
		due_at__lte=scheduled_date,
	).count()