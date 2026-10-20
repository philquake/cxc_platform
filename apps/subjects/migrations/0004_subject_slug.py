from django.db import migrations, models
from django.utils.text import slugify


def fill_slugs(apps, schema_editor):
    Subject = apps.get_model("subjects", "Subject")
    used = set()
    for subject in Subject.objects.order_by("pk"):
        base = slugify(subject.name) or slugify(subject.code) or "subject"
        slug, n = base, 2
        while slug in used:
            slug, n = f"{base}-{n}", n + 1
        used.add(slug)
        subject.slug = slug
        subject.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [("subjects", "0003_topic_exam_weight")]

    operations = [
        migrations.AddField(
            model_name="subject",
            name="slug",
            field=models.SlugField(blank=True, default="", max_length=220),
            preserve_default=False,
        ),
        migrations.RunPython(fill_slugs, migrations.RunPython.noop),
    ]
