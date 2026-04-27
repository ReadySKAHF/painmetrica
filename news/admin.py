from django.contrib import admin
from news.models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display  = ('title', 'status', 'date', 'created_at')
    list_filter   = ('status',)
    search_fields = ('title', 'preview')
    ordering      = ('-date',)
