from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db import connection
from unittest import mock

from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.lessons.models import Lesson
from apps.progress.models import QuizAttempt
from apps.questions.models import Answer, Question
from apps.subjects.models import Subject, Topic

from apps.quizzes.models import Quiz, QuizQuestion
from apps.quizzes.services import generate_lesson_quizzes, generate_mock_exam


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

	def test_mock_exam_distributes_rounding_remainder(self):
		topics = [self.topic]
		for slug in ("geometry", "statistics"):
			topics.append(Topic.objects.create(subject=self.subject, name=slug, slug=slug, exam_weight=1))
		self.topic.exam_weight = 1
		self.topic.save(update_fields=["exam_weight"])
		for topic in topics:
			for number in range(5):
				Question.objects.create(
					subject=self.subject,
					topic=topic,
					lesson=self.lesson,
					text=f"{topic.slug} {number}",
				)

		quiz, topic_counts = generate_mock_exam(self.subject, 10, 60)

		self.assertEqual(quiz.quiz_questions.count(), 10)
		self.assertEqual(sorted(topic_counts.values()), [3, 3, 4])

	def test_mock_exam_rolls_back_if_questions_cannot_be_saved(self):
		from unittest import mock

		with mock.patch("apps.quizzes.services.QuizQuestion.objects.bulk_create", side_effect=RuntimeError):
			with self.assertRaises(RuntimeError):
				generate_mock_exam(self.subject, 1, 30)
		self.assertFalse(Quiz.objects.filter(is_mock=True).exists())

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
		self.assertNotContains(response, "data-time-limit-minutes")

		response = self.client.get(reverse("quizzes:detail", args=[mock.pk]))

		self.assertContains(response, 'data-time-limit-minutes="45"')

	def test_listing_skips_questions_and_batches_attempt_queries(self):
		user = User.objects.create_user(username="lister", password="test-password")
		for n in range(3):
			quiz = Quiz.objects.create(
				title=f"Quiz {n}", subject=self.subject, topic=self.topic, lesson=self.lesson
			)
			QuizQuestion.objects.create(quiz=quiz, question=self.question)
			QuizAttempt.objects.create(
				user=user, quiz=quiz, score=1, total_questions=1, total_marks=1, completed_at=timezone.now()
			)
		self.client.force_login(user)

		with CaptureQueriesContext(connection) as ctx:
			response = self.client.get(reverse("quizzes:list"))

		self.assertContains(response, "1 question")
		self.assertNotContains(response, self.question.text)
		self.assertContains(response, "Last attempt: 1 of 1")
		self.assertEqual(len([q for q in ctx.captured_queries if "progress_quizattempt" in q["sql"]]), 1)
		self.assertFalse([q for q in ctx.captured_queries if "questions_answer" in q["sql"]])

	def test_detail_renders_questions_and_other_users_attempts_stay_hidden(self):
		quiz = Quiz.objects.create(
			title="Algebra quiz", subject=self.subject, topic=self.topic, lesson=self.lesson
		)
		QuizQuestion.objects.create(quiz=quiz, question=self.question)
		other = User.objects.create_user(username="other", password="test-password")
		QuizAttempt.objects.create(
			user=other, quiz=quiz, score=1, total_questions=1, total_marks=1, completed_at=timezone.now()
		)
		self.client.force_login(User.objects.create_user(username="me", password="test-password"))

		response = self.client.get(reverse("quizzes:detail", args=[quiz.pk]))

		self.assertContains(response, self.question.text)
		self.assertNotContains(response, "Last attempt")

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

	def test_quiz_detail_includes_next_lesson_and_other_quiz(self):
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
		self.assertEqual(response.context["other_quiz"], medium_quiz)

		# A quiz on a hidden lesson can't be opened, so it is never suggested.
		medium_quiz.lesson = self.other_lesson
		medium_quiz.save()
		self.other_lesson.is_active = False
		self.other_lesson.save()
		self.assertIsNone(self.client.get(reverse("quizzes:detail", args=[quiz.pk])).context["other_quiz"])

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
			total_questions=1, total_marks=1,
			completed_at=timezone.now(),
		)
		self.client.force_login(user)

		response = self.client.get(reverse("quizzes:list"), {"attempt": str(attempt.pk)})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["result_attempt"], attempt)


class MockExamTimeMultiplierTests(TestCase):
	def setUp(self):
		self.subject = Subject.objects.create(name="Mathematics", code="MATH")
		self.mock = Quiz.objects.create(
			title="Timed mock",
			subject=self.subject,
			is_mock=True,
			time_limit_minutes=60,
		)
		self.user = User.objects.create_user("student", password="A-strong-password-123")

	def _timer_minutes(self):
		response = self.client.get(reverse("quizzes:detail", args=[self.mock.id]))
		self.assertEqual(response.status_code, 200)
		return response

	def test_default_multiplier_keeps_time_limit(self):
		self.client.force_login(self.user)
		response = self._timer_minutes()
		self.assertContains(response, 'data-time-limit-minutes="60"')

	def test_profile_multiplier_extends_time_limit(self):
		from decimal import Decimal
		from apps.accounts.models import Profile

		Profile.objects.create(user=self.user, time_multiplier=Decimal("1.25"))
		self.client.force_login(self.user)
		response = self._timer_minutes()
		self.assertContains(response, 'data-time-limit-minutes="75"')
		self.assertContains(response, "includes your extra time")

	def test_anonymous_user_gets_base_time_limit(self):
		response = self._timer_minutes()
		self.assertContains(response, 'data-time-limit-minutes="60"')


