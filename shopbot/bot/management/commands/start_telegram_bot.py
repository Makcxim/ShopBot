import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.types import MenuButtonWebApp, WebAppInfo
from decouple import config
from django.core.management.base import BaseCommand

from ...telegram_bot import router


class Command(BaseCommand):
    help = 'Start telegram bot'

    def handle(self, *args, **options):
        print('Starting telegram bot!')

        TOKEN = config('TELEGRAM_BOT_TOKEN', default='TOKEN')
        dp = Dispatcher()
        default = DefaultBotProperties(parse_mode=ParseMode.HTML)

        # Тестовое окружение Telegram (бесплатные Stars): TELEGRAM_TEST=True в .env.
        # В тест-режиме методы вызываются по пути /bot<token>/test/<method>.
        if config('TELEGRAM_TEST', default=False, cast=bool):
            test_server = TelegramAPIServer(
                base='https://api.telegram.org/bot{token}/test/{method}',
                file='https://api.telegram.org/file/bot{token}/test/{path}',
            )
            dp_bot = Bot(TOKEN, session=AiohttpSession(api=test_server), default=default)
            print('Bot running in TEST environment')
        else:
            dp_bot = Bot(TOKEN, default=default)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        dp.include_router(router)

        app_base_url = config('APP_BASE_URL', default='https://google.com')
        main_page_url = config('MAIN_PAGE_URL', default='main_page')

        async def startup(dispatcher: Dispatcher, bot: Bot):
            # Кнопка-меню слева от поля ввода открывает витрину (а не список команд)
            await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
                text='Открыть магазин',
                web_app=WebAppInfo(url=f'{app_base_url}/{main_page_url}'),
            ))
            print('Telegram bot started!')

        dp.startup.register(startup)

        loop.run_until_complete(dp.start_polling(dp_bot, skip_updates=True))



