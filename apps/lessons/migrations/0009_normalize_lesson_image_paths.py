from django.db import migrations


def normalize_image_paths(apps, schema_editor):
    lesson_image_model = apps.get_model("lessons", "LessonImage")
    for lesson_image in lesson_image_model.objects.filter(image__contains="\\"):
        lesson_image.image = str(lesson_image.image).replace("\\", "/")
        lesson_image.save(update_fields=["image"])


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0008_add_introduction_images"),
    ]

    operations = [
        migrations.RunPython(normalize_image_paths, migrations.RunPython.noop),
    ]