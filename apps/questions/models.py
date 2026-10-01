from django.core.exceptions import ValidationError
from django.db import models
from apps.lessons.models import Lesson
from apps.subjects.models import Subject, Topic


class Question(models.Model):
    FORMAT_MULTIPLE_CHOICE = "multiple_choice"
    FORMAT_TRUE_FALSE = "true_false"
    FORMAT_SHORT_ANSWER = "short_answer"
    FORMAT_MATCHING = "matching"
    FORMAT_WORDED = "worded"

    FORMAT_CHOICES = [
        (FORMAT_MULTIPLE_CHOICE, "Multiple choice"),
        (FORMAT_TRUE_FALSE, "True / False"),
        (FORMAT_SHORT_ANSWER, "Short answer"),
        (FORMAT_MATCHING, "Matching"),
        (FORMAT_WORDED, "Worded answer"),
    ]

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
    format = models.CharField(
        max_length=30,
        choices=FORMAT_CHOICES,
        default=FORMAT_MULTIPLE_CHOICE,
    )
    expected_answer = models.TextField(blank=True, default="")
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
        if self.format in {self.FORMAT_SHORT_ANSWER, self.FORMAT_WORDED} and not self.expected_answer.strip():
            errors["expected_answer"] = "Open-ended questions require an expected answer."
        if self.lesson_id and self.subject_id and self.lesson.subject_id != self.subject_id:
            errors["subject"] = "The subject must match the lesson subject."
        if self.topic_id and self.subject_id and self.topic.subject_id != self.subject_id:
            errors["topic"] = "The topic must belong to the selected subject."
        if errors:
            raise ValidationError(errors)

    @property
    def is_open_ended(self):
        return self.format in {self.FORMAT_SHORT_ANSWER, self.FORMAT_WORDED}


class Answer(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    text = models.CharField(max_length=500)
    match_text = models.CharField(max_length=500, blank=True, default="")
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text