import csv
import io

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.lessons.models import Lesson
from apps.subjects.models import Subject, Topic

from .models import PATHWAY_CHOICES, Answer, Question

OPTION_COLUMNS = ["option_1", "option_2", "option_3", "option_4"]
COLUMNS = [
    "id", "subject", "topic", "lesson", "format", "text", "difficulty",
    "explanation", "expected_answer", *OPTION_COLUMNS, "correct",
    "marks", "mark_scheme", "hint", "estimated_time", "pathways",
]
PATHWAYS = [value for value, _ in PATHWAY_CHOICES]
SAMPLE_ROWS = [[""] + row for row in [
    ["Information Technology", "Hardware", "1", "multiple_choice", "Which device is an input device?", "easy",
     "A keyboard sends data into the computer.", "", "Monitor", "Keyboard", "Printer", "Speaker", "2",
     "", "", "", "", "guided|adaptive|practice"],
    ["Information Technology", "Hardware", "1", "true_false", "RAM is volatile memory.", "easy",
     "RAM loses its contents when power is removed.", "", "", "", "", "", "true",
     "", "", "", "", "guided|adaptive|practice"],
    ["Information Technology", "Hardware", "1", "short_answer", "What does CPU stand for?", "easy",
     "CPU is the main processing unit.", "Central Processing Unit", "", "", "", "", "",
     "", "", "", "", "guided|practice"],
    ["Information Technology", "Hardware", "1", "matching", "Match each device to its type.", "medium",
     "Devices are grouped by whether they send or show data.", "", "Mouse|Input", "Monitor|Output", "", "", "",
     "", "", "", "", "adaptive"],
    ["Information Technology", "Hardware", "1", "worded", "Explain two differences between RAM and ROM.", "hard",
     "RAM is temporary working memory; ROM holds start-up instructions.",
     "RAM is volatile and can be written to; ROM is non-volatile and read-only.", "", "", "", "", "",
     "4", "1 mark per correct difference (max 2), 1 mark each for explaining it (max 2).",
     "Think about what happens when the power goes off.", "4", "guided|practice"],
]]
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


def export_csv(questions):
    """Questions as CSV in the import layout; edit and re-import to update them by id."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    for question in questions.select_related("subject", "topic", "lesson").prefetch_related("answers"):
        answers = list(question.answers.all())
        options, correct = [""] * len(OPTION_COLUMNS), ""
        if question.format == Question.FORMAT_MATCHING:
            for i, answer in enumerate(answers[: len(options)]):
                options[i] = f"{answer.text}|{answer.match_text}"
        elif question.format == Question.FORMAT_TRUE_FALSE:
            correct = next((a.text for a in answers if a.is_correct), question.expected_answer).lower()
        elif question.format == Question.FORMAT_MULTIPLE_CHOICE:
            for i, answer in enumerate(answers[: len(options)]):
                options[i] = answer.text
                if answer.is_correct:
                    correct = str(i + 1)
        writer.writerow([
            question.pk, question.subject.code or question.subject.name, question.topic.name,
            question.lesson.lesson_number, question.format, question.text, question.difficulty,
            question.explanation, "" if question.format == Question.FORMAT_TRUE_FALSE else question.expected_answer,
            *options, correct, question.marks, question.mark_scheme, question.hint,
            question.estimated_time_minutes or "",
            "|".join(p for p in PATHWAYS if getattr(question, f"for_{p}")) or "none",
        ])
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


def import_questions(upload, allow_update=True):
    """Create questions from a CSV, or update them when the id column is filled.

    allow_update=False rejects rows with an id (for staff who may add but not change questions).
    All-or-nothing: returns (saved_count, errors).
    """
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
    missing = [c for c in ("subject", "topic", "lesson", "text", "pathways") if c not in reader.fieldnames]
    if missing:
        return 0, [f"Missing required column(s): {', '.join(missing)}. Download the template to see the layout."]

    errors, built, cache, seen_ids = [], [], {}, set()
    for line, row in enumerate(reader, start=2):
        row = {k: (v or "").strip() for k, v in row.items() if k}
        if not any(row.values()):
            continue
        try:
            existing = None
            if row.get("id"):
                if not allow_update:
                    raise ValueError("you can add questions but not change them; clear the id")
                if not row["id"].isdigit():
                    raise ValueError("'id' must be blank (new question) or an exported question id")
                if row["id"] in seen_ids:
                    raise ValueError(f"id {row['id']} appears more than once")
                seen_ids.add(row["id"])
                existing = Question.objects.filter(pk=int(row["id"])).first()
                if not existing:
                    raise ValueError(f"no question with id {row['id']}; clear the id to add it as new")
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
            for column in ("marks", "estimated_time"):
                if row.get(column) and not row[column].isdigit():
                    raise ValueError(f"'{column}' must be a whole number")
            pathways = {p.strip().lower() for p in row.get("pathways", "").split("|") if p.strip()}
            if pathways == {"none"}:
                pathways = set()
            elif not pathways or pathways - set(PATHWAYS):
                raise ValueError(f"'pathways' must be {', '.join(PATHWAYS)} separated by |, or none")
            question = existing or Question()
            fields = dict(
                subject=subject, topic=topic, lesson=lesson, text=row["text"], format=fmt,
                difficulty=difficulty, explanation=row.get("explanation", ""),
                expected_answer=row.get("expected_answer", ""),
                marks=int(row.get("marks") or 1), mark_scheme=row.get("mark_scheme", ""),
                hint=row.get("hint", ""),
                estimated_time_minutes=int(row["estimated_time"]) if row.get("estimated_time") else None,
                **{f"for_{p}": p in pathways for p in PATHWAYS},
            )
            for name, value in fields.items():
                setattr(question, name, value)
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
        new_answers, changed_answers, dropped = [], [], []
        for question, answers in built:
            is_new = question.pk is None
            question.save()
            for answer in answers:
                answer.question = question
            if is_new:
                new_answers += answers
                continue
            # Keep each option's row (and the past picks pointing at it): same text first, then by position.
            spare = list(question.answers.order_by("order", "id"))
            for answer in answers:
                match = next((a for a in spare if a.text.lower() == answer.text.lower()), None)
                if match:
                    answer.pk = match.pk
                    spare.remove(match)
            for answer in answers:
                if answer.pk is None and spare:
                    answer.pk = spare.pop(0).pk
                (changed_answers if answer.pk else new_answers).append(answer)
            dropped += [a.pk for a in spare]
        Answer.objects.filter(pk__in=dropped).delete()
        Answer.objects.bulk_update(changed_answers, ["text", "match_text", "is_correct", "order"])
        Answer.objects.bulk_create(new_answers)
    return len(built), []
