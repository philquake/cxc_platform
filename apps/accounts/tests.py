from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AccountFlowTests(TestCase):
	def test_signup_creates_and_logs_in_user(self):
		response = self.client.post(
		reverse("signup"),
		{
			"username": "newstudent",
			"first_name": "New",
			"last_name": "Student",
			"password1": "A-strong-password-123",
			"password2": "A-strong-password-123",
		},
	)

		self.assertRedirects(response, reverse("home"))
		self.assertTrue(response.wsgi_request.user.is_authenticated)
		self.assertTrue(
			get_user_model().objects.filter(username="newstudent").exists()
		)

	def test_login_authenticates_existing_user(self):
		get_user_model().objects.create_user(
			username="student",
			password="A-strong-password-123",
		)

		response = self.client.post(
			reverse("login"),
			{"username": "student", "password": "A-strong-password-123"},
		)

		self.assertRedirects(response, reverse("home"))
		self.assertTrue(response.wsgi_request.user.is_authenticated)

	def test_login_rejects_invalid_credentials(self):
		response = self.client.post(
			reverse("login"),
			{"username": "student", "password": "wrong-password"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Please enter a correct username and password.")
		self.assertFalse(response.wsgi_request.user.is_authenticated)

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

		self.assertRedirects(response, reverse("home"))
