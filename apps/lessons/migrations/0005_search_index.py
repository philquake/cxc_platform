from django.db import migrations

from apps.core.search import gin_index_operation, lesson_search_vector


class Migration(migrations.Migration):
    dependencies = [("lessons", "0004_sanitize_existing_content")]
    operations = [gin_index_operation("lessons", "lesson", "lesson_search_gin", lesson_search_vector)]
