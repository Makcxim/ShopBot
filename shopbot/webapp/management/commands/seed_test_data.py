from django.core.files import File
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from webapp.models import (
    Category,
    Product,
    Shop,
    ShopMembership,
    TelegramUser,
)

PLACEHOLDER_PATH = '/app/data/placeholder.png'

# Тестовый владелец магазина
OWNER = {
    'username': 'test_seller',
    'telegram_id': 100000001,
    'telegram_username': 'test_seller',
}

SHOP = {
    'name': 'Ключник',
    'slug': 'klyuchnik',
    'description': 'Магазин цифровых ключей для игр. Тестовый продавец.',
    'is_verified': True,
}

CATEGORIES = [
    {'name': 'RPG', 'slug': 'rpg'},
    {'name': 'Экшен', 'slug': 'action'},
    {'name': 'Открытый мир', 'slug': 'open-world'},
]

# price_stars — цена в Telegram Stars (целое число)
PRODUCTS = [
    {'name': 'Cyberpunk 2077', 'price_stars': 150, 'category': 'rpg',
     'short_description': 'RPG от CD Projekt RED',
     'description': 'Cyberpunk 2077 — приключенческая ролевая игра в открытом мире Найт-Сити.'},
    {'name': 'Elden Ring', 'price_stars': 250, 'category': 'action',
     'short_description': 'Action RPG от FromSoftware',
     'description': 'Elden Ring — action-RPG в огромном открытом мире от создателей Dark Souls.'},
    {'name': 'Baldurs Gate 3', 'price_stars': 200, 'category': 'rpg',
     'short_description': 'RPG от Larian Studios',
     'description': 'Baldur\'s Gate 3 — классическая партийная RPG по правилам D&D.'},
    {'name': 'Red Dead Redemption 2', 'price_stars': 130, 'category': 'open-world',
     'short_description': 'Open world от Rockstar',
     'description': 'Red Dead Redemption 2 — вестерн в открытом мире от Rockstar Games.'},
    {'name': 'The Witcher 3', 'price_stars': 50, 'category': 'rpg',
     'short_description': 'RPG от CD Projekt RED',
     'description': 'The Witcher 3: Wild Hunt — культовая RPG про ведьмака Геральта.'},
]


class Command(BaseCommand):
    help = 'Заполняет БД тестовыми данными (продавец, магазин, категории, товары, ключи)'

    def handle(self, *args, **options):
        if Shop.objects.exists():
            self.stdout.write('Данные уже есть. Пропускаю seed.')
            return

        owner, _ = TelegramUser.objects.get_or_create(
            telegram_id=OWNER['telegram_id'],
            defaults={
                'username': OWNER['username'],
                'telegram_username': OWNER['telegram_username'],
            },
        )
        self.stdout.write(f'Создан продавец: {owner}')

        shop = Shop.objects.create(**SHOP)
        ShopMembership.objects.create(user=owner, shop=shop, role=ShopMembership.Role.OWNER)
        self.stdout.write(f'Создан магазин: {shop}')

        categories = {}
        for cat in CATEGORIES:
            categories[cat['slug']] = Category.objects.create(**cat)
        self.stdout.write(f'Создано категорий: {len(categories)}')

        for data in PRODUCTS:
            product = Product(
                shop=shop,
                category=categories.get(data['category']),
                name=data['name'],
                slug=slugify(data['name']),
                short_description=data['short_description'],
                description=data['description'],
                price_stars=data['price_stars'],
            )
            try:
                with open(PLACEHOLDER_PATH, 'rb') as f:
                    product.image.save('placeholder.png', File(f), save=False)
            except FileNotFoundError:
                self.stdout.write(self.style.WARNING(
                    f'Плейсхолдер не найден ({PLACEHOLDER_PATH}), товар без картинки'
                ))
            product.save()
            self.stdout.write(f'Создан товар: {product.name} — {product.price_stars} ⭐')

        call_command('generate_product_keys')
        self.stdout.write(self.style.SUCCESS(
            f'Готово! Магазин «{shop.name}», {len(PRODUCTS)} товаров с ключами.'
        ))
