from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0010_lesson_numbers_and_sections"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="lesson",
            options={"ordering": ["lesson_number", "section_number", "title"]},
        ),
        migrations.AddConstraint(
            model_name="lesson",
            constraint=models.UniqueConstraint(
                fields=("subject", "lesson_number"),
                name="unique_lesson_number_per_subject",
            ),
        ),
    ]