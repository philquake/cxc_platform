from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.core.storage import SeekSafeCloudinaryStorage
from apps.lessons.models import Lesson
from apps.questions.models import Question
from apps.subjects.models import Subject, Topic

from apps.lessons.models import Lesson
from apps.questions.models import Answer, Question
from apps.subjects.models import Topic


class CoreViewTests(TestCase):
	def test_home_lists_only_active_subjects(self):
		active = Subject.objects.create(name="Mathematics", code="MATH")
		Subject.objects.create(name="Archived Science", code="SCI", is_active=False)

		response = self.client.get(reverse("home"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(list(response.context["subjects"]), [active])

	def test_legal_pages_render(self):
		for page_name in ("terms", "privacy"):
			with self.subTest(page=page_name):
				self.assertEqual(self.client.get(reverse(page_name)).status_code, 200)

	def test_ads_txt_is_served_as_plain_text(self):
		response = self.client.get("/ads.txt")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response["Content-Type"], "text/plain")
		self.assertTrue(b"google.com" in b"".join(response.streaming_content))

	def test_storage_rewinds_upload_before_saving_and_uploading(self):
		storage = SeekSafeCloudinaryStorage()
		content = SimpleUploadedFile("lesson.png", b"image-data")
		content.seek(4)

		with patch("cloudinary_storage.storage.MediaCloudinaryStorage._save") as save:
			storage._save("lesson.png", content)
			self.assertEqual(content.tell(), 0)
			save.assert_called_once_with("lesson.png", content)

		content.seek(4)
		with patch("cloudinary_storage.storage.MediaCloudinaryStorage._upload") as upload:
			storage._upload("lesson.png", content)
			self.assertEqual(content.tell(), 0)
			upload.assert_called_once_with("lesson.png", content)

	def test_search_returns_empty_results_without_a_query(self):
		response = self.client.get(reverse("search"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["query"], "")
		self.assertEqual(response.context["lesson_results"], [])
		self.assertEqual(response.context["question_results"], [])

	def test_search_matches_active_lessons_and_questions(self):
		subject = Subject.objects.create(name="Mathematics", code="MATH")
		topic = Topic.objects.create(subject=subject, name="Algebra", slug="algebra")
		lesson = Lesson.objects.create(
			subject=subject,
			title="Linear equations",
			content="Solve the equation",
		)
		question = Question.objects.create(
			subject=subject,
			topic=topic,
			lesson=lesson,
			text="Solve for x",
			explanation="Use a linear equation",
		)
		Lesson.objects.create(
			subject=subject,
			title="Archived equation",
			content="Linear equation",
			lesson_number=2,
			is_active=False,
		)

		with patch("apps.core.views.connection", SimpleNamespace(vendor="sqlite")):
			response = self.client.get(reverse("search"), {"q": "  equation  "})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["query"], "equation")
		self.assertEqual(response.context["lesson_results"], [lesson])
		self.assertEqual(response.context["question_results"], [question])

	def test_search_returns_lesson_and_question_matches_and_excludes_inactive(self):
		subject = Subject.objects.create(name="Mathematics", code="MATH")
		topic = Topic.objects.create(subject=subject, name="Algebra", slug="algebra")
		active_lesson = Lesson.objects.create(
			subject=subject,
			title="Quadratic equations",
			slug="quadratic-equations",
			content="<p>Learn how quadratic equations are solved.</p>",
		)
		inactive_lesson = Lesson.objects.create(
			subject=subject,
			title="Archived lesson",
			slug="archived-lesson",
			lesson_number=2,
			section_number=2,
			content="<p>Quadratic equations are explained here.</p>",
			is_active=False,
		)
		active_question = Question.objects.create(
			subject=subject,
			topic=topic,
			lesson=active_lesson,
			text="How do you solve a quadratic equation?",
		)
		Answer.objects.create(question=active_question, text="Use factoring or the quadratic formula", is_correct=True)
		inactive_question = Question.objects.create(
			subject=subject,
			topic=topic,
			lesson=inactive_lesson,
			text="How do you solve a cubic equation?",
			is_active=False,
		)
		Answer.objects.create(question=inactive_question, text="Use a calculator", is_correct=True)

		response = self.client.get(reverse("search"), {"q": "quadratic equation"})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, active_lesson.title)
		self.assertContains(response, active_question.text)
		self.assertNotContains(response, inactive_lesson.title)
		self.assertNotContains(response, inactive_question.text)
