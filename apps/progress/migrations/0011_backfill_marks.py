from django.db import migrations
from django.db.models import F


def backfill_marks(apps, schema_editor):
    # Every question was worth one mark before marks existed, so old percentages are unchanged.
    QuizAttempt = apps.get_model("progress", "QuizAttempt")
    QuizAnswer = apps.get_model("progress", "QuizAnswer")
    QuizAttempt.objects.update(total_marks=F("total_questions"))
    QuizAnswer.objects.filter(is_correct=True).update(marks_awarded=1)
    QuizAnswer.objects.filter(is_correct=False).update(marks_awarded=0)


class Migration(migrations.Migration):

    dependencies = [
        ("progress", "0010_quizanswer_feedback_quizanswer_marks_awarded_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_marks, migrations.RunPython.noop),
    ]
