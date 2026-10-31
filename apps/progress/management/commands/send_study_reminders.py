import logging
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.progress.models import FlashcardState, StudyPlanItem, UserProgress

logger = logging.getLogger(__name__)
# Only students who studied this past week, so a lapsed account isn't emailed every evening forever.
ACTIVE_WITHIN_DAYS = 7


class Command(BaseCommand):
	help = "Email students who haven't studied today about due flashcards, today's study plan and their streak. Run once each evening."

	def handle(self, *args, **options):
		# Piggybacks on this daily job so expired login sessions don't pile up in the database.
		call_command("clearsessions")
		today = timezone.localdate()
		students = UserProgress.objects.filter(
			last_activity_date__gte=today - timedelta(days=ACTIVE_WITHIN_DAYS),
			last_activity_date__lt=today,
			user__is_active=True,
			user__is_staff=False,
			user__is_superuser=False,
		).exclude(user__email="").exclude(user__profile__study_reminders=False).select_related("user")
		sent = 0
		for progress in students:
			user = progress.user
			due_cards = FlashcardState.objects.filter(user=user, question__is_active=True, due_at__lte=today).count()
			# Quiz items are left out: their completion is worked out on the plan page, not stored.
			plan_items = StudyPlanItem.objects.filter(
				plan__user=user, plan__is_active=True, scheduled_date=today, completed=False
			).exclude(item_type=StudyPlanItem.QUIZ).count()
			streak = progress.current_streak if progress.last_activity_date == today - timedelta(days=1) else 0
			if not (due_cards or plan_items or streak):
				continue
			# Shared cache, so a second run the same evening (a retry, a manual re-run) doesn't email anyone twice.
			if not cache.add(f"reminder:{user.pk}:{today}", True, 24 * 60 * 60):
				continue
			context = {
				"user": user,
				"due_cards": due_cards,
				"plan_items": plan_items,
				"streak": streak,
				"dashboard_url": settings.SITE_URL + reverse("progress:dashboard"),
				"flashcards_url": settings.SITE_URL + reverse("progress:flashcard-hub"),
				"stop_url": settings.SITE_URL + reverse(
					"stop-reminders", args=[signing.dumps(user.pk, salt="study-reminders")]
				),
			}
			try:
				send_mail(
					render_to_string("progress/reminder_subject.txt", context).strip(),
					render_to_string("progress/reminder_email.txt", context),
					settings.REMINDER_FROM_EMAIL,
					[user.email],
				)
			except OSError:
				# One bad address or SMTP hiccup shouldn't stop everyone else's reminder.
				logger.exception("Study reminder to user %s failed", user.pk)
				continue
			sent += 1
		self.stdout.write(f"Sent {sent} study reminder{'' if sent == 1 else 's'}.")
