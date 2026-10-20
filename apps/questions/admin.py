from django import forms
from django.contrib import admin
from django.db.models import Count, Exists, F, OuterRef, Q
from django.utils.html import format_html, format_html_join
from django.utils.text import Truncator

from apps.core.admin_import import ImportAdminMixin
from apps.lessons.models import Lesson
from apps.quizzes.admin import tag_subjects
from apps.quizzes.models import QuizQuestion
from apps.subjects.models import Topic

from .importers import import_questions, sample_csv
from .models import PATHWAY_CHOICES, Answer, Question


class QuestionImportForm(forms.Form):
    file = forms.FileField(label="CSV file", widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}))


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 2
    max_num = 4


class QuestionAdminForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tag_subjects(self)


class TopicFilter(admin.SimpleListFilter):
    """Topics of the subject chosen in the subject filter, or every topic with its subject code."""
    title = "topic"
    parameter_name = "topic"

    def lookups(self, request, model_admin):
        topics = Topic.objects.select_related("subject").order_by("subject__code", "name")
        subject_id = request.GET.get("subject__id__exact")
        if subject_id:
            return [(topic.pk, topic.name) for topic in topics.filter(subject_id=subject_id)]
        return [(topic.pk, f"{topic.name} ({topic.subject.code})") for topic in topics]

    def queryset(self, request, queryset):
        return queryset.filter(topic_id=self.value()) if self.value() else queryset


class LessonFilter(admin.SimpleListFilter):
    """Lessons of the chosen subject, narrowed to those with questions in the chosen topic."""
    title = "lesson"
    parameter_name = "lesson"

    def lookups(self, request, model_admin):
        lessons = Lesson.objects.select_related("subject").order_by("subject__code", "lesson_number")
        subject_id = request.GET.get("subject__id__exact")
        topic_id = request.GET.get("topic")
        if subject_id:
            lessons = lessons.filter(subject_id=subject_id)
        if topic_id:
            lessons = lessons.filter(questions__topic_id=topic_id).distinct()
        return [(lesson.pk, f"{lesson.subject.code} {lesson.lesson_number}. {lesson.title}") for lesson in lessons]

    def queryset(self, request, queryset):
        return queryset.filter(lesson_id=self.value()) if self.value() else queryset


class PathwayFilter(admin.SimpleListFilter):
    title = "pathway"
    parameter_name = "pathway"

    def lookups(self, request, model_admin):
        return PATHWAY_CHOICES

    def queryset(self, request, queryset):
        if self.value() in dict(PATHWAY_CHOICES):
            return queryset.filter(**{f"for_{self.value()}": True})
        return queryset


class UsageFilter(admin.SimpleListFilter):
    title = "usage"
    parameter_name = "usage"

    def lookups(self, request, model_admin):
        return [("used", "In a quiz"), ("unused", "Not in any quiz")]

    def queryset(self, request, queryset):
        in_quiz = Exists(QuizQuestion.objects.filter(question=OuterRef("pk")))
        if self.value() == "used":
            return queryset.filter(in_quiz)
        if self.value() == "unused":
            return queryset.filter(~in_quiz)
        return queryset


class ContentFilter(admin.SimpleListFilter):
    title = "content gaps"
    parameter_name = "gap"

    def lookups(self, request, model_admin):
        return [("explanation", "Missing explanation"), ("mark_scheme", "Worded without mark scheme")]

    def queryset(self, request, queryset):
        if self.value() == "explanation":
            return queryset.filter(explanation="")
        if self.value() == "mark_scheme":
            return queryset.filter(format=Question.FORMAT_WORDED, mark_scheme="")
        return queryset


class QualityFilter(admin.SimpleListFilter):
    """Uses the response counts annotated in QuestionAdmin.get_queryset."""
    title = "response quality"
    parameter_name = "quality"

    def lookups(self, request, model_admin):
        return [("low", "Below 20% correct"), ("high", "Above 95% correct"), ("none", "No responses")]

    def queryset(self, request, queryset):
        if self.value() == "low":
            return queryset.filter(response_count__gt=0, correct_response_count__lt=F("response_count") * 0.2)
        if self.value() == "high":
            return queryset.filter(response_count__gt=0, correct_response_count__gt=F("response_count") * 0.95)
        if self.value() == "none":
            return queryset.filter(response_count=0)
        return queryset


@admin.action(description="Activate selected questions")
def activate_questions(modeladmin, request, queryset):
    # Plain pk list: the changelist queryset carries aggregate annotations that update() can't take.
    count = Question.objects.filter(pk__in=list(queryset.values_list("pk", flat=True))).update(is_active=True)
    modeladmin.message_user(request, f"{count} questions activated.")


