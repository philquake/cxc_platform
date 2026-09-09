from django.db import migrations, models
import django.db.models.deletion


def copy_topic_subjects(apps, schema_editor):
    Lesson = apps.get_model("lessons", "Lesson")
    for lesson in Lesson.objects.select_related("topic"):
        lesson.subject_id = lesson.topic.subject_id
        lesson.save(update_fields=["subject"])


def clear_subjects(apps, schema_editor):
    Lesson = apps.get_model("lessons", "Lesson")
    Lesson.objects.update(subject=None)


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0002_alter_lesson_content"),
    ]

    operations = [
        migrations.AddField(
            model_name="lesson",
            name="subject",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="lessons",
                to="subjects.subject",
            ),
        ),
        migrations.RunPython(copy_topic_subjects, clear_subjects),
        migrations.AlterField(
            model_name="lesson",
            name="subject",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="lessons",
                to="subjects.subject",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="lesson",
            name="unique_lesson_slug_per_topic",
        ),
        migrations.RemoveField(
            model_name="lesson",
            name="topic",
        ),
        migrations.DeleteModel(
            name="Topic",
        ),
        migrations.AddConstraint(
            model_name="lesson",
            constraint=models.UniqueConstraint(
                fields=("subject", "slug"),
                name="unique_lesson_slug_per_subject",
            ),
        ),
    ]
