from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.shortcuts import redirect, render


def login_view(request):
	form = AuthenticationForm(request, data=request.POST or None)
	if request.method == "POST" and form.is_valid():
		user = authenticate(
			username=form.cleaned_data["username"],
			password=form.cleaned_data["password"],
		)
		if user is not None:
			login(request, user)
			return redirect("home")

	return render(request, "accounts/login.html", {"form": form})


def signup(request):
	form = UserCreationForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		user = form.save()
		login(request, user)
		return redirect("home")

	return render(request, "accounts/signup.html", {"form": form})
