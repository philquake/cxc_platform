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
    lesson_number = models.PositiveIntegerField(default=1)
    section_number = models.PositiveIntegerField(default=1)
    section_title = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(max_length=220, blank=True)
    content = CKEditor5Field("Content", config_name="extends")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["lesson_number", "section_number", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["subject", "slug"],
                name="unique_lesson_slug_per_subject",
            ),
            models.UniqueConstraint(
                fields=["subject", "lesson_number"],
                name="unique_lesson_number_per_subject",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class LessonImage(models.Model):
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="lesson_images/")
    alt_text = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.lesson.title} image {self.order + 1}"
