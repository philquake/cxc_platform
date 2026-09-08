from django.contrib import admin
from .models import Topic, Lesson


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "order", "is_active")
    list_filter = ("subject", "is_active")
    search_fields = ("name", "description")
    ordering = ("subject", "order")


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "topic", "order", "is_active", "updated_at")
    list_filter = ("topic__subject", "topic", "is_active")
    search_fields = ("title", "content")
    ordering = ("topic", "order")