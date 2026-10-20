from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.lessons.models import Lesson
from apps.progress.models import QuizAnswer, QuizAttempt
from apps.quizzes.models import Quiz
from apps.subjects.models import Subject, Topic

from .models import Answer, Question


class QuestionAnalyticsAdminTests(TestCase):
	def test_question_admin_shows_accuracy_flag_and_distractor_picks(self):
		staff = get_user_model().objects.create_superuser(
			username="admin",
			password="admin-password",
			email="admin@example.com",
		)
		subject = Subject.objects.create(name="Mathematics", code="MATH")
		topic = Topic.objects.create(subject=subject, name="Algebra", slug="algebra")
		lesson = Lesson.objects.create(
			subject=subject,
			title="Algebra",
			slug="algebra",
			content="Algebra",
		)
		question = Question.objects.create(
			subject=subject,
			topic=topic,
			lesson=lesson,
			text="What is 2 + 2?",
		)
		correct_answer = Answer.objects.create(
			question=question,
			text="4",
			is_correct=True,
		)
		dominant_distractor = Answer.objects.create(question=question, text="5")
		other_distractor = Answer.objects.create(question=question, text="6")
		quiz = Quiz.objects.create(
			subject=subject,
			topic=topic,
			lesson=lesson,
			title="Algebra quiz",
		)
		student = get_user_model().objects.create_user(username="student")
		for index in range(10):
			attempt = QuizAttempt.objects.create(
				user=student,
				quiz=quiz,
				total_questions=1,
				completed_at=timezone.now(),
			)
			is_correct = index == 0
			QuizAnswer.objects.create(
				attempt=attempt,
				question=question,
				selected_answer=(
					correct_answer
					if is_correct
					else dominant_distractor if index < 8 else other_distractor
				),
				is_correct=is_correct,
			)
		self.client.force_login(staff)

		response = self.client.get(
			reverse("admin:questions_question_change", args=[question.id])
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "10.0% (10)")
		self.assertContains(response, "Review: below 20% correct")
		self.assertContains(response, "5")
		self.assertContains(response, "7")
		self.assertContains(response, "70%")


class AdminImportTests(TestCase):
	def setUp(self):
		self.admin = get_user_model().objects.create_superuser("boss", "b@example.com", "pw")
		self.client.force_login(self.admin)
		self.subject = Subject.objects.create(name="Mathematics", code="MATH")
		self.topic = Topic.objects.create(subject=self.subject, name="Algebra", slug="algebra")
		self.lesson = Lesson.objects.create(subject=self.subject, title="Intro", lesson_number=1, content="<p>x</p>")

	def _upload(self, name, body):
		from django.core.files.uploadedfile import SimpleUploadedFile
		return SimpleUploadedFile(name, body.encode())

	def test_question_csv_import_creates_questions_and_answers(self):
		csv_text = (
			"subject,topic,lesson,format,text,option_1,option_2,correct,expected_answer\n"
			"MATH,Algebra,1,multiple_choice,2+2?,3,4,b,\n"
			"MATH,Algebra,1,true_false,1>0,,,true,\n"
			"MATH,Algebra,1,short_answer,Name x,,,,unknown\n"
		)
		response = self.client.post(
			reverse("admin:questions_question_import"), {"file": self._upload("q.csv", csv_text)}
		)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(Question.objects.count(), 3)
		mc = Question.objects.get(format="multiple_choice")
		self.assertEqual(mc.answers.get(is_correct=True).text, "4")

	def test_question_csv_import_is_all_or_nothing(self):
		csv_text = (
			"subject,topic,lesson,format,text,option_1,option_2,correct\n"
			"MATH,Algebra,1,multiple_choice,Good?,a,b,1\n"
			"MATH,Nope,1,multiple_choice,Bad?,a,b,1\n"
		)
		response = self.client.post(
			reverse("admin:questions_question_import"), {"file": self._upload("q.csv", csv_text)}
		)
		self.assertContains(response, "Row 3")
		self.assertEqual(Question.objects.count(), 0)

	def test_lesson_import_numbers_and_titles_from_files(self):
		html = "<h1>Networks</h1><p>Body</p><script>x</script>"
		response = self.client.post(
			reverse("admin:lessons_lesson_import"),
			{"subject": self.subject.pk, "files": [self._upload("a.html", html), self._upload("b_notes.txt", "Hi")]},
		)
		self.assertEqual(response.status_code, 200)
		lessons = Lesson.objects.filter(subject=self.subject).order_by("lesson_number")
		self.assertEqual([l.lesson_number for l in lessons], [1, 2, 3])
		self.assertEqual(lessons[1].title, "Networks")
		self.assertNotIn("script", lessons[1].content)
		self.assertEqual(lessons[2].title, "B Notes")
		self.assertFalse(lessons[2].is_active)

	def test_changelists_show_import_buttons(self):
		self.assertContains(self.client.get(reverse("admin:questions_question_changelist")), "Import questions")
		self.assertContains(self.client.get(reverse("admin:lessons_lesson_changelist")), "Upload notes")
		self.assertContains(self.client.get(reverse("admin:index")), "Upload notes")
