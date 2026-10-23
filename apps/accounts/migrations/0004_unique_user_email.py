from django.db import migrations


class Migration(migrations.Migration):
    """One account per email, case-insensitive. Blank emails (staff, old accounts) are exempt.

    Fails if two accounts already share an address; merge or fix those first.
    """

    dependencies = [
        ("accounts", "0003_profile_awaiting_verification"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunSQL(
            "CREATE UNIQUE INDEX auth_user_email_lower_uniq ON auth_user (LOWER(email)) WHERE email <> ''",
            "DROP INDEX auth_user_email_lower_uniq",
        ),
    ]
