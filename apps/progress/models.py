from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models, transaction
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
    time_taken_seconds = models.PositiveIntegerField(null=True, blank=True)
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
                self.interval_days = int(self.interval_days * self.ease + 0.5)
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
    target_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["target_date", "id"]

    def clean(self):
        super().clean()
        if self.is_active and self.user_id and self.subject_id and StudyPlan.objects.filter(
            user_id=self.user_id,
            subject_id=self.subject_id,
            is_active=True,
        ).exclude(pk=self.pk).exists():
            raise ValidationError("Only one active study plan is allowed per subject.")

    def save(self, *args, **kwargs):
        if self.is_active:
            using = kwargs.get("using")
            with transaction.atomic(using=using):
                if self.user_id and self.subject_id:
                    StudyPlan.objects.using(using).filter(
                        user_id=self.user_id,
                        subject_id=self.subject_id,
                        is_active=True,
                    ).exclude(pk=self.pk).update(is_active=False)
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} - {self.subject} study plan"


class StudyPlanItem(models.Model):
    LESSON = "lesson"
    QUIZ = "quiz"
    FLASHCARD_REVIEW = "flashcard_review"
    MISTAKE_REVIEW = "mistake_review"
    ITEM_TYPE_CHOICES = [
        (LESSON, "Lesson"),
        (QUIZ, "Quiz"),
        (FLASHCARD_REVIEW, "Flashcard review"),
        (MISTAKE_REVIEW, "Mistake review"),
    ]

    plan = models.ForeignKey(
        StudyPlan,
        on_delete=models.CASCADE,
        related_name="items",
    )
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="study_plan_items",
        null=True,
        blank=True,
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name="study_plan_items",
        null=True,
        blank=True,
    )
    scheduled_date = models.DateField()
    order = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["scheduled_date", "order"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(item_type="lesson", lesson__isnull=False)
                    | (~models.Q(item_type="lesson") & models.Q(lesson__isnull=True))
                ),
                name="study_plan_item_lesson_target",
            ),
            models.CheckConstraint(
                condition=models.Q(item_type="lesson") | models.Q(topic__isnull=False),
                name="study_plan_item_topic_target",
            ),
            models.UniqueConstraint(
                fields=["plan", "scheduled_date", "order"],
                name="unique_plan_day_item_order",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.item_type == self.LESSON:
            if not self.lesson_id:
                errors["lesson"] = "Lesson items need a lesson."
        elif self.lesson_id:
            errors["lesson"] = "Only lesson items can reference a lesson."
        if self.item_type != self.LESSON and not self.topic_id:
            errors["topic"] = "Review and quiz items need a topic."
        if self.plan_id and self.lesson_id and self.lesson.subject_id != self.plan.subject_id:
            errors["lesson"] = "The lesson must belong to the plan subject."
        if self.plan_id and self.topic_id and self.topic.subject_id != self.plan.subject_id:
            errors["topic"] = "The topic must belong to the plan subject."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.plan.subject} - {self.get_item_type_display()}"