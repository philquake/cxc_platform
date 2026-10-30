import html
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import nh3
from django.db import transaction

from .models import Lesson

ALLOWED = {".html", ".htm", ".txt", ".docx"}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx_to_html(upload):
    with zipfile.ZipFile(upload) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))
    out, list_open = [], False
    for p in root.iter(W + "p"):
        style = p.find(f"{W}pPr/{W}pStyle")
        style = style.get(W + "val", "") if style is not None else ""
        is_item = p.find(f"{W}pPr/{W}numPr") is not None
        runs = []
        for r in p.iter(W + "r"):
            t = html.escape("".join(x.text or "" for x in r.iter(W + "t")))
            if not t:
                continue
            if r.find(f"{W}rPr/{W}b") is not None:
                t = f"<strong>{t}</strong>"
            if r.find(f"{W}rPr/{W}i") is not None:
                t = f"<em>{t}</em>"
            runs.append(t)
        body = "".join(runs).strip()
        if list_open and not is_item:
            out.append("</ul>")
            list_open = False
        if not body:
            continue
        heading = re.match(r"(?:Heading|Title)\s*(\d?)", style, re.I)
        if heading:
            level = min(int(heading.group(1) or 1) + 1, 4)
            out.append(f"<h{level}>{body}</h{level}>")
        elif is_item:
            if not list_open:
                out.append("<ul>")
                list_open = True
            out.append(f"<li>{body}</li>")
        else:
            out.append(f"<p>{body}</p>")
    if list_open:
        out.append("</ul>")
    return "\n".join(out)


def _clean_html(raw):
    body = re.search(r"(?is)<body[^>]*>(.*)</body>", raw)
    return nh3.clean(body.group(1) if body else raw).strip()


def _txt_to_html(raw):
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    return "\n".join("<p>" + html.escape(p).replace("\n", "<br>") + "</p>" for p in paragraphs)


def _convert(upload, ext):
    if ext == ".docx":
        return _docx_to_html(upload)
    raw = upload.read().decode("utf-8-sig", errors="replace")
    return _txt_to_html(raw) if ext == ".txt" else _clean_html(raw)


def _split_title(content, filename):
    """Use the first heading as the title when there is one, else the file name."""
    match = re.match(r"\s*<h[1-4][^>]*>(.*?)</h[1-4]>", content, re.S | re.I)
    if match:
        title = html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
        if title:
            return title[:200], content[match.end():].strip()
    return re.sub(r"[_-]+", " ", Path(filename).stem).strip().title()[:200], content


def import_lessons(subject, uploads, publish):
    """Create one lesson per file. All-or-nothing: returns (created_titles, errors)."""
    errors, built = [], []
    for upload in sorted(uploads, key=lambda f: f.name.lower()):
        ext = Path(upload.name).suffix.lower()
        if ext not in ALLOWED:
            errors.append(f"{upload.name}: unsupported type (use .docx, .html or .txt)")
            continue
        try:
            content = _convert(upload, ext)
        except Exception:
            errors.append(f"{upload.name}: could not be read; is it a valid {ext} file?")
            continue
        if not content.strip():
            errors.append(f"{upload.name}: no text found")
            continue
        built.append(_split_title(content, upload.name))
    if errors or not built:
        return [], errors or ["No files were chosen."]

    with transaction.atomic():
        number = max(Lesson.objects.filter(subject=subject).values_list("lesson_number", flat=True), default=0)
        # New notes go at the end of the course, so into its last unit.
        section = max(Lesson.objects.filter(subject=subject).values_list("section_number", flat=True), default=1)
        created = []
        for title, content in built:
            number += 1
            # Lesson.save picks a free slug from the title.
            Lesson.objects.create(subject=subject, title=title, lesson_number=number, section_number=section,
                                  content=content, is_active=publish)
            created.append(f"{number}. {title}")
    return created, []
