from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.lessons.models import Lesson
from apps.progress.models import QuizAnswer, QuizAttempt
from apps.quizzes.models import Quiz
from apps.subjects.models import Subject, Topic

from .models import Answer, Question


class QuestionAnalyticsAdminTests(TestCase):
	def test_question_admin_shows_accuracy_flag_and_distractor_picks(self):
		staff = get_user_model().objects.create_superuser(
			username="admin",
			password="admin-password",
			email="admin@example.com",
		)
		subject = Subject.objects.create(name="Mathematics", code="MATH")
		topic = Topic.objects.create(subject=subject, name="Algebra", slug="algebra")
		lesson = Lesson.objects.create(
			subject=subject,
			title="Algebra",
			slug="algebra",
			content="Algebra",
		)
		question = Question.objects.create(
			subject=subject,
			topic=topic,
			lesson=lesson,
			text="What is 2 + 2?",
		)
		correct_answer = Answer.objects.create(
			question=question,
			text="4",
			is_correct=True,
		)
		dominant_distractor = Answer.objects.create(question=question, text="5")
		other_distractor = Answer.objects.create(question=question, text="6")
		quiz = Quiz.objects.create(
			subject=subject,
			topic=topic,
			lesson=lesson,
			title="Algebra quiz",
		)
		student = get_user_model().objects.create_user(username="student")
		for index in range(10):
			attempt = QuizAttempt.objects.create(
				user=student,
				quiz=quiz,
				total_questions=1,
				completed_at=timezone.now(),
			)
			is_correct = index == 0
			QuizAnswer.objects.create(
				attempt=attempt,
				question=question,
				selected_answer=(
					correct_answer
					if is_correct
					else dominant_distractor if index < 8 else other_distractor
				),
				is_correct=is_correct,
			)
		self.client.force_login(staff)

		response = self.client.get(
			reverse("admin:questions_question_change", args=[question.id])
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "10.0% (10)")
		self.assertContains(response, "Review: below 20% correct")
		self.assertContains(response, "5")
		self.assertContains(response, "7")
		self.assertContains(response, "70%")
