import nh3
from django.db import migrations

from apps.lessons.models import ALLOWED_ATTRIBUTES


def sanitize(apps, schema_editor):
    Lesson = apps.get_model("lessons", "Lesson")
    for lesson in Lesson.objects.all().only("id", "content"):
        cleaned = nh3.clean(lesson.content, attributes=ALLOWED_ATTRIBUTES)
        if cleaned != lesson.content:
            Lesson.objects.filter(pk=lesson.pk).update(content=cleaned)


class Migration(migrations.Migration):

    dependencies = [
        ("lessons", "0003_remove_lesson_order"),
    ]

    operations = [
        migrations.RunPython(sanitize, migrations.RunPython.noop),
    ]
