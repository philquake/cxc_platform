from django.urls import path
from .views import home, privacy, terms

urlpatterns = [
    path("", home, name="home"),
    path("terms/", terms, name="terms"),
    path("privacy/", privacy, name="privacy"),
]