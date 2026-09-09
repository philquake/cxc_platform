from django.db import migrations, models


def copy_section_titles(apps, schema_editor):
    Lesson = apps.get_model("lessons", "Lesson")
    Section = apps.get_model("lessons", "Section")

    for lesson in Lesson.objects.all():
        section = Section.objects.filter(lesson_id=lesson.pk).order_by("order", "title", "id").first()
        if section is not None:
            lesson.section = section.title
            lesson.save(update_fields=["section"])


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0004_section"),
    ]

    operations = [
        migrations.AddField(
            model_name="lesson",
            name="section",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.RunPython(copy_section_titles, migrations.RunPython.noop),
        migrations.DeleteModel(
            name="Section",
        ),
    ]
