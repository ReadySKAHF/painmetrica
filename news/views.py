import datetime

from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from django.contrib.auth.mixins import LoginRequiredMixin

from accounts.mixins import DoctorRequiredMixin
from news.models import Article


class NewsListView(LoginRequiredMixin, ListView):
    model               = Article
    template_name       = 'news/news_list.html'
    context_object_name = 'articles'
    paginate_by         = 10

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.user_type == 'patient':
            qs = qs.filter(status=Article.STATUS_PUBLISHED)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.user.user_type == 'patient':
            ctx['total_articles'] = Article.objects.filter(status=Article.STATUS_PUBLISHED).count()
        else:
            ctx['total_articles'] = Article.objects.count()
        return ctx


class ArticleFormView(DoctorRequiredMixin, View):
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
        return redirect('news:list')


class ArticleDetailView(View):
    def get(self, request, pk):
        article = get_object_or_404(Article, pk=pk, status=Article.STATUS_PUBLISHED)
        return render(request, 'news/article_detail.html', {'article': article})


class ArticlePublishView(DoctorRequiredMixin, View):
    def post(self, request, pk):
        article = get_object_or_404(Article, pk=pk)
        if article.status == Article.STATUS_DRAFT:
            article.status = Article.STATUS_PUBLISHED
        else:
            article.status = Article.STATUS_DRAFT
        article.save()
        return redirect('news:list')
