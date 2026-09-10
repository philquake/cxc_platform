import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0006_alter_lesson_slug"),
    ]

    operations = [
        migrations.CreateModel(
            name="LessonImage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("image", models.ImageField(upload_to="lesson_images/")),
                ("alt_text", models.CharField(blank=True, max_length=200)),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "lesson",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="lessons.lesson",
                    ),
                ),
            ],
            options={"ordering": ["order", "id"]},
        ),
    ]