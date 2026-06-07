from django.core.files import File
from django.core.management import call_command
from django.core.management.base import BaseCommand

from webapp.models import ShopProduct

TEST_PRODUCTS = [
    {'name': 'Cyberpunk 2077', 'price': 1499.00, 'short_description': 'RPG от CD Projekt RED'},
    {'name': 'Elden Ring', 'price': 2499.00, 'short_description': 'Action RPG от FromSoftware'},
    {'name': 'Baldurs Gate 3', 'price': 1999.00, 'short_description': 'RPG от Larian Studios'},
    {'name': 'Red Dead Redemption 2', 'price': 1299.00, 'short_description': 'Open world от Rockstar'},
    {'name': 'The Witcher 3', 'price': 499.00, 'short_description': 'RPG от CD Projekt RED'},
]

PLACEHOLDER_PATH = '/app/data/placeholder.png'


class Command(BaseCommand):
    help = 'Seed database with test products and keys'

    def handle(self, *args, **options):
        if ShopProduct.objects.exists():
            self.stdout.write('Products already exist. Skipping seed.')
            return

        for product_data in TEST_PRODUCTS:
            product = ShopProduct(
                name=product_data['name'],
                price=product_data['price'],
                short_description=product_data['short_description'],
            )
            try:
                with open(PLACEHOLDER_PATH, 'rb') as f:
                    product.image_original.save('placeholder.png', File(f), save=False)
            except FileNotFoundError:
                self.stdout.write(self.style.WARNING(f'Placeholder not found at {PLACEHOLDER_PATH}, skipping image'))
            product.save()
            self.stdout.write(f'Created: {product.name}')

        call_command('generate_product_keys')
        self.stdout.write(self.style.SUCCESS('Done! Created 5 products with 10 keys each.'))