from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.lessons.models import Lesson
from apps.quizzes.models import Quiz
from apps.subjects.models import Subject, Topic

from .models import LessonProgress, QuizAnswer, QuizAttempt, UserProgress, XPTransaction


def _award_xp(user, topic, amount, reason, lesson_progress=None, quiz_attempt=None):
	with transaction.atomic():
		xp_transaction = XPTransaction.objects.create(
			user=user,
			topic=topic,
			amount=amount,
			reason=reason,
			lesson_progress=lesson_progress,
			quiz_attempt=quiz_attempt,
		)
		progress, _ = UserProgress.objects.select_for_update().get_or_create(user=user)
		today = timezone.localdate()
		if progress.last_activity_date == today:
			pass
		elif progress.last_activity_date == today - timedelta(days=1):
			progress.current_streak += 1
		else:
			progress.current_streak = 1
		progress.total_xp += amount
		progress.longest_streak = max(progress.longest_streak, progress.current_streak)
		progress.last_activity_date = today
		progress.save()
	return xp_transaction


def _topic_for_lesson(lesson):
	question = lesson.questions.filter(topic__is_active=True).select_related("topic").first()
	if question:
		return question.topic
	quiz = lesson.quizzes.filter(is_active=True).select_related("topic").first()
	if quiz:
		return quiz.topic
	topic = Topic.objects.filter(
		subject=lesson.subject,
		is_active=True,
	).order_by("name").first()
	if topic:
		return topic
	topic, _ = Topic.objects.get_or_create(
		subject=lesson.subject,
		slug="general",
		defaults={"name": "General"},
	)
	return topic


@login_required
def dashboard(request):
	user_progress, _ = UserProgress.objects.get_or_create(user=request.user)
	lesson_progress_ids = set(
		LessonProgress.objects.filter(
			user=request.user,
			completed=True,
		).values_list("lesson_id", flat=True)
	)
	latest_attempts = {}
	for attempt in QuizAttempt.objects.filter(
		user=request.user,
		completed_at__isnull=False,
		quiz__is_active=True,
		quiz__lesson__is_active=True,
	).select_related("quiz", "quiz__lesson"):
		latest_attempts.setdefault(attempt.quiz_id, attempt)

	subjects = list(
		Subject.objects.filter(is_active=True).prefetch_related("lessons", "topics")
	)
	for subject in subjects:
		lessons = [lesson for lesson in subject.lessons.all() if lesson.is_active]
		completed_count = 0
		for lesson in lessons:
			lesson.is_completed = lesson.id in lesson_progress_ids
			lesson.latest_quiz_attempt = next(
				(
					attempt
					for attempt in latest_attempts.values()
					if attempt.quiz.lesson_id == lesson.id
				),
				None,
			)
			if lesson.is_completed:
				completed_count += 1
			subject.progress_lessons = lessons
		subject.lesson_count = len(lessons)
		subject.completed_count = completed_count
		subject.progress_percentage = round(
			(completed_count / len(lessons)) * 100
		) if lessons else 0
		subject.active_topics = [topic for topic in subject.topics.all() if topic.is_active]

	return render(
		request,
		"progress/dashboard.html",
		{"subjects": subjects, "user_progress": user_progress},
	)


def _safe_next_url(request, fallback):
	redirect_to = request.POST.get("next", "")
	if redirect_to and url_has_allowed_host_and_scheme(
		redirect_to,
		allowed_hosts={request.get_host()},
		require_https=request.is_secure(),
	):
		return redirect_to
	return fallback


@login_required
@require_POST
def complete_lesson(request, lesson_id):
	lesson = get_object_or_404(Lesson, pk=lesson_id, is_active=True)
	lesson_progress, _ = LessonProgress.objects.get_or_create(
		user=request.user,
		lesson=lesson,
		defaults={"completed": True, "completed_at": timezone.now()},
	)
	if not hasattr(lesson_progress, "xp_transaction"):
		_award_xp(
			request.user,
			_topic_for_lesson(lesson),
			50,
			"Completed lesson",
			lesson_progress=lesson_progress,
		)
	fallback = reverse(
		"subjects:lesson-detail",
		kwargs={
			"subject_slug": slugify(lesson.subject.name),
			"lesson_slug": lesson.slug,
		},
	)
	return redirect(_safe_next_url(request, fallback))


@login_required
@require_POST
def submit_quiz(request, quiz_id):
	quiz = get_object_or_404(
		Quiz.objects.prefetch_related("quiz_questions__question__answers"),
		pk=quiz_id,
		is_active=True,
		lesson__is_active=True,
	)
	quiz_questions = list(quiz.quiz_questions.all())
	selected_answers = {}
	for quiz_question in quiz_questions:
		value = request.POST.get(f"question-{quiz_question.question_id}")
		if value and value.isdigit():
			selected_answers[quiz_question.question_id] = int(value)

	attempt = QuizAttempt.objects.create(
		user=request.user,
		quiz=quiz,
		total_questions=len(quiz_questions),
		completed_at=timezone.now(),
	)
	score = 0
	for quiz_question in quiz_questions:
		selected_id = selected_answers.get(quiz_question.question_id)
		selected_answer = next(
			(
				answer
				for answer in quiz_question.question.answers.all()
				if answer.id == selected_id
			),
			None,
		)
		is_correct = bool(selected_answer and selected_answer.is_correct)
		if is_correct:
			score += 1
		QuizAnswer.objects.create(
			attempt=attempt,
			question=quiz_question.question,
			selected_answer=selected_answer,
			is_correct=is_correct,
		)
	attempt.score = score
	attempt.save(update_fields=["score"])
	_award_xp(
		request.user,
		quiz.topic,
		25 + attempt.percentage // 5,
		f"Completed quiz: {attempt.percentage}%",
		quiz_attempt=attempt,
	)

	destination = _safe_next_url(request, reverse("quizzes:list"))
	separator = "&" if "?" in destination else "?"
	return redirect(f"{destination}{separator}attempt={attempt.id}")


@login_required
def leaderboard(request, subject_slug, topic_slug):
	subject = next(
		(
			item
			for item in Subject.objects.filter(is_active=True)
			if subject_slug in {slugify(item.name), slugify(item.code)}
		),
		None,
	)
	if subject is None:
		raise Http404("Subject not found")
	topic = get_object_or_404(Topic, subject=subject, slug=topic_slug, is_active=True)
	all_rows = list(
		XPTransaction.objects.filter(topic=topic)
		.values("user_id", "user__username")
		.annotate(xp=Sum("amount"))
		.order_by("-xp", "user_id")
	)
	for index, row in enumerate(all_rows, start=1):
		row["rank"] = index
	current_user_row = next((row for row in all_rows if row["user_id"] == request.user.id), None)
	return render(
		request,
		"progress/leaderboard.html",
		{
			"subject": subject,
			"topic": topic,
			"leaderboard": all_rows[:20],
			"current_user_row": current_user_row,
		},
	)

# Create your views here.
