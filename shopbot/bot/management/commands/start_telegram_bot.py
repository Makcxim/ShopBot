import asyncio

from aiogram import Bot, Dispatcher
from decouple import config
from django.core.management.base import BaseCommand

from ...telegram_bot import router


class Command(BaseCommand):
    help = 'Start telegram bot'

    def handle(self, *args, **options):
        print('Starting telegram bot!')

        TOKEN = config('TELEGRAM_BOT_TOKEN', default='TOKEN')
        dp = Dispatcher()
        dp_bot = Bot(TOKEN)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        dp.include_router(router)

        async def startup(dispatcher: Dispatcher, bot: Bot):
            print('Telegram bot started!')

        dp.startup.register(startup)

        loop.run_until_complete(dp.start_polling(dp_bot, skip_updates=True))



