from pathlib import Path

from django.conf import settings
from django.db import migrations


IMAGE_FILES = (
    ("img-1.png", "Introduction to Information Technology image 1", 0),
    ("image.png", "Introduction to Information Technology image 2", 1),
)


def add_introduction_images(apps, schema_editor):
    lesson_model = apps.get_model("lessons", "Lesson")
    lesson_image_model = apps.get_model("lessons", "LessonImage")

    for lesson in lesson_model.objects.filter(
        title__icontains="Introduction to Information Technology"
    ):
        for filename, alt_text, order in IMAGE_FILES:
            image_path = Path("lesson_images") / filename
            if (settings.MEDIA_ROOT / image_path).exists():
                lesson_image_model.objects.get_or_create(
                    lesson=lesson,
                    image=str(image_path),
                    defaults={"alt_text": alt_text, "order": order},
                )


def remove_introduction_images(apps, schema_editor):
    lesson_image_model = apps.get_model("lessons", "LessonImage")
    lesson_image_model.objects.filter(
        image__in=[f"lesson_images/{filename}" for filename, _, _ in IMAGE_FILES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0007_lessonimage"),
    ]

    operations = [
        migrations.RunPython(add_introduction_images, remove_introduction_images),
    ]