from django.contrib import admin
from django.contrib.auth.models import User
from django.db import transaction
from django.urls import reverse
from django.utils.html import format_html, linebreaks

from .models import (
    Classroom,
    FlashcardState,
    LessonProgress,
    QuizAttempt,
    QuizAnswer,
    StudyPlan,
    StudyPlanItem,
    TopicMasteryStat,
    UserProgress,
    XPTransaction,
)


@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "total_xp",
        "current_streak",
        "longest_streak",
        "last_activity_date",
    )
    ordering = ("-total_xp",)
    search_fields = ("user__username",)


@admin.register(XPTransaction)
class XPTransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "topic", "amount", "reason", "created_at")
    list_filter = ("topic", "reason")
    search_fields = ("user__username", "topic__name", "reason")


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "lesson",
        "completed",
        "completed_at",
        "updated_at",
    )
    list_filter = (
        "completed",
        "lesson__subject",
    )
    search_fields = (
        "user__username",
        "lesson__title",
    )


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "quiz",
        "score",
        "total_marks",
        "awaiting_review",
        "started_at",
        "completed_at",
    )
    list_filter = ("awaiting_review", "quiz")
    search_fields = (
        "user__username",
        "quiz__title",
    )


class AwaitingMarkingFilter(admin.SimpleListFilter):
    title = "marking"
    parameter_name = "marking"

    def lookups(self, request, model_admin):
        return [("pending", "Awaiting marking"), ("marked", "Marked")]

    def queryset(self, request, queryset):
        if self.value() == "pending":
            return queryset.filter(marks_awarded__isnull=True)
        if self.value() == "marked":
            return queryset.filter(marks_awarded__isnull=False)
        return queryset


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "attempt",
        "question",
        "student_answer",
        "marking_guide",
        "max_marks",
        "marks_awarded",
        "feedback",
        "is_correct",
    )
    list_editable = ("marks_awarded", "feedback")
    list_filter = (AwaitingMarkingFilter, "question__format", "attempt__quiz__subject", "is_correct")
    list_select_related = ("attempt__user", "attempt__quiz", "question", "selected_answer")
    search_fields = ("attempt__user__username", "question__text", "selected_text")
    readonly_fields = ("attempt", "question", "selected_answer", "selected_text", "is_correct")

    def has_add_permission(self, request):
        return False

    @admin.display(description="Student answer")
    def student_answer(self, obj):
        return obj.selected_answer.text if obj.selected_answer else obj.selected_text or "No answer"

    @admin.display(description="Expected answer / mark scheme")
    def marking_guide(self, obj):
        return format_html(
            "<strong>{}</strong>{}",
            obj.question.expected_answer.replace("|", " / "),
            linebreaks(obj.question.mark_scheme),
        )

    @admin.display(description="Out of")
    def max_marks(self, obj):
        return obj.question.marks

    def save_model(self, request, obj, form, change):
        from .views import finalize_attempt

        if obj.marks_awarded is not None:
            obj.is_correct = obj.marks_awarded == obj.question.marks
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            # Lock the attempt so two markers finishing it at once can't both award XP.
            attempt = QuizAttempt.objects.select_for_update().get(pk=obj.attempt_id)
            if attempt.answers.filter(marks_awarded__isnull=True).exists():
                return
            if attempt.awaiting_review:
                # Marking happens later, so it shouldn't move the student's streak.
                finalize_attempt(attempt, update_streak=False)
            else:
                # A correction after finalising fixes the score; XP and mastery stay as first recorded.
                attempt.score = sum(attempt.answers.values_list("marks_awarded", flat=True))
                attempt.save(update_fields=["score"])


class StudyPlanItemInline(admin.TabularInline):
    model = StudyPlanItem
    extra = 0
    fields = ("scheduled_date", "order", "item_type", "lesson", "topic", "completed", "completed_at")
    raw_id_fields = ("lesson", "topic")


@admin.register(StudyPlan)
class StudyPlanAdmin(admin.ModelAdmin):
    list_display = ("user", "subject", "target_date", "is_active", "created_at")
    list_filter = ("is_active", "subject")
    search_fields = ("user__username",)
    raw_id_fields = ("user",)
    inlines = (StudyPlanItemInline,)


@admin.register(FlashcardState)
class FlashcardStateAdmin(admin.ModelAdmin):
    list_display = ("user", "question", "due_at", "interval_days", "reps", "ease", "last_reviewed_at")
    list_filter = ("question__subject",)
    list_select_related = ("user", "question")
    search_fields = ("user__username", "question__text")
    raw_id_fields = ("user", "question")


@admin.register(TopicMasteryStat)
class TopicMasteryStatAdmin(admin.ModelAdmin):
    """Read-only: totals are frozen at answer time and only record_attempt should write them."""
    list_display = ("user", "topic", "difficulty", "n", "weighted_correct", "weighted_total", "updated_at")
    list_filter = ("topic__subject", "difficulty")
    list_select_related = ("user", "topic")
    search_fields = ("user__username", "topic__name")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ("name", "teacher", "join_code", "student_count", "progress_link")
    search_fields = ("name", "teacher__username", "join_code")
    filter_horizontal = ("students",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related("teacher")
        # Teachers only manage their own classes; the owner sees all of them.
        return queryset if request.user.is_superuser else queryset.filter(teacher=request.user)

    def get_readonly_fields(self, request, obj=None):
        return ("join_code",) if request.user.is_superuser else ("join_code", "teacher")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "teacher":
            kwargs["queryset"] = User.objects.filter(is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not obj.teacher_id:
            obj.teacher = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Students")
    def student_count(self, obj):
        return obj.students.count()

    @admin.display(description="Progress")
    def progress_link(self, obj):
        return format_html('<a href="{}">View progress</a>', reverse("progress:class-detail", args=[obj.pk]))
