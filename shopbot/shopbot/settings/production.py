"""Настройки для продакшна (gunicorn + nginx + TLS)."""
from .base import *  # noqa: F401,F403

DEBUG = False

# ALLOWED_HOSTS и CSRF_TRUSTED_ORIGINS должны быть заданы в .env
# (наследуются из base.py через config()).

# За nginx TLS терминируется на проксе — доверяем заголовку.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# HSTS (включать после проверки, что весь трафик идёт по HTTPS)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
