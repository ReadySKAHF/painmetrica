from django.contrib.auth import logout
from django.utils import timezone


class SessionTimeoutMiddleware:
    """Завершает сессию после 30 минут бездействия."""

    TIMEOUT_SECONDS = 1800  # 30 минут

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            last_activity = request.session.get('last_activity')
            now = timezone.now().timestamp()

            if last_activity and (now - last_activity) > self.TIMEOUT_SECONDS:
                logout(request)
            else:
                request.session['last_activity'] = now

        return self.get_response(request)
