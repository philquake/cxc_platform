from django.urls import path
from pathlib import Path
from .views import about, binary_converter, home, privacy, search, terms, tools_index
from django.http import FileResponse, HttpResponse

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def ads_txt(request):
    return FileResponse(
        open(BASE_DIR / "ads.txt", "rb"),
        content_type="text/plain"
    )
    
def robots_txt(request):
    lines = ["User-agent: *", "Disallow: /admin/", "Disallow: /accounts/", "Disallow: /progress/", "Disallow: /ckeditor5/",
             f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}"]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


urlpatterns = [
    path("", home, name="home"),
    path("search/", search, name="search"),
    path("tools/", tools_index, name="tools"),
    path("tools/binary-converter/", binary_converter, name="binary-converter"),
    path("about/", about, name="about"),
    path("terms/", terms, name="terms"),
    path("privacy/", privacy, name="privacy"),
    path("ads.txt", ads_txt),
    path("robots.txt", robots_txt),
]

