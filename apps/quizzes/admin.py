from django import forms
from django.contrib import admin
from django.forms.models import BaseInlineFormSet

from apps.questions.models import Question
from apps.subjects.models import Topic
from .models import Quiz, QuizQuestion

class QuizQuestionInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Question.objects.filter(is_active=True)
        self.form.base_fields["question"].queryset = queryset

        widget = DataAttrSelect(
            data_attrs={
                q.id: {
                    "data-subject": q.subject_id,
                    "data-topic": q.topic_id,
                    "data-lesson": q.lesson_id,
                    "data-difficulty": q.difficulty,
                }
                for q in queryset
            }
        )
        widget.choices = self.form.base_fields["question"].choices
        self.form.base_fields["question"].widget = widget
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
        fields = ("subject", "topic", "lesson", "title", "description", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        topic_subject_map = dict(Topic.objects.values_list("id", "subject_id"))
        widget = DataAttrSelect(
            data_attrs={
                topic_id: {"data-subject": subject_id}
                for topic_id, subject_id in topic_subject_map.items()
            }
        )
        widget.choices = self.fields["topic"].choices
        self.fields["topic"].widget = widget


class QuizQuestionInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        quiz = self.instance
        if quiz and quiz.pk:
            queryset = Question.objects.filter(
                subject=quiz.subject,
                topic=quiz.topic,
                lesson=quiz.lesson,
                is_active=True,
            )
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
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = ("subject", "topic", "lesson", "is_active")
    search_fields = ("title", "description")
    fields = ("subject", "topic", "lesson", "title", "description", "is_active")
    inlines = [QuizQuestionInline]

    class Media:
        js = ("admin/js/quiz_admin.js",)