from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

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

	def _import(self, name, payload):
		subject = Subject.objects.get_or_create(name="Mathematics", code="MATH")[0]
		created, errors = import_lessons(subject, [SimpleUploadedFile(name, payload)], publish=True)
		self.assertEqual(errors, [])
		return Lesson.objects.get(subject=subject)

	def test_html_keeps_educational_formatting_and_safe_links(self):
		lesson = self._import(
			"ok.html",
			b'<html><body><h1>Binary</h1><h2>Bits</h2><p>A <strong>bit</strong> is <em>0</em> or 1.</p>'
			b'<ul><li>one</li></ul><ol><li>two</li></ol>'
			b'<a href="https://example.com/x">link</a><table><tr><td>1</td></tr></table></body></html>',
		)

		self.assertEqual(lesson.title, "Binary")
		for keep in ("<h2>Bits</h2>", "<strong>bit</strong>", "<em>0</em>", "<ul><li>one</li></ul>",
					 "<ol><li>two</li></ol>", 'href="https://example.com/x"', "<td>1</td>"):
			self.assertIn(keep, lesson.content)

	def test_html_payloads_do_not_survive_import_or_render(self):
		payloads = (
			b"<p>x</p><img src=x onerror=alert(1)>",
			b'<p><a href="javascript:alert(1)">x</a><a href=" JaVaScRiPt:alert(1)">y</a></p>',
			b"<p>x</p><script>alert(1)</script><style>@import 'x'</style>",
			b'<p onclick="alert(1)" style="x" onmouseover=alert(1)>x</p><iframe src="//evil"></iframe>',
			b'<p>ok</p><object data="x"></object><embed src="x"><svg onload=alert(1)></svg><form action="x"><input></form>',
		)
		for n, payload in enumerate(payloads):
			Lesson.objects.all().delete()
			lesson = self._import(f"p{n}.html", payload)
			rendered = lesson.content
			for bad in ("onerror", "onclick", "onload", "onmouseover", "javascript:", "<script",
						"<iframe", "<object", "<embed", "<svg", "<form", "<style", "style="):
				self.assertNotIn(bad, rendered.lower(), payload)

	def test_served_lesson_page_contains_no_executable_payload(self):
		subject = Subject.objects.create(name="Mathematics", code="MATH")
		import_lessons(subject, [SimpleUploadedFile(
			"evil.html", b'<h1>Evil</h1><p>hi</p><img src=x onerror=alert(1)><script>alert(1)</script>'
			b'<a href="javascript:alert(1)">go</a>')], publish=True)
		lesson = Lesson.objects.get(subject=subject)

		response = self.client.get(reverse("subjects:lesson-detail", kwargs={
			"subject_slug": "mathematics", "lesson_slug": lesson.slug}))

		self.assertContains(response, "<p>hi</p>", html=True)
		body = response.content.decode().lower()
		self.assertNotIn("onerror=alert", body)
		self.assertNotIn("javascript:alert", body)
		self.assertNotIn("<script>alert(1)", body)

	def test_txt_escapes_markup_and_keeps_paragraphs(self):
		lesson = self._import("t.txt", b"Title\n\n<script>alert(1)</script>\nline two\n\n<img src=x onerror=alert(1)>")

		self.assertNotIn("<script", lesson.content)
		self.assertNotIn("<img", lesson.content)
		self.assertIn("&lt;script&gt;", lesson.content)
		self.assertEqual(lesson.content.count("<p>"), 3)
		self.assertIn("<br>", lesson.content)


class LessonSaveSanitizeTests(TestCase):
	def test_save_strips_scripts_but_keeps_editor_styles(self):
		subject = Subject.objects.create(name="IT", code="IT")
		lesson = Lesson.objects.create(
			subject=subject, title="Safe", lesson_number=1,
			content='<p style="color:red">Hi</p><script>alert(1)</script><a href="javascript:alert(1)">x</a>',
		)
		self.assertIn('style="color:red"', lesson.content)
		self.assertNotIn("script", lesson.content)
		self.assertNotIn("javascript:", lesson.content)


class OptimizeImagesFilterTests(TestCase):
	def test_filter_strips_scripts_even_for_unsanitized_stored_content(self):
		from apps.lessons.templatetags.lesson_extra import optimize_images

		out = optimize_images('<p onclick="x()">Hi</p><script>alert(1)</script>')

		self.assertNotIn("<script", out)
		self.assertNotIn("onclick", out)
		self.assertIn("Hi", out)


class LessonQuizActionTests(TestCase):
	def test_action_generates_inactive_quizzes_and_reports_shortages(self):
		from django.contrib.auth import get_user_model

		from apps.questions.models import Question
		from apps.quizzes.models import Quiz
		from apps.subjects.models import Topic

		self.client.force_login(get_user_model().objects.create_superuser("boss", "b@example.com", "pw"))
		subject = Subject.objects.create(name="Information Technology", code="IT")
		topic = Topic.objects.create(subject=subject, name="Hardware", slug="hardware")
		lesson = Lesson.objects.create(subject=subject, title="Memory", content="<p>x</p>")
		for i in range(2):
			Question.objects.create(subject=subject, topic=topic, lesson=lesson, text=f"Q{i}", difficulty="easy")
		url = reverse("admin:lessons_lesson_changelist")
		form = {"action": "generate_quizzes", "_selected_action": [lesson.id], "easy": 3, "medium": "", "hard": ""}

		response = self.client.post(url, form, follow=True)
		self.assertContains(response, "Easy: 2 of 3 eligible")
		self.assertFalse(Quiz.objects.exists())

		response = self.client.post(url, {**form, "allow_partial": "on"}, follow=True)
		quiz = Quiz.objects.get()
		self.assertEqual((quiz.topic, quiz.difficulty, quiz.is_active, quiz.questions.count()), (topic, "easy", False, 2))
		self.assertContains(response, "inactive quizzes")
