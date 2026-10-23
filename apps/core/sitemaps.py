from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.lessons.models import Lesson
from apps.subjects.models import Subject

# Only public content pages (the ones that may show ads). Quiz, progress, account and search pages stay out.


class StaticPagesSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return ["home", "subjects:list", "tools", "binary-converter", "terms", "privacy"]

    def location(self, item):
        return reverse(item)


class SubjectSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Subject.objects.filter(is_active=True)

    def location(self, item):
        return reverse("subjects:detail", kwargs={"slug": item.slug})

    def lastmod(self, item):
        return item.updated_at


class LessonSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return Lesson.objects.filter(is_active=True, subject__is_active=True).select_related("subject")

    def location(self, item):
        return reverse("subjects:lesson-detail", kwargs={"subject_slug": item.subject.slug, "lesson_slug": item.slug})

    def lastmod(self, item):
        return item.updated_at


SITEMAPS = {"pages": StaticPagesSitemap, "subjects": SubjectSitemap, "lessons": LessonSitemap}
