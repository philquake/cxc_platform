from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.lessons.models import Lesson
from apps.quizzes.models import Quiz

from .models import LessonProgress, QuizAnswer, QuizAttempt


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

	return redirect(
		_safe_next_url(request, reverse("quizzes:list"))
	)

# Create your views here.
