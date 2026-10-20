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


class SubjectDetailProgressTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name="Mathematics", code="MATH")
        self.first = Lesson.objects.create(
            subject=self.subject, title="Number sense", slug="number-sense", lesson_number=1, content="x"
        )
        self.second = Lesson.objects.create(
            subject=self.subject, title="Algebra", slug="algebra", lesson_number=2, content="x"
        )
        self.url = reverse("subjects:detail", args=["mathematics"])

    def test_signed_in_student_sees_progress_and_next_lesson(self):
        user = User.objects.create_user("student", password="A-strong-password-123")
        LessonProgress.objects.create(user=user, lesson=self.first, completed=True, completed_at=timezone.now())
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertContains(response, "1 of 2 lessons complete")
        self.assertContains(response, "Continue: Algebra")
        self.assertEqual(response.context["next_lesson"], self.second)

    def test_anonymous_visitor_sees_lessons_without_progress(self):
        response = self.client.get(self.url)

        self.assertContains(response, "Number sense")
        self.assertNotContains(response, "lessons complete")

    def test_missing_page_shows_helpful_404(self):
        response = self.client.get("/definitely-not-a-page/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "We can't find that page", status_code=404)


class LessonPagerTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name="Mathematics", code="MATH")
        self.lessons = [
            Lesson.objects.create(
                subject=self.subject, title=title, slug=slug, lesson_number=number, content="x"
            )
            for number, (title, slug) in enumerate(
                [("Number sense", "number-sense"), ("Algebra", "algebra"), ("Geometry", "geometry")],
                start=1,
            )
        ]

    def _get(self, slug):
        return self.client.get(reverse("subjects:lesson-detail", args=["mathematics", slug]))

    def test_middle_lesson_links_to_previous_and_next(self):
        response = self._get("algebra")

        self.assertEqual(response.context["previous_lesson"], self.lessons[0])
        self.assertEqual(response.context["next_lesson"], self.lessons[2])
        self.assertEqual(response.context["lesson_position"], 2)
        self.assertContains(response, 'rel="next"')
        self.assertContains(response, "Geometry")

    def test_first_lesson_has_no_previous_link(self):
        response = self._get("number-sense")

        self.assertIsNone(response.context["previous_lesson"])
        self.assertNotContains(response, 'rel="prev"')

    def test_last_lesson_points_back_to_the_subject(self):
        response = self._get("geometry")

        self.assertIsNone(response.context["next_lesson"])
        self.assertContains(response, "Back to course")


class LessonMasteryTests(TestCase):
    def test_best_quiz_score_sets_mastery_level_and_unit_progress(self):
        user = User.objects.create_user("student", password="pw")
        subject = Subject.objects.create(name="Mathematics", code="MATH")
        topic = Topic.objects.create(subject=subject, name="Number", slug="number")
        lesson = Lesson.objects.create(
            subject=subject, title="Number sense", slug="number-sense",
            lesson_number=1, section_number=1, section_title="Foundations", content="x",
        )
        quiz = Quiz.objects.create(
            subject=subject, topic=topic, lesson=lesson, title="Number quiz"
        )
        for score in (3, 9):
            QuizAttempt.objects.create(
                user=user, quiz=quiz, score=score, total_questions=10,
                completed_at=timezone.now(),
            )
        self.client.force_login(user)

        response = self.client.get(reverse("subjects:detail", kwargs={"slug": "mathematics"}))

        unit = response.context["units"][0]
        self.assertEqual(unit["title"], "Foundations")
        self.assertEqual(unit["lessons"][0].mastery_level, "proficient")
        self.assertEqual(unit["lessons"][0].mastery_step, 3)
        self.assertEqual(response.context["mastered_total"], 1)
