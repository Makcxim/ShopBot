import html
import json
from pathlib import Path

from aiogram import Bot, F, Router, types
from aiogram.enums import ContentType
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message, PreCheckoutQuery, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asgiref.sync import sync_to_async
from decouple import config
from django.db import transaction
from django.utils import timezone

from webapp.models import Order, OrderItem, Product, ProductKey, ShopMembership, TelegramUser

router = Router(name=__name__)

WELCOME_BANNER = Path(__file__).resolve().parent / 'assets' / 'welcome.png'


@router.message(Command("help", "start"))
async def command_start_handler(message: Message):
    APP_BASE_URL = config('APP_BASE_URL', default='https://google.com')
    MAIN_PAGE_URL = config('MAIN_PAGE_URL', default='main_page')

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text="🎮 Открыть магазин",
        web_app=WebAppInfo(url=f"{APP_BASE_URL}/{MAIN_PAGE_URL}"),
    ))
    name = html.escape(message.from_user.first_name or 'друг')
    caption = (
        f"👋 Привет, <b>{name}</b>!\n\n"
        "Это <b>маркетплейс цифровых ключей</b> для игр 🎮\n"
        "Тысячи ключей от разных магазинов — покупка в пару кликов прямо в Telegram.\n\n"
        "💳 Карта не нужна: оплата за <b>Telegram Stars</b> ⭐\n"
        "🔑 Ключи приходят сюда, в чат, сразу после оплаты.\n\n"
        "Жми кнопку ниже, чтобы открыть витрину 👇"
    )
    markup = builder.as_markup()

    if WELCOME_BANNER.exists():
        await message.answer_photo(FSInputFile(WELCOME_BANNER), caption=caption, reply_markup=markup)
    else:
        await message.answer(caption, reply_markup=markup)


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
    """Создаёт заказ, выдаёт ключи покупателю и уведомляет владельцев магазинов."""
    sp = message.successful_payment
    payload = json.loads(sp.invoice_payload)

    thx_msg, keys_msg, seller_notifications = await sync_to_async(_process_payment)(
        telegram_id=message.from_user.id,
        telegram_username=message.from_user.username or '',
        full_name=message.from_user.full_name,
        payload=payload,
        total_stars=sp.total_amount,            # для XTR это целое число звёзд
        charge_id=sp.telegram_payment_charge_id,
    )

    await message.answer(thx_msg)
    await message.answer(keys_msg)

    # Уведомляем владельцев магазинов о продаже (если они запускали бота)
    for owner_id, text in seller_notifications:
        try:
            await message.bot.send_message(owner_id, text)
        except Exception:
            pass  # владелец мог не начать диалог с ботом


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

    order_lines = []     # строки состава заказа для чека
    keys_blocks = []     # блоки с ключами по товарам
    # Сводка продаж по магазинам для уведомления владельцев: shop_id -> (shop, [строки])
    shop_sales = {}

    for item in payload:
        product = Product.objects.get(id=item['product_id'])
        quantity = int(item['quantity'])
        name = html.escape(product.name)

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

        order_lines.append(f"• {name} — {quantity} × {product.price_stars} ⭐")

        keys_lines = "\n".join(f"<code>{html.escape(k)}</code>" for k in key_values)
        keys_blocks.append(f"🎮 <b>{name}</b>\n{keys_lines}")

        entry = shop_sales.setdefault(product.shop_id, (product.shop, []))
        entry[1].append(f"• {name} × {quantity} = {product.price_stars * quantity} ⭐")

    order.status = Order.Status.DELIVERED
    order.save(update_fields=['status'])

    thx_msg = (
        "🎉 <b>Спасибо за покупку!</b>\n\n"
        f"✅ Оплата прошла успешно — заказ <b>#{order.id}</b> на <b>{total_stars} ⭐</b>.\n\n"
        "<b>Состав заказа:</b>\n" + "\n".join(order_lines)
        + "\n\nВаши ключи — в следующем сообщении 👇"
    )
    keys_msg = (
        "🔑 <b>Ваши ключи</b>\n\n"
        + "\n\n".join(keys_blocks)
        + "\n\n<i>Нажмите на ключ, чтобы скопировать. Сохраните его в надёжном месте.</i>\n"
        "Приятной игры! 🎮"
    )

    # Формируем уведомления владельцам (один владелец может иметь несколько магазинов)
    notifications = []
    buyer_name = html.escape(full_name or telegram_username or f'tg_{telegram_id}')
    for shop, lines in shop_sales.values():
        owner_ids = ShopMembership.objects.filter(
            shop=shop, role=ShopMembership.Role.OWNER
        ).values_list('user__telegram_id', flat=True)
        shop_total = sum(
            oi.price_stars * oi.quantity
            for oi in order.items.all() if oi.shop_id == shop.id
        )
        text = (
            "🛒 <b>Новая продажа!</b>\n\n"
            f"🏪 Магазин: <b>{html.escape(shop.name)}</b>\n"
            f"🧾 Заказ: <b>#{order.id}</b>\n"
            f"👤 Покупатель: {buyer_name}\n\n"
            + "\n".join(lines)
            + f"\n\n💰 <b>Итого: {shop_total} ⭐</b>"
        )
        for owner_id in owner_ids:
            if owner_id:
                notifications.append((owner_id, text))

    return thx_msg, keys_msg, notifications
