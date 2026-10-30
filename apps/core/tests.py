from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.core.storage import SeekSafeCloudinaryStorage
from apps.lessons.models import Lesson
from apps.questions.models import Answer, Question
from apps.subjects.models import Subject, Topic


class CoreViewTests(TestCase):
	def test_home_lists_only_active_subjects(self):
		active = Subject.objects.create(name="Mathematics", code="MATH")
		Subject.objects.create(name="Archived Science", code="SCI", is_active=False)

		response = self.client.get(reverse("home"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(list(response.context["subjects"]), [active])

	def test_home_offers_the_exam_countdown_only_when_there_are_lessons(self):
		subject = Subject.objects.create(name="Mathematics", code="MATH")
		self.assertNotContains(self.client.get(reverse("home")), 'id="exam-date"')

		Lesson.objects.create(subject=subject, title="Linear equations", content="Solve")
		response = self.client.get(reverse("home"))

		self.assertContains(response, 'id="exam-date"')
		self.assertEqual(response.context["lesson_max"], 1)

	def test_sitemap_lists_only_public_active_pages(self):
		subject = Subject.objects.create(name="Mathematics", code="MATH")
		hidden = Subject.objects.create(name="Hidden", code="HID", is_active=False)
		Lesson.objects.create(subject=subject, title="Linear equations", content="Solve")
		Lesson.objects.create(subject=subject, title="Draft", lesson_number=2, content="x", is_active=False)
		Lesson.objects.create(subject=hidden, title="Secret", content="x")

		body = self.client.get("/sitemap.xml").content.decode()

		for path in ("/", "/subjects/", "/terms/", "/privacy/", "/subjects/mathematics/", "/subjects/mathematics/lessons/linear-equations/"):
			self.assertIn(f"<loc>http://testserver{path}</loc>", body)
		for path in ("draft", "secret", "hidden", "/quizzes/", "/progress/", "/accounts/"):
			self.assertNotIn(path, body)

	def test_binary_converter_is_public_and_in_the_sitemap(self):
		response = self.client.get(reverse("binary-converter"))

		self.assertContains(response, "Binary converter")
		self.assertContains(response, '<link rel="canonical" href="http://testserver/tools/binary-converter/">')
		self.assertContains(response, 'id="panel-practice"')
		self.assertContains(response, "pagead2.googlesyndication.com")
		self.assertContains(self.client.get(reverse("tools")), reverse("binary-converter"))
		self.assertIn("<loc>http://testserver/tools/binary-converter/</loc>", self.client.get("/sitemap.xml").content.decode())

	def test_robots_txt_points_to_the_sitemap_and_hides_private_areas(self):
		body = self.client.get("/robots.txt").content.decode()

		self.assertIn("Sitemap: http://testserver/sitemap.xml", body)
		self.assertIn("Disallow: /admin/", body)

	def test_search_console_tag_only_when_token_is_set(self):
		tag = '<meta name="google-site-verification" content="abc123">'
		with self.settings(GOOGLE_SITE_VERIFICATION=""):
			self.assertNotContains(self.client.get(reverse("home")), "google-site-verification")
		with self.settings(GOOGLE_SITE_VERIFICATION="abc123"):
			self.assertContains(self.client.get(reverse("home")), tag, html=True)
		with self.settings(GOOGLE_SITE_VERIFICATION='<meta name="google-site-verification" content="abc123" />'):
			self.assertContains(self.client.get(reverse("home")), tag, html=True)

	def test_home_counts_only_active_lessons_and_questions(self):
		subject = Subject.objects.create(name="Mathematics", code="MATH")
		topic = Topic.objects.create(subject=subject, name="Algebra", slug="algebra")
		lesson = Lesson.objects.create(subject=subject, title="Linear equations", content="Solve")
		Lesson.objects.create(subject=subject, title="Archived", content="Old", lesson_number=2, is_active=False)
		for text, active in (("Solve for x", True), ("Solve for y", True), ("Old one", False)):
			Question.objects.create(
				subject=subject, topic=topic, lesson=lesson, text=text,
				explanation="Use a linear equation", is_active=active,
			)

		response = self.client.get(reverse("home"))

		listed = response.context["subjects"][0]
		self.assertEqual((listed.lesson_count, listed.question_count), (1, 2))
		self.assertContains(response, "1 lesson, 2 questions", html=False)

	def test_legal_pages_render(self):
		for page_name in ("terms", "privacy"):
			with self.subTest(page=page_name):
				self.assertEqual(self.client.get(reverse(page_name)).status_code, 200)

	def test_about_page_and_site_icons(self):
		self.assertContains(self.client.get(reverse("about")), "mailto:")
		home = self.client.get(reverse("home"))
		for needle in ("favicon.svg", "apple-touch-icon", "site.webmanifest", "theme-color"):
			self.assertContains(home, needle)

	def test_privacy_page_discloses_ad_cookies(self):
		self.assertContains(self.client.get(reverse("privacy")), "adssettings.google.com")

	def test_404_page_renders_without_ads(self):
		response = self.client.get("/no-such-page/")

		self.assertContains(response, "We can't find that page", status_code=404)
		self.assertNotContains(response, "adsbygoogle", status_code=404)
		self.assertContains(self.client.get(reverse("home")), "adsbygoogle")
		self.assertNotContains(self.client.get(reverse("search")), "adsbygoogle")

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
		# Active question on a hidden lesson: its result link would 404.
		Question.objects.create(
			subject=subject, topic=topic, lesson=inactive_lesson, text="Name the quadratic discriminant."
		)
		hidden = Subject.objects.create(name="Hidden", code="HID", is_active=False)
		Lesson.objects.create(subject=hidden, title="Hidden quadratic equations", content="<p>quadratic equation</p>")

		response = self.client.get(reverse("search"), {"q": "quadratic equation"})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, active_lesson.title)
		self.assertContains(response, active_question.text)
		self.assertNotContains(response, inactive_lesson.title)
		self.assertNotContains(response, inactive_question.text)
		self.assertNotContains(response, "quadratic discriminant")
		self.assertNotContains(response, "Hidden quadratic equations")
