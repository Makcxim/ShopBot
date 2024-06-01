import json

import requests
from decouple import config
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from webapp.models import ShopProduct


@csrf_exempt
def create_invoice_link(request):
    data = json.loads(request.body)
    prices_data = data.get('prices')

    base_api_url = config('TELEGRAM_API_URL', default='https://api.telegram.org/bot')
    telegram_token = config('TELEGRAM_BOT_TOKEN', default='123')
    api_url = f'{base_api_url}{telegram_token}/createInvoiceLink'

    payload = []

    for price in prices_data:
        product = ShopProduct.objects.get(id=price['label'])
        payload.append({'id': price['label'], 'amount': price['amount'] // 100})
        price['amount'] = int(product.price * price['amount'])
        price['label'] = product.name

    url = requests.post(api_url, 
        json={
            'title': "Форма оплаты заказа",
            'description': 'Выбранные товары',
            'payload': payload,
            'provider_token': config('TELEGRAM_PROVIDER_TOKEN', default='123'),
            'currency': 'RUB',
            'prices': prices_data,
            'need_name': True,
            'need_phone_number': True,
            'need_email': True,
        }
    )

    return HttpResponse(url.text)




