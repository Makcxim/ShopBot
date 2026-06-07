"""Валидация Telegram WebApp initData.

Telegram передаёт в WebApp строку initData (кто пользователь, его id, username и т.д.)
вместе с подписью hash. Подпись проверяется по схеме из официальной документации:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

Без проверки подписи любой мог бы открыть URL вне Telegram и подделать telegram_id.
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from decouple import config

# Максимальный возраст initData (в секундах). Защита от повторного использования старой подписи.
MAX_AUTH_AGE = 24 * 60 * 60


def validate_init_data(init_data: str, max_age: int = MAX_AUTH_AGE) -> dict | None:
    """Проверяет подпись initData и возвращает данные пользователя или None.

    Возвращает dict с ключами Telegram-пользователя (id, username, first_name, ...)
    при успехе, иначе None.
    """
    if not init_data:
        return None

    bot_token = config('TELEGRAM_BOT_TOKEN', default='')
    if not bot_token:
        return None

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop('hash', None)
    if not received_hash:
        return None

    # data_check_string: отсортированные по ключу пары "key=value", через \n
    data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(pairs.items()))

    secret_key = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    # Проверка свежести подписи
    auth_date = pairs.get('auth_date')
    if auth_date is not None:
        try:
            if time.time() - int(auth_date) > max_age:
                return None
        except ValueError:
            return None

    user_raw = pairs.get('user')
    if not user_raw:
        return None

    try:
        return json.loads(user_raw)
    except json.JSONDecodeError:
        return None
