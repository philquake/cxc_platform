from django.contrib import admin
from django.forms.models import BaseInlineFormSet

from apps.questions.models import Question
from .models import Quiz, QuizQuestion


class QuizQuestionInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        quiz = self.instance
        if quiz and quiz.pk:
            self.form.base_fields["question"].queryset = Question.objects.filter(
                subject=quiz.subject,
                topic=quiz.topic,
                lesson=quiz.lesson,
                is_active=True,
            )


class QuizQuestionInline(admin.TabularInline):
    model = QuizQuestion
    formset = QuizQuestionInlineFormSet
    extra = 1


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
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