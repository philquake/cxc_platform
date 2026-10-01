from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import OuterRef, Subquery, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.lessons.models import Lesson
from apps.questions.models import Question
from apps.quizzes.models import Quiz
from apps.subjects.models import Subject, Topic

from .analytics import estimated_readiness, topic_mastery
from .models import (
    FlashcardState,
    LessonProgress,
    QuizAnswer,
    QuizAttempt,
    UserProgress,
    XPTransaction,
)


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
		topic_results = topic_mastery(request.user, subject)
		active_topics = [topic for topic in subject.topics.all() if topic.is_active]
		for topic in active_topics:
			result = topic_results.get(topic.id)
			topic.mastery = result
			topic.mastery_percentage = result["accuracy_percent"] if result else None
			topic.mastery_count = result["n"] if result else 0
			topic.mastery_available = bool(result and result["enough_data"])
		lesson_by_id = {lesson.id: lesson for lesson in lessons}
		for topic_id, lesson_id in Question.objects.filter(
			subject=subject,
			topic_id__in=topic_results,
			is_active=True,
			lesson__is_active=True,
		).order_by("lesson__lesson_number", "lesson_id").values_list(
			"topic_id", "lesson_id"
		):
			topic = next((item for item in active_topics if item.id == topic_id), None)
			if topic and not hasattr(topic, "mastery_lesson"):
				topic.mastery_lesson = lesson_by_id.get(lesson_id)
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
		subject.active_topics = active_topics
		latest_mock = QuizAttempt.objects.filter(
			user=request.user,
			quiz__subject=subject,
			quiz__title__icontains="mock",
			quiz__is_active=True,
			quiz__lesson__is_active=True,
			completed_at__isnull=False,
			total_questions__gt=0,
		).select_related("quiz").order_by("-completed_at", "-started_at").first()
		subject.readiness = estimated_readiness(
			active_topics,
			topic_results,
			latest_mock,
		)
		subject.weakest_topics = sorted(
			(topic for topic in active_topics if topic.mastery_available),
			key=lambda topic: topic.mastery["accuracy"],
		)[:3]

	latest_attempt_for_quiz = QuizAttempt.objects.filter(
		user=OuterRef("user"),
		quiz=OuterRef("quiz"),
		completed_at__isnull=False,
	).order_by("-completed_at", "-started_at", "-pk")
	score_trend = list(
		QuizAttempt.objects.filter(
			user=request.user,
			completed_at__isnull=False,
			quiz__is_active=True,
			quiz__lesson__is_active=True,
			pk=Subquery(latest_attempt_for_quiz.values("pk")[:1]),
		).select_related("quiz").order_by("-completed_at", "-started_at")
	)

	return render(
		request,
		"progress/dashboard.html",
		{
			"subjects": subjects,
			"user_progress": user_progress,
			"score_trend": score_trend,
		},
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


def _ensure_flashcard_state(user, question, *, due_days=0):
	state, _ = FlashcardState.objects.get_or_create(
		user=user,
		question=question,
	)
	state.due_at = timezone.localdate() + timedelta(days=due_days)
	state.last_reviewed_at = timezone.now()
	state.save(update_fields=["due_at", "last_reviewed_at"])
	return state


def _normalize_answer_text(value):
	return " ".join((value or "").strip().lower().split())


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
	selected_text_answers = {}
	matching_answers = {}
	for quiz_question in quiz_questions:
		question = quiz_question.question
		if question.format == Question.FORMAT_MATCHING:
			matching_answers[question.id] = {
				str(answer.id): request.POST.get(
					f"question-{question.id}-{answer.id}", ""
				).strip()
				for answer in question.answers.all()
			}
			continue
		value = request.POST.get(f"question-{question.id}")
		if value is None:
			continue
		if question.is_open_ended:
			selected_text_answers[question.id] = value.strip()
		elif value.isdigit():
			selected_answers[question.id] = int(value)

	attempt = QuizAttempt.objects.create(
		user=request.user,
		quiz=quiz,
		total_questions=len(quiz_questions),
		completed_at=timezone.now(),
	)
	score = 0
	for quiz_question in quiz_questions:
		question = quiz_question.question
		selected_answer = None
		selected_text = ""
		if question.format == Question.FORMAT_MATCHING:
			selected_pairs = matching_answers.get(question.id, {})
			answer_rows = list(question.answers.all())
			selected_text = "; ".join(
				f"{answer.text}: {selected_pairs.get(str(answer.id), '')}"
				for answer in answer_rows
			)
			correct_pairs = {
				str(answer.id): _normalize_answer_text(answer.match_text)
				for answer in answer_rows
			}
			is_correct = bool(correct_pairs) and all(
				correct_value
				and _normalize_answer_text(selected_pairs.get(answer_id, "")) == correct_value
				for answer_id, correct_value in correct_pairs.items()
			)
		elif question.format in {Question.FORMAT_SHORT_ANSWER, Question.FORMAT_WORDED}:
			selected_text = selected_text_answers.get(question.id, "")
			is_correct = (
				_normalize_answer_text(selected_text)
				== _normalize_answer_text(question.expected_answer)
			)
		elif question.format == Question.FORMAT_TRUE_FALSE and not question.answers.exists():
			selected_text = request.POST.get(f"question-{question.id}", "").strip()
			is_correct = (
				_normalize_answer_text(selected_text)
				== _normalize_answer_text(question.expected_answer)
			)
		else:
			selected_id = selected_answers.get(question.id)
			selected_answer = next(
				(
					answer
					for answer in question.answers.all()
					if answer.id == selected_id
				),
				None,
			)
			is_correct = bool(selected_answer and selected_answer.is_correct)
		if is_correct:
			score += 1
		else:
			_ensure_flashcard_state(request.user, question)
		QuizAnswer.objects.create(
			attempt=attempt,
			question=question,
			selected_answer=selected_answer,
			selected_text=selected_text,
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
		XPTransaction.objects.filter(
			topic=topic,
			user__is_staff=False,
			user__is_superuser=False,
		)
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

@login_required
def subject_leaderboard(request, subject_slug):
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

	all_rows = list(
		XPTransaction.objects.filter(
			topic__subject=subject,
			user__is_staff=False,
			user__is_superuser=False,
		)
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
			"topic": None,
			"leaderboard": all_rows[:20],
			"current_user_row": current_user_row,
		},
	)

@login_required
def mistake_bank(request):
    wrong_answers = (
        QuizAnswer.objects.filter(
            attempt__user=request.user,
            is_correct=False,
        )
        .select_related("question", "question__subject", "question__topic", "selected_answer")
        .prefetch_related("question__answers")
        .order_by("-attempt__completed_at")
    )

    # collapse to one entry per question (latest miss), so repeats don't spam the list
    seen = {}
    for wa in wrong_answers:
        seen.setdefault(wa.question_id, wa)

    grouped = {}
    for mistake in seen.values():
        subject = mistake.question.subject
        topic = mistake.question.topic
        subject_group = grouped.setdefault(
            subject.id,
            {"subject": subject, "topics": {}},
        )
        topic_group = subject_group["topics"].setdefault(
            topic.id,
            {"topic": topic, "mistakes": []},
        )
        topic_group["mistakes"].append(mistake)

    mistake_groups = [
        {
            "subject": subject_group["subject"],
            "topics": list(subject_group["topics"].values()),
        }
        for subject_group in grouped.values()
    ]

    return render(request, "progress/mistake_bank.html", {
        "mistake_groups": mistake_groups,
    })
    
@login_required
def flashcard_session(request, subject_slug, topic_slug=None):
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

    topic = None
    if topic_slug:
        topic = get_object_or_404(Topic, subject=subject, slug=topic_slug, is_active=True)

    states = FlashcardState.objects.filter(
        user=request.user,
        question__subject=subject,
        question__is_active=True,
        due_at__lte=timezone.localdate(),
    )
    if topic is not None:
        states = states.filter(question__topic=topic)

    cards = list(
        states.select_related("question", "question__subject", "question__topic")
        .prefetch_related("question__answers")
        .order_by("due_at", "question_id")
    )
    return render(
        request,
        "progress/flashcards.html",
        {
            "subject": subject,
            "topic": topic,
            "cards": cards,
            "due_count": len(cards),
        },
    )


@login_required
@require_POST
def review_flashcard(request):
    question_id = request.POST.get("question_id")
    rating = (request.POST.get("rating") or "").lower()
    if question_id is None or rating == "":
        return JsonResponse({"ok": False, "error": "Missing data"}, status=400)

    question = get_object_or_404(Question, pk=question_id, is_active=True)
    due_days = {"again": 0, "hard": 1, "good": 3, "easy": 5}.get(rating, 0)
    _ensure_flashcard_state(request.user, question, due_days=due_days)
    return JsonResponse({"ok": True, "due_days": due_days})