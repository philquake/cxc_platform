from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("quizzes", "0002_quiz_subject_quiz_topic"),
    ]

    operations = [
        migrations.AlterField(
            model_name="quiz",
            name="subject",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="quizzes",
                to="subjects.subject",
            ),
        ),
        migrations.AlterField(
            model_name="quiz",
            name="topic",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="quizzes",
                to="subjects.topic",
            ),
        ),
    ]
