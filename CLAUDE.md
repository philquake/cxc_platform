# CLAUDE.md

Guidance for working in this repo. Read this first, then change code.

## What this is

**compile/** (older branding: "CXCStudy") is an exam-prep platform for Caribbean CSEC IT and CAPE Computer Science students. Students read lessons, take quizzes and mock exams, review flashcards, and track progress with XP, streaks, leaderboards and study plans.

Owner: Phil (IT/CS teacher, Jamaica). Repo: `github.com/philquake/cxc_platform`.

## Stack

- Django 6.1, Python, PostgreSQL on Supabase (`DATABASE_URL`; `sslmode` comes from `DB_SSLMODE`, default `require`, set `disable` for local Postgres without SSL). Port 6543 (transaction pooler) switches to `CONN_MAX_AGE=0` and no server-side cursors; otherwise `CONN_MAX_AGE=600`
- Templates in top-level `templates/`, static in `static/` (plain CSS, no build step)
- django-bootstrap5 (base CSS only, no Bootstrap JS; most styling is custom in `static/css/`)
- Django admin is restyled with `static/admin/css/shadcn.css` and `templates/admin/` (custom index with a stats dashboard)
- django-ckeditor-5 for lesson content (config name `extends`)
- Cloudinary for media via `apps.core.storage.SeekSafeCloudinaryStorage`
- WhiteNoise (`CompressedManifestStaticFilesStorage`) for static files
- Deployed on Render (HTTPS proxy: `SECURE_PROXY_SSL_HEADER`, `CSRF_TRUSTED_ORIGINS`)
- Google AdSense script in `templates/_adsense.html`, included via `{% block adsense %}` only on content pages (home, courses, course, lesson, search with results; not the legal pages). Keep it off quiz, progress, account and error pages (AdSense inventory policy). `ads.txt` served from repo root via `apps/core/urls.py`

## Environment variables

Required: `DJANGO_SECRET_KEY`, `DATABASE_URL`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`.
Login throttling: django-axes locks a username for 15 min after 5 failed logins (`/accounts/login/` and `/admin/`); it adds `axes_*` tables, so run `migrate` on deploy. When `DEBUG` is false, session/CSRF cookies are secure and HSTS is on (Render terminates HTTPS and sets `X-Forwarded-Proto`).
Optional: `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `EMAIL_BACKEND` (defaults to console), `DEFAULT_FROM_EMAIL`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DB_SSLMODE`.
Loaded from `.env` at the repo root via django-environ. Never commit it.

## Common commands

```
python manage.py runserver
python manage.py makemigrations
python manage.py migrate
python manage.py test                 # all apps (uses in-memory SQLite, never Supabase)
python manage.py test apps.progress   # one app
python manage.py collectstatic --noinput
```

## Layout

```
config/            settings, root urls, wsgi/asgi
apps/
  core/            home, search, terms/privacy, /tools/ (binary converter), ads.txt, Cloudinary storage (no models)
  accounts/        signup/login/logout, account edit, password reset/change, Profile model + admin inline, `auth_extras` templatetags
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
- `Subject` 1─* `Lesson` (unique `subject+slug` and `subject+lesson_number`; slug auto-generated from title on save). Student-facing lesson order is always `section_number` (unit), then `lesson_number`: `Lesson.Meta`, lesson reader, quiz "next lesson", study plan and dashboard all use it.
- `Question` belongs to Subject, Topic **and** Lesson (all required). `clean()` enforces they agree.
  - Formats: `multiple_choice`, `true_false`, `short_answer`, `matching`, `worded`
  - Open-ended formats need `expected_answer`; short answers may list alternatives separated by `|` (punctuation and case are ignored). Worded answers are marked by a teacher (`expected_answer` is the reference answer).
  - `marks` (default 1), `mark_scheme`, `hint`, `estimated_time_minutes`, and pathway flags `for_guided`/`for_adaptive`/`for_practice` (default all on). True/false may have no `Answer` rows (uses `expected_answer`). Matching uses `Answer.text` + `Answer.match_text`.
- `Quiz` is either a **practice quiz** (requires topic + lesson) or a **mock exam** (`is_mock=True`, no topic/lesson, optional `time_limit_minutes`). Enforced in `clean()` and a DB check constraint.
- `QuizQuestion` through table. For practice quizzes the question must match the quiz topic and lesson; for mocks only the subject.
- `progress`: `UserProgress` (XP, streak, levels need 500 XP for level 2, then 100 XP more per level: 600, 700, ...), `LessonProgress`, `QuizAttempt`/`QuizAnswer`, `XPTransaction` (one per lesson completion or quiz attempt), `FlashcardState` (SM-2), `TopicMasteryStat`, `StudyPlan`/`StudyPlanItem`.
- Only one active `StudyPlan` per user+subject; saving an active plan deactivates the others.

## Key behaviours

- **Signup and email verification** (`accounts/views.py`): signup creates an inactive user with `Profile.awaiting_verification=True` and emails a one-time link (`default_token_generator`, expires after `PASSWORD_RESET_TIMEOUT`, 3 days). If sending fails the signup rolls back. Signing up again with the same username or email deletes the unverified account first, so a mistyped email never blocks a student. The link activates, clears the flag and signs the student in. Only never-logged-in inactive users with the flag can verify or resend, so an admin deactivation can't be undone by the student. Login tells an unverified student (right password only) to verify, with a resend link (`verify-email-resend`, same response whether or not anything was sent). Signed-in users with no email see a prompt in `base.html` to add one. Changing (or adding) an email on the profile page only takes effect from a signed link sent to the new address (`confirm-email-change`, 3 days, void once the email changes another way). Verification resends and change links are limited to one per address per 5 minutes via the cache (default LocMemCache, so per worker).

- **XP**: lesson complete = 50 XP, quiz = `25 + percentage // 5`, awarded only on a first completion or a strictly higher percentage than the user's previous best for that quiz (`finalize_attempt` and `complete_lesson` lock the user's `UserProgress` row so concurrent requests can't double-award; attempts are always recorded; past XP is untouched). Streak updates in `_award_xp`. Staff/superusers are excluded from leaderboards.
- **Quiz scoring** (`progress.views.submit_quiz`): `QuizAttempt.score` is marks awarded out of `total_marks` (`total_questions` is just the count). Objective formats score all-or-nothing; text is normalized for short answer, true/false-without-answers and matching. Non-blank worded answers get `marks_awarded=None` and the attempt is `awaiting_review`; teachers mark them in the QuizAnswer admin ("Awaiting marking" filter, editable in the list), and the last mark calls `finalize_attempt` (score, flashcards, `record_attempt`, XP, no streak change). Pending attempts are excluded from best-score, lesson mastery, readiness and the admin average, and unmarked answers from the mistake bank, profile accuracy and study-plan mistake reviews. A student can't resubmit a quiz while an earlier attempt of it still has unmarked answers. Question statistics (admin list, quality flag, dashboard) count marked answers only, and the student dashboard shows "Being marked" instead of a provisional score. Answers short of full marks create or reset a `FlashcardState` due today.
- **Flashcards**: `FlashcardState.review()` implements SM-2 with ratings `again/hard/good/easy`. Reviews are posted via fetch from `flashcards.html`, which alerts the student if a rating fails to save.
- **Mastery** (`progress/analytics.py`): recency-weighted accuracy, 14-day half-life, needs 5+ answers (`MIN_EVIDENCE`) before a topic counts. Totals live in `TopicMasteryStat` (user+topic+difficulty), updated by `record_attempt` at the end of `submit_quiz`, so reads never scan answer history. Anything that creates `QuizAnswer` rows directly (tests, imports) must call `record_attempt`. Totals are frozen at answer time: later topic/difficulty edits or deleted attempts don't change them. Readiness = 70% topic mastery + 30% latest mock when a mock exists.
- **Study plan** (`progress/study_plan.py`): remaining lessons sorted by `exam_weight * (1 - accuracy)`, max 3 lessons/day, flashcard review after each lesson, mistake review for topics with misses, a quiz every 4th lesson. Picking a new exam date deletes the user's old plans for that subject (items cascade).
- **Mock exams**: generated from the Subject admin action (`quizzes/services.py`). Questions sampled per topic by weight. Shortages are not padded from other topics.
- **Lesson quizzes**: the Lesson admin action calls `generate_lesson_quizzes` to make inactive Easy (MCQ), Medium (T/F, MCQ, short answer) and Hard (worded) practice quizzes from one topic+lesson, optionally one pathway. Format rules apply only here, not in `Question.clean()`. Any shortage raises unless "allow fewer" is ticked.
  - **Easy**: multiple choice only.
  - **Medium**: a mix of multiple choice, true/false and short answer.
  - **Hard**: worded answers, marked by a teacher against the question's reference answer, mark scheme and explanation.
  - Generated quizzes are **auto-draw** (`Quiz.auto_draw`, `draw_size`): no fixed question rows. Each page load draws a fresh set from the lesson's active questions of that difficulty (`draw_lesson_questions`): unseen questions first, then ones last answered wrongly, then the rest. Default sizes are 8 / 8 / 4 (`DEFAULT_COUNTS`); a bank under 3 questions is not offered. The page signs the drawn ids (`drawn` field) and `submit_quiz` scores exactly that set, rejecting a missing or tampered value.
  - **Mastery vs the bank** (`subjects/views.py::_lesson_mastery`): the best-score level is capped by coverage, the share of the lesson's active questions the student has a marked answer for: under 40% caps at Familiar, under 70% at Proficient, and Mastered also needs 100% on a non-Easy quiz. The course page shows "x of y questions seen".
- **Tools** (`/tools/`, `/tools/binary-converter/`): public, ad-eligible SEO pages. The converter is all client-side (`static/js/binary_tools.js`, BigInt, textContent only): bases with fractions and working, sign-magnitude/one's/two's complement, add/subtract with overflow, ASCII, BCD, CAPE mantissa/exponent and IEEE 754, plus a Practice tab (random marked problems; each generator reuses the calculator's own helpers so answer and working can't drift apart). The page has canonical, JSON-LD (WebApplication + FAQPage) and sitemap entries; keep the FAQ text and JSON-LD in step. Tabs deep-link by hash (`#signed`, `#float`...).
- **Search**: Postgres full-text (`SearchVector`/`SearchRank`) when available, `icontains` fallback otherwise (used in tests on SQLite). Results only include lessons/questions whose subject and lesson are active, so every result link opens.
- **Question CSV** (`questions/importers.py`): the "Export selected questions to CSV" admin action writes the same columns the importer reads (`COLUMNS`). A blank `id` adds a question; an exported `id` updates it (needs change permission), reusing answer rows by matching text, then position, so past attempts keep their selected option. `pathways` is required on every row: `guided|adaptive|practice`, or `none`. Imports are all-or-nothing.
- **Quiz page**: question order is shuffled on every render unless `Quiz.shuffle_questions` is off (prefetched as `quiz.question_list`). Hints show on non-mock quizzes.
- **Lesson images**: `optimize_images` filter injects Cloudinary transforms into `res.cloudinary.com/.../image/upload/` URLs in lesson HTML.

## URL conventions

- Subjects are addressed by `Subject.slug` (auto-generated from the name on first save, unique, editable in admin). `get_subject_or_404` also accepts the subject code. Templates build URLs with `subject.slug`.
- Namespaces: `subjects:`, `quizzes:`, `progress:`. Accounts and core URLs are un-namespaced (`login`, `signup`, `account`, `home`, `search`, `terms`, `privacy`).
- Redirects after auth/submit go through `apps.core.http.safe_next_url` (`url_has_allowed_host_and_scheme`). Use it for any new `next` handling.

## Conventions

- Keep structure lean: reuse existing models, views and CSS classes before adding new ones.
- Pedagogy first: every question should carry a real explanation.
- Light theme: navy (`--color-navy`, header/footer), apricot accent (`--color-accent`; use `--color-accent-ink` for apricot-toned text), sky, warm-white body (`--color-bg-body`, `--color-panel`). Use the CSS variables in `static/css/base.css`. Don't hard-code colors.
- Mobile breakpoints in use: 900px, 760px, 560px (a few pages also use 959px, 680px, 640px, 480px, 420px). New components need at least the 560px rule.
- Learning pages (landing page, courses, course page with expandable units and mastery meters, lesson reader with unit outline, stepped practice quiz) share `static/css/learn.css` and `static/js/quiz_stepper.js`. UI font is Figtree; the home page still uses the Imbue masthead. Lesson mastery (Attempted/Familiar/Proficient/Mastered) comes from the best quiz score per lesson (`subjects/views.py::_lesson_mastery`). Progress pages share a navy page band via `static/css/progress_learn.css` (loaded after `progress.css`).
- Page CSS lives in `static/css/<feature>.css` and is loaded through `{% block extra_css %}`. Bump the `?v=` query string when a cached stylesheet changes (currently `3.2` for `base.css`, `3.0` for `layout.css`, `2.2` for `site.css`).
- Views use function-based style. Many files indent with tabs (progress/views, quizzes/views, tests). Match the file you're editing; don't reformat whole files.
- Auth templates (`templates/accounts/*.html`) are standalone pages using `auth.css`, not `base.html`.
- 404 page (`templates/404.html`, `static/css/not_found.css`) has search plus subject/home links and no ads; it only renders with `DEBUG=False`. `500.html` is standalone with inline styles.
- Legal pages (`templates/legal/`): the privacy policy discloses Google AdSense cookies and opt-outs (section 5) and says the site is not directed at under-13s. Terms of Use are adapted from the General Legal (CC0) template: Jamaican law, liability capped at fees paid in the prior 12 months or US$50, no arbitration or US state clauses. Bump the "Last updated" date when either changes, and keep them consistent with what the site actually does (ads, cookies, data).
- Admin customisation matters: dashboard on the admin index (`templates/admin/index.html`, gated per view permission, with an "Awaiting marking" count), question analytics and filters (subject-scoped topic/lesson, pathway, usage, content gaps, response quality), CSV import/export, the marking queue (QuizAnswer admin; no add page), the Lesson "Generate Easy/Medium/Hard quizzes" action, Lesson "Activate/Deactivate selected lessons" actions (need change permission), topic/lesson filtering by subject on the quiz and question forms (`static/admin/js/quiz_admin.js`, options tagged by `quizzes.admin.tag_subjects`), lesson image picker (`static/admin/js/lesson_media.js`).

## Deployment gotchas

- `collectstatic` must run on deploy. WhiteNoise's manifest storage raises on missing static references, so a template referencing a nonexistent file will 500 in production.
- Cloudinary uploads need the file pointer rewound; that is why `SeekSafeCloudinaryStorage` exists. Keep it for both `DEFAULT` storage and `CKEDITOR_5_FILE_STORAGE`.
- `MEDIA_URL` is `media/` and is only served locally when `DEBUG=True`.
- Behind Render's proxy, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` must include the production domain.
- Migrations `questions/0002`, `quizzes/0002` and `progress/0006` contain data migrations. Don't squash or reorder them casually.

## Known issues and cleanup candidates

- `apps.core` is not in `INSTALLED_APPS`. It works because it has no models, but add it if you introduce any.
- Mock exam timers restart on page reload (the start time is signed per render), so recorded mock times can be gamed. Accepted for self-practice; store the start in the session if mocks ever count for grades.
- `StudyPlanItem` ordering and constraints changed in migration 0006; the admin for `progress` registers only `UserProgress`, `XPTransaction`, `LessonProgress`, `QuizAttempt` and `QuizAnswer`, not `StudyPlan`/`StudyPlanItem`/`FlashcardState`/`TopicMasteryStat`.
- Admin actions (activate/deactivate questions, generate lesson quizzes, generate mock exams) have no `allowed_permissions`, so any staff user who can view the changelist can run them. Fine while the owner is the only (super)user; add `permissions=[...]` / `has_perm("quizzes.add_quiz")` checks before giving teachers limited staff roles.
- `complete_lesson` falls back to an inactive "General" topic (created on demand) when a subject has no active topics, only so the XP row has a topic.
- Templates now use "compile/" consistently; the repo name and README title still say "CXC Platform".
- `dashboard` runs several queries per subject, and the study plan view one flashcard count per plan item. Watch performance as content grows.
- `AGENTS.md` holds separate agent-behaviour guidance ("lazy senior dev" style); keep it consistent with this file.
- `ads.txt` is read from the repo root; the test expects `google.com` in it.

## Testing notes

- Tests use `TestCase` and create their own Subject/Topic/Lesson/Question fixtures inline. There are no shared fixtures.
- Search tests patch `apps.core.views.connection` to simulate SQLite when needed.
- `QuizAnswer` rows created directly in tests need `marks_awarded` (e.g. `int(is_correct)`); without it they count as unmarked and are skipped by the mistake bank, accuracy and question statistics.
- When adding a feature, add a test in the owning app's `tests.py`. Cross-app flows (quiz submit, XP, flashcards) are tested in `apps/progress/tests.py`.
