import datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from news.models import Article

User = get_user_model()

_NO_REDIS = dict(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    SESSION_ENGINE='django.contrib.sessions.backends.db',
)


# ─────────────────────────────────────────────
# Вспомогательные фабрики
# ─────────────────────────────────────────────

def make_doctor(email='doctor@test.com', can_manage_news=False, **kwargs):
    return User.objects.create_user(
        email=email, password='TestPass123!',
        first_name='Иван', last_name='Иванов',
        user_type='doctor', is_email_verified=True,
        can_manage_news=can_manage_news, **kwargs
    )


def make_article(title='Статья', status=Article.STATUS_PUBLISHED, **kwargs):
    return Article.objects.create(
        title=title,
        preview='Краткое превью',
        content='Полный текст статьи',
        status=status,
        date=datetime.date.today(),
        **kwargs
    )


# ─────────────────────────────────────────────
# Модель Article
# ─────────────────────────────────────────────

class ArticleModelTests(TestCase):

    def test_статус_черновика_по_умолчанию(self):
        article = Article.objects.create(title='Новая статья')
        self.assertEqual(article.status, Article.STATUS_DRAFT)

    def test_строковое_представление(self):
        article = Article.objects.create(title='Заголовок статьи')
        self.assertEqual(str(article), 'Заголовок статьи')

    def test_создание_опубликованной_статьи(self):
        article = make_article(status=Article.STATUS_PUBLISHED)
        self.assertEqual(article.status, Article.STATUS_PUBLISHED)

    def test_создание_черновика(self):
        article = make_article(title='Черновик', status=Article.STATUS_DRAFT)
        self.assertEqual(article.status, Article.STATUS_DRAFT)

    def test_константы_статусов(self):
        self.assertEqual(Article.STATUS_DRAFT, 'draft')
        self.assertEqual(Article.STATUS_PUBLISHED, 'published')


# ─────────────────────────────────────────────
# NewsListView
# ─────────────────────────────────────────────