@admin.action(description="Deactivate selected questions")
def deactivate_questions(modeladmin, request, queryset):
    count = Question.objects.filter(pk__in=list(queryset.values_list("pk", flat=True))).update(is_active=False)
    modeladmin.message_user(request, f"{count} questions deactivated.")


@admin.register(Question)
class QuestionAdmin(ImportAdminMixin, admin.ModelAdmin):
    form = QuestionAdminForm
    import_form_class = QuestionImportForm
    import_title = "Import questions"
    import_template_csv = staticmethod(sample_csv)
    import_help = (
        "Upload a CSV with one question per row. Subjects, topics and lessons must already exist "
        "(lesson is the lesson number). If any row has a problem, nothing is imported."
    )

    def run_import(self, request, form):
        count, errors = import_questions(form.cleaned_data["file"])
        return ([f"{count} questions added"] if count else []), errors
    fieldsets = (
        ("Question", {"fields": ("subject", "topic", "lesson", "format", "text")}),
        ("Answer and marking", {"fields": ("expected_answer", "marks", "mark_scheme", "explanation", "hint")}),
        (
            "Classification",
            {"fields": ("difficulty", ("for_guided", "for_adaptive", "for_practice"), "estimated_time_minutes", "is_active")},
        ),
        (
            "Response analytics",
            {
                "classes": ("collapse",),
                "fields": (
                    "response_accuracy",
                    "quality_flag",
                    "distractor_analysis",
                ),
            },
        ),
    )
    list_display = (
        "short_text",
        "subject",
        "topic",
        "lesson",
        "format",
        "difficulty",
        "marks",
        "response_accuracy",
        "quality_flag",
        "is_active",
    )
    list_filter = (
        "subject",
        TopicFilter,
        LessonFilter,
        "format",
        "difficulty",
        PathwayFilter,
        "marks",
        "is_active",
        UsageFilter,
        ContentFilter,
        QualityFilter,
    )
    list_select_related = ("subject", "topic", "lesson")
    list_per_page = 50
    search_fields = (
        "text",
        "explanation",
        "expected_answer",
        "mark_scheme",
        "answers__text",
        "topic__name",
        "lesson__title",
        "subject__code",
        "=id",
    )
    search_help_text = "Searches question text, answers and options, explanations, mark schemes, topic, lesson, subject code, or an exact ID."
    actions = (activate_questions, deactivate_questions)
    inlines = [AnswerInline]
    readonly_fields = ("response_accuracy", "quality_flag", "distractor_analysis")

    class Media:
        js = ("admin/js/quiz_admin.js",)

    @admin.display(description="Question", ordering="text")
    def short_text(self, obj):
        return Truncator(obj.text).chars(80)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            # distinct: searching answer options joins Answer rows, which would multiply these counts.
            response_count=Count("attempt_answers", distinct=True),
            correct_response_count=Count(
                "attempt_answers",
                filter=Q(attempt_answers__is_correct=True),
                distinct=True,
            ),
        )

    @admin.display(description="Correct")
    def response_accuracy(self, obj):
        total = getattr(obj, "response_count", None)
        correct = getattr(obj, "correct_response_count", None)
        if total is None:
            total = obj.attempt_answers.count()
            correct = obj.attempt_answers.filter(is_correct=True).count()
        if not total:
            return "No responses"
        return f"{correct * 100 / total:.1f}% ({total})"

    @admin.display(description="Quality flag")
    def quality_flag(self, obj):
        total = getattr(obj, "response_count", None)
        correct = getattr(obj, "correct_response_count", None)
        if total is None:
            total = obj.attempt_answers.count()
            correct = obj.attempt_answers.filter(is_correct=True).count()
        if not total:
            return "No response data"
        percentage = correct * 100 / total
        if percentage < 20:
            return "Review: below 20% correct"
        if percentage > 95:
            return "Review: above 95% correct"
        return "Within range"

    @admin.display(description="Distractor analysis")
    def distractor_analysis(self, obj):
        total = obj.attempt_answers.count()
        if not total:
            return "No response data"
        distractors = Answer.objects.filter(
            question=obj,
            is_correct=False,
        ).annotate(
            pick_count=Count("selected_in_attempts"),
        ).order_by("order", "id")
        if not distractors:
            return "No incorrect answer options"
        rows = format_html_join(
            "",
            "<tr><td>{}</td><td>{}</td><td>{}%</td></tr>",
            (
                (
                    answer.text,
                    answer.pick_count,
                    round(answer.pick_count * 100 / total),
                )
                for answer in distractors
            ),
        )
        return format_html(
            "<table><thead><tr><th>Wrong option</th><th>Picks</th>"
            "<th>Share of responses</th></tr></thead><tbody>{}</tbody></table>"
            "<p>{} total responses</p>",
            rows,
            total,
        )