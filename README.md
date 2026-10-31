# compile/ (CXC Platform)

compile/ is a free exam-prep site for Caribbean students taking CSEC Information Technology and CAPE Computer Science. Students read lessons, take practice quizzes and timed mock exams, review flashcards, and track their progress with XP, streaks, leaderboards and study plans.

## Who it is for

The site is open to anyone studying on their own. There are no classes, groups or teacher accounts. The owner is the only admin: they write the content and mark worded answers in the Django admin.

Each student is moved between three quiz pathways (guided, personalised, exam practice) per topic, based on their recent quiz results. Students never choose a pathway and are not shown which one they are on.

## Features

**For students**
- Courses grouped into units, with a lesson reader, unit outline and mastery meters
- Practice quizzes in five formats: multiple choice, true/false, short answer, matching and worded (teacher-marked) answers
- Timed mock exams weighted by topic; the timer survives a page reload
- Flashcards (SM-2 spaced repetition) made automatically from missed questions, and a mistake bank
- XP, levels, daily streaks and topic/subject leaderboards, with a "Hide me from leaderboards" setting
- Topic mastery, exam readiness and a personal study plan built from an exam date
- Evening study reminder emails (flashcards due, today's plan, streak at risk), with one-click unsubscribe
- Site search, a binary converter tool, and email verification at signup
- Profile page with study log, data download (JSON) and self-service account deletion

**For the admin**
- Lesson authoring with CKEditor 5 and Cloudinary image uploads
- Question bank with CSV import/export, analytics, quality flags and content-gap filters
- Lesson quiz generator (Easy/Medium/Hard, optionally per pathway), auto-drawn quizzes and a mock exam generator
- Marking queue for worded answers, with feedback shown to the student
- Admin dashboard with site stats and an "Awaiting marking" count

## Technology

- Python 3.12+ and Django 6.1
- PostgreSQL on Supabase (tests use in-memory SQLite)
- django-ckeditor-5, Cloudinary storage, WhiteNoise, django-axes (login throttling), nh3 (HTML sanitising)
- Plain CSS and JavaScript, no build step
- Deployed on Render with gunicorn

## Project structure

```text
apps/
  accounts/   Signup, email verification, login, profile, data download, account deletion
  core/       Home, search, tools, about, terms, privacy, sitemap, robots.txt, ads.txt
  lessons/    Lessons, lesson images, lesson import
  progress/   XP, streaks, attempts, flashcards, mistake bank, study plans, mastery, pathways, study reminders
  questions/  Questions, answers, CSV import/export
  quizzes/    Practice quizzes, mock exams, quiz generators
  subjects/   Subjects, topics, course and lesson pages
config/       Settings, URLs, WSGI and ASGI
static/       CSS, JavaScript and admin assets
templates/    Page and email templates
```

## Setup

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill it in. Never commit `.env`. Required: `DJANGO_SECRET_KEY`, `DATABASE_URL`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`. With `DEBUG` off you also need the `EMAIL_*` SMTP settings, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.

3. Create the tables and an admin account, then start the server:

   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py runserver
   ```

   Open <http://127.0.0.1:8000/>. The admin is at <http://127.0.0.1:8000/admin/>.

## Deploying on Render

- Build: install requirements, then `python manage.py collectstatic --noinput` and `python manage.py migrate`.
- Start: `gunicorn config.wsgi`.
- Set `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` to the production domain.
- Migrations also create the database cache table used for email rate limits.

### Study reminders

Add a Render **Cron Job** that runs once each evening:

```bash
python manage.py send_study_reminders
```

A schedule of `0 23 * * *` (UTC) sends at 6 pm Jamaica time. Give the cron job the same environment variables as the web service. Reminders are sent from `REMINDER_FROM_EMAIL` (default `compile/ <tutorcole15@gmail.com>`). Gmail only sends as the account you sign in with, so set `EMAIL_HOST=smtp.gmail.com`, `EMAIL_HOST_USER=tutorcole15@gmail.com` and a Gmail app password as `EMAIL_HOST_PASSWORD`. Links in the email use `SITE_URL`, which defaults to the first `CSRF_TRUSTED_ORIGINS` entry.

## Main URLs

| URL | Purpose |
| --- | --- |
| `/` | Home |
| `/subjects/` | Courses |
| `/subjects/<subject>/lessons/<lesson>/` | Lesson reader |
| `/quizzes/` | Quizzes |
| `/progress/` | Dashboard |
| `/progress/flashcards/` | Flashcards |
| `/progress/mistakes/` | Mistake bank |
| `/progress/study-plan/<subject>/` | Study plan |
| `/progress/leaderboard/<subject>/` | Leaderboard |
| `/accounts/profile/` | Profile and settings |
| `/search/` | Search |
| `/tools/` | Tools |
| `/admin/` | Admin |

## Commands

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py send_study_reminders
```

Coverage for the content apps:

```bash
pip install -r requirements-dev.txt
python -m coverage run manage.py test apps.core apps.subjects apps.lessons apps.quizzes
python -m coverage report
```

## Migrations

Some migrations contain data changes (`questions/0002`, `quizzes/0002`, `progress/0006`). Don't delete, squash or reorder applied migrations casually; test any cleanup against both a fresh and an existing database.

## License

All rights reserved. See [LICENSE](LICENSE).
