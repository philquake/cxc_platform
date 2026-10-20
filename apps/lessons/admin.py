from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.utils.html import format_html, format_html_join

from django import forms

from apps.core.admin_import import ImportAdminMixin
from apps.questions.models import PATHWAY_CHOICES
from apps.quizzes.services import DEFAULT_COUNTS, generate_lesson_quizzes
from apps.subjects.models import Subject, Topic

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


class LessonQuizSettingsForm(forms.Form):
    topic = forms.ModelChoiceField(
        label="Topic",
        queryset=Topic.objects.none(),
        required=False,
        help_text="Leave blank to use the lesson's only topic.",
    )
    easy = forms.IntegerField(label="Easy", min_value=0, max_value=100, initial=DEFAULT_COUNTS["easy"], required=False)
    medium = forms.IntegerField(label="Medium", min_value=0, max_value=100, initial=DEFAULT_COUNTS["medium"], required=False)
    hard = forms.IntegerField(label="Hard", min_value=0, max_value=100, initial=DEFAULT_COUNTS["hard"], required=False)
    pathway = forms.ChoiceField(label="Pathway", choices=[("", "Any pathway"), *PATHWAY_CHOICES], required=False)
    allow_partial = forms.BooleanField(label="Allow fewer than requested", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["topic"].queryset = Topic.objects.filter(is_active=True).select_related("subject")


class LessonQuizActionForm(ActionForm, LessonQuizSettingsForm):
    pass


@admin.action(description="Generate Easy/Medium/Hard quizzes for selected lessons")
def generate_quizzes(modeladmin, request, queryset):
    form = LessonQuizSettingsForm(request.POST)
    if not form.is_valid():
        modeladmin.message_user(request, f"Check the quiz settings: {form.errors.as_text()}", level=messages.ERROR)
        return
    data = form.cleaned_data
    counts = {difficulty: data[difficulty] or 0 for difficulty in DEFAULT_COUNTS}
    for lesson in queryset.select_related("subject"):
        topic = data["topic"]
        if topic is None:
            topics = list(Topic.objects.filter(questions__lesson=lesson).distinct()[:2])
            if len(topics) != 1:
                modeladmin.message_user(
                    request, f"{lesson}: its questions span several topics (or none); choose a topic.", level=messages.WARNING
                )
                continue
            topic = topics[0]
        try:
            quizzes, shortages = generate_lesson_quizzes(
                topic, lesson, counts, pathway=data["pathway"], allow_partial=data["allow_partial"]
            )
        except ValueError as error:
            modeladmin.message_user(request, f"{lesson}: {error}", level=messages.WARNING)
            continue
        made = ", ".join(f"{quiz.get_difficulty_display()} ({quiz.quiz_questions.count()})" for quiz in quizzes)
        note = f" Short: {'; '.join(shortages)}." if shortages else ""
        modeladmin.message_user(
            request,
            f"{lesson}: created {made} as inactive quizzes. Preview them under Quizzes, then tick Active.{note}",
            level=messages.SUCCESS,
        )


@admin.register(Lesson)
class LessonAdmin(ImportAdminMixin, admin.ModelAdmin):
    action_form = LessonQuizActionForm
    actions = (generate_quizzes,)
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
