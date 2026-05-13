import datetime
import uuid

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from django.contrib.auth.mixins import LoginRequiredMixin

from accounts.mixins import NewsManagerRequiredMixin
from news.models import Article

_DETAIL_TTL = 60 * 10  # 10 мин — статья меняется редко
_COUNT_TTL  = 60 * 5   # 5 мин  — счётчик опубликованных


def _article_cache_key(pk):
    return f'news:article:{pk}'


def _invalidate_article(pk):
    """Сбрасывает кэш конкретной статьи и счётчика опубликованных."""
    cache.delete(_article_cache_key(pk))
    cache.delete('news:published_count')


class NewsListView(LoginRequiredMixin, ListView):
    model               = Article
    template_name       = 'news/news_list.html'
    context_object_name = 'articles'
    paginate_by         = 10

    def get_queryset(self):
        # defer 'content' — крупное HTML-поле, в списке не нужно
        qs = super().get_queryset().defer('content', 'created_at', 'updated_at')
        if not self.request.user.can_manage_news:
            qs = qs.filter(status=Article.STATUS_PUBLISHED)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        is_news_manager = self.request.user.can_manage_news
        ctx['is_news_manager'] = is_news_manager
        if is_news_manager:
            ctx['total_articles'] = Article.objects.count()
        else:
            count = cache.get('news:published_count')
            if count is None:
                count = Article.objects.filter(status=Article.STATUS_PUBLISHED).count()
                cache.set('news:published_count', count, _COUNT_TTL)
            ctx['total_articles'] = count
        return ctx


class ArticleFormView(NewsManagerRequiredMixin, View):
    template_name = 'news/article_form.html'

    def _render(self, request, article=None):
        from django.shortcuts import render
        return render(request, self.template_name, {'article': article})

    def get(self, request, pk=None):
        article = get_object_or_404(Article, pk=pk) if pk else None
        return self._render(request, article)

    def post(self, request, pk=None):
        action = request.POST.get('action', 'save')
        article = get_object_or_404(Article, pk=pk) if pk else None

        if action == 'delete' and article:
            _invalidate_article(article.pk)
            article.delete()
            return redirect('news:list')

        if article is None:
            article = Article()

        article.title   = request.POST.get('title', '').strip()
        article.preview = request.POST.get('preview', '').strip()
        article.content = request.POST.get('content', '').strip()

        article.date = datetime.date.today()

        if 'cover_image' in request.FILES:
            article.cover_image = request.FILES['cover_image']
        elif request.POST.get('keep_image') == '0':
            article.cover_image = None

        article.save()
        _invalidate_article(article.pk)
        return redirect('news:list')


class ArticleDetailView(View):
    def get(self, request, pk):
        key = _article_cache_key(pk)
        article = cache.get(key)
        if article is None:
            article = get_object_or_404(Article, pk=pk, status=Article.STATUS_PUBLISHED)
            cache.set(key, article, _DETAIL_TTL)
        return render(request, 'news/article_detail.html', {'article': article})


class ArticleInlineImageUploadView(NewsManagerRequiredMixin, View):
    def post(self, request):
        image = request.FILES.get('image')
        if not image:
            return JsonResponse({'error': 'No image'}, status=400)
        ext = image.name.rsplit('.', 1)[-1].lower() if '.' in image.name else 'jpg'
        path = default_storage.save(
            f'news/inline/{uuid.uuid4().hex}.{ext}',
            ContentFile(image.read()),
        )
        return JsonResponse({'url': default_storage.url(path)})


class ArticlePublishView(NewsManagerRequiredMixin, View):
    def post(self, request, pk):
        article = get_object_or_404(Article, pk=pk)
        if article.status == Article.STATUS_DRAFT:
            article.status = Article.STATUS_PUBLISHED
            article.date = datetime.date.today()
        else:
            article.status = Article.STATUS_DRAFT
        article.save()
        _invalidate_article(pk)
        return redirect('news:list')
