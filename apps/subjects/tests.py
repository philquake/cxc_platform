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


class SubjectViewTests(TestCase):
    def test_subject_list_and_detail_include_active_content(self):
        subject = Subject.objects.create(name="Mathematics", code="MATH")
        Subject.objects.create(name="Archived Science", code="SCI", is_active=False)
        active_lesson = Lesson.objects.create(
            subject=subject,
            title="Algebra",
            slug="algebra",
            content="<p>Algebra</p>",
        )
        Lesson.objects.create(
            subject=subject,
            title="Archived",
            slug="archived",
            content="<p>Archived</p>",
            is_active=False,
            lesson_number=2,
        )

        list_response = self.client.get(reverse("subjects:list"))
        detail_response = self.client.get(reverse("subjects:detail", args=["math"]))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list(list_response.context["subjects"]), [subject])
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.context["subject"].active_lessons, [active_lesson])

    def test_inactive_subject_is_not_publicly_available(self):
        Subject.objects.create(name="Archived Science", code="SCI", is_active=False)

        response = self.client.get(reverse("subjects:detail", args=["science"]))

        self.assertEqual(response.status_code, 404)
