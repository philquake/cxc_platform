import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.test import TestCase, override_settings
from django.urls import reverse


class AccountFlowTests(TestCase):
	def test_signup_creates_inactive_user_and_emails_a_link(self):
		response = self.client.post(
		reverse("signup"),
		{
			"username": "newstudent",
			"first_name": "New",
			"last_name": "Student",
			"email": "newstudent@example.com",
			"password1": "A-strong-password-123",
			"password2": "A-strong-password-123",
		},
	)

		self.assertRedirects(response, reverse("verify-email-sent"))
		self.assertFalse(response.wsgi_request.user.is_authenticated)
		user = get_user_model().objects.get(username="newstudent")
		self.assertEqual(user.email, "newstudent@example.com")
		self.assertFalse(user.is_active)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ["newstudent@example.com"])

	def test_login_authenticates_existing_user(self):
		get_user_model().objects.create_user(
			username="student",
			password="A-strong-password-123",
		)

		response = self.client.post(
			reverse("login"),
			{"username": "student", "password": "A-strong-password-123"},
		)

		self.assertRedirects(response, reverse("progress:dashboard"))
		self.assertTrue(response.wsgi_request.user.is_authenticated)

	@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
	def test_password_reset_sends_link_to_registered_email(self):
		get_user_model().objects.create_user(
			username="student",
			password="A-strong-password-123",
			email="student@example.com",
		)

		response = self.client.post(
			reverse("password_reset"),
			{"email": "student@example.com"},
		)

		self.assertRedirects(response, reverse("password_reset_done"))
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn("password-reset/", mail.outbox[0].body)

	def test_account_profile_updates_name_and_email(self):
		user = get_user_model().objects.create_user(
			username="student",
			password="A-strong-password-123",
			email="before@example.com",
		)
		self.client.force_login(user)

		response = self.client.post(
			reverse("account"),
			{
				"first_name": "Updated",
				"last_name": "Student",
				"email": "updated@example.com",
			},
		)

		self.assertRedirects(response, reverse("account"))
		user.refresh_from_db()
		self.assertEqual(user.first_name, "Updated")
		self.assertEqual(user.last_name, "Student")
		# The new address only takes effect from the link sent to it.
		self.assertEqual(user.email, "before@example.com")
		self.assertEqual(mail.outbox[-1].to, ["updated@example.com"])
		link = re.search(r"https?://\S+", mail.outbox[-1].body).group(0)

		self.assertRedirects(self.client.get(link), reverse("account"))
		user.refresh_from_db()
		self.assertEqual(user.email, "updated@example.com")
		self.client.get(link)
		self.assertEqual(get_user_model().objects.filter(email="updated@example.com").count(), 1)

	def test_password_change_updates_password_and_keeps_user_logged_in(self):
		user = get_user_model().objects.create_user(
			username="student",
			password="A-strong-password-123",
		)
		self.client.force_login(user)

		response = self.client.post(
			reverse("password_change"),
			{
				"old_password": "A-strong-password-123",
				"new_password1": "An-even-stronger-password-456",
				"new_password2": "An-even-stronger-password-456",
			},
		)

		self.assertRedirects(response, reverse("password_change_done"))
		user.refresh_from_db()
		self.assertTrue(user.check_password("An-even-stronger-password-456"))
		self.assertTrue(response.wsgi_request.user.is_authenticated)

	def test_login_rejects_invalid_credentials(self):
		response = self.client.post(
			reverse("login"),
			{"username": "student", "password": "wrong-password"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Please enter a correct username and password.")
		self.assertFalse(response.wsgi_request.user.is_authenticated)

	def test_repeated_failed_logins_lock_account_login_and_admin_login(self):
		get_user_model().objects.create_user(username="student", password="A-strong-password-123")
		for url_name in ("login", "admin:login"):
			with self.subTest(url_name):
				for _ in range(5):
					self.client.post(reverse(url_name), {"username": "student", "password": "wrong"})
				response = self.client.post(
					reverse(url_name), {"username": "student", "password": "A-strong-password-123"}
				)
				self.assertEqual(response.status_code, 429)
				self.assertNotIn("_auth_user_id", self.client.session)

	def test_other_users_are_not_locked_out(self):
		get_user_model().objects.create_user(username="student", password="A-strong-password-123")
		get_user_model().objects.create_user(username="friend", password="A-strong-password-123")
		for _ in range(5):
			self.client.post(reverse("login"), {"username": "student", "password": "wrong"})
		response = self.client.post(
			reverse("login"), {"username": "friend", "password": "A-strong-password-123"}
		)
		self.assertEqual(response.status_code, 302)

	def test_logout_requires_post_and_clears_session(self):
		user = get_user_model().objects.create_user(
			username="student",
			password="A-strong-password-123",
		)
		self.client.force_login(user)

		get_response = self.client.get(reverse("logout"))
		self.assertEqual(get_response.status_code, 405)

		post_response = self.client.post(reverse("logout"))
		self.assertRedirects(post_response, reverse("home"))
		self.assertFalse(post_response.wsgi_request.user.is_authenticated)

	def test_auth_redirect_rejects_external_next_url(self):
		get_user_model().objects.create_user(
			username="student",
			password="A-strong-password-123",
		)

		response = self.client.post(
			reverse("login"),
			{
				"username": "student",
				"password": "A-strong-password-123",
				"next": "https://example.com/steal-session",
			},
		)

		self.assertRedirects(response, reverse("progress:dashboard"))


class AuthFormAccessibilityTests(TestCase):
	def test_invalid_signup_links_errors_to_fields(self):
		response = self.client.post(
			reverse("signup"),
			{"username": "x", "password1": "a", "password2": "b"},
		)

		self.assertContains(response, 'role="alert"')
		self.assertContains(response, 'aria-invalid="true"')
		self.assertContains(response, 'aria-describedby="id_password2-help id_password2-errors"')
		self.assertContains(response, 'id="id_password2-errors"')

	def test_valid_form_has_no_error_summary(self):
		response = self.client.get(reverse("signup"))

		self.assertNotContains(response, 'role="alert"')
		self.assertNotContains(response, 'aria-invalid')


class ProfilePageTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username="student", password="A-strong-password-123", first_name="Ada", last_name="Lee"
		)
		self.client.force_login(self.user)

	def test_profile_renders_stats_and_study_log(self):
		response = self.client.get(reverse("account"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["initials"], "AL")
		self.assertEqual(response.context["days_studied"], 0)
		self.assertContains(response, "Study log")

	def test_study_log_buckets_by_jamaica_day(self):
		from datetime import date, datetime, timezone as dt_timezone
		from unittest import mock

		from apps.accounts.views import _study_log
		from apps.progress.models import XPTransaction
		from apps.subjects.models import Subject, Topic

		topic = Topic.objects.create(subject=Subject.objects.create(name="Maths", code="M"), name="A", slug="a")
		# 22:00 Mar 1 Jamaica is already Mar 2 in UTC; it must count toward Mar 1.
		tx = XPTransaction.objects.create(user=self.user, topic=topic, amount=10, reason="t")
		XPTransaction.objects.filter(pk=tx.pk).update(created_at=datetime(2026, 3, 2, 3, 0, tzinfo=dt_timezone.utc))
		with mock.patch("django.utils.timezone.now", return_value=datetime(2026, 3, 2, 15, 0, tzinfo=dt_timezone.utc)):
			cells, days = _study_log(self.user)
		self.assertEqual(days, 1)
		self.assertEqual([c["day"] for c in cells if c["count"]], [date(2026, 3, 1)])

	def test_profile_saves_display_name(self):
		response = self.client.post(
			reverse("account"),
			{"display_name": "Ada L.", "first_name": "Ada", "last_name": "Lee", "email": "ada@example.com"},
		)

		self.assertRedirects(response, reverse("account"))
		self.user.refresh_from_db()
		self.assertEqual(self.user.profile.display_name, "Ada L.")

	def test_profile_changes_password_and_keeps_session(self):
		response = self.client.post(
			reverse("account"),
			{
				"action": "password",
				"old_password": "A-strong-password-123",
				"new_password1": "Another-strong-pass-456",
				"new_password2": "Another-strong-pass-456",
			},
		)

		self.assertRedirects(response, reverse("account"))
		self.user.refresh_from_db()
		self.assertTrue(self.user.check_password("Another-strong-pass-456"))
		self.assertEqual(self.client.get(reverse("account")).status_code, 200)

	def test_profile_rejects_wrong_old_password(self):
		response = self.client.post(
			reverse("account"),
			{"action": "password", "old_password": "nope", "new_password1": "x", "new_password2": "x"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Your password was not changed")


class SignupAbuseTests(TestCase):
	data = {
		"username": "bot", "first_name": "B", "last_name": "Ot", "email": "dup@example.com",
		"password1": "A-strong-password-123", "password2": "A-strong-password-123",
	}

	def test_honeypot_field_blocks_signup(self):
		self.client.post(reverse("signup"), {**self.data, "website": "http://spam"})
		self.assertFalse(get_user_model().objects.filter(username="bot").exists())

	def test_duplicate_email_is_rejected_case_insensitively(self):
		get_user_model().objects.create_user(username="first", email="Dup@Example.com", password="x")
		response = self.client.post(reverse("signup"), self.data)
		self.assertContains(response, "already exists")
		self.assertFalse(get_user_model().objects.filter(username="bot").exists())

	def test_profile_cannot_take_another_accounts_email(self):
		get_user_model().objects.create_user(username="first", email="Dup@Example.com", password="x")
		me = get_user_model().objects.create_user(username="me", email="me@example.com", password="x")
		self.client.force_login(me)
		response = self.client.post(reverse("account"), {"first_name": "M", "last_name": "E", "email": "dup@example.com"})
		self.assertContains(response, "already exists")
		me.refresh_from_db()
		self.assertEqual(me.email, "me@example.com")


class EmailVerificationTests(TestCase):
	def setUp(self):
		cache.clear()

	data = {
		"username": "newstudent", "first_name": "New", "last_name": "Student", "email": "new@example.com",
		"password1": "A-strong-password-123", "password2": "A-strong-password-123",
	}

	def signup(self):
		self.client.post(reverse("signup"), self.data)
		return re.search(r"https?://\S+", mail.outbox[-1].body).group(0)

	def test_link_activates_and_signs_in_once(self):
		link = self.signup()

		response = self.client.get(link)

		self.assertRedirects(response, reverse("progress:dashboard"))
		user = get_user_model().objects.get(username="newstudent")
		self.assertTrue(user.is_active)
		self.assertFalse(user.profile.awaiting_verification)
		self.client.logout()
		self.assertContains(self.client.get(link), "That link has expired")

	def test_bad_link_is_rejected(self):
		self.signup()
		user = get_user_model().objects.get(username="newstudent")
		uid = urlsafe_base64_encode(force_bytes(user.pk))

		for path in (f"/accounts/verify/{uid}/wrong-token/", "/accounts/verify/!!/x/"):
			with self.subTest(path=path):
				self.assertContains(self.client.get(path), "That link has expired")
		user.refresh_from_db()
		self.assertFalse(user.is_active)

	def test_unverified_login_explains_only_with_the_right_password(self):
		self.signup()
		url = reverse("login")

		right = self.client.post(url, {"username": "newstudent", "password": "A-strong-password-123"})
		wrong = self.client.post(url, {"username": "newstudent", "password": "nope"})

		self.assertFalse(right.wsgi_request.user.is_authenticated)
		self.assertContains(right, "isn't verified yet")
		self.assertNotContains(wrong, "isn't verified yet")

	def test_resend_only_reaches_pending_signups(self):
		self.signup()
		banned = get_user_model().objects.create_user(username="banned", email="banned@example.com", password="x")
		banned.is_active = False
		banned.save()
		mail.outbox.clear()

		for email in ("NEW@example.com", "banned@example.com", "nobody@example.com"):
			response = self.client.post(reverse("verify-email-resend"), {"email": email})
			self.assertRedirects(response, reverse("verify-email-sent"))

		self.assertEqual([message.to for message in mail.outbox], [["new@example.com"]])

	def test_resend_is_limited_to_one_email_per_address_every_few_minutes(self):
		self.signup()
		mail.outbox.clear()

		for _ in range(3):
			self.client.post(reverse("verify-email-resend"), {"email": "new@example.com"})

		self.assertEqual(len(mail.outbox), 1)

	def test_email_change_link_is_void_once_the_email_changes_another_way(self):
		user = get_user_model().objects.create_user(username="me", email="me@example.com", password="x")
		self.client.force_login(user)
		self.client.post(reverse("account"), {"first_name": "M", "last_name": "E", "email": "first@example.com"})
		stale = re.search(r"https?://\S+", mail.outbox[-1].body).group(0)
		user.email = "other@example.com"
		user.save()

		self.client.get(stale)
		self.client.get(stale.replace("/confirm/", "/confirm/x"))

		user.refresh_from_db()
		self.assertEqual(user.email, "other@example.com")

	def test_failed_email_rolls_back_signup(self):
		with mock.patch("apps.accounts.views.send_mail", side_effect=OSError):
			response = self.client.post(reverse("signup"), self.data)

		self.assertContains(response, "send the verification email")
		self.assertFalse(get_user_model().objects.filter(username="newstudent").exists())

	def test_users_without_email_are_asked_to_add_one(self):
		user = get_user_model().objects.create_user(username="old", password="x")
		self.client.force_login(user)
		self.assertContains(self.client.get(reverse("home")), "Add your email")
		user.email = "old@example.com"
		user.save()
		self.assertNotContains(self.client.get(reverse("home")), "Add your email")
