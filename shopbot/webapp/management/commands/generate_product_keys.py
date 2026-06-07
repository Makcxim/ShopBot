import time

from django.core.management.base import BaseCommand

from webapp.models import Product, ProductKey


class Command(BaseCommand):
    help = 'Генерирует по 10 тестовых ключей для каждого товара без ключей'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=10, help='Сколько ключей на товар')

    def handle(self, *args, **options):
        count = options['count']
        products = Product.objects.all()

        for product in products:
            if product.keys.exists():
                self.stdout.write(f'У товара "{product.name}" уже есть ключи, пропускаю')
                continue
            for i in range(count):
                ProductKey.objects.create(
                    product=product,
                    key=f'{product.slug}-KEY-{i}-{int(time.time())}',
                )
            self.stdout.write(f'Создано {count} ключей для "{product.name}"')

        self.stdout.write(self.style.SUCCESS('Готово!'))
