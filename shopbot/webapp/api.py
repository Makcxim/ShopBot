import json

import requests
from decouple import config
from django.contrib.auth import login
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Сессионная аутентификация без CSRF — для WebApp-эндпоинтов.

    Telegram WebApp кэширует HTML, из-за чего csrf-токен в странице расходится
    с cookie. Запросы идут с того же домена, пользователь действует над своими
    же данными, поэтому CSRF-проверку отключаем (как и у эндпоинтов корзины).
    """

    def enforce_csrf(self, request):
        return

from . import cart as cart_utils
from .models import Order, Product, ProductKey, TelegramUser
from .serializers import CartItemSerializer, TelegramUserSerializer
from .telegram_auth import validate_init_data


def _telegram_api_url(method):
    """URL метода Bot API с учётом тестового окружения."""
    base = config('TELEGRAM_API_URL', default='https://api.telegram.org/bot')
    token = config('TELEGRAM_BOT_TOKEN', default='123')
    test = '/test' if config('TELEGRAM_TEST', default=False, cast=bool) else ''
    return f'{base}{token}{test}/{method}'


class TelegramAuthView(APIView):
    """POST /api/auth/telegram/ — авторизация по initData из Telegram WebApp."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        init_data = request.data.get('init_data', '')
        tg_user = validate_init_data(init_data)
        if tg_user is None:
            return Response(
                {'detail': 'Некорректные данные авторизации'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        telegram_id = tg_user.get('id')
        username = tg_user.get('username') or f'tg_{telegram_id}'

        user, _ = TelegramUser.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                'username': username,
                'telegram_username': tg_user.get('username', '') or '',
                'first_name': tg_user.get('first_name', '') or '',
                'last_name': tg_user.get('last_name', '') or '',
                'avatar_url': tg_user.get('photo_url', '') or '',
            },
        )

        login(request._request, user, backend='django.contrib.auth.backends.ModelBackend')
        return Response(TelegramUserSerializer(user).data)


class CartAddView(APIView):
    """POST /api/cart/add/ — добавить товар в корзину (сессия)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        cart_utils.add_to_cart(request.session, data['product_id'], data['quantity'])
        return Response({'cart_count': cart_utils.cart_count(request.session)})


class CartRemoveView(APIView):
    """POST /api/cart/remove/ — удалить товар из корзины."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        product_id = request.data.get('product_id')
        cart_utils.remove_from_cart(request.session, product_id)
        return Response({'cart_count': cart_utils.cart_count(request.session)})


class CartSetView(APIView):
    """POST /api/cart/set/ — задать количество товара (0 — удалить)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            product_id = int(request.data.get('product_id'))
            quantity = int(request.data.get('quantity'))
        except (TypeError, ValueError):
            return Response({'detail': 'Некорректные данные'}, status=status.HTTP_400_BAD_REQUEST)

        product = Product.objects.filter(id=product_id).first()
        if product and quantity > product.stock:
            quantity = product.stock  # не больше, чем в наличии

        cart_utils.set_quantity(request.session, product_id, quantity)
        _, total = cart_utils.cart_items(request.session)
        subtotal = (product.price_stars * quantity) if product else 0
        return Response({
            'cart_count': cart_utils.cart_count(request.session),
            'quantity': max(quantity, 0),
            'subtotal': subtotal,
            'total': total,
        })


class CartClearView(APIView):
    """POST /api/cart/clear/ — очистить корзину (после успешной оплаты)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        cart_utils.save_cart(request.session, {})
        return Response({'cart_count': 0})


class CreateInvoiceView(APIView):
    """POST /api/create-invoice/ — создаёт ссылку на оплату Telegram Stars из корзины."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        items, total = cart_utils.cart_items(request.session)
        if not items:
            return Response({'detail': 'Корзина пуста'}, status=status.HTTP_400_BAD_REQUEST)

        # Проверка наличия ключей
        for item in items:
            if item['product'].stock < item['quantity']:
                return Response(
                    {'detail': f'Недостаточно ключей: {item["product"].name}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        payload = [
            {'product_id': item['product'].id, 'quantity': item['quantity']}
            for item in items
        ]

        response = requests.post(
            _telegram_api_url('createInvoiceLink'),
            json={
                'title': 'Оплата заказа',
                'description': 'Покупка цифровых ключей',
                'payload': json.dumps(payload),
                'provider_token': '',       # для Stars провайдер не нужен
                'currency': 'XTR',          # Telegram Stars
                'prices': [{'label': 'Заказ', 'amount': total}],  # целое число звёзд
            },
        )
        result = response.json()
        if not result.get('ok'):
            return Response(
                {'detail': 'Не удалось создать счёт', 'telegram': result},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({'invoice_link': result['result']})


class RefundOrderView(APIView):
    """POST /api/orders/<pk>/refund/ — возврат звёзд покупателю (refundStarPayment).

    Покупатель может вернуть свой оплаченный заказ. Ключи возвращаются в наличие,
    заказ помечается как возвращённый.
    """

    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk, buyer=request.user)

        if order.status == Order.Status.REFUNDED:
            return Response({'detail': 'Заказ уже возвращён'}, status=status.HTTP_400_BAD_REQUEST)
        if order.status not in (Order.Status.PAID, Order.Status.DELIVERED):
            return Response({'detail': 'Этот заказ нельзя вернуть'}, status=status.HTTP_400_BAD_REQUEST)
        if not order.telegram_payment_charge_id:
            return Response({'detail': 'Нет данных платежа для возврата'}, status=status.HTTP_400_BAD_REQUEST)

        response = requests.post(
            _telegram_api_url('refundStarPayment'),
            json={
                'user_id': request.user.telegram_id,
                'telegram_payment_charge_id': order.telegram_payment_charge_id,
            },
        )
        result = response.json()
        if not result.get('ok'):
            return Response(
                {'detail': 'Telegram отклонил возврат', 'telegram': result},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Возвращаем ключи в наличие и помечаем заказ возвращённым
        for item in order.items.all():
            ProductKey.objects.filter(order_item=item).update(
                is_sold=False, sold_at=None, order_item=None
            )
        order.status = Order.Status.REFUNDED
        order.save(update_fields=['status'])

        return Response({'status': 'refunded'})
