from django.contrib.auth.models import User
from django.db import models

from apps.lessons.models import Lesson
from apps.questions.models import Question
from apps.quizzes.models import Quiz
from apps.subjects.models import Topic


class UserProgress(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="progress_summary",
    )
    total_xp = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    LEVEL_XP = 500

    @property
    def level(self):
        return (self.total_xp // self.LEVEL_XP) + 1

    @property
    def level_xp(self):
        return self.total_xp % self.LEVEL_XP

    @property
    def level_progress(self):
        return round((self.level_xp / self.LEVEL_XP) * 100)

    @property
    def level_xp_required(self):
        return self.LEVEL_XP

    def __str__(self):
        return f"{self.user.username} - Level {self.level}"


class LessonProgress(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="lesson_progress",
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="progress",
    )
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "lesson"],
                name="unique_user_lesson_progress",
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.lesson.title}"
    
class QuizAttempt(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="quiz_attempts",
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    score = models.PositiveIntegerField(default=0)
    total_questions = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    @property
    def percentage(self):
        if self.total_questions == 0:
            return 0

        return round(
            (self.score / self.total_questions) * 100
        )

    def __str__(self):
        return f"{self.user.username} - {self.quiz.title}"
    
class QuizAnswer(models.Model):
    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="attempt_answers",
    )
    selected_answer = models.ForeignKey(
        "questions.Answer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="selected_in_attempts",
    )
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.attempt} - {self.question}"


class XPTransaction(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="xp_transactions",
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name="xp_transactions",
    )
    amount = models.PositiveIntegerField()
    reason = models.CharField(max_length=120)
    lesson_progress = models.OneToOneField(
        LessonProgress,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="xp_transaction",
    )
    quiz_attempt = models.OneToOneField(
        QuizAttempt,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="xp_transaction",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} +{self.amount} XP ({self.reason})"
    
class MistakeReview(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mistake_reviews")
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "question"], name="unique_user_question_review")
        ]