@override_settings(**_NO_REDIS)
class NewsListViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('news:list')

    def test_неавторизованный_редиректится(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_обычный_доктор_видит_только_опубликованные(self):
        make_article(title='Опубликована', status=Article.STATUS_PUBLISHED)
        make_article(title='Черновик', status=Article.STATUS_DRAFT)
        doctor = make_doctor()
        self.client.force_login(doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        articles = list(response.context['articles'])
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, 'Опубликована')

    def test_редактор_видит_все_статьи_включая_черновики(self):
        make_article(title='Опубликована', status=Article.STATUS_PUBLISHED)
        make_article(title='Черновик', status=Article.STATUS_DRAFT)
        editor = make_doctor(email='editor@test.com', can_manage_news=True)
        self.client.force_login(editor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(list(response.context['articles'])), 2)

    def test_контекст_содержит_флаг_редактора(self):
        editor = make_doctor(email='editor@test.com', can_manage_news=True)
        self.client.force_login(editor)
        response = self.client.get(self.url)
        self.assertTrue(response.context['is_news_manager'])

    def test_контекст_обычного_доктора_не_редактор(self):
        doctor = make_doctor()
        self.client.force_login(doctor)
        response = self.client.get(self.url)
        self.assertFalse(response.context['is_news_manager'])

    def test_список_пустой_если_нет_опубликованных(self):
        make_article(title='Только черновик', status=Article.STATUS_DRAFT)
        doctor = make_doctor()
        self.client.force_login(doctor)
        response = self.client.get(self.url)
        self.assertEqual(len(list(response.context['articles'])), 0)


# ─────────────────────────────────────────────
# ArticleDetailView
# ─────────────────────────────────────────────

@override_settings(**_NO_REDIS)
class ArticleDetailViewTests(TestCase):

    def test_опубликованная_статья_доступна_анониму(self):
        article = make_article(status=Article.STATUS_PUBLISHED)
        response = self.client.get(reverse('news:detail', kwargs={'pk': article.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['article'].pk, article.pk)

    def test_черновик_возвращает_404(self):
        article = make_article(title='Черновик', status=Article.STATUS_DRAFT)
        response = self.client.get(reverse('news:detail', kwargs={'pk': article.pk}))
        self.assertEqual(response.status_code, 404)

    def test_несуществующая_статья_возвращает_404(self):
        response = self.client.get(reverse('news:detail', kwargs={'pk': 99999}))
        self.assertEqual(response.status_code, 404)


# ─────────────────────────────────────────────
# ArticleFormView (создание / редактирование)
# ─────────────────────────────────────────────

@override_settings(**_NO_REDIS)
class ArticleFormViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.editor = make_doctor(email='editor@test.com', can_manage_news=True)
        self.regular_doctor = make_doctor()

    def test_неавторизованный_не_может_открыть_форму(self):
        response = self.client.get(reverse('news:add'))
        self.assertEqual(response.status_code, 302)

    def test_обычный_доктор_не_может_открыть_форму_создания(self):
        self.client.force_login(self.regular_doctor)
        response = self.client.get(reverse('news:add'))
        self.assertEqual(response.status_code, 403)

    def test_редактор_видит_форму_создания(self):
        self.client.force_login(self.editor)
        response = self.client.get(reverse('news:add'))
        self.assertEqual(response.status_code, 200)

    def test_создание_статьи_редиректит_на_список(self):
        self.client.force_login(self.editor)
        response = self.client.post(reverse('news:add'), {
            'title': 'Новая статья',
            'preview': 'Краткое описание',
            'content': 'Полный текст',
        })
        self.assertRedirects(response, reverse('news:list'))
        self.assertTrue(Article.objects.filter(title='Новая статья').exists())

    def test_созданная_статья_является_черновиком(self):
        self.client.force_login(self.editor)
        self.client.post(reverse('news:add'), {
            'title': 'Черновик через форму',
            'preview': '',
            'content': '',
        })
        article = Article.objects.get(title='Черновик через форму')
        self.assertEqual(article.status, Article.STATUS_DRAFT)

    def test_редактирование_статьи(self):
        article = make_article(title='Старый заголовок')
        self.client.force_login(self.editor)
        response = self.client.post(reverse('news:edit', kwargs={'pk': article.pk}), {
            'title': 'Новый заголовок',
            'preview': 'Обновлённое превью',
            'content': 'Обновлённый текст',
        })
        self.assertRedirects(response, reverse('news:list'))
        article.refresh_from_db()
        self.assertEqual(article.title, 'Новый заголовок')

    def test_удаление_статьи(self):
        article = make_article()
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse('news:edit', kwargs={'pk': article.pk}),
            {'action': 'delete'},
        )
        self.assertRedirects(response, reverse('news:list'))
        self.assertFalse(Article.objects.filter(pk=article.pk).exists())

    def test_обычный_доктор_не_может_редактировать(self):
        article = make_article()
        self.client.force_login(self.regular_doctor)
        response = self.client.post(
            reverse('news:edit', kwargs={'pk': article.pk}),
            {'title': 'Взлом'},
        )
        self.assertEqual(response.status_code, 403)
        article.refresh_from_db()
        self.assertNotEqual(article.title, 'Взлом')


# ─────────────────────────────────────────────
# ArticlePublishView (toggle publish)
# ─────────────────────────────────────────────

@override_settings(**_NO_REDIS)
class ArticlePublishViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.editor = make_doctor(email='editor@test.com', can_manage_news=True)
        self.regular_doctor = make_doctor()

    def test_публикация_черновика(self):
        article = make_article(title='Черновик', status=Article.STATUS_DRAFT)
        self.client.force_login(self.editor)
        self.client.post(reverse('news:toggle_publish', kwargs={'pk': article.pk}))
        article.refresh_from_db()
        self.assertEqual(article.status, Article.STATUS_PUBLISHED)

    def test_снятие_с_публикации(self):
        article = make_article(status=Article.STATUS_PUBLISHED)
        self.client.force_login(self.editor)
        self.client.post(reverse('news:toggle_publish', kwargs={'pk': article.pk}))
        article.refresh_from_db()
        self.assertEqual(article.status, Article.STATUS_DRAFT)

    def test_неавторизованный_не_может_переключать_статус(self):
        article = make_article(title='Черновик', status=Article.STATUS_DRAFT)
        self.client.post(reverse('news:toggle_publish', kwargs={'pk': article.pk}))
        article.refresh_from_db()
        self.assertEqual(article.status, Article.STATUS_DRAFT)

    def test_обычный_доктор_не_может_переключать_статус(self):
        article = make_article(title='Черновик', status=Article.STATUS_DRAFT)
        self.client.force_login(self.regular_doctor)
        response = self.client.post(reverse('news:toggle_publish', kwargs={'pk': article.pk}))
        self.assertEqual(response.status_code, 403)
        article.refresh_from_db()
        self.assertEqual(article.status, Article.STATUS_DRAFT)

    def test_повторная_публикация_снимает_статью(self):
        article = make_article(status=Article.STATUS_DRAFT)
        self.client.force_login(self.editor)
        self.client.post(reverse('news:toggle_publish', kwargs={'pk': article.pk}))
        self.client.post(reverse('news:toggle_publish', kwargs={'pk': article.pk}))
        article.refresh_from_db()
        self.assertEqual(article.status, Article.STATUS_DRAFT)
