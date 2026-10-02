from django.urls import path
from pathlib import Path
from .views import home, privacy, search, terms
from django.http import FileResponse

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def ads_txt(request):
    return FileResponse(
        open(BASE_DIR / "ads.txt", "rb"),
        content_type="text/plain"
    )
    
urlpatterns = [
    path("", home, name="home"),
    path("search/", search, name="search"),
    path("terms/", terms, name="terms"),
    path("privacy/", privacy, name="privacy"),
    path("ads.txt", ads_txt),
]

