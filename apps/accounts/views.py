from datetime import timedelta

from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.db.models import Count, Q
from django.utils import timezone
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from apps.progress.models import LessonProgress, QuizAnswer, QuizAttempt, UserProgress, XPTransaction
from apps.subjects.models import Subject
from .forms import AccountProfileForm, DisplayNameForm, SignupForm
from .models import Profile

STUDY_LOG_WEEKS = 12

def _redirect_after_auth(request):
	redirect_to = request.POST.get("next") or request.GET.get("next")
	if redirect_to and url_has_allowed_host_and_scheme(
		redirect_to,
		allowed_hosts={request.get_host()},
		require_https=request.is_secure(),
	):
		return redirect(redirect_to)
	return redirect("progress:dashboard")


def login_view(request):
	form = AuthenticationForm(request, data=request.POST or None)
	if request.method == "POST" and form.is_valid():
		login(request, form.get_user())
		return _redirect_after_auth(request)

	return render(
		request,
		"accounts/login.html",
		{"form": form, "next": request.GET.get("next", "")},
	)


def signup(request):
	form = SignupForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		user = form.save()
		login(request, user, backend="django.contrib.auth.backends.ModelBackend")
		messages.success(
			request,
			f"Welcome to compile/, {user.username}. Pick a subject to start your first lesson.",
		)
		return _redirect_after_auth(request)

	return render(
		request,
		"accounts/signup.html",
		{"form": form, "next": request.GET.get("next", "")},
	)


def _study_log(user):
	"""Day cells for the last STUDY_LOG_WEEKS weeks (Monday-first columns), shaded 0-3 by activity count."""
	today = timezone.localdate()
	start = today - timedelta(days=today.weekday() + 7 * (STUDY_LOG_WEEKS - 1))
	counts = {}
	for created in XPTransaction.objects.filter(
		user=user, created_at__date__gte=start - timedelta(days=1)
	).values_list("created_at", flat=True):
		day = timezone.localtime(created).date()
		counts[day] = counts.get(day, 0) + 1
	cells = []
	for offset in range((today - start).days + 1):
		day = start + timedelta(days=offset)
		count = counts.get(day, 0)
		cells.append({"day": day, "count": count, "level": min(count, 3)})
	return cells, sum(1 for cell in cells if cell["count"])


@login_required
def account(request):
	profile, _ = Profile.objects.get_or_create(user=request.user)
	is_password_post = request.method == "POST" and request.POST.get("action") == "password"
	is_details_post = request.method == "POST" and not is_password_post
	form = AccountProfileForm(request.POST if is_details_post else None, instance=request.user)
	name_form = DisplayNameForm(request.POST if is_details_post else None, instance=profile)
	password_form = PasswordChangeForm(request.user, request.POST if is_password_post else None)
	if is_details_post and form.is_valid() and name_form.is_valid():
		form.save()
		name_form.save()
		messages.success(request, "Profile saved.")
		return redirect("account")
	if is_password_post and password_form.is_valid():
		user = password_form.save()
		update_session_auth_hash(request, user)
		messages.success(request, "Password changed.")
		return redirect("account")

	user_progress, _ = UserProgress.objects.get_or_create(user=request.user)
	answers = QuizAnswer.objects.filter(attempt__user=request.user)
	answered = answers.count()
	correct = answers.filter(is_correct=True).count()
	completed_by_subject = {
		row["lesson__subject_id"]: row["n"]
		for row in LessonProgress.objects.filter(user=request.user, completed=True, lesson__is_active=True)
		.values("lesson__subject_id").annotate(n=Count("id"))
	}
	subjects = list(Subject.objects.filter(is_active=True).annotate(
		lesson_total=Count("lessons", filter=Q(lessons__is_active=True))
	))
	for subject in subjects:
		subject.done = completed_by_subject.get(subject.id, 0)
		subject.percent = round(subject.done / subject.lesson_total * 100) if subject.lesson_total else 0
	study_log, days_studied = _study_log(request.user)

	return render(
		request,
		"accounts/account.html",
		{
			"form": form,
			"name_form": name_form,
			"password_form": password_form,
			"password_open": is_password_post,
			"profile": profile,
			"user_progress": user_progress,
			"display_name": profile.display_name or request.user.get_full_name() or request.user.username,
			"initials": ((request.user.first_name[:1] + request.user.last_name[:1]) or request.user.username[:2]).upper(),
			"lessons_done": sum(completed_by_subject.values()),
			"quizzes_taken": QuizAttempt.objects.filter(user=request.user, completed_at__isnull=False).count(),
			"accuracy": round(correct / answered * 100) if answered else None,
			"subjects": subjects,
			"study_log": study_log,
			"study_log_weeks": STUDY_LOG_WEEKS,
			"days_studied": days_studied,
			"recent": XPTransaction.objects.filter(user=request.user).select_related("topic")[:6],
		},
	)


@require_POST
def logout_view(request):
	logout(request)
	return redirect("home")
