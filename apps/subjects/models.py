from django.db import models
from django.utils.text import slugify

class Subject(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or slugify(self.code) or "subject"
            self.slug, n = base, 2
            while Subject.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug, n = f"{base}-{n}", n + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Topic(models.Model):
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="topics",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    description = models.TextField(blank=True)
    exam_weight = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["subject", "slug"],
                name="unique_topic_slug_per_subject",
            ),
        ]

    def __str__(self):
        return f"{self.subject.code} - {self.name}"