from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.lessons.models import Lesson
from apps.progress.models import LessonProgress, QuizAttempt
from apps.quizzes.models import Quiz
from apps.subjects.models import Subject, Topic


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

    def test_subject_detail_accepts_subject_name_slug(self):
        subject = Subject.objects.create(name="Cape Computer Science", code="CAPE-CS")

        response = self.client.get(reverse("subjects:detail", args=["cape-computer-science"]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["subject"], subject)
        self.assertEqual(str(subject), "Cape Computer Science")

    def test_lesson_detail_returns_404_for_missing_subject_or_inactive_lesson(self):
        missing_subject = self.client.get(
            reverse("subjects:lesson-detail", args=["missing-subject", "lesson"])
        )
        subject = Subject.objects.create(name="Mathematics", code="MATH")
        Lesson.objects.create(
            subject=subject,
            title="Archived",
            slug="archived",
            content="Archived",
            is_active=False,
        )

        inactive_lesson = self.client.get(
            reverse("subjects:lesson-detail", args=["mathematics", "archived"])
        )

        self.assertEqual(missing_subject.status_code, 404)
        self.assertEqual(inactive_lesson.status_code, 404)

    def test_authenticated_lesson_detail_includes_completed_progress_and_latest_attempt(self):
        subject = Subject.objects.create(name="Mathematics", code="MATH")
        topic = Topic.objects.create(subject=subject, name="Algebra", slug="algebra")
        lesson = Lesson.objects.create(
            subject=subject,
            title="Algebra",
            slug="algebra",
            content="Algebra",
        )
        quiz = Quiz.objects.create(
            title="Algebra quiz",
            subject=subject,
            topic=topic,
            lesson=lesson,
        )
        user = User.objects.create_user(username="student", password="test-password")
        progress = LessonProgress.objects.create(user=user, lesson=lesson, completed=True)
        attempt = QuizAttempt.objects.create(
            user=user,
            quiz=quiz,
            completed_at=timezone.now(),
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("subjects:lesson-detail", args=["mathematics", "algebra"])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["lesson_progress"], progress)
        self.assertEqual(list(response.context["quizzes"]), [quiz])
        self.assertEqual(response.context["quizzes"][0].latest_attempt, attempt)
