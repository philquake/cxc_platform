from django.test import TestCase
from django.urls import reverse

from apps.subjects.models import Subject

class CoreViewTests(TestCase):
	def test_home_lists_only_active_subjects(self):
		active = Subject.objects.create(name="Mathematics", code="MATH")
		Subject.objects.create(name="Archived Science", code="SCI", is_active=False)

		response = self.client.get(reverse("home"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(list(response.context["subjects"]), [active])

	def test_legal_pages_render(self):
		for page_name in ("terms", "privacy"):
			with self.subTest(page=page_name):
				self.assertEqual(self.client.get(reverse(page_name)).status_code, 200)
