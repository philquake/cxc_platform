from django.contrib import admin
from django.utils.html import format_html, format_html_join

from .models import Lesson, LessonImage


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = (
        "lesson_number",
        "title",
        "section_number",
        "section_title",
        "subject",
        "is_active",
        "updated_at",
    )
    list_filter = ("subject", "is_active")
    search_fields = ("title", "section_title", "content")
    ordering = ("subject", "lesson_number")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("available_images",)
    fields = (
        "subject",
        "title",
        "lesson_number",
        "section_number",
        "section_title",
        "slug",
        "content",
        "available_images",
        "is_active",
    )

    @admin.display(description="Existing images")
    def available_images(self, obj):
        images = LessonImage.objects.select_related("lesson").order_by(
            "lesson__title", "order", "id"
        )
        options = format_html_join(
            "",
            '<option value="{}" data-alt="{}">{} - {}</option>',
            (
                (lesson_image.image.url, lesson_image.alt_text, lesson_image.lesson.title, lesson_image.image.name)
                for lesson_image in images
                if lesson_image.image
            ),
        )
        return format_html(
            '<div id="lesson-image-library">'
            '<select id="lesson-image-select">'
            '<option value="">Select an existing image...</option>{}'
            "</select> "
            '<button type="button" class="button" id="lesson-image-insert">Insert at cursor</button>'
            '<p class="help">Click inside Content first, then select an image and insert it at that position.</p>'
            "</div>",
            options,
        )

    class Media:
        js = ("admin/js/lesson_media.js",)
