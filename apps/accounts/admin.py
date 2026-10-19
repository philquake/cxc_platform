from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Profile


class ProfileInline(admin.StackedInline):
	model = Profile
	can_delete = False
	fields = ("display_name", "time_multiplier")


class UserAdmin(BaseUserAdmin):
	inlines = [ProfileInline]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
	list_display = ("user", "time_multiplier")
	list_filter = ("time_multiplier",)
	search_fields = ("user__username", "user__email")


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
