from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.lessons.models import Lesson
from apps.questions.models import Answer, Question
from apps.quizzes.models import Quiz, QuizQuestion
from apps.subjects.models import Subject, Topic

from apps.progress.models import (
	LessonProgress,
	QuizAnswer,
	QuizAttempt,
	UserProgress,
	XPTransaction,
)


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
