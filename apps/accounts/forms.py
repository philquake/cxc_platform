from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Profile


class SignupForm(UserCreationForm):
    first_name = User._meta.get_field("first_name").formfield(required=True)
    last_name = User._meta.get_field("last_name").formfield(required=True)
    email = User._meta.get_field("email").formfield(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")


class AccountProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")


class DisplayNameForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("display_name",)
        help_texts = {"display_name": "Shown on your profile and leaderboards. Leave blank to use your username."}
