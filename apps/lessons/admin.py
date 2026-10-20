from django.contrib import admin
from django.utils.html import format_html, format_html_join

from django import forms

from apps.core.admin_import import ImportAdminMixin
from apps.subjects.models import Subject

from .importers import import_lessons
from .models import Lesson, LessonImage


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data]
        return [super(MultipleFileField, self).clean(f, initial) for f in files if f]


class LessonImportForm(forms.Form):
    subject = forms.ModelChoiceField(Subject.objects.all())
    files = MultipleFileField(
        label="Notes files",
        widget=MultipleFileInput(attrs={"accept": ".docx,.html,.htm,.txt"}),
        help_text="Word (.docx), HTML or plain text. Select several to add several lessons.",
    )
    publish = forms.BooleanField(
        required=False, label="Publish immediately",
        help_text="Leave unticked to import as drafts you can check first.",
    )


@admin.register(Lesson)
class LessonAdmin(ImportAdminMixin, admin.ModelAdmin):
    import_form_class = LessonImportForm
    import_title = "Upload notes"
    import_help = (
        "Each file becomes one lesson, numbered after the subject's last lesson. The first heading "
        "(or the file name) is the title. Images in Word files are not carried over; add them in the editor."
    )

    def run_import(self, request, form):
        return import_lessons(form.cleaned_data["subject"], form.cleaned_data["files"], form.cleaned_data["publish"])

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
