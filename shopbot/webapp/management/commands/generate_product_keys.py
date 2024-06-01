import time

from django.core.management import call_command
from django.core.management.base import BaseCommand

from webapp.models import ShopProduct, ShopProductKey


class Command(BaseCommand):
    help = 'Generate 10 test keys for each product'

    def handle(self, *args, **options):
        print('Generating test keys!')

        products = ShopProduct.objects.all()

        for product in products:
            for i in range(10):
                ShopProductKey.objects.create(
                    product=product,
                    key=f'{product.name}_key_{i}_{time.time()}'
                )

        print('Generated 10 keys for each product!')

        call_command('update_remain_keys')
