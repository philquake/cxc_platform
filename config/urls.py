from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from apps.core.sitemaps import SITEMAPS

admin.site.site_header = "compile/ admin"
admin.site.site_title = "compile/ admin"
admin.site.index_title = "Dashboard"

urlpatterns = [
    path('sitemap.xml', sitemap, {'sitemaps': SITEMAPS}, name='sitemap'),
    path('admin/', admin.site.urls),
    path('ckeditor5/', include('django_ckeditor_5.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('progress/', include('apps.progress.urls')),
    path('', include('apps.core.urls')),
    path('subjects/', include('apps.subjects.urls')),
    path('quizzes/', include('apps.quizzes.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
