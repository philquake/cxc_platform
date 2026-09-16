from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST


def _redirect_after_auth(request):
	redirect_to = request.POST.get("next") or request.GET.get("next")
	if redirect_to and url_has_allowed_host_and_scheme(
		redirect_to,
		allowed_hosts={request.get_host()},
		require_https=request.is_secure(),
	):
		return redirect(redirect_to)
	return redirect("home")


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
	form = UserCreationForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		user = form.save()
		login(request, user)
		return _redirect_after_auth(request)

	return render(
		request,
		"accounts/signup.html",
		{"form": form, "next": request.GET.get("next", "")},
	)


@require_POST
def logout_view(request):
	logout(request)
	return redirect("home")
