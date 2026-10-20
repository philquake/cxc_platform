import csv
import io

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.lessons.models import Lesson
from apps.subjects.models import Subject, Topic

from .models import Answer, Question

OPTION_COLUMNS = ["option_1", "option_2", "option_3", "option_4"]
COLUMNS = [
    "subject", "topic", "lesson", "format", "text", "difficulty",
    "explanation", "expected_answer", *OPTION_COLUMNS, "correct",
]
SAMPLE_ROWS = [
    ["Information Technology", "Hardware", "1", "multiple_choice", "Which device is an input device?", "easy",
     "A keyboard sends data into the computer.", "", "Monitor", "Keyboard", "Printer", "Speaker", "2"],
    ["Information Technology", "Hardware", "1", "true_false", "RAM is volatile memory.", "easy",
     "RAM loses its contents when power is removed.", "", "", "", "", "", "true"],
    ["Information Technology", "Hardware", "1", "short_answer", "What does CPU stand for?", "easy",
     "CPU is the main processing unit.", "Central Processing Unit", "", "", "", "", ""],
    ["Information Technology", "Hardware", "1", "matching", "Match each device to its type.", "medium",
     "Devices are grouped by whether they send or show data.", "", "Mouse|Input", "Monitor|Output", "", "", ""],
]
FORMAT_ALIASES = {
    "mcq": "multiple_choice", "multiple choice": "multiple_choice", "true/false": "true_false",
    "true false": "true_false", "short answer": "short_answer", "worded answer": "worded",
}


def sample_csv():
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    writer.writerows(SAMPLE_ROWS)
    return out.getvalue()


def _lookup(rows_cache, key, finder):
    if key not in rows_cache:
        rows_cache[key] = finder()
    return rows_cache[key]


def _build_answers(question, row, line):
    fmt = question.format
    options = [row.get(c, "").strip() for c in OPTION_COLUMNS]
    options = [o for o in options if o]
    correct = row.get("correct", "").strip()
    if fmt == Question.FORMAT_MULTIPLE_CHOICE:
        if len(options) < 2:
            raise ValueError("multiple choice needs at least two options")
        index = None
        if correct.isdigit():
            index = int(correct) - 1
        elif len(correct) == 1 and correct.lower() in "abcd":
            index = "abcd".index(correct.lower())
        else:
            matches = [i for i, o in enumerate(options) if o.lower() == correct.lower()]
            index = matches[0] if matches else None
        if index is None or not 0 <= index < len(options):
            raise ValueError("'correct' must be 1-4, a-d, or the text of one option")
        return [Answer(question=question, text=o, is_correct=i == index, order=i) for i, o in enumerate(options)]
    if fmt == Question.FORMAT_TRUE_FALSE:
        value = correct.lower()
        if value not in {"true", "false", "t", "f"}:
            raise ValueError("'correct' must be true or false")
        is_true = value.startswith("t")
        question.expected_answer = "True" if is_true else "False"
        return [
            Answer(question=question, text="True", is_correct=is_true, order=0),
            Answer(question=question, text="False", is_correct=not is_true, order=1),
        ]
    if fmt == Question.FORMAT_MATCHING:
        pairs = []
        for i, option in enumerate(options):
            left, sep, right = option.partition("|")
            if not sep or not left.strip() or not right.strip():
                raise ValueError(f"option_{i + 1} must look like 'left|right'")
            pairs.append(Answer(question=question, text=left.strip(), match_text=right.strip(), is_correct=True, order=i))
        if len(pairs) < 2:
            raise ValueError("matching needs at least two pairs")
        return pairs
    return []


def import_questions(upload):
    """Create questions from a CSV. All-or-nothing: returns (created_count, errors)."""
    try:
        text = upload.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return 0, ["The file is not UTF-8 text. In Excel use 'Save as CSV UTF-8'."]
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    reader.fieldnames = [(f or "").strip().lower() for f in (reader.fieldnames or [])]
    missing = [c for c in ("subject", "topic", "lesson", "text") if c not in reader.fieldnames]
    if missing:
        return 0, [f"Missing required column(s): {', '.join(missing)}. Download the template to see the layout."]

    errors, built, cache = [], [], {}
    for line, row in enumerate(reader, start=2):
        row = {k: (v or "").strip() for k, v in row.items() if k}
        if not any(row.values()):
            continue
        try:
            subject = _lookup(cache, ("s", row["subject"].lower()), lambda: next(
                (s for s in Subject.objects.all()
                 if row["subject"].lower() in (s.name.lower(), (s.code or "").lower())), None))
            if not subject:
                raise ValueError(f"unknown subject '{row['subject']}'")
            topic = _lookup(cache, ("t", subject.pk, row["topic"].lower()),
                            lambda: Topic.objects.filter(subject=subject, name__iexact=row["topic"]).first())
            if not topic:
                raise ValueError(f"no topic '{row['topic']}' in {subject.name}; create it first")
            if not row["lesson"].isdigit():
                raise ValueError("'lesson' must be the lesson number")
            lesson = _lookup(cache, ("l", subject.pk, int(row["lesson"])),
                             lambda: Lesson.objects.filter(subject=subject, lesson_number=int(row["lesson"])).first())
            if not lesson:
                raise ValueError(f"{subject.name} has no lesson number {row['lesson']}")
            fmt = row.get("format", "").lower() or Question.FORMAT_MULTIPLE_CHOICE
            fmt = FORMAT_ALIASES.get(fmt, fmt)
            if fmt not in dict(Question.FORMAT_CHOICES):
                raise ValueError(f"unknown format '{fmt}'")
            difficulty = row.get("difficulty", "").lower() or "medium"
            question = Question(
                subject=subject, topic=topic, lesson=lesson, text=row["text"], format=fmt,
                difficulty=difficulty, explanation=row.get("explanation", ""),
                expected_answer=row.get("expected_answer", ""),
            )
            answers = _build_answers(question, row, line)
            try:
                question.full_clean()
            except ValidationError as exc:
                raise ValueError("; ".join(m for msgs in exc.message_dict.values() for m in msgs))
            built.append((question, answers))
        except ValueError as exc:
            errors.append(f"Row {line}: {exc}")

    if errors or not built:
        return 0, errors or ["The file has no question rows."]
    with transaction.atomic():
        for question, answers in built:
            question.save()
            for answer in answers:
                answer.question = question
            Answer.objects.bulk_create(answers)
    return len(built), []
