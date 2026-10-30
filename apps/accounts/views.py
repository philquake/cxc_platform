import logging
from datetime import timedelta

from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.shortcuts import redirect, render
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST
from apps.core.http import safe_next_url
from apps.progress.models import LessonProgress, QuizAnswer, QuizAttempt, UserProgress, XPTransaction
from apps.subjects.models import Subject
from .forms import AccountProfileForm, DisplayNameForm, ResendVerificationForm, SignupForm
from .models import Profile

logger = logging.getLogger(__name__)
EMAIL_LINK_MAX_AGE = 3 * 24 * 60 * 60
RESEND_COOLDOWN = 5 * 60
SIGNUP_REPLACE_AFTER = timedelta(minutes=3)


def _cooling_down(email):
	"""True if a link went to this address in the last RESEND_COOLDOWN seconds; otherwise starts the clock."""
	# shortcut: default LocMemCache is per worker process, so each gunicorn worker allows its own email; use a shared cache if abuse shows up.
	return not cache.add(f"email-link:{email.lower()}", True, RESEND_COOLDOWN)

STUDY_LOG_WEEKS = 12


class ThrottledPasswordResetView(auth_views.PasswordResetView):
	"""At most one reset email per address per RESEND_COOLDOWN, like the other emailed links."""

	def form_valid(self, form):
		if _cooling_down(form.cleaned_data["email"]):
			# Same redirect as a real send, so it never reveals whether anything went out.
			return redirect(self.get_success_url())
		return super().form_valid(form)

def _pending_users():
	# Never-used signups only, so a teacher's deactivation can't be undone with a verification link.
	return User.objects.filter(is_active=False, last_login__isnull=True, profile__awaiting_verification=True)


def _send_verification(request, user):
	link = request.build_absolute_uri(reverse("verify-email", args=[
		urlsafe_base64_encode(force_bytes(user.pk)), default_token_generator.make_token(user),
	]))
	send_mail(
		render_to_string("accounts/verify_subject.txt").strip(),
		render_to_string("accounts/verify_email.txt", {"user": user, "link": link}),
		None,
		[user.email],
	)


def login_view(request):
	form = AuthenticationForm(request, data=request.POST or None)
	if request.method == "POST" and form.is_valid():
		login(request, form.get_user())
		return redirect(safe_next_url(request, reverse("progress:dashboard")))
	unverified = False
	if request.method == "POST" and not getattr(request, "axes_locked_out", False):
		# Explain the failed sign-in only to someone who knows the password.
		pending = _pending_users().filter(username=request.POST.get("username", "")).first()
		unverified = bool(pending and pending.check_password(request.POST.get("password", "")))

	return render(
		request,
		"accounts/login.html",
		{"form": form, "next": request.GET.get("next", ""), "unverified": unverified},
	)


def signup(request):
	# Hidden "website" field: people never fill it, bots usually do.
	if request.POST.get("website"):
		return redirect("home")
	if request.method == "POST":
		# Unverified signups hold no data, so a retry (say after a mistyped email) replaces them instead of being blocked.
		# A brand-new one is left alone for a few minutes, so a stranger can't cancel it by posting the same username.
		taken = Q(pk__in=[])
		for field in ("username", "email"):
			if request.POST.get(field, "").strip():
				taken |= Q(**{f"{field}__iexact": request.POST[field].strip()})
		_pending_users().filter(taken, profile__created_at__lt=timezone.now() - SIGNUP_REPLACE_AFTER).delete()
	form = SignupForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		try:
			# Rolled back if the email fails, so the student can simply sign up again.
			with transaction.atomic():
				user = form.save(commit=False)
				user.is_active = False
				user.save()
				Profile.objects.create(user=user, awaiting_verification=True)
				_send_verification(request, user)
		except IntegrityError:
			# Lost a race for the same username or email.
			form.add_error(None, "That username or email was just taken. Try again.")
		except OSError:
			logger.exception("Verification email failed at signup")
			form.add_error(None, "We couldn't send the verification email. Check the address and try again.")
		else:
			return redirect("verify-email-sent")

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
	# Months run down the columns, so a month change is a staircase: an edge above the first day of the
	# month, and an edge beside the old month's days in the column before it.
	for index, cell in enumerate(cells):
		month = cell["day"].month
		cell["month_start"] = cell["day"].day == 1
		cell["edge_left"] = index >= 7 and cells[index - 7]["day"].month != month
		cell["edge_top"] = index % 7 > 0 and cells[index - 1]["day"].month != month
	return cells, sum(1 for cell in cells if cell["count"])


