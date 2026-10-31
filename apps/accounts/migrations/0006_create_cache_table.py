from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    # The email resend cooldown lives in the database cache (settings.CACHES); this saves a separate deploy step.
    call_command("createcachetable", database=schema_editor.connection.alias)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_profile_hide_from_leaderboard")]

    operations = [migrations.RunPython(create_cache_table, migrations.RunPython.noop)]
