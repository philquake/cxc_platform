from django.test import TestCase
from django.urls import reverse

from apps.lessons.models import Lesson
from apps.subjects.models import Subject


class LessonDetailTemplateTests(TestCase):
    def test_lesson_detail_page_renders(self):
        subject = Subject.objects.create(
            name="Cape Computer Science Unit 1",
            code="CAPE-UNIT-1",
        )
        Lesson.objects.create(
            subject=subject,
            title="Logic Gates",
            slug="logic-gates",
            lesson_number=1,
            content="<p>Logic gates are foundational.</p>",
        )

        response = self.client.get(
            reverse(
                "subjects:lesson-detail",
                kwargs={
                    "subject_slug": "cape-computer-science-unit-1",
                    "lesson_slug": "logic-gates",
                },
            )
        )

        self.assertEqual(response.status_code, 200)
