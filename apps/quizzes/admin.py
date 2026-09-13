from django.contrib import admin

from .models import Quiz, QuizQuestion


class QuizQuestionInline(admin.TabularInline):
    model = QuizQuestion
    extra = 1


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "lesson",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = ("lesson__subject", "lesson", "is_active")
    search_fields = ("title", "description")
    inlines = [QuizQuestionInline]