class LessonQuizGeneratorTests(TestCase):
	def setUp(self):
		self.subject = Subject.objects.create(name="Information Technology", code="IT")
		self.topic = Topic.objects.create(subject=self.subject, name="Hardware", slug="hardware")
		self.lesson = Lesson.objects.create(subject=self.subject, title="Memory", slug="memory", content="<p>RAM</p>")
		self.other_lesson = Lesson.objects.create(
			subject=self.subject, title="Storage", slug="storage", content="<p>Disks</p>", lesson_number=2
		)

	def make(self, difficulty, fmt, count=1, lesson=None, **extra):
		return [
			Question.objects.create(
				subject=self.subject, topic=self.topic, lesson=lesson or self.lesson, text=f"{difficulty} {fmt} {i}",
				difficulty=difficulty, format=fmt, expected_answer="x", **extra,
			)
			for i in range(count)
		]

	def formats(self, quiz):
		return set(quiz.questions.values_list("format", flat=True))

	def test_each_difficulty_gets_only_its_allowed_formats(self):
		easy = self.make("easy", Question.FORMAT_MULTIPLE_CHOICE, 3)
		self.make("easy", Question.FORMAT_TRUE_FALSE, 3)  # wrong format for easy
		self.make("medium", Question.FORMAT_TRUE_FALSE, 2)
		self.make("medium", Question.FORMAT_SHORT_ANSWER, 2)
		self.make("medium", Question.FORMAT_MATCHING, 2)  # not allowed in medium
		self.make("hard", Question.FORMAT_WORDED, 2)
		self.make("hard", Question.FORMAT_MULTIPLE_CHOICE, 2)  # not allowed in hard
		quizzes, shortages = generate_lesson_quizzes(self.topic, self.lesson, {"easy": 3, "medium": 4, "hard": 2})
		by_difficulty = {quiz.difficulty: quiz for quiz in quizzes}
		self.assertEqual(shortages, [])
		self.assertEqual(set(by_difficulty["easy"].questions.all()), set(easy))
		self.assertEqual(self.formats(by_difficulty["medium"]), {Question.FORMAT_TRUE_FALSE, Question.FORMAT_SHORT_ANSWER})
		self.assertEqual(self.formats(by_difficulty["hard"]), {Question.FORMAT_WORDED})
		for quiz in quizzes:
			self.assertFalse(quiz.is_active)
			self.assertEqual((quiz.topic, quiz.lesson), (self.topic, self.lesson))
			quiz.full_clean()

	def test_filters_by_lesson_pathway_and_active_and_never_duplicates(self):
		wanted = self.make("easy", Question.FORMAT_MULTIPLE_CHOICE, 2, for_guided=True)
		self.make("easy", Question.FORMAT_MULTIPLE_CHOICE, 2, lesson=self.other_lesson)
		self.make("easy", Question.FORMAT_MULTIPLE_CHOICE, 2, for_guided=False)
		self.make("easy", Question.FORMAT_MULTIPLE_CHOICE, 2, is_active=False)
		(quiz,), _ = generate_lesson_quizzes(self.topic, self.lesson, {"easy": 2}, pathway="guided")
		self.assertEqual(quiz.pathway, "guided")
		self.assertEqual(sorted(quiz.questions.values_list("pk", flat=True)), sorted(q.pk for q in wanted))

	def test_shortage_raises_with_counts_unless_partial_allowed(self):
		self.make("easy", Question.FORMAT_MULTIPLE_CHOICE, 2)
		self.make("hard", Question.FORMAT_WORDED, 1)
		with self.assertRaisesMessage(ValueError, "Easy: 2 of 5 eligible; Medium: 0 of 2 eligible; Hard: 1 of 3 eligible"):
			generate_lesson_quizzes(self.topic, self.lesson, {"easy": 5, "medium": 2, "hard": 3})
		self.assertFalse(Quiz.objects.exists())
		quizzes, shortages = generate_lesson_quizzes(
			self.topic, self.lesson, {"easy": 5, "medium": 2, "hard": 3}, allow_partial=True
		)
		self.assertEqual([quiz.quiz_questions.count() for quiz in quizzes], [2, 1])  # medium has none, so skipped
		self.assertEqual(len(shortages), 3)

	def test_rejects_topic_from_another_subject(self):
		other = Topic.objects.create(subject=Subject.objects.create(name="Maths", code="MATH"), name="Algebra", slug="algebra")
		with self.assertRaises(ValueError):
			generate_lesson_quizzes(other, self.lesson, {"easy": 1})

	def test_failure_mid_creation_rolls_back_every_quiz(self):
		self.make("easy", Question.FORMAT_MULTIPLE_CHOICE)
		self.make("hard", Question.FORMAT_WORDED)
		real = QuizQuestion.objects.bulk_create
		calls = []

		def fail_second(*args, **kwargs):
			calls.append(1)
			if len(calls) == 2:
				raise RuntimeError("boom")
			return real(*args, **kwargs)

		with mock.patch.object(QuizQuestion.objects, "bulk_create", side_effect=fail_second):
			with self.assertRaises(RuntimeError):
				generate_lesson_quizzes(self.topic, self.lesson, {"easy": 1, "hard": 1})
		self.assertFalse(Quiz.objects.exists())
		self.assertFalse(QuizQuestion.objects.exists())

	def test_unshuffled_quiz_keeps_set_order(self):
		questions = self.make("easy", Question.FORMAT_MULTIPLE_CHOICE, 6)
		quiz = Quiz.objects.create(
			subject=self.subject, topic=self.topic, lesson=self.lesson, title="Fixed", shuffle_questions=False
		)
		for order, question in enumerate(reversed(questions)):
			QuizQuestion.objects.create(quiz=quiz, question=question, order=order)
		page = self.client.get(reverse("quizzes:detail", args=[quiz.id])).content.decode()
		positions = [page.index(f"easy multiple_choice {i}<") for i in reversed(range(6))]
		self.assertEqual(positions, sorted(positions))
