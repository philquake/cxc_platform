from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.lessons.importers import import_lessons

from apps.lessons.models import Lesson, LessonImage
from apps.subjects.models import Subject


class LessonModelTests(TestCase):
	def test_lesson_generates_slug_from_title(self):
		subject = Subject.objects.create(name="Mathematics", code="MATH")

		lesson = Lesson.objects.create(
			subject=subject,
			title="Logic Gates",
			content="<p>Logic gates</p>",
		)

		self.assertEqual(lesson.slug, "logic-gates")
		self.assertEqual(str(lesson), "Logic Gates")

	def test_lesson_image_string_includes_lesson_and_display_order(self):
		subject = Subject.objects.create(name="Mathematics", code="MATH")
		lesson = Lesson.objects.create(
			subject=subject,
			title="Logic Gates",
			content="<p>Logic gates</p>",
		)
		image = LessonImage.objects.create(
			lesson=lesson,
			image="lesson_images/gate.png",
			order=1,
		)

		self.assertEqual(str(image), "Logic Gates image 2")


class LessonImporterTests(TestCase):
	def test_txt_and_html_import_strips_script_vectors(self):
		subject = Subject.objects.create(name="Mathematics", code="MATH")
		payload = b'<h1>Evil</h1><img src=x/onerror=alert(1)><a href="javascript:alert(1)">x</a><script>bad()</script>'
		uploads = [
			SimpleUploadedFile("a.html", payload),
			SimpleUploadedFile("b.txt", b"Plain Title\n\nBody <b>text</b>"),
		]

		created, errors = import_lessons(subject, uploads, publish=True)

		self.assertEqual(errors, [])
		self.assertEqual(len(created), 2)
		html_lesson = Lesson.objects.get(subject=subject, lesson_number=1)
		for bad in (" onerror", "javascript:", "<script"):
			self.assertNotIn(bad, html_lesson.content)
		self.assertIn("&lt;b&gt;", Lesson.objects.get(lesson_number=2).content)
