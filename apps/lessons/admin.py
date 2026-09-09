from django.contrib import admin
from .models import Lesson


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "section", "subject", "order", "is_active", "updated_at")
    list_filter = ("subject", "is_active")
    search_fields = ("title", "section", "content")
    ordering = ("subject", "order")
    prepopulated_fields = {"slug": ("title",)}
