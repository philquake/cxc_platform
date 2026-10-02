from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm

from apps.quizzes.services import generate_mock_exam
from .models import Subject, Topic


class MockExamActionForm(ActionForm):
    question_count = forms.IntegerField(
        label="Target questions per mock",
        min_value=1,
        max_value=250,
        initial=40,
        required=False,
    )
    time_limit_minutes = forms.IntegerField(
        label="Time limit in minutes",
        min_value=1,
        max_value=480,
        initial=120,
        required=False,
    )
    topics = forms.ModelMultipleChoiceField(
        label="Limit to topics (optional)",
        queryset=Topic.objects.none(),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["topics"].queryset = Topic.objects.filter(is_active=True).select_related("subject")


@admin.action(description="Generate weighted mock exam for selected subjects")
def generate_mock_exams(modeladmin, request, queryset):
    question_count = int(request.POST.get("question_count") or 40)
    time_limit_minutes = int(request.POST.get("time_limit_minutes") or 120)
    topic_ids = request.POST.getlist("topics")
    requested_topics = Topic.objects.filter(pk__in=topic_ids, is_active=True)
    for subject in queryset:
        topics = requested_topics.filter(subject=subject) if topic_ids else None
        try:
            quiz, _ = generate_mock_exam(
                subject,
                question_count,
                time_limit_minutes,
                topics=topics,
            )
        except ValueError as error:
            modeladmin.message_user(request, f"{subject}: {error}", level=messages.WARNING)
            continue
        actual_count = quiz.quiz_questions.count()
        modeladmin.message_user(
            request,
            f"Created {quiz} with {actual_count} of {question_count} requested questions. "
            "Topic shortages are not filled from other topics.",
            level=messages.SUCCESS,
        )


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "is_active")
    list_filter = ("subject", "is_active")
    search_fields = ("name", "subject__name", "subject__code")


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    action_form = MockExamActionForm
    actions = (generate_mock_exams,)
    list_display = ("name", "code", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    prepopulated_fields = {}