from django.db import models
from django.core.exceptions import ValidationError
from apps.lessons.models import Lesson
from apps.questions.models import Question


class Quiz(models.Model):
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="quizzes",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    questions = models.ManyToManyField(
        Question,
        through="QuizQuestion",
        related_name="quizzes",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.title


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
            if self.quiz.lesson_id != self.question.lesson_id:
                raise ValidationError(
                    {"question": "The question must belong to the quiz lesson."}
                )

    def __str__(self):
        return f"{self.quiz.title} - {self.question}"