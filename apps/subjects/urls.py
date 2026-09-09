from django.urls import path

from . import views


app_name = "subjects"

urlpatterns = [
    path("", views.subject_list, name="list"),
    path("<slug:subject_slug>/lessons/<slug:lesson_slug>/", views.lesson_detail, name="lesson-detail"),
    path("<slug:slug>/", views.subject_detail, name="detail"),
]