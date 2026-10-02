from django.test import TestCase

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
