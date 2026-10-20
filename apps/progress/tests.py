import time

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core import signing
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Profile
from apps.lessons.models import Lesson
from apps.questions.models import Answer, Question
from apps.quizzes.models import Quiz, QuizQuestion
from apps.subjects.models import Subject, Topic

from apps.progress.models import (
	FlashcardState,
	LessonProgress,
	QuizAnswer,
	QuizAttempt,
	StudyPlan,
	StudyPlanItem,
	TopicMasteryStat,
	UserProgress,
	XPTransaction,
)
from apps.progress.analytics import difficulty_breakdown, estimated_readiness, record_attempt, topic_mastery

class ProgressFlowTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username="student",
			password="A-strong-password-123",
		)
		subject = Subject.objects.create(name="Mathematics", code="MATH")
		topic = Topic.objects.create(subject=subject, name="Algebra", slug="algebra")
		self.lesson = Lesson.objects.create(
			subject=subject,
			title="Algebra",
			slug="algebra",
			content="<p>Algebra</p>",
		)
		question = Question.objects.create(
			subject=subject,
			topic=topic,
			lesson=self.lesson,
			text="What is 2 + 2?",
		)
		correct_answer = Answer.objects.create(
			question=question,
			text="4",
			is_correct=True,
		)
		Answer.objects.create(question=question, text="5")
		self.quiz = Quiz.objects.create(
			subject=subject,
			topic=topic,
			lesson=self.lesson,
			title="Algebra quiz",
		)
		QuizQuestion.objects.create(quiz=self.quiz, question=question)
		self.correct_answer = correct_answer

	def test_progress_dashboard_requires_login(self):
		response = self.client.get(reverse("progress:dashboard"))

		self.assertRedirects(
			response,
			f"/accounts/login/?next={reverse('progress:dashboard')}",
		)

	def test_progress_dashboard_shows_lesson_state_for_user(self):
		LessonProgress.objects.create(
			user=self.user,
			lesson=self.lesson,
			completed=True,
			completed_at=timezone.now(),
		)
		self.client.force_login(self.user)

		response = self.client.get(reverse("progress:dashboard"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "100%")
		self.assertContains(response, "Completed")

	def test_topic_mastery_uses_recency_weighted_answers(self):
		question = self.correct_answer.question
		first_attempt = QuizAttempt.objects.create(
			user=self.user,
			quiz=self.quiz,
			total_questions=1, total_marks=1,
			completed_at=timezone.now() - timezone.timedelta(days=1),
		)
		QuizAnswer.objects.create(
			attempt=first_attempt,
			question=question,
			selected_answer=self.correct_answer,
			is_correct=True,
		)
		record_attempt(first_attempt)
		latest_attempt = QuizAttempt.objects.create(
			user=self.user,
			quiz=self.quiz,
			total_questions=1, total_marks=1,
			completed_at=timezone.now(),
		)
		QuizAnswer.objects.create(
			attempt=latest_attempt,
			question=question,
			is_correct=False,
		)
		record_attempt(latest_attempt)

		mastery = topic_mastery(self.user, question.subject)

		self.assertEqual(mastery[question.topic_id]["n"], 2)
		self.assertGreater(mastery[question.topic_id]["accuracy"], 0)
		self.assertLess(mastery[question.topic_id]["accuracy"], 0.5)

	def test_incremental_totals_match_recomputing_from_every_answer(self):
		from datetime import timedelta

		question = self.correct_answer.question
		now = timezone.now()
		# Recorded out of date order on purpose: 20 days ago, today, 5 days ago.
		history = [(20, True), (0, False), (5, True), (5, False)]
		for days_ago, is_correct in history:
			attempt = QuizAttempt.objects.create(
				user=self.user, quiz=self.quiz, total_questions=1, total_marks=1, completed_at=now - timedelta(days=days_ago)
			)
			QuizAnswer.objects.create(attempt=attempt, question=question, is_correct=is_correct)
			record_attempt(attempt)

		weights = [0.5 ** (days_ago / 14) for days_ago, _ in history]
		expected = sum(w for w, (_, ok) in zip(weights, history) if ok) / sum(weights)
		result = topic_mastery(self.user, question.subject)[question.topic_id]

		self.assertAlmostEqual(result["accuracy"], expected, places=6)
		self.assertEqual(result["n"], 4)

	def test_difficulty_breakdown_groups_answers_by_question_difficulty(self):
		question = self.correct_answer.question
		question.difficulty = "hard"
		question.save(update_fields=["difficulty"])
		attempt = QuizAttempt.objects.create(
			user=self.user,
			quiz=self.quiz,
			total_questions=1, total_marks=1,
			completed_at=timezone.now(),
		)
		QuizAnswer.objects.create(
			attempt=attempt,
			question=question,
			is_correct=True,
		)
		record_attempt(attempt)

		breakdown = difficulty_breakdown(self.user, question.subject)

		self.assertEqual(breakdown["hard"]["accuracy_percent"], 100)
		self.assertEqual(breakdown["hard"]["n"], 1)
		self.assertIsNone(breakdown["easy"]["accuracy_percent"])

	def test_dashboard_uses_explicit_mock_mode_for_readiness_and_trend(self):
		mock = Quiz.objects.create(
			subject=self.quiz.subject,
			title="Practice paper",
			is_mock=True,
		)
		attempt = QuizAttempt.objects.create(
			user=self.user,
			quiz=mock,
			score=1,
			total_questions=1, total_marks=1,
			time_taken_seconds=120,
			completed_at=timezone.now(),
		)
		self.client.force_login(self.user)

		response = self.client.get(reverse("progress:dashboard"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["score_trend"], [attempt])
		self.assertEqual(response.context["subjects"][0].readiness["mock_attempt"], attempt)
		self.assertContains(response, "Mock")
		self.assertContains(response, "Average mock time")

	def test_mock_submission_records_duration_and_wrong_answers(self):
		question = Question.objects.create(
			subject=self.quiz.subject,
			topic=self.quiz.topic,
			lesson=self.lesson,
			text="Mock question",
		)
		correct = Answer.objects.create(question=question, text="yes", is_correct=True)
		mock = Quiz.objects.create(
			subject=self.quiz.subject,
			title="Subject paper",
			is_mock=True,
			time_limit_minutes=30,
		)
		QuizQuestion.objects.create(quiz=mock, question=question)
		self.client.force_login(self.user)

		response = self.client.post(
			reverse("progress:submit-quiz", args=[mock.id]),
			{
				f"question-{question.id}": "",
				"time_taken_seconds": "1",  # ignored: the server times the exam itself
				"mock_started": signing.dumps([mock.id, self.user.id, int(time.time()) - 75]),
			},
		)

		self.assertEqual(response.status_code, 302)
		attempt = QuizAttempt.objects.get(user=self.user, quiz=mock)
		self.assertIn(attempt.time_taken_seconds, range(75, 80))
		self.assertFalse(attempt.answers.get().is_correct)
		self.assertTrue(FlashcardState.objects.filter(user=self.user, question=question).exists())

	def test_readiness_excludes_topics_without_enough_answers_and_blends_mock(self):
		topic = self.correct_answer.question.topic
		topic.exam_weight = 3
		unknown_topic = Topic.objects.create(
			subject=topic.subject,
			name="Geometry",
			slug="geometry",
			exam_weight=1,
		)
		mock = Quiz.objects.create(
			subject=topic.subject,
			topic=topic,
			lesson=self.lesson,
			title="Mathematics mock paper",
		)
		mock_attempt = QuizAttempt.objects.create(
			user=self.user,
			quiz=mock,
			score=1,
			total_questions=2, total_marks=2,
			completed_at=timezone.now(),
		)
		results = {
			topic.id: {"accuracy": 0.8, "enough_data": True},
			unknown_topic.id: {"accuracy": 0, "enough_data": False},
		}

		readiness = estimated_readiness(
			[topic, unknown_topic],
			results,
			mock_attempt,
		)

		self.assertEqual(readiness["score_percent"], 71)
		self.assertEqual(readiness["confidence_percent"], 75)
		self.assertEqual(readiness["band"], "Building")

	def test_readiness_is_unknown_without_any_topic_with_enough_answers(self):
		topic = self.correct_answer.question.topic

		readiness = estimated_readiness(
			[topic],
			{topic.id: {"accuracy": 1, "enough_data": False}},
		)

		self.assertFalse(readiness["available"])
		self.assertEqual(readiness["confidence_percent"], 0)

	def test_dashboard_shows_topic_mastery_and_score_trend(self):
		attempt = QuizAttempt.objects.create(
			user=self.user,
			quiz=self.quiz,
			score=1,
			total_questions=1, total_marks=1,
			completed_at=timezone.now(),
		)
		QuizAnswer.objects.create(
			attempt=attempt,
			question=self.correct_answer.question,
			selected_answer=self.correct_answer,
			is_correct=True,
		)
		record_attempt(attempt)
		self.client.force_login(self.user)

		response = self.client.get(reverse("progress:dashboard"))

		self.assertContains(response, "Topic mastery")
		self.assertContains(response, "Estimated readiness")
		self.assertContains(response, "Unknown, 1/5 answers")
		self.assertContains(response, "Quiz and mock score trend")
		self.assertContains(response, "Algebra quiz")
		self.assertContains(
			response,
			reverse("subjects:lesson-detail", args=["mathematics", "algebra"]),
		)
		self.assertContains(response, reverse("progress:mistake-bank"))

	def test_dashboard_shows_only_latest_completed_attempt_per_quiz(self):
		now = timezone.now()
		older_attempt = QuizAttempt.objects.create(
			user=self.user,
			quiz=self.quiz,
			score=0,
			total_questions=1, total_marks=1,
			completed_at=now - timezone.timedelta(days=1),
		)
		latest_attempt = QuizAttempt.objects.create(
			user=self.user,
			quiz=self.quiz,
			score=1,
			total_questions=1, total_marks=1,
			completed_at=now,
		)
		other_quiz = Quiz.objects.create(
			subject=self.quiz.subject,
			topic=self.quiz.topic,
			lesson=self.lesson,
			title="Algebra revision quiz",
		)
		other_attempt = QuizAttempt.objects.create(
			user=self.user,
			quiz=other_quiz,
			score=1,
			total_questions=1, total_marks=1,
			completed_at=now - timezone.timedelta(hours=1),
		)
		self.client.force_login(self.user)

		response = self.client.get(reverse("progress:dashboard"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			{attempt.pk for attempt in response.context["score_trend"]},
			{latest_attempt.pk, other_attempt.pk},
		)
		self.assertTrue(QuizAttempt.objects.filter(pk=older_attempt.pk).exists())
		self.assertEqual(QuizAttempt.objects.filter(user=self.user).count(), 3)

	def test_mistake_bank_groups_questions_by_subject_and_topic(self):
		math_question = self.correct_answer.question
		geometry = Topic.objects.create(
			subject=math_question.subject,
			name="Geometry",
			slug="geometry",
		)
		geometry_question = Question.objects.create(
			subject=math_question.subject,
			topic=geometry,
			lesson=self.lesson,
			text="What is the area of a square?",
		)
		geometry_wrong_answer = Answer.objects.create(
			question=geometry_question,
			text="Side times two",
		)
		QuizQuestion.objects.create(quiz=self.quiz, question=geometry_question)
		math_attempt = QuizAttempt.objects.create(
			user=self.user,
			quiz=self.quiz,
			total_questions=2, total_marks=2,
			completed_at=timezone.now(),
		)
		QuizAnswer.objects.create(
			attempt=math_attempt,
			question=math_question,
			selected_answer=Answer.objects.create(
				question=math_question,
				text="5",
			),
			is_correct=False, marks_awarded=0,
		)
		QuizAnswer.objects.create(
			attempt=math_attempt,
			question=geometry_question,
			selected_answer=geometry_wrong_answer,
			is_correct=False, marks_awarded=0,
		)

		science = Subject.objects.create(name="Science", code="SCI")
		biology = Topic.objects.create(
			subject=science,
			name="Biology",
			slug="biology",
		)
		science_lesson = Lesson.objects.create(
			subject=science,
			title="Cells",
			slug="cells",
			content="<p>Cells</p>",
		)
		science_question = Question.objects.create(
			subject=science,
			topic=biology,
			lesson=science_lesson,
			text="What is the basic unit of life?",
		)
		science_wrong_answer = Answer.objects.create(
			question=science_question,
			text="An atom",
		)
		science_quiz = Quiz.objects.create(
			subject=science,
			topic=biology,
			lesson=science_lesson,
			title="Biology quiz",
		)
		QuizQuestion.objects.create(quiz=science_quiz, question=science_question)
		science_attempt = QuizAttempt.objects.create(
			user=self.user,
			quiz=science_quiz,
			total_questions=1, total_marks=1,
			completed_at=timezone.now(),
		)
		QuizAnswer.objects.create(
			attempt=science_attempt,
			question=science_question,
			selected_answer=science_wrong_answer,
			is_correct=False, marks_awarded=0,
		)
		self.client.force_login(self.user)

		response = self.client.get(reverse("progress:mistake-bank"))

		self.assertEqual(response.status_code, 200)
		groups = response.context["mistake_groups"]
		groups_by_subject = {group["subject"].name: group for group in groups}
		self.assertEqual(set(groups_by_subject), {"Mathematics", "Science"})
		self.assertEqual(
			[group["topic"].name for group in groups_by_subject["Mathematics"]["topics"]],
			["Algebra", "Geometry"],
		)
		self.assertContains(response, 'class="mistake-subject"')
		self.assertContains(response, 'class="mistake-topic"')

	def test_authenticated_user_can_complete_lesson_once(self):
		self.client.force_login(self.user)

		response = self.client.post(
			reverse("progress:complete-lesson", args=[self.lesson.id]),
		)

		self.assertRedirects(response, reverse("subjects:lesson-detail", kwargs={
			"subject_slug": "mathematics",
			"lesson_slug": "algebra",
		}))
		self.assertEqual(
			LessonProgress.objects.filter(user=self.user, lesson=self.lesson).count(),
			1,
		)
		self.assertTrue(
			LessonProgress.objects.get(user=self.user, lesson=self.lesson).completed
		)
		progress = UserProgress.objects.get(user=self.user)
		self.assertEqual(progress.total_xp, 50)
		self.assertEqual(progress.current_streak, 1)

		self.client.post(
			reverse("progress:complete-lesson", args=[self.lesson.id]),
		)
		self.assertEqual(XPTransaction.objects.filter(user=self.user).count(), 1)

	def test_anonymous_user_is_sent_to_login_for_lesson_progress(self):
		response = self.client.post(
			reverse("progress:complete-lesson", args=[self.lesson.id]),
		)

		self.assertRedirects(
			response,
			f"/accounts/login/?next={reverse('progress:complete-lesson', args=[self.lesson.id])}",
		)

	def test_dashboard_links_to_subject_flashcards_and_flashcards_page_renders(self):
		self.client.force_login(self.user)
		question = self.lesson.subject.questions.get()
		FlashcardState.objects.create(
			user=self.user,
			question=question,
			due_at=timezone.localdate(),
		)

		dashboard_response = self.client.get(reverse("progress:dashboard"))
		self.assertContains(
			dashboard_response,
			reverse("progress:flashcards", args=["mathematics"]),
		)
		self.assertContains(dashboard_response, "Review 1 due card")
		self.assertContains(dashboard_response, "No active plan yet")

		flashcards_response = self.client.get(
			reverse("progress:flashcards", args=["mathematics"])
		)
		self.assertEqual(flashcards_response.status_code, 200)
		self.assertContains(flashcards_response, "What is 2 + 2?")

	def test_flashcard_hub_offers_all_due_and_subject_sessions(self):
		self.client.force_login(self.user)
		FlashcardState.objects.create(
			user=self.user,
			question=self.correct_answer.question,
			due_at=timezone.localdate(),
		)
		second_subject = Subject.objects.create(name="Biology", code="BIO")
		second_topic = Topic.objects.create(subject=second_subject, name="Cells", slug="cells")
		second_lesson = Lesson.objects.create(
			subject=second_subject,
			title="Cells",
			slug="cells",
			content="<p>Cells</p>",
		)
		second_question = Question.objects.create(
			subject=second_subject,
			topic=second_topic,
			lesson=second_lesson,
			text="What is a cell?",
		)
		Answer.objects.create(question=second_question, text="A basic unit of life", is_correct=True)
		FlashcardState.objects.create(
			user=self.user,
			question=second_question,
			due_at=timezone.localdate(),
		)

		hub_response = self.client.get(reverse("progress:flashcard-hub"))
		self.assertEqual(hub_response.status_code, 200)
		self.assertContains(hub_response, reverse("progress:flashcards-all"))
		self.assertContains(hub_response, reverse("progress:flashcards", args=["mathematics"]))
		self.assertContains(hub_response, reverse("progress:flashcards", args=["biology"]))
		self.assertContains(hub_response, "2 due cards")

		all_cards_response = self.client.get(reverse("progress:flashcards-all"))
		self.assertEqual(all_cards_response.status_code, 200)
		self.assertContains(all_cards_response, "What is 2 + 2?")
		self.assertContains(all_cards_response, "What is a cell?")
		self.assertContains(all_cards_response, "2 cards due today")

	def test_dashboard_suggests_active_study_plan_and_getting_started(self):
		self.client.force_login(self.user)
		StudyPlan.objects.create(
			user=self.user,
			subject=self.lesson.subject,
			target_date=timezone.localdate() + timezone.timedelta(days=30),
		)

		response = self.client.get(reverse("progress:dashboard"))

		self.assertContains(response, "Continue your active plan")
		self.assertContains(response, "No cards due yet")
		self.assertContains(response, "Take a lesson quiz to add cards")

	def test_wrong_answer_creates_flashcard_state(self):
		self.client.force_login(self.user)
		wrong_answer = self.correct_answer.question.answers.exclude(id=self.correct_answer.id).first()

		self.client.post(
			reverse("progress:submit-quiz", args=[self.quiz.id]),
			{f"question-{self.correct_answer.question_id}": wrong_answer.id},
		)

		self.assertTrue(
			FlashcardState.objects.filter(
				user=self.user,
				question=self.correct_answer.question,
			).exists()
		)

	def test_flashcard_reviews_apply_sm2_growth_ease_and_reset(self):
		self.client.force_login(self.user)
		review_url = reverse("progress:review-flashcard")
		payload = {"question_id": self.correct_answer.question_id, "rating": "good"}

		first = self.client.post(review_url, payload)
		self.assertEqual(first.json()["due_days"], 1)
		state = FlashcardState.objects.get(user=self.user, question=self.correct_answer.question)
		self.assertEqual((state.reps, state.interval_days, state.ease), (1, 1, 2.5))

		second = self.client.post(review_url, payload)
		self.assertEqual(second.json()["due_days"], 6)
		state.refresh_from_db()
		self.assertEqual((state.reps, state.interval_days), (2, 6))

		hard = self.client.post(review_url, {**payload, "rating": "hard"})
		self.assertEqual(hard.json()["due_days"], 14)
		state.refresh_from_db()
		self.assertEqual(state.reps, 3)
		self.assertAlmostEqual(state.ease, 2.36)

		again = self.client.post(review_url, {**payload, "rating": "again"})
		self.assertEqual(again.json()["due_days"], 1)
		state.refresh_from_db()
		self.assertEqual((state.reps, state.interval_days), (0, 1))

	def test_flashcard_reviews_round_sm2_intervals_to_nearest_day(self):
		state = FlashcardState.objects.create(
			user=self.user,
			question=self.correct_answer.question,
			reps=2,
			interval_days=5,
			ease=2.5,
		)

		reviewed_at = timezone.now()
		due_days = state.review("good", reviewed_at=reviewed_at)

		self.assertEqual(due_days, 13)
		self.assertEqual(state.due_at, timezone.localdate(reviewed_at) + timezone.timedelta(days=13))

	def test_flashcard_review_rejects_malformed_or_missing_question_id(self):
		self.client.force_login(self.user)
		url = reverse("progress:review-flashcard")

		for data in ({"question_id": "abc", "rating": "good"}, {"question_id": "1.5", "rating": "good"}, {"rating": "good"}):
			self.assertEqual(self.client.post(url, data).status_code, 400, data)
		self.assertEqual(self.client.post(url, {"question_id": 999999, "rating": "good"}).status_code, 404)
		self.assertEqual(
			self.client.post(url, {"question_id": self.correct_answer.question_id, "rating": "good"}).status_code, 200
		)

	def test_study_plan_complete_item_validates_id_and_ownership(self):
		plan = StudyPlan.objects.create(
			user=self.user,
			subject=self.lesson.subject,
			target_date=timezone.localdate() + timezone.timedelta(days=7),
		)
		item = StudyPlanItem.objects.create(
			plan=plan,
			item_type=StudyPlanItem.FLASHCARD_REVIEW,
			topic=self.correct_answer.question.topic,
			scheduled_date=timezone.localdate(),
		)
		url = reverse("progress:study-plan", args=["mathematics"])

		self.client.force_login(self.user)
		for bad in ("abc", "-1", "1.0"):
			self.assertEqual(self.client.post(url, {"complete_item": bad}).status_code, 400, bad)
		self.assertEqual(self.client.post(url, {"complete_item": 999999}).status_code, 404)

		other = get_user_model().objects.create_user(username="intruder", password="pw-12345-x")
		self.client.force_login(other)
		self.assertEqual(self.client.post(url, {"complete_item": item.pk}).status_code, 404)

	def test_flashcard_review_rejects_unknown_rating(self):
		self.client.force_login(self.user)

		response = self.client.post(
			reverse("progress:review-flashcard"),
			{"question_id": self.correct_answer.question_id, "rating": "soon"},
		)

		self.assertEqual(response.status_code, 400)
		self.assertFalse(FlashcardState.objects.filter(user=self.user).exists())

	def test_study_plan_items_require_one_same_subject_target_and_valid_date(self):
		plan = StudyPlan.objects.create(
			user=self.user,
			subject=self.lesson.subject,
			target_date=timezone.localdate() + timezone.timedelta(days=7),
		)
		valid_item = StudyPlanItem(
			plan=plan,
			item_type=StudyPlanItem.LESSON,
			lesson=self.lesson,
			topic=self.correct_answer.question.topic,
			scheduled_date=timezone.localdate(),
		)
		valid_item.full_clean()
		valid_item.save()

		with self.assertRaises(Exception):
			StudyPlanItem(
				plan=plan,
				item_type=StudyPlanItem.LESSON,
				scheduled_date=timezone.localdate(),
			).full_clean()

		other_subject = Subject.objects.create(name="Science", code="SCI")
		other_lesson = Lesson.objects.create(
			subject=other_subject,
			title="Cells",
			content="<p>Cells</p>",
		)
		with self.assertRaises(Exception):
			StudyPlanItem(
				plan=plan,
				item_type=StudyPlanItem.LESSON,
				topic=self.correct_answer.question.topic,
				lesson=other_lesson,
				scheduled_date=timezone.localdate(),
			).full_clean()

	def test_short_answer_questions_are_scored_by_expected_text(self):
		short_answer_question = Question.objects.create(
			subject=self.lesson.subject,
			topic=self.lesson.subject.topics.get(slug="algebra"),
			lesson=self.lesson,
			text="Name the capital of Jamaica.",
			format="short_answer",
			expected_answer="Kingston",
		)
		quiz = Quiz.objects.create(
			subject=self.lesson.subject,
			topic=self.lesson.subject.topics.get(slug="algebra"),
			lesson=self.lesson,
			title="Short answer quiz",
		)
		quiz.quiz_questions.create(question=short_answer_question)
		self.client.force_login(self.user)
		page = self.client.get(reverse("quizzes:detail", args=[quiz.id]))

		self.assertContains(page, f'name="question-{short_answer_question.id}"')
		self.assertContains(page, 'placeholder="Type your answer"')

		response = self.client.post(
			reverse("progress:submit-quiz", args=[quiz.id]),
			{f"question-{short_answer_question.id}": "kingston"},
		)

		self.assertEqual(response.status_code, 302)
		attempt = QuizAttempt.objects.get(user=self.user, quiz=quiz)
		self.assertEqual(attempt.score, 1)
		self.assertTrue(attempt.answers.get().is_correct)

	def test_matching_question_requires_every_pair_to_match(self):
		matching_question = Question.objects.create(
			subject=self.lesson.subject,
			topic=self.lesson.subject.topics.get(slug="algebra"),
			lesson=self.lesson,
			text="Match each term to its value.",
			format=Question.FORMAT_MATCHING,
		)
		first_pair = Answer.objects.create(
			question=matching_question,
			text="2 + 2",
			match_text="4",
		)
		second_pair = Answer.objects.create(
			question=matching_question,
			text="3 + 3",
			match_text="6",
		)
		quiz = Quiz.objects.create(
			subject=self.lesson.subject,
			topic=self.lesson.subject.topics.get(slug="algebra"),
			lesson=self.lesson,
			title="Matching quiz",
		)
		quiz.quiz_questions.create(question=matching_question)
		page = self.client.get(reverse("quizzes:detail", args=[quiz.id]))

		self.assertContains(page, "Choose a match")
		self.client.force_login(self.user)

		response = self.client.post(
			reverse("progress:submit-quiz", args=[quiz.id]),
			{
				f"question-{matching_question.id}-{first_pair.id}": "4",
				f"question-{matching_question.id}-{second_pair.id}": "4",
			},
		)

		self.assertEqual(response.status_code, 302)
		attempt = QuizAttempt.objects.get(user=self.user, quiz=quiz)
		self.assertEqual(attempt.score, 0)
		self.assertFalse(attempt.answers.get().is_correct)

	def test_true_false_question_scores_expected_text_without_answer_rows(self):
		true_false_question = Question.objects.create(
			subject=self.lesson.subject,
			topic=self.lesson.subject.topics.get(slug="algebra"),
			lesson=self.lesson,
			text="Four is an even number.",
			format=Question.FORMAT_TRUE_FALSE,
			expected_answer="True",
		)
		quiz = Quiz.objects.create(
			subject=self.lesson.subject,
			topic=self.lesson.subject.topics.get(slug="algebra"),
			lesson=self.lesson,
			title="True or false quiz",
		)
		quiz.quiz_questions.create(question=true_false_question)
		page = self.client.get(reverse("quizzes:detail", args=[quiz.id]))

		self.assertContains(page, 'value="True"')
		self.client.force_login(self.user)

		response = self.client.post(
			reverse("progress:submit-quiz", args=[quiz.id]),
			{f"question-{true_false_question.id}": "true"},
		)

		self.assertEqual(response.status_code, 302)
		attempt = QuizAttempt.objects.get(user=self.user, quiz=quiz)
		self.assertEqual(attempt.score, 1)

	def test_quiz_submission_saves_score_and_answers(self):
		question = self.correct_answer.question
		question.explanation = "Because 2 + 2 = 4, the correct answer is four."
		question.save(update_fields=["explanation"])
		wrong_answer = question.answers.exclude(pk=self.correct_answer.pk).first()
		self.client.force_login(self.user)

		response = self.client.post(
			reverse("progress:submit-quiz", args=[self.quiz.id]),
			{f"question-{question.id}": wrong_answer.id},
		)

		self.assertEqual(response.status_code, 302)
		self.assertIn("/quizzes/?attempt=", response["Location"])
		result_response = self.client.get(response["Location"])
		self.assertContains(result_response, "✓ Correct answer: 4")
		self.assertContains(result_response, "Because 2 + 2 = 4, the correct answer is four.")
		attempt = QuizAttempt.objects.get(user=self.user, quiz=self.quiz)
		self.assertEqual(attempt.score, 0)
		self.assertEqual(attempt.total_questions, 1)
		self.assertEqual(attempt.answers.count(), 1)
		self.assertFalse(attempt.answers.get().is_correct)
		self.assertEqual(UserProgress.objects.get(user=self.user).total_xp, 0)

	def test_topic_leaderboard_is_scoped_to_topic(self):
		other_user = get_user_model().objects.create_user(username="other")
		XPTransaction.objects.create(
			user=self.user,
			topic=self.quiz.topic,
			amount=50,
			reason="Completed lesson",
		)
		XPTransaction.objects.create(
			user=other_user,
			topic=self.quiz.topic,
			amount=100,
			reason="Completed quiz",
		)
		self.client.force_login(self.user)

		response = self.client.get(
			reverse(
				"progress:leaderboard",
				args=["mathematics", "algebra"],
			)
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, f"Student #{other_user.id}")
		self.assertContains(response, "100 XP")

	def test_quiz_submission_ignores_answer_from_another_question(self):
		other_question = Question.objects.create(
			subject=self.lesson.subject,
			topic=self.lesson.subject.topics.get(slug="algebra"),
			lesson=self.lesson,
			text="Other question",
		)
		other_answer = Answer.objects.create(
			question=other_question,
			text="Also not valid",
			is_correct=True,
		)
		self.client.force_login(self.user)

		self.client.post(
			reverse("progress:submit-quiz", args=[self.quiz.id]),
			{f"question-{self.correct_answer.question_id}": other_answer.id},
		)

		attempt = QuizAttempt.objects.get(user=self.user, quiz=self.quiz)
		self.assertEqual(attempt.score, 0)
		self.assertIsNone(attempt.answers.get().selected_answer)

# Create your tests here.


class AdminDashboardTests(TestCase):
	def setUp(self):
		self.admin_user = get_user_model().objects.create_superuser(
			username="admin",
			password="admin-password",
			email="admin@example.com",
		)
		student = get_user_model().objects.create_user(username="student")
		subject = Subject.objects.create(name="Mathematics", code="MATH")
		topic = Topic.objects.create(subject=subject, name="Algebra", slug="algebra")
		lesson = Lesson.objects.create(subject=subject, title="Algebra", slug="algebra", content="x")
		self.hard = Question.objects.create(subject=subject, topic=topic, lesson=lesson, text="Too hard question")
		Answer.objects.create(question=self.hard, text="4", is_correct=True)
		self.unanswerable = Question.objects.create(
			subject=subject, topic=topic, lesson=lesson, text="Missing answer question"
		)
		self.quiz = Quiz.objects.create(subject=subject, topic=topic, lesson=lesson, title="Algebra quiz")
		attempt = QuizAttempt.objects.create(
			user=student, quiz=self.quiz, score=0, total_questions=1, total_marks=1, completed_at=timezone.now()
		)
		QuizAnswer.objects.create(attempt=attempt, question=self.hard, is_correct=False, marks_awarded=0)

	def test_dashboard_shows_stats_flags_and_recent_attempts(self):
		self.client.force_login(self.admin_user)

		response = self.client.get(reverse("admin:index"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Active questions")
		self.assertContains(response, "1 flagged for review")
		self.assertContains(response, "Too hard question")
		self.assertContains(response, "Missing answer question")
		self.assertContains(response, "No answer")
		self.assertContains(response, "0% average score")
		self.assertContains(response, reverse("admin:progress_quizattempt_change", args=[QuizAttempt.objects.get().pk]))
		self.assertContains(response, 'id="recent-actions-module"')
		self.assertContains(response, 'id="nav-sidebar"')

	def test_dashboard_hides_data_without_view_permissions(self):
		staff = get_user_model().objects.create_user(username="staff", is_staff=True)
		self.client.force_login(staff)

		response = self.client.get(reverse("admin:index"))

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, "Too hard question")
		self.assertNotContains(response, "stat-card")
		self.assertNotContains(response, "Recent quiz attempts")

	def test_quiz_change_form_loads_quiz_admin_script(self):
		self.client.force_login(self.admin_user)

		response = self.client.get(reverse("admin:quizzes_quiz_change", args=[self.quiz.pk]))

		self.assertContains(response, "admin/js/quiz_admin.js")
		self.assertContains(response, 'data-difficulty="medium"')


class QuizXPPolicyTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(username="student", password="x")
		subject = Subject.objects.create(name="Mathematics", code="MATH")
		topic = Topic.objects.create(subject=subject, name="Algebra", slug="algebra")
		lesson = Lesson.objects.create(subject=subject, title="Algebra", slug="algebra", content="<p>A</p>")
		self.question = Question.objects.create(subject=subject, topic=topic, lesson=lesson, text="2 + 2?")
		self.right = Answer.objects.create(question=self.question, text="4", is_correct=True)
		self.wrong = Answer.objects.create(question=self.question, text="5")
		self.quiz = Quiz.objects.create(subject=subject, topic=topic, lesson=lesson, title="Quiz")
		QuizQuestion.objects.create(quiz=self.quiz, question=self.question)
		self.client.force_login(self.user)

	def submit(self, answer):
		return self.client.post(
			reverse("progress:submit-quiz", args=[self.quiz.id]),
			{f"question-{self.question.id}": answer.id},
		)

	def xp(self):
		return UserProgress.objects.get(user=self.user).total_xp

	def test_xp_only_for_first_completion_and_new_best(self):
		self.submit(self.wrong)  # 0% earns nothing, so blank/wrong submits can't farm XP
		self.assertFalse(XPTransaction.objects.filter(user=self.user).exists())
		self.submit(self.right)  # first scoring attempt: 25 + 20
		self.assertEqual(self.xp(), 45)
		self.submit(self.right)  # equal best
		self.submit(self.wrong)  # lower score
		self.assertEqual(self.xp(), 45)
		self.assertEqual(QuizAttempt.objects.filter(user=self.user).count(), 4)
		self.assertEqual(XPTransaction.objects.filter(user=self.user).count(), 1)

	def test_written_answer_ignores_punctuation_and_case(self):
		open_question = Question.objects.create(
			subject=self.quiz.subject, topic=self.quiz.topic, lesson=self.quiz.lesson, text="CPU stands for?",
			format=Question.FORMAT_SHORT_ANSWER, expected_answer="Central Processing Unit",
		)
		QuizQuestion.objects.create(quiz=self.quiz, question=open_question, order=1)
		self.client.post(
			reverse("progress:submit-quiz", args=[self.quiz.id]),
			{f"question-{open_question.id}": "  central processing unit. "},
		)
		self.assertTrue(QuizAnswer.objects.get(question=open_question).is_correct)

	def test_short_answer_accepts_listed_alternatives(self):
		short = Question.objects.create(
			subject=self.quiz.subject, topic=self.quiz.topic, lesson=self.quiz.lesson, text="Short",
			format=Question.FORMAT_SHORT_ANSWER, expected_answer="RAM|random access memory",
		)
		QuizQuestion.objects.create(quiz=self.quiz, question=short, order=1)
		self.client.post(reverse("progress:submit-quiz", args=[self.quiz.id]), {f"question-{short.id}": "Random Access Memory"})
		self.assertTrue(QuizAnswer.objects.get(question=short).is_correct)

	def _worded(self, marks=4):
		worded = Question.objects.create(
			subject=self.quiz.subject, topic=self.quiz.topic, lesson=self.quiz.lesson, text="Explain",
			format=Question.FORMAT_WORDED, expected_answer="volatile", marks=marks,
		)
		QuizQuestion.objects.create(quiz=self.quiz, question=worded, order=1)
		return worded

	def _mark(self, answer, marks):
		from django.contrib.admin.sites import site
		from django.test import RequestFactory

		from apps.progress.admin import QuizAnswerAdmin

		answer.marks_awarded = marks
		answer.full_clean()
		QuizAnswerAdmin(QuizAnswer, site).save_model(RequestFactory().post("/"), answer, None, True)

	def test_worded_answer_waits_for_marking_then_scores_partial_credit(self):
		worded = self._worded()
		self.client.post(
			reverse("progress:submit-quiz", args=[self.quiz.id]),
			{f"question-{self.question.id}": self.right.id, f"question-{worded.id}": "It is volatile."},
		)
		attempt = QuizAttempt.objects.get(user=self.user)
		answer = QuizAnswer.objects.get(question=worded)
		self.assertTrue(attempt.awaiting_review)
		self.assertIsNone(answer.marks_awarded)
		self.assertEqual(attempt.total_marks, 5)
		self.assertFalse(XPTransaction.objects.filter(user=self.user).exists())
		self.assertFalse(TopicMasteryStat.objects.filter(user=self.user).exists())
		self.assertFalse(FlashcardState.objects.filter(user=self.user).exists())
		page = self.client.get(reverse("quizzes:detail", args=[self.quiz.id]) + f"?attempt={attempt.id}")
		self.assertContains(page, "waiting for your teacher to mark")

		answer.feedback = "Name a second difference."
		self._mark(answer, 2)
		attempt.refresh_from_db()
		answer.refresh_from_db()
		self.assertFalse(attempt.awaiting_review)
		self.assertEqual((attempt.score, attempt.percentage), (3, 60))
		self.assertFalse(answer.is_correct)
		self.assertEqual(self.xp(), 25 + 60 // 5)
		self.assertTrue(TopicMasteryStat.objects.filter(user=self.user).exists())
		self.assertTrue(FlashcardState.objects.filter(user=self.user, question=worded).exists())
		page = self.client.get(reverse("quizzes:detail", args=[self.quiz.id]) + f"?attempt={attempt.id}")
		self.assertContains(page, "2/4 marks")
		self.assertContains(page, "Name a second difference.")

		self._mark(answer, 4)  # a correction updates the score but awards no more XP
		attempt.refresh_from_db()
		self.assertEqual(attempt.score, 5)
		self.assertTrue(QuizAnswer.objects.get(pk=answer.pk).is_correct)
		self.assertEqual(XPTransaction.objects.filter(user=self.user).count(), 1)

	def test_marking_queue_lists_pending_answers_and_marks_them_inline(self):
		worded = self._worded()
		self.client.post(
			reverse("progress:submit-quiz", args=[self.quiz.id]),
			{f"question-{self.question.id}": self.right.id, f"question-{worded.id}": "Loses data without power"},
		)
		answer = QuizAnswer.objects.get(question=worded)
		self.client.force_login(get_user_model().objects.create_superuser("teacher", "t@example.com", "pw"))
		url = reverse("admin:progress_quizanswer_changelist") + "?marking=pending"
		response = self.client.get(url)
		self.assertContains(response, "Loses data without power")
		self.assertEqual(list(response.context["cl"].result_list), [answer])
		response = self.client.post(url, {
			"form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1",
			"form-0-id": answer.id, "form-0-marks_awarded": "3", "form-0-feedback": "Good", "_save": "Save",
		})
		self.assertEqual(response.status_code, 302)
		attempt = QuizAttempt.objects.get(user=self.user)
		self.assertEqual((attempt.awaiting_review, attempt.score), (False, 4))
		self.assertEqual(self.xp(), 25 + 80 // 5)

	def test_blank_worded_answer_needs_no_marking(self):
		self._worded()
		self.submit(self.right)
		attempt = QuizAttempt.objects.get(user=self.user)
		self.assertFalse(attempt.awaiting_review)
		self.assertEqual((attempt.score, attempt.total_marks), (1, 5))

	def test_pending_answers_are_not_mistakes_and_block_retakes_until_marked(self):
		worded = self._worded(marks=1)
		self.client.post(
			reverse("progress:submit-quiz", args=[self.quiz.id]),
			{f"question-{self.question.id}": self.right.id, f"question-{worded.id}": "volatile"},
		)
		self.assertNotContains(self.client.get(reverse("progress:mistake-bank")), "Explain")
		self.assertEqual(self.client.get(reverse("account")).context["accuracy"], 100)
		response = self.client.post(
			reverse("progress:submit-quiz", args=[self.quiz.id]),
			{f"question-{self.question.id}": self.right.id},
			follow=True,
		)
		self.assertContains(response, "still being marked")
		self.assertEqual(QuizAttempt.objects.filter(user=self.user).count(), 1)
		self._mark(QuizAnswer.objects.get(question=worded), 0)
		self.assertContains(self.client.get(reverse("progress:mistake-bank")), "Explain")
		self.client.post(reverse("progress:submit-quiz", args=[self.quiz.id]), {f"question-{self.question.id}": self.right.id})
		self.assertEqual(QuizAttempt.objects.filter(user=self.user).count(), 2)

	def test_unmarked_answers_stay_out_of_stats_and_deleting_the_question_unblocks_retakes(self):
		worded = self._worded()
		self.client.post(
			reverse("progress:submit-quiz", args=[self.quiz.id]),
			{f"question-{self.question.id}": self.right.id, f"question-{worded.id}": "It is volatile."},
		)
		self.assertContains(self.client.get(reverse("progress:dashboard")), "Being marked")
		self.client.force_login(get_user_model().objects.create_superuser("teacher", "t@example.com", "pw"))
		self.assertContains(self.client.get(reverse("admin:questions_question_change", args=[worded.id])), "No responses")
		self.assertEqual(self.client.get(reverse("admin:progress_quizanswer_add")).status_code, 403)

		worded.delete()  # takes its unmarked answer with it, leaving the attempt flagged with nothing to mark
		self.client.force_login(self.user)
		self.submit(self.right)
		self.assertEqual(QuizAttempt.objects.filter(user=self.user).count(), 2)

	def test_marks_cannot_exceed_question_marks(self):
		worded = self._worded(marks=2)
		self.client.post(
			reverse("progress:submit-quiz", args=[self.quiz.id]),
			{f"question-{self.question.id}": self.right.id, f"question-{worded.id}": "x"},
		)
		answer = QuizAnswer.objects.get(question=worded)
		answer.marks_awarded = 3
		with self.assertRaises(ValidationError):
			answer.full_clean()

	def test_multi_mark_objective_question_scores_all_or_nothing(self):
		self.question.marks = 3
		self.question.save()
		self.submit(self.right)
		attempt = QuizAttempt.objects.get(user=self.user)
		self.assertEqual((attempt.score, attempt.total_marks, attempt.percentage), (3, 3, 100))

	def test_matching_dropdown_options_are_not_in_answer_order(self):
		match = Question.objects.create(
			subject=self.quiz.subject, topic=self.quiz.topic, lesson=self.quiz.lesson, text="Match",
			format=Question.FORMAT_MATCHING,
		)
		for order, (left, right) in enumerate([("Mouse", "Output"), ("Monitor", "Input")]):
			Answer.objects.create(question=match, text=left, match_text=right, is_correct=True, order=order)
		QuizQuestion.objects.create(quiz=self.quiz, question=match, order=1)
		page = self.client.get(reverse("quizzes:detail", args=[self.quiz.id])).content.decode()
		self.assertLess(page.index('value="Input"'), page.index('value="Output"'))

	def test_inactive_question_is_not_scored_or_flashcarded(self):
		hidden = Question.objects.create(
			subject=self.quiz.subject, topic=self.quiz.topic, lesson=self.quiz.lesson, text="Gone?", is_active=False
		)
		QuizQuestion.objects.create(quiz=self.quiz, question=hidden, order=1)
		self.submit(self.right)
		attempt = QuizAttempt.objects.get(user=self.user)
		self.assertEqual((attempt.score, attempt.total_questions), (1, 1))
		self.assertFalse(FlashcardState.objects.filter(question=hidden).exists())

	def test_wrong_answers_reset_flashcards_and_mistake_bank_shows_latest_per_question(self):
		self.submit(self.wrong)
		self.submit(self.wrong)
		self.assertEqual(FlashcardState.objects.filter(user=self.user, question=self.question).count(), 1)
		response = self.client.get(reverse("progress:mistake-bank"))
		groups = response.context["mistake_groups"]
		self.assertEqual(len(groups[0]["topics"][0]["mistakes"]), 1)
		self.assertEqual(
			groups[0]["topics"][0]["mistakes"][0].attempt_id, QuizAttempt.objects.order_by("-id").first().id
		)

	def test_failed_submission_rolls_back_attempt_and_xp(self):
		from unittest import mock

		with mock.patch("apps.progress.views._award_xp", side_effect=RuntimeError):
			with self.assertRaises(RuntimeError):
				self.submit(self.right)
		self.assertFalse(QuizAttempt.objects.exists())
		self.assertFalse(QuizAnswer.objects.exists())

	def test_shared_answer_rows_match_separate_queries(self):
		from unittest import mock
		from apps.progress.analytics import mastery_rows

		self.submit(self.right)
		self.submit(self.wrong)
		subject = self.quiz.subject
		rows = mastery_rows(self.user, subject)
		with mock.patch("django.utils.timezone.now", return_value=timezone.now()):
			self.assertEqual(topic_mastery(self.user, subject, rows), topic_mastery(self.user, subject))
			self.assertEqual(
				difficulty_breakdown(self.user, subject, rows), difficulty_breakdown(self.user, subject)
			)

	def test_unknown_quiz_is_404(self):
		self.assertEqual(
			self.client.post(reverse("progress:submit-quiz", args=[9999])).status_code, 404
		)


class JamaicaStudyDayTests(TestCase):
	def award_at(self, user, topic, utc_moment):
		from unittest import mock
		from apps.progress.views import _award_xp

		with mock.patch("django.utils.timezone.now", return_value=utc_moment):
			_award_xp(user, topic, 10, "test")

	def test_streak_rolls_over_at_jamaica_midnight_not_utc(self):
		from datetime import datetime, timezone as dt_timezone

		user = get_user_model().objects.create_user(username="s", password="x")
		subject = Subject.objects.create(name="Mathematics", code="MATH")
		topic = Topic.objects.create(subject=subject, name="Algebra", slug="algebra")
		# 22:00 Mar 1 Jamaica (UTC-5) is already Mar 2 in UTC.
		self.award_at(user, topic, datetime(2026, 3, 2, 3, 0, tzinfo=dt_timezone.utc))
		# 23:30 Mar 1 Jamaica: same local day, so the streak must not advance.
		self.award_at(user, topic, datetime(2026, 3, 2, 4, 30, tzinfo=dt_timezone.utc))
		progress = UserProgress.objects.get(user=user)
		self.assertEqual(progress.current_streak, 1)
		self.assertEqual(str(progress.last_activity_date), "2026-03-01")
		# 00:30 Mar 2 Jamaica: next local day.
		self.award_at(user, topic, datetime(2026, 3, 2, 5, 30, tzinfo=dt_timezone.utc))
		progress.refresh_from_db()
		self.assertEqual(progress.current_streak, 2)
		self.assertEqual(str(progress.last_activity_date), "2026-03-02")


	def test_flashcard_due_date_uses_jamaica_day(self):
		from datetime import date, datetime, timezone as dt_timezone

		user = get_user_model().objects.create_user(username="f", password="x")
		subject = Subject.objects.create(name="Mathematics", code="MATH")
		topic = Topic.objects.create(subject=subject, name="Algebra", slug="algebra")
		lesson = Lesson.objects.create(subject=subject, title="A", slug="a", content="<p>A</p>")
		question = Question.objects.create(subject=subject, topic=topic, lesson=lesson, text="Q?")
		state = FlashcardState.objects.create(user=user, question=question)
		# 22:00 Mar 1 in Jamaica is already Mar 2 in UTC; a 1-day interval is due Mar 2 locally.
		state.review("good", reviewed_at=datetime(2026, 3, 2, 3, 0, tzinfo=dt_timezone.utc))
		self.assertEqual(state.due_at, date(2026, 3, 2))


class LeaderboardDisplayNameTests(TestCase):
	def setUp(self):
		self.viewer = get_user_model().objects.create_user(username="viewer", password="x")
		subject = Subject.objects.create(name="Mathematics", code="MATH")
		self.topic = Topic.objects.create(subject=subject, name="Algebra", slug="algebra")
		self.url = reverse("progress:subject-leaderboard", args=["mathematics"])

	def add_user(self, username, xp, display_name=None, email=""):
		user = get_user_model().objects.create_user(username=username, email=email, password="x")
		if display_name is not None:
			Profile.objects.create(user=user, display_name=display_name)
		XPTransaction.objects.create(user=user, topic=self.topic, amount=xp, reason="t")
		return user

	def test_display_name_blank_fallback_and_no_profile(self):
		self.add_user("named", 90, "Ada L.", email="secret@example.com")
		self.add_user("blank", 80, "")
		self.add_user("noprofile", 70)
		self.client.force_login(self.viewer)
		with self.assertNumQueries(5):
			response = self.client.get(self.url)
		self.assertContains(response, "Ada L.")
		# No display name: show a neutral label, never the username.
		self.assertContains(response, "Student #")
		self.assertNotContains(response, "noprofile")
		self.assertNotContains(response, "named")
		self.assertNotContains(response, "secret@example.com")

	def test_top_twenty_limit_ties_and_rank_beyond_list(self):
		for i in range(22):
			self.add_user(f"u{i:02d}", 100 - i)
		me = self.add_user("me", 1)
		self.client.force_login(me)
		response = self.client.get(self.url)
		self.assertEqual(len(response.context["leaderboard"]), 20)
		self.assertEqual([r["rank"] for r in response.context["leaderboard"]][:3], [1, 2, 3])
		self.assertEqual(response.context["current_user_row"]["rank"], 23)

	def test_equal_xp_ties_break_by_user_id(self):
		first = self.add_user("first", 50)
		second = self.add_user("second", 50)
		self.client.force_login(self.viewer)
		rows = self.client.get(self.url).context["leaderboard"]
		self.assertEqual([r["user_id"] for r in rows], [first.id, second.id])

	def test_rank_beyond_list_counts_ties_by_user_id(self):
		for i in range(20):
			self.add_user(f"top{i:02d}", 100)
		tied_first = self.add_user("tied_a", 5)
		tied_second = self.add_user("tied_b", 5)
		self.client.force_login(tied_second)
		self.assertEqual(self.client.get(self.url).context["current_user_row"]["rank"], 22)
		self.assertLess(tied_first.id, tied_second.id)
