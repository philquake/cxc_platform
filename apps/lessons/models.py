from django.db import models
from django_ckeditor_5.fields import CKEditor5Field
from apps.subjects.models import Subject


class Lesson(models.Model):
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="lessons",
    )
    title = models.CharField(max_length=200)
    section = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(max_length=220, blank=True)
    content = CKEditor5Field("Content", config_name="extends")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["subject", "slug"],
                name="unique_lesson_slug_per_subject",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
