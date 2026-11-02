from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from apps.progress.models import QuizAnswer

from .models import Question, QuestionReport


@login_required
@require_POST
def report_question(request, question_id):
	question = get_object_or_404(Question, pk=question_id)
	# Only students who answered it can report, so the queue can't be spammed with random ids.
	if not QuizAnswer.objects.filter(attempt__user=request.user, question=question).exists():
		return HttpResponseForbidden()
	QuestionReport.objects.update_or_create(
		user=request.user,
		question=question,
		defaults={"note": request.POST.get("note", "").strip()[:500], "resolved": False},
	)
	return JsonResponse({"ok": True})
