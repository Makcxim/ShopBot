import io

import requests
from django.core.files.base import ContentFile
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
STEAM_HEADER = 'https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg'

CATEGORIES = [
    {'name': 'RPG', 'slug': 'rpg', 'icon': '⚔️'},
    {'name': 'Экшен', 'slug': 'action', 'icon': '💥'},
    {'name': 'Открытый мир', 'slug': 'open-world', 'icon': '🗺️'},
    {'name': 'Стратегии', 'slug': 'strategy', 'icon': '♟️'},
    {'name': 'Хорроры', 'slug': 'horror', 'icon': '👻'},
    {'name': 'Гонки', 'slug': 'racing', 'icon': '🏎️'},
]

# Магазины: владелец (telegram_id, username) + список товаров.
# appid — id игры в Steam для скачивания реальной обложки.
SHOPS = [
    {
        'shop': {'name': 'Ключник', 'slug': 'klyuchnik', 'is_verified': True,
                 'description': 'Лучшие цены на ключи AAA-проектов. Моментальная выдача.'},
        'owner': {'telegram_id': 100000001, 'username': 'klyuchnik_owner'},
        'products': [
            {'name': 'Cyberpunk 2077', 'appid': 1091500, 'price': 150, 'cat': 'rpg',
             'short': 'RPG от CD Projekt RED', 'desc': 'Приключенческая ролевая игра в открытом мире Найт-Сити.'},
            {'name': 'The Witcher 3: Wild Hunt', 'appid': 292030, 'price': 50, 'cat': 'rpg',
             'short': 'Культовая RPG про ведьмака', 'desc': 'Огромный открытый мир, сотни часов контента, ведьмак Геральт.'},
            {'name': 'Elden Ring', 'appid': 1245620, 'price': 250, 'cat': 'action',
             'short': 'Souls-like от FromSoftware', 'desc': 'Action-RPG в открытом мире от создателей Dark Souls.'},
            {'name': 'Red Dead Redemption 2', 'appid': 1174180, 'price': 130, 'cat': 'open-world',
             'short': 'Вестерн от Rockstar', 'desc': 'Эпичный вестерн в открытом мире от Rockstar Games.'},
        ],
    },
    {
        'shop': {'name': 'GameVault', 'slug': 'gamevault', 'is_verified': True,
                 'description': 'Магазин инди и AAA. Гарантия на все ключи.'},
        'owner': {'telegram_id': 100000002, 'username': 'gamevault_owner'},
        'products': [
            {'name': 'Baldur\'s Gate 3', 'appid': 1086940, 'price': 200, 'cat': 'rpg',
             'short': 'RPG года от Larian', 'desc': 'Партийная RPG по правилам D&D с огромной свободой выбора.'},
            {'name': 'Hades', 'appid': 1145360, 'price': 40, 'cat': 'action',
             'short': 'Рогалик от Supergiant', 'desc': 'Динамичный роглайт про побег из подземного царства.'},
            {'name': 'Hollow Knight', 'appid': 367520, 'price': 25, 'cat': 'action',
             'short': 'Метроидвания', 'desc': 'Атмосферная метроидвания в королевстве насекомых.'},
            {'name': 'Stardew Valley', 'appid': 413150, 'price': 20, 'cat': 'strategy',
             'short': 'Фермерский симулятор', 'desc': 'Уютная ферма, отношения, исследование пещер.'},
        ],
    },
    {
        'shop': {'name': 'Pixel Store', 'slug': 'pixel-store', 'is_verified': False,
                 'description': 'Молодой магазин. Низкие цены на популярные тайтлы.'},
        'owner': {'telegram_id': 100000003, 'username': 'pixel_owner'},
        'products': [
            {'name': 'DOOM Eternal', 'appid': 782330, 'price': 90, 'cat': 'action',
             'short': 'Брутальный шутер', 'desc': 'Скоростной шутер про истребление демонов.'},
            {'name': 'Resident Evil 4', 'appid': 2050650, 'price': 180, 'cat': 'horror',
             'short': 'Ремейк классики', 'desc': 'Ремейк легендарного survival-horror.'},
            {'name': 'Forza Horizon 5', 'appid': 1551360, 'price': 160, 'cat': 'racing',
             'short': 'Аркадные гонки', 'desc': 'Открытый мир Мексики и сотни автомобилей.'},
        ],
    },
    {
        'shop': {'name': 'RetroKeys', 'slug': 'retrokeys', 'is_verified': True,
                 'description': 'Классика и стратегии. Для ценителей.'},
        'owner': {'telegram_id': 100000004, 'username': 'retro_owner'},
        'products': [
            {'name': 'Sid Meier\'s Civilization VI', 'appid': 289070, 'price': 70, 'cat': 'strategy',
             'short': 'Глобальная стратегия', 'desc': 'Построй империю, что выдержит испытание временем.'},
            {'name': 'Cities: Skylines', 'appid': 255710, 'price': 35, 'cat': 'strategy',
             'short': 'Градостроительный симулятор', 'desc': 'Построй город мечты с нуля.'},
            {'name': 'Phasmophobia', 'appid': 739630, 'price': 45, 'cat': 'horror',
             'short': 'Кооп-хоррор', 'desc': 'Охота на призраков с друзьями.'},
        ],
    },
]


class Command(BaseCommand):
    help = 'Заполняет БД тестовыми данными (магазины, категории, товары, ключи, обложки Steam)'

    def add_arguments(self, parser):
        parser.add_argument('--no-images', action='store_true', help='Не скачивать обложки')

    def handle(self, *args, **options):
        if Shop.objects.exists():
            self.stdout.write('Данные уже есть. Пропускаю seed.')
            return

        # Категории
        categories = {c['slug']: Category.objects.create(**c) for c in CATEGORIES}
        self.stdout.write(f'Создано категорий: {len(categories)}')

        for entry in SHOPS:
            owner, _ = TelegramUser.objects.get_or_create(
                telegram_id=entry['owner']['telegram_id'],
                defaults={
                    'username': entry['owner']['username'],
                    'telegram_username': entry['owner']['username'],
                },
            )
            shop = Shop.objects.create(**entry['shop'])
            ShopMembership.objects.create(user=owner, shop=shop, role=ShopMembership.Role.OWNER)
            self.stdout.write(f'Магазин: {shop.name} (владелец {owner})')

            for data in entry['products']:
                product = Product(
                    shop=shop,
                    category=categories.get(data['cat']),
                    name=data['name'],
                    slug=slugify(data['name']),
                    short_description=data['short'],
                    description=data['desc'],
                    price_stars=data['price'],
                )
                self._attach_image(product, data.get('appid'), options['no_images'])
                product.save()
                self.stdout.write(f'  товар: {product.name} — {product.price_stars} ⭐')

        call_command('generate_product_keys')
        self.stdout.write(self.style.SUCCESS(
            f'Готово! Магазинов: {Shop.objects.count()}, товаров: {Product.objects.count()}.'
        ))

    def _attach_image(self, product, appid, no_images):
        """Скачивает обложку Steam; при неудаче — локальный placeholder."""
        if appid and not no_images:
            try:
                url = STEAM_HEADER.format(appid=appid)
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200 and resp.content:
                    product.image.save(f'{product.slug}.jpg', ContentFile(resp.content), save=False)
                    return
            except requests.RequestException:
                pass
        try:
            with open(PLACEHOLDER_PATH, 'rb') as f:
                product.image.save('placeholder.png', ContentFile(f.read()), save=False)
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING(f'Нет картинки для {product.name}'))
