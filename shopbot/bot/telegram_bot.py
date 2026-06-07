import json

from aiogram import Bot, F, Router, types
from aiogram.enums import ContentType
from aiogram.filters import Command
from aiogram.types import Message, PreCheckoutQuery, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asgiref.sync import sync_to_async
from decouple import config
from django.db import transaction
from django.utils import timezone

from webapp.models import Order, OrderItem, Product, ProductKey, TelegramUser

router = Router(name=__name__)


@router.message(Command("help", "start"))
async def command_start_handler(message: Message):
    APP_BASE_URL = config('APP_BASE_URL', default='https://google.com')
    MAIN_PAGE_URL = config('MAIN_PAGE_URL', default='main_page')

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text="Открыть магазин",
        web_app=WebAppInfo(url=f"{APP_BASE_URL}/{MAIN_PAGE_URL}"),
    ))
    await message.answer(
        "Вас приветствует маркетплейс цифровых ключей! Покупайте ключи за Telegram Stars ⭐",
        reply_markup=builder.as_markup(),
    )


@router.pre_checkout_query()
async def pre_checkout_query(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    """Перед оплатой проверяем, что ключей хватает на все позиции заказа."""
    payload = json.loads(pre_checkout_query.invoice_payload)

    ok = await sync_to_async(_has_enough_keys)(payload)
    if not ok:
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id, ok=False,
            error_message="Недостаточно ключей! Обратитесь в поддержку.",
        )
        return

    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    """Создаёт заказ, выдаёт ключи и отправляет их покупателю."""
    sp = message.successful_payment
    payload = json.loads(sp.invoice_payload)

    thx_msg, keys_msg = await sync_to_async(_process_payment)(
        telegram_id=message.from_user.id,
        telegram_username=message.from_user.username or '',
        full_name=message.from_user.full_name,
        payload=payload,
        total_stars=sp.total_amount,            # для XTR это целое число звёзд
        charge_id=sp.telegram_payment_charge_id,
    )

    await message.answer(thx_msg)
    await message.answer(keys_msg)


def _has_enough_keys(payload):
    for item in payload:
        available = ProductKey.objects.filter(
            product_id=item['product_id'], is_sold=False
        ).count()
        if available < int(item['quantity']):
            return False
    return True


@transaction.atomic
def _process_payment(telegram_id, telegram_username, full_name, payload, total_stars, charge_id):
    """Синхронная обработка успешной оплаты в одной транзакции."""
    buyer, _ = TelegramUser.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={
            'username': telegram_username or f'tg_{telegram_id}',
            'telegram_username': telegram_username,
        },
    )

    order = Order.objects.create(
        buyer=buyer,
        status=Order.Status.PAID,
        total_stars=total_stars,
        telegram_payment_charge_id=charge_id,
    )

    thx_msg = f"Спасибо за покупку на {total_stars} ⭐!\n"
    keys_msg = "Ваши ключи:\n"

    for index, item in enumerate(payload, start=1):
        product = Product.objects.get(id=item['product_id'])
        quantity = int(item['quantity'])

        order_item = OrderItem.objects.create(
            order=order,
            product=product,
            shop=product.shop,
            quantity=quantity,
            price_stars=product.price_stars,
        )

        # Резервируем свободные ключи
        keys = list(
            ProductKey.objects.select_for_update()
            .filter(product=product, is_sold=False)[:quantity]
        )
        key_values = [k.key for k in keys]

        for key in keys:
            key.is_sold = True
            key.sold_at = timezone.now()
            key.order_item = order_item
            key.save(update_fields=['is_sold', 'sold_at', 'order_item'])

        order_item.delivered_keys = key_values
        order_item.save(update_fields=['delivered_keys'])

        thx_msg += f"{index}) {product.name} — {quantity} шт. по {product.price_stars} ⭐\n"
        for n, key in enumerate(key_values, start=1):
            keys_msg += f"Ключ №{n} от {product.name}: {key}\n"

    order.status = Order.Status.DELIVERED
    order.save(update_fields=['status'])

    return thx_msg, keys_msg
