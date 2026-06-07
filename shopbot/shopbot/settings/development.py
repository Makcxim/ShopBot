"""Настройки для локальной разработки."""
from decouple import Csv, config

from .base import *  # noqa: F401,F403

DEBUG = True

# В DEBUG Django и так разрешает localhost; добавляем явные хосты на случай тоннеля.
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS', cast=Csv(), default='localhost,127.0.0.1,[::1]'
)
