import json

import requests
from decouple import config
from django.contrib.auth import login
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import cart as cart_utils
from .models import Product, TelegramUser
from .serializers import CartItemSerializer, TelegramUserSerializer
from .telegram_auth import validate_init_data


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

        base_api_url = config('TELEGRAM_API_URL', default='https://api.telegram.org/bot')
        telegram_token = config('TELEGRAM_BOT_TOKEN', default='123')
        # Тестовое окружение: метод вызывается через /test (бесплатные Stars)
        test_segment = '/test' if config('TELEGRAM_TEST', default=False, cast=bool) else ''
        api_url = f'{base_api_url}{telegram_token}{test_segment}/createInvoiceLink'

        response = requests.post(
            api_url,
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
