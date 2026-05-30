from django.db import models


class Article(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Черновик'),
        (STATUS_PUBLISHED, 'Опубликована'),
    ]

    title       = models.CharField(max_length=300, blank=True, verbose_name='Заголовок')
    preview     = models.TextField(blank=True, verbose_name='Краткое превью')
    content     = models.TextField(blank=True, verbose_name='Полный текст')
    cover_image = models.ImageField(upload_to='news/', blank=True, null=True, verbose_name='Обложка')
    date        = models.DateField(null=True, blank=True, verbose_name='Дата публикации')
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True, verbose_name='Статус')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Статья'
        verbose_name_plural = 'Статьи'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.cover_image and hasattr(self.cover_image, 'file'):
            try:
                from PIL import Image
                import io
                from django.core.files.base import ContentFile
                img = Image.open(self.cover_image)
                img = img.convert('RGB')
                img.thumbnail((1200, 800), Image.LANCZOS)
                buffer = io.BytesIO()
                img.save(buffer, format='WEBP', quality=85, optimize=True)
                orig_name = self.cover_image.name or 'cover'
                name = orig_name.rsplit('.', 1)[0] + '.webp'
                self.cover_image = ContentFile(buffer.getvalue(), name=name)
            except Exception:
                pass
        super().save(*args, **kwargs)
