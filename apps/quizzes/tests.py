from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.lessons.models import Lesson
from apps.questions.models import Answer, Question
from apps.subjects.models import Subject, Topic

from apps.quizzes.models import Quiz, QuizQuestion


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
