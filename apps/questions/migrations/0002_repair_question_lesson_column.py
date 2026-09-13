from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("lessons", "0011_lesson_number_constraint"),
        ("questions", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            DECLARE
                constraint_record record;
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'questions_question'
                      AND column_name = 'topic_id'
                ) THEN
                    FOR constraint_record IN
                        SELECT DISTINCT tc.constraint_name
                        FROM information_schema.table_constraints AS tc
                        JOIN information_schema.key_column_usage AS kcu
                          ON tc.constraint_name = kcu.constraint_name
                         AND tc.table_schema = kcu.table_schema
                        WHERE tc.table_name = 'questions_question'
                          AND tc.constraint_type = 'FOREIGN KEY'
                          AND kcu.column_name = 'topic_id'
                    LOOP
                        EXECUTE format(
                            'ALTER TABLE questions_question DROP CONSTRAINT %I',
                            constraint_record.constraint_name
                        );
                    END LOOP;

                    ALTER TABLE questions_question
                        RENAME COLUMN topic_id TO lesson_id;

                    ALTER TABLE questions_question
                        ADD CONSTRAINT questions_question_lesson_id_fk
                        FOREIGN KEY (lesson_id) REFERENCES lessons_lesson (id)
                        DEFERRABLE INITIALLY DEFERRED;
                END IF;
            END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]