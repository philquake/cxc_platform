# CXC Platform

CXC Platform is a Django-based learning platform for Caribbean students preparing for CSEC and CAPE examinations. It provides subjects, ordered lessons, rich lesson content, image uploads, questions, quizzes, accounts, and progress tracking.

## Features

- Subject and lesson browsing
- Lesson numbering and section organization
- Rich lesson authoring with CKEditor 5
- Inline image uploads inside lesson content
- Reusable existing-image selection in the Django admin
- Questions and answers linked to lessons
- Quizzes assembled from questions
- User accounts and lesson progress tracking
- PostgreSQL database support
- Static and uploaded media handling for development

## Technology

- Python
- Django 6.1
- PostgreSQL
- django-ckeditor-5
- django-bootstrap5
- django-browser-reload
- Pillow
- psycopg

## Project Structure

```text
apps/
  accounts/   Login and signup flows
  core/       Home page
  lessons/    Lessons, lesson images, and lesson migrations
  progress/   Lesson progress and quiz attempts
  questions/  Questions and answers
  quizzes/    Quizzes and quiz-question ordering
  subjects/   Subject and lesson browsing
config/       Django settings, URLs, WSGI, and ASGI
static/       CSS and admin JavaScript
templates/    Shared and app templates
media/        Local uploaded media files
manage.py     Django command-line entry point
```

## Requirements

- Python 3.12 or newer is recommended.
- PostgreSQL must be running and accessible.
- The project dependencies are listed in `requirements.txt`.

## Setup

### 1. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root. Do not commit it.

```dotenv
DJANGO_SECRET_KEY=replace-with-a-secure-secret-key
DJANGO_DEBUG=true

POSTGRES_DB=cxc_platform
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
```

The settings module reads these values with `python-dotenv`. `ALLOWED_HOSTS` is currently empty, so add your development or production hostnames before deploying.

### 4. Apply migrations

```bash
python manage.py migrate
```

### 5. Create an admin user

```bash
python manage.py createsuperuser
```

### 6. Start the development server

```bash
python manage.py runserver
```

Open <http://127.0.0.1:8000/> in a browser. The admin is available at <http://127.0.0.1:8000/admin/>.

## Lesson Authoring

1. Sign in to the Django admin.
2. Open **Lessons** and create or edit a lesson.
3. Set a unique lesson number for the subject.
4. Set the section number and section title.
5. Add lesson content through CKEditor.
6. Use the CKEditor image button to upload a new image at the cursor.
7. To reuse an existing database image, click inside the content editor, select an image under **Existing images**, and click **Insert at cursor**.
8. Save the lesson.

Lessons are displayed on the subject page grouped by section number. Sections and lessons are ordered from lowest to highest number.

Uploaded images are stored under `media/lesson_images/` during development. The original seeded images for the Introduction to Information Technology lesson are also stored there.

## URLs

| URL | Purpose |
| --- | --- |
| `/` | Home page |
| `/accounts/login/` | Sign in |
| `/accounts/signup/` | Create an account |
| `/subjects/` | Subject list |
| `/subjects/<subject>/` | Subject lesson list |
| `/subjects/<subject>/lessons/<lesson>/` | Lesson detail |
| `/admin/` | Django administration |
| `/ckeditor5/image_upload/` | CKEditor image upload endpoint |

## Useful Commands

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test
python manage.py showmigrations
```

To inspect lesson ordering:

```bash
python manage.py shell -c "from apps.lessons.models import Lesson; print(list(Lesson.objects.order_by('section_number', 'lesson_number').values_list('section_number', 'lesson_number', 'title')))"
```

## Migrations

Lesson migrations currently cover:

- The original topic-based lesson structure
- Migration from topics to subjects
- The former section model and its simplification into lesson section fields
- CKEditor content
- Lesson image storage
- Seeded lesson images
- Image path normalization
- Lesson and section numbering

Do not delete applied migrations individually. If migration cleanup is needed, squash them deliberately and test the resulting migration chain against a fresh database and an existing database.

## Static and Media Files

Static files are served from `static/` in development. Uploaded files are stored in `MEDIA_ROOT`, configured as the project `media/` directory. Development media URLs are enabled only when `DEBUG` is true.

For production, configure:

- A secure `SECRET_KEY`
- `DEBUG=false`
- `ALLOWED_HOSTS`
- PostgreSQL credentials
- Static file collection and serving
- Persistent or object storage for uploaded media
- A production WSGI or ASGI server

## Testing and Validation

Run the Django system check before starting the server:

```bash
python manage.py check
```

Run the test suite with:

```bash
python manage.py test
```

The project currently has app test modules, but some contain no test cases yet.
