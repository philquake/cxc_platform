from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .forms import AccountProfileForm, SignupForm

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
		login(request, user)
		messages.success(
			request,
			f"You're signed up, {user.username}! Welcome to compile/.",
		)
		return _redirect_after_auth(request)

	return render(
		request,
		"accounts/signup.html",
		{"form": form, "next": request.GET.get("next", "")},
	)


@login_required
def account(request):
	form = AccountProfileForm(request.POST or None, instance=request.user)
	if request.method == "POST" and form.is_valid():
		form.save()
		messages.success(request, "Your account details have been updated.")
		return redirect("account")

	return render(request, "accounts/account.html", {"form": form})


@require_POST
def logout_view(request):
	logout(request)
	return redirect("home")
