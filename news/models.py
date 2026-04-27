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
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, verbose_name='Статус')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Статья'
        verbose_name_plural = 'Статьи'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return self.title
