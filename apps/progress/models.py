from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.lessons.models import Lesson
from apps.questions.models import Question
from apps.quizzes.models import Quiz
from apps.subjects.models import Subject, Topic


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
    selected_text = models.TextField(blank=True, default="")
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
        
class FlashcardState(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="flashcard_states")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="flashcard_states")
    ease = models.FloatField(default=2.5)          # SM-2 ease factor
    interval_days = models.PositiveIntegerField(default=0)
    due_at = models.DateField(null=True, blank=True)
    reps = models.PositiveIntegerField(default=0)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "question"], name="unique_user_question_flashcard")
        ]

    def review(self, rating, *, reviewed_at=None):
        qualities = {"again": 0, "hard": 3, "good": 4, "easy": 5}
        if rating not in qualities:
            raise ValueError("Unsupported flashcard rating.")

        quality = qualities[rating]
        reviewed_at = reviewed_at or timezone.now()
        self.ease = max(
            1.3,
            self.ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02),
        )
        if quality < 3:
            self.reps = 0
            self.interval_days = 1
        else:
            if self.reps == 0:
                self.interval_days = 1
            elif self.reps == 1:
                self.interval_days = 6
            else:
                self.interval_days = round(self.interval_days * self.ease)
            self.reps += 1

        self.due_at = timezone.localdate(reviewed_at) + timedelta(days=self.interval_days)
        self.last_reviewed_at = reviewed_at
        self.save(
            update_fields=[
                "ease",
                "interval_days",
                "due_at",
                "reps",
                "last_reviewed_at",
            ]
        )
        return self.interval_days


class StudyPlan(models.Model):
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="study_plans",
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="study_plans",
    )
    title = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_date", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="study_plan_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.title}"


class StudyPlanItem(models.Model):
    plan = models.ForeignKey(
        StudyPlan,
        on_delete=models.CASCADE,
        related_name="items",
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="study_plan_items",
        null=True,
        blank=True,
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="study_plan_items",
        null=True,
        blank=True,
    )
    scheduled_date = models.DateField()
    order = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["scheduled_date", "order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(lesson__isnull=False, quiz__isnull=True)
                    | models.Q(lesson__isnull=True, quiz__isnull=False)
                ),
                name="study_plan_item_one_target",
            ),
            models.UniqueConstraint(
                fields=["plan", "scheduled_date", "order"],
                name="unique_plan_day_item_order",
            ),
        ]

    def clean(self):
        super().clean()
        target = self.lesson or self.quiz
        if self.plan_id and target and target.subject_id != self.plan.subject_id:
            raise ValidationError("The study item must belong to the plan subject.")
        if self.plan_id and (
            self.scheduled_date < self.plan.start_date
            or (self.plan.end_date and self.scheduled_date > self.plan.end_date)
        ):
            raise ValidationError("The scheduled date must fall within the plan dates.")

    def __str__(self):
        return f"{self.plan.title} - {self.lesson or self.quiz}"