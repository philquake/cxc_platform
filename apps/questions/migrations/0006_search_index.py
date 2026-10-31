from django.db import migrations

from apps.core.search import gin_index_operation, question_search_vector


class Migration(migrations.Migration):
    dependencies = [("questions", "0005_question_estimated_time_minutes_and_more")]
    operations = [gin_index_operation("questions", "question", "question_search_gin", question_search_vector)]
