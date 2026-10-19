from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="time_multiplier",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("1.00"),
                help_text="Extra time on timed mock exams, e.g. 1.25 gives 25% more time. Set by staff for students with accommodations.",
                max_digits=3,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("1.00")),
                    django.core.validators.MaxValueValidator(Decimal("3.00")),
                ],
            ),
        ),
    ]
