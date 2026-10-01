from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.lessons.models import Lesson
from apps.questions.models import Answer, Question
from apps.quizzes.models import Quiz, QuizQuestion
from apps.subjects.models import Subject, Topic

from apps.progress.models import (
	FlashcardState,
	LessonProgress,
	QuizAnswer,
	QuizAttempt,
	UserProgress,
	XPTransaction,
)
from apps.progress.analytics import estimated_readiness, topic_mastery


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
			total_questions=1,
			completed_at=timezone.now() - timezone.timedelta(days=1),
		)
		QuizAnswer.objects.create(
			attempt=first_attempt,
			question=question,
			selected_answer=self.correct_answer,
			is_correct=True,
		)
		latest_attempt = QuizAttempt.objects.create(
			user=self.user,
			quiz=self.quiz,
			total_questions=1,
			completed_at=timezone.now(),
		)
		QuizAnswer.objects.create(
			attempt=latest_attempt,
			question=question,
			is_correct=False,
		)

		mastery = topic_mastery(self.user, question.subject)

		self.assertEqual(mastery[question.topic_id]["n"], 2)
		self.assertGreater(mastery[question.topic_id]["accuracy"], 0)
		self.assertLess(mastery[question.topic_id]["accuracy"], 0.5)

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
			total_questions=2,
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
			total_questions=1,
			completed_at=timezone.now(),
		)
		QuizAnswer.objects.create(
			attempt=attempt,
			question=self.correct_answer.question,
			selected_answer=self.correct_answer,
			is_correct=True,
		)
		self.client.force_login(self.user)

		response = self.client.get(reverse("progress:dashboard"))

		self.assertContains(response, "Topic mastery")
		self.assertContains(response, "Estimated readiness")
		self.assertContains(response, "Unknown · 1/5 answers")
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
			total_questions=1,
			completed_at=now - timezone.timedelta(days=1),
		)
		latest_attempt = QuizAttempt.objects.create(
			user=self.user,
			quiz=self.quiz,
			score=1,
			total_questions=1,
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
			total_questions=1,
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
			total_questions=2,
			completed_at=timezone.now(),
		)
		QuizAnswer.objects.create(
			attempt=math_attempt,
			question=math_question,
			selected_answer=Answer.objects.create(
				question=math_question,
				text="5",
			),
			is_correct=False,
		)
		QuizAnswer.objects.create(
			attempt=math_attempt,
			question=geometry_question,
			selected_answer=geometry_wrong_answer,
			is_correct=False,
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
			total_questions=1,
			completed_at=timezone.now(),
		)
		QuizAnswer.objects.create(
			attempt=science_attempt,
			question=science_question,
			selected_answer=science_wrong_answer,
			is_correct=False,
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

		flashcards_response = self.client.get(
			reverse("progress:flashcards", args=["mathematics"])
		)
		self.assertEqual(flashcards_response.status_code, 200)
		self.assertContains(flashcards_response, "What is 2 + 2?")

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

	def test_reviewing_card_as_again_or_hard_creates_flashcard_state(self):
		self.client.force_login(self.user)

		response = self.client.post(
			reverse("progress:review-flashcard"),
			{"question_id": self.correct_answer.question_id, "rating": "again"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(
			FlashcardState.objects.filter(
				user=self.user,
				question=self.correct_answer.question,
			).exists()
		)

		response = self.client.post(
			reverse("progress:review-flashcard"),
			{"question_id": self.correct_answer.question_id, "rating": "hard"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(
			FlashcardState.objects.filter(
				user=self.user,
				question=self.correct_answer.question,
			).exists()
		)

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
		self.client.force_login(self.user)

		response = self.client.post(
			reverse("progress:submit-quiz", args=[self.quiz.id]),
			{f"question-{self.correct_answer.question_id}": self.correct_answer.id},
		)

		self.assertEqual(response.status_code, 302)
		self.assertIn("/quizzes/?attempt=", response["Location"])
		result_response = self.client.get(response["Location"])
		self.assertContains(result_response, "+45 XP earned")
		attempt = QuizAttempt.objects.get(user=self.user, quiz=self.quiz)
		self.assertEqual(attempt.score, 1)
		self.assertEqual(attempt.total_questions, 1)
		self.assertEqual(attempt.answers.count(), 1)
		self.assertTrue(attempt.answers.get().is_correct)
		self.assertEqual(UserProgress.objects.get(user=self.user).total_xp, 45)

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
		self.assertContains(response, "other")
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
