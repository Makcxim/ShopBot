import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

from aiogram import Bot, F, Router, types
from aiogram.enums import ContentType
from aiogram.filters import Command
from aiogram.types import Message, PreCheckoutQuery, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asgiref.sync import sync_to_async
from decouple import config
from django.core.management import call_command

from webapp.models import ShopOrder, ShopProduct, ShopProductKey

router = Router(name=__name__)


@router.message(Command("help", "start"))
async def command_start_handler(message: Message):

    APP_BASE_URL = config('APP_BASE_URL', default='https://google.com')
    MAIN_PAGE_URL = config('MAIN_PAGE_URL', default='main_page')

    # kb = [[types.KeyboardButton(text="переход", web_app=WebAppInfo(url=f"{APP_BASE_URL}/{MAIN_PAGE_URL}"))]]
    # markup = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text="Открыть магазин", web_app=WebAppInfo(url=f"{APP_BASE_URL}/{MAIN_PAGE_URL}"))
    )
    await message.answer("Вам привествует магазин КЛЮЧНИК покупайте ключи стим только у нас!", reply_markup=builder.as_markup())



@router.pre_checkout_query()
async def pre_checkout_query(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    payload = json.loads(pre_checkout_query.invoice_payload)

    for item in payload:
        product_id = item['id']
        amount = item['amount']
        keys = await get_product_keys_by_id(product_id, amount)
        if len(keys) < amount:
            await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Недостаточно ключей! Обратитесь в поддержку!")
            return

    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


async def get_product_by_id(product_id):
    # Получение продукта по id
    return await sync_to_async(ShopProduct.objects.get)(id=product_id)


async def update_bought_keys(keys):
    # Обновление статуса ключей
    await sync_to_async(ShopProductKey.objects.filter(key__in=keys).update, thread_sensitive=True)(is_sold=True)


async def get_product_keys_by_id(product_id, amount):
    # Получение ключей продукта
    keys = await sync_to_async(list)(
        ShopProductKey.objects.filter(product=product_id, is_sold=False).values_list('key', flat=True)[:amount]
    )

    return keys


@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    # list of dicts id=product_id, amount=product_amount
    payload = json.loads(message.successful_payment.invoice_payload)  

    thx_msg = (
        f"Спасибо за покупку на "
        f"{message.successful_payment.total_amount // 100} "
        f"{message.successful_payment.currency}!\n"
    )
    msg = 'Ваши ключи:\n'

    for _, i in enumerate(payload):
        product = await get_product_by_id(i['id'])
        thx_msg += (
            f"{_+1}) {product.name} - "
            f"{i['amount']} шт. по цене {product.price}\n"
        )
        keys = await get_product_keys_by_id(i['id'], i['amount'])
        for __, key in enumerate(keys):
            msg += f"Ключ №{__+1} от {product.name}: {key}\n"
    
    await message.answer(thx_msg)
    await message.answer(msg)

    await update_bought_keys(list(keys))

    await write_success_payment_to_db(message.from_user.id, payload)

    await run_command_in_thread()


async def write_success_payment_to_db(telegram_id, payload):

    for prod in payload:
        product = await get_product_by_id(prod['id'])

        order = ShopOrder(
            telegram_id=telegram_id,
            product=product,
            count=prod['amount'],
            total_price=product.price * prod['amount'],
        )

        await sync_to_async(order.save)()


async def run_command_in_thread():
    with ThreadPoolExecutor() as executor:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, 
                                   call_command, 
                                   'update_remain_keys'
                                   )

