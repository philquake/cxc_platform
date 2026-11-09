from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('progress', '0013_delete_classroom'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprogress',
            name='freeze_used_on',
            field=models.DateField(blank=True, null=True),
        ),
    ]
