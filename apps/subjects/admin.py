from django.contrib import admin
from .models import Subject, Topic


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "is_active")
    list_filter = ("subject", "is_active")
    search_fields = ("name", "subject__name", "subject__code")


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    prepopulated_fields = {}