from django import forms
from django.contrib import admin
from django.forms.models import BaseInlineFormSet

from apps.lessons.models import Lesson
from apps.questions.models import Question
from apps.subjects.models import Topic
from .models import Quiz, QuizQuestion

class DataAttrSelect(forms.Select):
    """A Select widget that stamps extra data-* attributes onto each
    <option>, keyed by the choice's pk, so client-side JS can filter
    the visible options without another round-trip to the server."""

    def __init__(self, *args, data_attrs=None, **kwargs):
        self.data_attrs = data_attrs or {}
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        pk = getattr(value, "value", value)
        extra = self.data_attrs.get(pk)
        if extra:
            option["attrs"].update(extra)
        return option


class QuizAdminForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = (
            "subject",
            "topic",
            "lesson",
            "title",
            "description",
            "is_mock",
            "time_limit_minutes",
            "difficulty",
            "pathway",
            "shuffle_questions",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tag_subjects(self)


def tag_subjects(form):
    """Stamp data-subject on topic and lesson options so quiz_admin.js can filter them by subject."""
    for name, model in (("topic", Topic), ("lesson", Lesson)):
        if name not in form.fields:
            continue
        widget = DataAttrSelect(
            data_attrs={
                pk: {"data-subject": subject_id}
                for pk, subject_id in model.objects.values_list("id", "subject_id")
            }
        )
        widget.choices = form.fields[name].choices
        form.fields[name].widget = widget


class QuizQuestionInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        quiz = self.instance
        if quiz and quiz.pk:
            queryset = Question.objects.filter(subject=quiz.subject, is_active=True)
            if not quiz.is_mock:
                queryset = queryset.filter(topic=quiz.topic, lesson=quiz.lesson)
            self.form.base_fields["question"].queryset = queryset

            difficulty_map = dict(queryset.values_list("id", "difficulty"))
            widget = DataAttrSelect(
                data_attrs={
                    question_id: {"data-difficulty": difficulty}
                    for question_id, difficulty in difficulty_map.items()
                }
            )
            widget.choices = self.form.base_fields["question"].choices
            self.form.base_fields["question"].widget = widget


class QuizQuestionInline(admin.TabularInline):
    model = QuizQuestion
    formset = QuizQuestionInlineFormSet
    extra = 1


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    form = QuizAdminForm
    list_display = (
        "title",
        "subject",
        "topic",
        "lesson",
        "is_mock",
        "difficulty",
        "time_limit_minutes",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = ("subject", "topic", "lesson", "difficulty", "pathway", "is_active")
    search_fields = ("title", "description")
    fields = (
        "subject",
        "topic",
        "lesson",
        "title",
        "description",
        "is_mock",
        "time_limit_minutes",
        "difficulty",
        "pathway",
        "shuffle_questions",
        "is_active",
    )
    inlines = [QuizQuestionInline]

    class Media:
        js = ("admin/js/quiz_admin.js",)