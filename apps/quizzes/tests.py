from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.lessons.models import Lesson
from apps.progress.models import QuizAttempt
from apps.questions.models import Answer, Question
from apps.subjects.models import Subject, Topic

from apps.quizzes.models import Quiz, QuizQuestion
from apps.quizzes.services import generate_mock_exam


class QuizModelTests(TestCase):
	def setUp(self):
		self.subject = Subject.objects.create(name="Mathematics", code="MATH")
		self.topic = Topic.objects.create(
			subject=self.subject,
			name="Algebra",
			slug="algebra",
		)
		self.lesson = Lesson.objects.create(
			subject=self.subject,
			title="Algebra",
			slug="algebra",
			content="<p>Algebra</p>",
			lesson_number=1,
			section_number=1,
		)
		self.other_lesson = Lesson.objects.create(
			subject=self.subject,
			title="Geometry",
			slug="geometry",
			content="<p>Geometry</p>",
			lesson_number=2,
			section_number=1,
		)
		self.question = Question.objects.create(
			subject=self.subject,
			topic=self.topic,
			lesson=self.lesson,
			text="What is 2 + 2?",
		)

	def test_quiz_is_attached_to_lesson(self):
		quiz = Quiz.objects.create(
			title="Algebra quiz",
			subject=self.subject,
			topic=self.topic,
			lesson=self.lesson,
		)

		self.assertEqual(quiz.lesson, self.lesson)
		self.assertEqual(self.lesson.quizzes.get(), quiz)

	def test_quiz_question_must_match_quiz_lesson(self):
		quiz = Quiz.objects.create(
			title="Algebra quiz",
			subject=self.subject,
			topic=self.topic,
			lesson=self.lesson,
		)
		other_question = Question.objects.create(
			subject=self.subject,
			topic=self.topic,
			lesson=self.other_lesson,
			text="What is a triangle?",
		)

		with self.assertRaises(ValidationError):
			QuizQuestion(quiz=quiz, question=other_question).full_clean()

	def test_question_can_have_four_answers(self):
		answers = [
			Answer(question=self.question, text=text, order=order)
			for order, text in enumerate(("1", "2", "3", "4"))
		]
		Answer.objects.bulk_create(answers)

		self.assertEqual(self.question.answers.count(), 4)

	def test_mock_exam_generation_uses_topic_weights_without_padding(self):
		second_topic = Topic.objects.create(
			subject=self.subject,
			name="Geometry",
			slug="geometry",
			exam_weight=1,
		)
		self.topic.exam_weight = 3
		self.topic.save(update_fields=["exam_weight"])
		second_question = Question.objects.create(
			subject=self.subject,
			topic=second_topic,
			lesson=self.other_lesson,
			text="How many sides has a triangle?",
		)

		quiz, topic_counts = generate_mock_exam(self.subject, 8, 90)

		self.assertTrue(quiz.is_mock)
		self.assertIsNone(quiz.topic)
		self.assertIsNone(quiz.lesson)
		self.assertEqual(topic_counts, {self.topic.id: 1, second_topic.id: 1})
		self.assertEqual(
			set(quiz.questions.values_list("id", flat=True)),
			{self.question.id, second_question.id},
		)
		self.assertEqual(quiz.time_limit_minutes, 90)

	def test_mock_question_can_span_topics_and_lessons(self):
		second_topic = Topic.objects.create(
			subject=self.subject,
			name="Geometry",
			slug="geometry",
		)
		other_question = Question.objects.create(
			subject=self.subject,
			topic=second_topic,
			lesson=self.other_lesson,
			text="How many sides has a triangle?",
		)
		mock = Quiz.objects.create(
			title="Subject mock",
			subject=self.subject,
			is_mock=True,
		)

		QuizQuestion(quiz=mock, question=other_question).full_clean()

	def test_mock_exam_rejects_invalid_limits(self):
		with self.assertRaisesMessage(ValueError, "Question count must be greater than zero."):
			generate_mock_exam(self.subject, 0, 30)
		with self.assertRaisesMessage(ValueError, "Time limit must be greater than zero."):
			generate_mock_exam(self.subject, 1, 0)

	def test_mock_exam_rejects_topics_without_weight_or_questions(self):
		self.topic.exam_weight = 0
		self.topic.save(update_fields=["exam_weight"])
		with self.assertRaisesMessage(ValueError, "no active topics with a positive exam weight"):
			generate_mock_exam(self.subject, 5, 30)

		empty_topic = Topic.objects.create(
			subject=self.subject,
			name="Empty",
			slug="empty",
		)
		with self.assertRaisesMessage(ValueError, "No active questions are available"):
			generate_mock_exam(self.subject, 5, 30, topics=[empty_topic])

	def test_quiz_clean_rejects_missing_practice_relationships(self):
		quiz = Quiz(title="Incomplete practice", subject=self.subject)

		with self.assertRaises(ValidationError) as error:
			quiz.full_clean()

		self.assertIn("topic", error.exception.message_dict)
		self.assertIn("lesson", error.exception.message_dict)

	def test_quiz_question_rejects_a_question_from_another_subject(self):
		quiz = Quiz.objects.create(
			title="Algebra quiz",
			subject=self.subject,
			topic=self.topic,
			lesson=self.lesson,
		)
		other_subject = Subject.objects.create(name="Science", code="SCI")
		other_topic = Topic.objects.create(subject=other_subject, name="Physics", slug="physics")
		other_lesson = Lesson.objects.create(
			subject=other_subject,
			title="Motion",
			slug="motion",
			content="Motion",
		)
		other_question = Question.objects.create(
			subject=other_subject,
			topic=other_topic,
			lesson=other_lesson,
			text="What is speed?",
		)

		with self.assertRaises(ValidationError):
			QuizQuestion(quiz=quiz, question=other_question).full_clean()

	def test_subject_quiz_page_renders_lessonless_mock_and_timer(self):
		mock = Quiz.objects.create(
			title="Timed mock",
			subject=self.subject,
			is_mock=True,
			time_limit_minutes=45,
		)
		QuizQuestion.objects.create(quiz=mock, question=self.question)

		response = self.client.get(reverse("quizzes:subject-list", args=["mathematics"]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Timed mock")
		self.assertContains(response, "45 minutes")
		self.assertContains(response, 'data-time-limit-minutes="45"')

	def test_quiz_index_shows_only_active_quizzes(self):
		active_quiz = Quiz.objects.create(
			title="Algebra quiz",
			subject=self.subject,
			topic=self.topic,
			lesson=self.lesson,
		)
		Quiz.objects.create(
			title="Archived quiz",
			subject=self.subject,
			topic=self.topic,
			lesson=self.lesson,
			is_active=False,
		)

		response = self.client.get(reverse("quizzes:list"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(list(response.context["quizzes"]), [active_quiz])

	def test_topic_quiz_page_filters_to_active_topic_quizzes(self):
		quiz = Quiz.objects.create(
			title="Algebra quiz",
			subject=self.subject,
			topic=self.topic,
			lesson=self.lesson,
		)
		QuizQuestion.objects.create(quiz=quiz, question=self.question)

		response = self.client.get(
			reverse("quizzes:topic-list", args=["math", "algebra"])
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["topic"], self.topic)
		self.assertEqual(list(response.context["quizzes"]), [quiz])

	def test_quiz_detail_includes_next_lesson_and_medium_quiz(self):
		quiz = Quiz.objects.create(
			title="Algebra quiz",
			subject=self.subject,
			topic=self.topic,
			lesson=self.lesson,
		)
		medium_quiz = Quiz.objects.create(
			title="Medium Algebra quiz",
			subject=self.subject,
			topic=self.topic,
			lesson=self.lesson,
		)

		response = self.client.get(reverse("quizzes:detail", args=[quiz.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["next_lesson"], self.other_lesson)
		self.assertEqual(response.context["medium_quiz"], medium_quiz)

	def test_lesson_quiz_page_returns_404_when_no_quiz_exists(self):
		response = self.client.get(reverse("quizzes:lesson-list", args=[self.other_lesson.pk]))

		self.assertEqual(response.status_code, 404)

	def test_authenticated_quiz_index_displays_owned_completed_attempt(self):
		quiz = Quiz.objects.create(
			title="Algebra quiz",
			subject=self.subject,
			topic=self.topic,
			lesson=self.lesson,
		)
		user = User.objects.create_user(username="student", password="test-password")
		attempt = QuizAttempt.objects.create(
			user=user,
			quiz=quiz,
			total_questions=1,
			completed_at=timezone.now(),
		)
		self.client.force_login(user)

		response = self.client.get(reverse("quizzes:list"), {"attempt": str(attempt.pk)})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["result_attempt"], attempt)
