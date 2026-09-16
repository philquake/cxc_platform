from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import Question, Answer


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4
    min_num = 4
    max_num = 4
    validate_min = True
    validate_max = True


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "text",
        "subject",
        "topic",
        "lesson",
        "difficulty",
        "is_active",
    )
    list_filter = (
        "subject",
        "topic",
        "lesson",
        "difficulty",
        "is_active",
    )
    search_fields = ("text", "explanation")
    inlines = [AnswerInline]