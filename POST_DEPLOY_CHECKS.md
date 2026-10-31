# Post-deploy checks for the audit fixes (commit 2a44a25)

Do these after deploying. Each step says what you should see.

## 1. Deploy and migrate
1. Push `main` and let Render deploy.
2. Run `python manage.py migrate` (Render shell). It should apply `lessons.0005_search_index` and `questions.0006_search_index`.
3. In the Supabase SQL editor run:
   `select indexname from pg_indexes where indexname in ('lesson_search_gin','question_search_gin');`
   You should see both names.

## 2. Search uses the index
1. In the SQL editor run `explain select id from lessons_lesson where (setweight(to_tsvector('english'::regconfig, coalesce(title,'')),'A') || setweight(to_tsvector('english'::regconfig, coalesce(content,'')),'B')) @@ plainto_tsquery('english','memory');`
   You should see a Bitmap Index Scan on `lesson_search_gin` (a tiny table may still show a seq scan; add `set enable_seqscan=off;` first to prove the index matches).
2. On the live site search for a word you know is in a lesson. Lessons and questions should still appear, best match first.

## 3. Login lockout is per IP
1. Open a private window and fail login 5 times for a test username. You should be locked out.
2. On your phone (different network) try that same username. You should NOT be locked out.
3. If everyone is locked together, the proxy count is wrong. Set `AXES_PROXY_COUNT=2` in Render env vars and redeploy.
4. Log in to /admin/ normally to confirm you are not locked.

## 4. Signup cap and email
1. Sign up with a real test email. The verification email should arrive.
2. (Optional) lower `SIGNUPS_PER_HOUR` temporarily to see the "a lot of signups" message.

## 5. Pages still fast and correct
1. Home page shows the right lesson and question counts per subject.
2. Dashboard, a course page and a lesson page load and look the same as before.

## 6. Reminders
1. In the Render shell run `python manage.py send_study_reminders` twice.
2. The second run should say `Sent 0 study reminders.` and the first should send the real ones.

## 7. Study plan
1. On a study plan page, double-click "Create plan". You should end up with one plan.

If anything fails, note the step and tell Claude.
