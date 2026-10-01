from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("subjects", "0002_topic"),
    ]

    operations = [
        migrations.AddField(
            model_name="topic",
            name="exam_weight",
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]