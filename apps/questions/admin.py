from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import Question, Answer


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "text",
        "lesson",
        "difficulty",
        "is_active",
    )
    list_filter = (
        "lesson__subject",
        "lesson",
        "difficulty",
        "is_active",
    )
    search_fields = ("text", "explanation")
    inlines = [AnswerInline]