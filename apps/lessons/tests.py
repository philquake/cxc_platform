from django.test import TestCase

from apps.lessons.models import Lesson
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
