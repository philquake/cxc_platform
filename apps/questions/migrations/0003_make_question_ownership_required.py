from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("questions", "0002_question_subject_question_topic"),
    ]

    operations = [
        migrations.AlterField(
            model_name="question",
            name="subject",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="questions",
                to="subjects.subject",
            ),
        ),
        migrations.AlterField(
            model_name="question",
            name="topic",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="questions",
                to="subjects.topic",
            ),
        ),
    ]
