from django.contrib.postgres.search import SearchVector

# A fixed config is required for an index: the database default isn't immutable.
SEARCH_CONFIG = "english"


def lesson_search_vector():
    return SearchVector("title", weight="A", config=SEARCH_CONFIG) + SearchVector("content", weight="B", config=SEARCH_CONFIG)


def question_search_vector():
    return SearchVector("text", weight="A", config=SEARCH_CONFIG) + SearchVector("explanation", weight="B", config=SEARCH_CONFIG)


def gin_index_operation(app_label, model_name, index_name, vector):
    """Migration operation adding a GIN index on a search vector; a no-op off Postgres (tests run on SQLite)."""
    from django.contrib.postgres.indexes import GinIndex
    from django.db import migrations

    def add(apps, schema_editor):
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.add_index(apps.get_model(app_label, model_name), GinIndex(vector(), name=index_name))

    def remove(apps, schema_editor):
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.remove_index(
                apps.get_model(app_label, model_name), GinIndex(vector(), name=index_name)
            )

    return migrations.RunPython(add, remove)
