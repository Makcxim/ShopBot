"""Выбор настроек по переменной окружения DJANGO_ENV (development|production)."""
import os

_env = os.environ.get('DJANGO_ENV', 'development')

if _env == 'production':
    from .production import *  # noqa: F401,F403
else:
    from .development import *  # noqa: F401,F403
