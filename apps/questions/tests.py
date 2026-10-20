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
				total_questions=1, total_marks=1,
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

	def test_sample_csv_imports_marks_mark_scheme_and_hint(self):
		from .importers import import_questions, sample_csv

		it = Subject.objects.create(name="Information Technology", code="IT")
		Topic.objects.create(subject=it, name="Hardware", slug="hardware")
		Lesson.objects.create(subject=it, title="Hardware", lesson_number=1, content="<p>x</p>")
		count, errors = import_questions(self._upload("sample.csv", sample_csv()))
		self.assertEqual((count, errors), (5, []))
		worded = Question.objects.get(format=Question.FORMAT_WORDED)
		self.assertEqual((worded.marks, worded.estimated_time_minutes, worded.difficulty), (4, 4, "hard"))
		self.assertTrue(worded.mark_scheme and worded.hint)
		count, errors = import_questions(self._upload("bad.csv", "subject,topic,lesson,text,marks\nIT,Hardware,1,Q,two\n"))
		self.assertEqual(errors, ["Row 2: 'marks' must be a whole number"])

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


class QuestionAdminFilterTests(TestCase):
	def setUp(self):
		self.client.force_login(get_user_model().objects.create_superuser("boss", "b@example.com", "pw"))
		self.it = Subject.objects.create(name="Information Technology", code="IT")
		self.maths = Subject.objects.create(name="Mathematics", code="MATH")
		self.hardware = Topic.objects.create(subject=self.it, name="Hardware", slug="hardware")
		self.algebra = Topic.objects.create(subject=self.maths, name="Algebra", slug="algebra")
		self.it_lesson = Lesson.objects.create(subject=self.it, title="Memory", lesson_number=1, content="<p>x</p>")
		self.maths_lesson = Lesson.objects.create(subject=self.maths, title="Equations", lesson_number=1, content="<p>x</p>")
		self.ram = Question.objects.create(
			subject=self.it, topic=self.hardware, lesson=self.it_lesson, text="Which is volatile?",
			explanation="RAM loses data.", for_guided=False,
		)
		Answer.objects.create(question=self.ram, text="RAM chip", is_correct=True)
		Answer.objects.create(question=self.ram, text="RAM stick")
		self.bare = Question.objects.create(
			subject=self.maths, topic=self.algebra, lesson=self.maths_lesson, text="Solve x + 1 = 2",
			format=Question.FORMAT_WORDED, expected_answer="1",
		)
		self.quiz = Quiz.objects.create(subject=self.it, topic=self.hardware, lesson=self.it_lesson, title="Memory quiz")
		self.quiz.questions.add(self.ram)

	def changelist(self, query=""):
		response = self.client.get(reverse("admin:questions_question_changelist") + query)
		self.assertEqual(response.status_code, 200)
		return response

	def shown(self, query):
		return set(self.changelist(query).context["cl"].result_list)

	def test_topic_filter_lists_only_the_chosen_subjects_topics(self):
		response = self.changelist(f"?subject__id__exact={self.it.id}")
		topic_filter = next(spec for spec in response.context["cl"].filter_specs if getattr(spec, "parameter_name", None) == "topic")
		self.assertEqual([label for _, label in topic_filter.lookup_choices], ["Hardware"])
		self.assertEqual(self.shown(f"?topic={self.algebra.id}"), {self.bare})

	def test_new_filters_return_matching_questions(self):
		self.assertEqual(self.shown("?pathway=guided"), {self.bare})
		self.assertEqual(self.shown("?usage=unused"), {self.bare})
		self.assertEqual(self.shown("?usage=used"), {self.ram})
		self.assertEqual(self.shown("?gap=explanation"), {self.bare})
		self.assertEqual(self.shown("?gap=mark_scheme"), {self.bare})
		self.assertEqual(self.shown("?quality=none"), {self.ram, self.bare})

	def test_search_finds_answer_options_without_inflating_accuracy(self):
		student = get_user_model().objects.create_user(username="student")
		for is_correct in (True, False):
			attempt = QuizAttempt.objects.create(
				user=student, quiz=self.quiz, total_questions=1, total_marks=1, completed_at=timezone.now()
			)
			QuizAnswer.objects.create(attempt=attempt, question=self.ram, is_correct=is_correct)
		response = self.changelist("?q=RAM")
		self.assertEqual(list(response.context["cl"].result_list), [self.ram])
		self.assertContains(response, "50.0% (2)")
		self.assertEqual(self.shown(f"?q={self.bare.id}"), {self.bare})

	def test_activate_and_deactivate_actions(self):
		url = reverse("admin:questions_question_changelist")
		self.client.post(url, {"action": "deactivate_questions", "_selected_action": [self.ram.id, self.bare.id]})
		self.assertFalse(Question.objects.filter(is_active=True).exists())
		self.client.post(url, {"action": "activate_questions", "_selected_action": [self.ram.id]})
		self.assertEqual(list(Question.objects.filter(is_active=True)), [self.ram])