def verify_email_sent(request):
	return render(request, "accounts/verify_sent.html")


def verify_email(request, uidb64, token):
	try:
		user = _pending_users().get(pk=urlsafe_base64_decode(uidb64).decode())
	except (TypeError, ValueError, OverflowError, User.DoesNotExist, ValidationError):
		user = None
	# Logging in changes last_login, which also invalidates the token, so each link works once.
	if user is None or not default_token_generator.check_token(user, token):
		return render(request, "accounts/verify_resend.html", {"form": ResendVerificationForm(), "invalid_link": True})
	user.is_active = True
	user.save(update_fields=["is_active"])
	Profile.objects.filter(user=user).update(awaiting_verification=False)
	login(request, user, backend="django.contrib.auth.backends.ModelBackend")
	messages.success(request, f"Email verified. Welcome to compile/, {user.username}. Pick a subject to start your first lesson.")
	return redirect("progress:dashboard")


def resend_verification(request):
	form = ResendVerificationForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		email = form.cleaned_data["email"]
		for user in _pending_users().filter(email__iexact=email) if not _cooling_down(email) else []:
			try:
				_send_verification(request, user)
			except OSError:
				logger.exception("Verification email failed on resend")
		# Same page whether or not anything was sent, so it never reveals which emails have accounts.
		return redirect("verify-email-sent")
	return render(request, "accounts/verify_resend.html", {"form": form})


def _send_email_change(request, user, new_email):
	# Signed with the current email, so the link stops working once the email changes by any route.
	token = signing.dumps([user.pk, user.email, new_email], salt="email-change")
	send_mail(
		"Confirm your new compile/ email address",
		render_to_string("accounts/email_change_email.txt", {
			"user": user, "link": request.build_absolute_uri(reverse("confirm-email-change", args=[token])),
		}),
		None,
		[new_email],
	)


def confirm_email_change(request, token):
	try:
		user_id, old_email, new_email = signing.loads(token, salt="email-change", max_age=EMAIL_LINK_MAX_AGE)
	except (signing.BadSignature, ValueError):
		user_id = None
	updated = False
	if user_id is not None and not User.objects.filter(email__iexact=new_email).exists():
		try:
			updated = User.objects.filter(pk=user_id, email=old_email, is_active=True).update(email=new_email)
		except IntegrityError:
			pass  # another account took the address between the check and the write
	if updated:
		messages.success(request, f"Your email is now {new_email}.")
	else:
		messages.error(request, "That email link has expired or was already used. Change your email again to get a new one.")
	return redirect("account" if request.user.is_authenticated else "login")


@login_required
def account(request):
	profile, _ = Profile.objects.get_or_create(user=request.user)
	old_email = request.user.email  # the form writes the new address onto request.user while validating
	is_password_post = request.method == "POST" and request.POST.get("action") == "password"
	is_details_post = request.method == "POST" and not is_password_post
	form = AccountProfileForm(request.POST if is_details_post else None, instance=request.user)
	name_form = DisplayNameForm(request.POST if is_details_post else None, instance=profile)
	password_form = PasswordChangeForm(request.user, request.POST if is_password_post else None)
	if is_details_post and form.is_valid() and name_form.is_valid():
		new_email = form.cleaned_data["email"]
		user = form.save(commit=False)
		user.email = old_email  # a new address only takes effect from the link sent to it
		user.save()
		name_form.save()
		messages.success(request, "Profile saved.")
		if new_email.lower() != old_email.lower():
			if _cooling_down(new_email):
				messages.info(request, f"We recently sent a link to {new_email}. Wait a few minutes before asking again.")
			else:
				try:
					_send_email_change(request, user, new_email)
				except OSError:
					logger.exception("Email change confirmation failed")
					messages.error(request, "We couldn't email your new address, so your email is unchanged. Try again.")
				else:
					messages.info(request, f"We sent a link to {new_email}. Your email changes when you open it.")
		return redirect("account")
	if is_password_post and password_form.is_valid():
		user = password_form.save()
		update_session_auth_hash(request, user)
		messages.success(request, "Password changed.")
		return redirect("account")

	user_progress, _ = UserProgress.objects.get_or_create(user=request.user)
	answers = QuizAnswer.objects.filter(attempt__user=request.user, marks_awarded__isnull=False)
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
