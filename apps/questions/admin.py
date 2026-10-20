from django import forms
from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html, format_html_join

from apps.core.admin_import import ImportAdminMixin

from .importers import import_questions, sample_csv
from .models import Question, Answer


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
        (
            None,
            {
                "fields": (
                    "subject",
                    "topic",
                    "lesson",
                    "text",
                    "format",
                    "expected_answer",
                    "difficulty",
                    "explanation",
                    "is_active",
                )
            },
        ),
        (
            "Response analytics",
            {
                "fields": (
                    "response_accuracy",
                    "quality_flag",
                    "distractor_analysis",
                )
            },
        ),
    )
    list_display = (
        "text",
        "subject",
        "topic",
        "lesson",
        "format",
        "difficulty",
        "response_accuracy",
        "quality_flag",
        "is_active",
    )
    list_filter = (
        "subject",
        "topic",
        "lesson",
        "format",
        "difficulty",
        "is_active",
    )
    search_fields = ("text", "explanation")
    inlines = [AnswerInline]
    readonly_fields = ("response_accuracy", "quality_flag", "distractor_analysis")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            response_count=Count("attempt_answers"),
            correct_response_count=Count(
                "attempt_answers",
                filter=Q(attempt_answers__is_correct=True),
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