from django.db import models
from django.core.exceptions import ValidationError
from apps.lessons.models import Lesson
from apps.questions.models import Question
from apps.subjects.models import Subject, Topic


class Quiz(models.Model):
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="quizzes",
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name="quizzes",
        null=True,
        blank=True,
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="quizzes",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    questions = models.ManyToManyField(
        Question,
        through="QuizQuestion",
        related_name="quizzes",
    )
    is_active = models.BooleanField(default=True)
    is_mock = models.BooleanField(default=False)
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(is_mock=True)
                    | (models.Q(topic__isnull=False) & models.Q(lesson__isnull=False))
                ),
                name="quiz_non_mock_requires_topic_lesson",
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        errors = {}
        if self.is_mock and (self.topic_id or self.lesson_id):
            errors["topic"] = "Mock exams cannot be attached to a single topic or lesson."
        if not self.is_mock and not self.topic_id:
            errors["topic"] = "Practice quizzes must belong to a topic."
        if not self.is_mock and not self.lesson_id:
            errors["lesson"] = "Practice quizzes must belong to a lesson."
        if self.lesson_id and self.subject_id and self.lesson.subject_id != self.subject_id:
            errors["subject"] = "The subject must match the lesson subject."
        if self.topic_id and self.subject_id and self.topic.subject_id != self.subject_id:
            errors["topic"] = "The topic must belong to the selected subject."
        if errors:
            raise ValidationError(errors)


class QuizQuestion(models.Model):
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="quiz_questions",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="quiz_questions",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["quiz", "question"],
                name="unique_question_per_quiz",
            )
        ]

    def clean(self):
        super().clean()
        if self.quiz_id and self.question_id:
            if self.quiz.subject_id != self.question.subject_id:
                raise ValidationError({"question": "The question must belong to the quiz subject."})
            if not self.quiz.is_mock and self.quiz.topic_id != self.question.topic_id:
                raise ValidationError({"question": "The question must belong to the quiz topic."})
            if not self.quiz.is_mock and self.quiz.lesson_id != self.question.lesson_id:
                raise ValidationError(
                    {"question": "The question must belong to the quiz lesson."}
                )

    def __str__(self):
        return f"{self.quiz.title} - {self.question}"