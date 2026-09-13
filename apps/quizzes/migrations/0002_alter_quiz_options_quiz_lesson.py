import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lessons", "0011_lesson_number_constraint"),
        ("quizzes", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="quiz",
            options={"ordering": ["id"]},
        ),
        migrations.AddField(
            model_name="quiz",
            name="lesson",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="quizzes",
                to="lessons.lesson",
            ),
        ),
    ]