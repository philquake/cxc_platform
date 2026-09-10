from django.db import migrations, models


def populate_lesson_numbers(apps, schema_editor):
    lesson_model = apps.get_model("lessons", "Lesson")
    subject_ids = lesson_model.objects.values_list("subject_id", flat=True).distinct()

    for subject_id in subject_ids:
        lessons = lesson_model.objects.filter(subject_id=subject_id).order_by(
            "order", "title", "id"
        )
        for lesson_number, lesson in enumerate(lessons, start=1):
            lesson.lesson_number = lesson_number
            lesson.save(update_fields=["lesson_number"])


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0009_normalize_lesson_image_paths"),
    ]

    operations = [
        migrations.AddField(
            model_name="lesson",
            name="lesson_number",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="lesson",
            name="section_number",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.RenameField(
            model_name="lesson",
            old_name="section",
            new_name="section_title",
        ),
        migrations.RunPython(populate_lesson_numbers, migrations.RunPython.noop),
    ]