from django.apps import AppConfig


class TestsConfig(AppConfig):
    name = 'tests'

    def ready(self):
        import tests.signals  # noqa
