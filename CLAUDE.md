# CLAUDE.md

Guidance for working in this repo. Read this first, then change code.

## What this is

**compile/** (older branding: "CXCStudy") is an exam-prep platform for Caribbean CSEC IT and CAPE Computer Science students. Students read lessons, take quizzes and mock exams, review flashcards, and track progress with XP, streaks, leaderboards and study plans.

Owner: Phil (IT/CS teacher, Jamaica). Repo: `github.com/philquake/cxc_platform`.

## Stack

- Django 6.1, Python, PostgreSQL on Supabase (`DATABASE_URL`; `sslmode` comes from `DB_SSLMODE`, default `require`, set `disable` for local Postgres without SSL). Port 6543 (transaction pooler) switches to `CONN_MAX_AGE=0` and no server-side cursors; otherwise `CONN_MAX_AGE=600`
- Templates in top-level `templates/`, static in `static/` (plain CSS, no build step)
- django-bootstrap5 (base CSS/JS only; most styling is custom in `static/css/`), django-browser-reload (dev)
- Django admin is restyled with `static/admin/css/shadcn.css` and `templates/admin/` (custom index with a stats dashboard)
- django-ckeditor-5 for lesson content (config name `extends`)
- Cloudinary for media via `apps.core.storage.SeekSafeCloudinaryStorage`
- WhiteNoise (`CompressedManifestStaticFilesStorage`) for static files
- Deployed on Render (HTTPS proxy: `SECURE_PROXY_SSL_HEADER`, `CSRF_TRUSTED_ORIGINS`)
- Google AdSense script in `base.html`; `ads.txt` served from repo root via `apps/core/urls.py`

## Environment variables

Required: `DJANGO_SECRET_KEY`, `DATABASE_URL`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`.
Optional: `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `EMAIL_BACKEND` (defaults to console), `DEFAULT_FROM_EMAIL`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DB_SSLMODE`.
Loaded from `.env` at the repo root via django-environ. Never commit it.

## Common commands

```
python manage.py runserver
python manage.py makemigrations
python manage.py migrate
python manage.py test                 # all apps
python manage.py test apps.progress   # one app
python manage.py collectstatic --noinput
```

## Layout

```
config/            settings, root urls, wsgi/asgi
apps/
  core/            home, search, terms/privacy, ads.txt, Cloudinary storage (empty models.py)
  accounts/        signup/login/logout, account edit, password reset/change, Profile model + admin inline (never created by views), `auth_extras` templatetags
  subjects/        Subject, Topic (exam_weight), subject/lesson views
  lessons/         Lesson (CKEditor5 content), LessonImage, `optimize_images` template filter
  questions/       Question (5 formats), Answer
  quizzes/         Quiz (practice or mock), QuizQuestion, mock exam generator service
  progress/        XP, streaks, attempts, flashcards (SM-2), mistake bank, study plans, analytics, `admin_dashboard` templatetag (admin index stats)
templates/         base.html, 404/500 + per-app folders (accounts, admin, core, legal, progress, quizzes, subjects)
static/css|js|admin/css|admin/js
```

## Data model (key relationships)

- `Subject` 1─* `Topic` (unique `subject+slug`; `exam_weight` drives mocks and study plans)
- `Subject` 1─* `Lesson` (unique `subject+slug` and `subject+lesson_number`; slug auto-generated from title on save)
- `Question` belongs to Subject, Topic **and** Lesson (all required). `clean()` enforces they agree.
  - Formats: `multiple_choice`, `true_false`, `short_answer`, `matching`, `worded`
  - Open-ended formats need `expected_answer`. True/false may have no `Answer` rows (uses `expected_answer`). Matching uses `Answer.text` + `Answer.match_text`.
- `Quiz` is either a **practice quiz** (requires topic + lesson) or a **mock exam** (`is_mock=True`, no topic/lesson, optional `time_limit_minutes`). Enforced in `clean()` and a DB check constraint.
- `QuizQuestion` through table. For practice quizzes the question must match the quiz topic and lesson; for mocks only the subject.
- `progress`: `UserProgress` (XP, streak, level = 500 XP/level), `LessonProgress`, `QuizAttempt`/`QuizAnswer`, `XPTransaction` (one per lesson completion or quiz attempt), `MistakeReview`, `FlashcardState` (SM-2), `StudyPlan`/`StudyPlanItem`.
- Only one active `StudyPlan` per user+subject; saving an active plan deactivates the others.

## Key behaviours

- **XP**: lesson complete = 50 XP, quiz = `25 + percentage // 5`. Streak updates in `_award_xp`. Staff/superusers are excluded from leaderboards.
- **Quiz scoring** (`progress.views.submit_quiz`): normalizes text (lowercase, collapsed whitespace) for short answer, worded, true/false-without-answers and matching. Wrong answers create or reset a `FlashcardState` due today.
- **Flashcards**: `FlashcardState.review()` implements SM-2 with ratings `again/hard/good/easy`. Reviews are posted via fetch from `flashcards.html`.
- **Mastery** (`progress/analytics.py`): recency-weighted accuracy, 14-day half-life, needs 5+ answers (`MIN_EVIDENCE`) before a topic counts. Readiness = 70% topic mastery + 30% latest mock when a mock exists.
- **Study plan** (`progress/study_plan.py`): remaining lessons sorted by `exam_weight * (1 - accuracy)`, max 3 lessons/day, flashcard review after each lesson, mistake review for topics with misses, a quiz every 4th lesson.
- **Mock exams**: generated from the Subject admin action (`quizzes/services.py`). Questions sampled per topic by weight. Shortages are not padded from other topics.
- **Search**: Postgres full-text (`SearchVector`/`SearchRank`) when available, `icontains` fallback otherwise (used in tests on SQLite).
- **Quiz page**: question order is randomized on every render (`order_by("?")`).
- **Lesson images**: `optimize_images` filter injects Cloudinary transforms into `res.cloudinary.com/.../image/upload/` URLs in lesson HTML.

## URL conventions

- Subjects are addressed by **slugified subject name** (`subject.name|slugify`), and several views also accept the slugified code. Lookup is done by iterating active subjects in Python, not via a slug field.
- `lesson_detail` finds the subject with `name__iexact=slug.replace("-", " ")`. This breaks for subject names containing real hyphens or punctuation. Prefer adding a proper `slug` field if you touch this.
- Namespaces: `subjects:`, `quizzes:`, `progress:`. Accounts and core URLs are un-namespaced (`login`, `signup`, `account`, `home`, `search`, `terms`, `privacy`).
- Redirects after auth/submit go through `url_has_allowed_host_and_scheme`. Keep that check on any new `next` handling.

## Conventions

- Keep structure lean: reuse existing models, views and CSS classes before adding new ones.
- Pedagogy first: every question should carry a real explanation.
- Light theme: navy (`--color-navy`, header/footer), apricot accent (`--color-accent`; use `--color-accent-ink` for apricot-toned text), sky, warm-white body (`--color-bg-body`, `--color-panel`). Use the CSS variables in `static/css/base.css`. Don't hard-code colors.
- Mobile breakpoints in use: 900px, 760px, 560px (a few pages also use 959px, 680px, 640px, 480px, 420px). New components need at least the 560px rule.
- Learning pages (landing page, courses, course page with expandable units and mastery meters, lesson reader with unit outline, stepped practice quiz) share `static/css/learn.css` and `static/js/quiz_stepper.js`. UI font is Figtree; the home page still uses the Imbue masthead. Lesson mastery (Attempted/Familiar/Proficient/Mastered) comes from the best quiz score per lesson (`subjects/views.py::_lesson_mastery`). Progress pages share a navy page band via `static/css/progress_learn.css` (loaded after `progress.css`). `static/css/pages.css` is now unused by templates.
- Page CSS lives in `static/css/<feature>.css` and is loaded through `{% block extra_css %}`. Bump the `?v=` query string when a cached stylesheet changes (currently `3.0` for `base.css` and `layout.css`).
- Views use function-based style. Many files indent with tabs (progress/views, quizzes/views, tests). Match the file you're editing; don't reformat whole files.
- Auth templates (`templates/accounts/*.html`) are standalone pages using `auth.css`, not `base.html`.
- Admin customisation matters: dashboard on the admin index (`templates/admin/index.html`, gated per view permission), question analytics, quiz question filtering by subject/topic/lesson (`static/admin/js/quiz_admin.js`), lesson image picker (`static/admin/js/lesson_media.js`).

## Deployment gotchas

- `collectstatic` must run on deploy. WhiteNoise's manifest storage raises on missing static references, so a template referencing a nonexistent file will 500 in production.
- Cloudinary uploads need the file pointer rewound; that is why `SeekSafeCloudinaryStorage` exists. Keep it for both `DEFAULT` storage and `CKEDITOR_5_FILE_STORAGE`.
- `MEDIA_URL` is `media/` and is only served locally when `DEBUG=True`.
- Behind Render's proxy, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` must include the production domain.
- Migrations `questions/0002`, `quizzes/0002` and `progress/0006` contain data migrations. Don't squash or reorder them casually.

## Known issues and cleanup candidates

- `apps.core` is not in `INSTALLED_APPS`. It works because it has no models, but add it if you introduce any.
- `quizzes/admin.py` defines `QuizQuestionInlineFormSet` twice; the second definition wins and the first is dead code. `DataAttrSelect` is defined after its first use.
- `progress/tests.py` still has duplicated test methods (`test_flashcard_reviews_apply_sm2_growth_ease_and_reset`, `test_flashcard_review_rejects_unknown_rating`, `test_study_plan_items_require_one_same_subject_target_and_valid_date`); later definitions shadow earlier ones, so delete the first copies.
- `StudyPlanItem` ordering and constraints changed in migration 0006; the admin for `progress` registers only `UserProgress`, `XPTransaction`, `LessonProgress`, `QuizAttempt` and `QuizAnswer`, not `StudyPlan`/`StudyPlanItem`/`FlashcardState`/`MistakeReview`.
- Templates now use "compile/" consistently; the repo name and README title still say "CXC Platform".
- `Profile` model is in the admin (inline on User) but no view or signal creates it.
- `templates/subjects/lesson_detail.html` calls `quiz.quiz_questions.count()` per quiz (extra queries).
- `dashboard` and the study plan view run several queries per subject. Watch performance as content grows.
- `AGENTS.md` holds separate agent-behaviour guidance ("lazy senior dev" style); keep it consistent with this file.
- `ads.txt` is read from the repo root; the test expects `google.com` in it.

## Testing notes

- Tests use `TestCase` and create their own Subject/Topic/Lesson/Question fixtures inline. There are no shared fixtures.
- Search tests patch `apps.core.views.connection` to simulate SQLite when needed.
- When adding a feature, add a test in the owning app's `tests.py`. Cross-app flows (quiz submit, XP, flashcards) are tested in `apps/progress/tests.py`.
