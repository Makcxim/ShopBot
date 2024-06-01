from django.core.management.base import BaseCommand

from webapp.models import ShopProduct, ShopProductKey


class Command(BaseCommand):
    help = 'Updates all remain keys for all products'

    def handle(self, *args, **options):
        print('Generating test keys!')

        products = ShopProduct.objects.all()

        for product in products:
            remain = ShopProductKey.objects.filter(product=product, is_sold=False).count()
            product.remain = remain
            product.save()
            print(f'Updated product {product.name} remain to {remain}')
        
        print('All products updated!')
