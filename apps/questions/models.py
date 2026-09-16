from django.core.exceptions import ValidationError
from django.db import models
from apps.lessons.models import Lesson
from apps.subjects.models import Subject, Topic


class Question(models.Model):
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    text = models.TextField()
    explanation = models.TextField(blank=True)
    difficulty = models.CharField(
        max_length=20,
        choices=[
            ("easy", "Easy"),
            ("medium", "Medium"),
            ("hard", "Hard"),
        ],
        default="medium",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.text[:80]

    def clean(self):
        super().clean()
        errors = {}
        if self.lesson_id and self.subject_id and self.lesson.subject_id != self.subject_id:
            errors["subject"] = "The subject must match the lesson subject."
        if self.topic_id and self.subject_id and self.topic.subject_id != self.subject_id:
            errors["topic"] = "The topic must belong to the selected subject."
        if errors:
            raise ValidationError(errors)


class Answer(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text