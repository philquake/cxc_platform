from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.lessons.models import Lesson
from apps.quizzes.models import Quiz
from apps.subjects.models import Subject

from .models import LessonProgress, QuizAnswer, QuizAttempt


@login_required
def dashboard(request):
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
		Subject.objects.filter(is_active=True).prefetch_related("lessons")
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

	return render(request, "progress/dashboard.html", {"subjects": subjects})


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
	LessonProgress.objects.update_or_create(
		user=request.user,
		lesson=lesson,
		defaults={"completed": True, "completed_at": timezone.now()},
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

	destination = _safe_next_url(request, reverse("quizzes:list"))
	separator = "&" if "?" in destination else "?"
	return redirect(f"{destination}{separator}attempt={attempt.id}")

# Create your views here.
