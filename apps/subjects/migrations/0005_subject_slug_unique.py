from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("subjects", "0004_subject_slug")]

    operations = [
        migrations.AlterField(
            model_name="subject",
            name="slug",
            field=models.SlugField(blank=True, max_length=220, unique=True),
        ),
    ]
