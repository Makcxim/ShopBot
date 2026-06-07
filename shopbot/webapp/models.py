from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class TelegramUserManager(UserManager):
    """Менеджер, гарантирующий наличие telegram_id при создании пользователей."""

    def create_user(self, username, telegram_id=None, password=None, **extra_fields):
        if telegram_id is None:
            raise ValueError('Поле telegram_id обязательно')
        return super().create_user(
            username, password=password, telegram_id=telegram_id, **extra_fields
        )

    def create_superuser(self, username, telegram_id=None, password=None, **extra_fields):
        if telegram_id is None:
            raise ValueError('Поле telegram_id обязательно')
        return super().create_superuser(
            username, password=password, telegram_id=telegram_id, **extra_fields
        )


class TelegramUser(AbstractUser):
    """Пользователь, связанный с аккаунтом Telegram."""

    telegram_id = models.BigIntegerField('Telegram ID', unique=True)
    telegram_username = models.CharField('Telegram username', max_length=255, blank=True)
    avatar_url = models.URLField('Аватар', blank=True)

    # Логин в админку остаётся по username; createsuperuser дополнительно спросит telegram_id.
    REQUIRED_FIELDS = ['telegram_id']

    objects = TelegramUserManager()

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.telegram_username or self.username


class Shop(models.Model):
    """Магазин. Может иметь нескольких участников с ролями (владелец/сотрудник)."""

    name = models.CharField('Название', max_length=255)
    slug = models.SlugField('Slug', unique=True)
    description = models.TextField('Описание', blank=True)
    logo = models.ImageField('Логотип', upload_to='shops/logos/', blank=True)
    is_verified = models.BooleanField('Проверен', default=False)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='ShopMembership',
        related_name='shops',
        verbose_name='Участники',
    )

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = 'Магазины'

    def __str__(self):
        return self.name


class ShopMembership(models.Model):
    """Связь пользователя с магазином и его роль в нём."""

    class Role(models.TextChoices):
        OWNER = 'owner', 'Владелец'
        STAFF = 'staff', 'Сотрудник'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shop_memberships',
        verbose_name='Пользователь',
    )
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name='memberships', verbose_name='Магазин'
    )
    role = models.CharField('Роль', max_length=10, choices=Role.choices, default=Role.STAFF)
    joined_at = models.DateTimeField('Присоединился', auto_now_add=True)

    class Meta:
        verbose_name = 'Участник магазина'
        verbose_name_plural = 'Участники магазина'
        unique_together = ('user', 'shop')

    def __str__(self):
        return f'{self.user} — {self.shop} ({self.get_role_display()})'


class Category(models.Model):
    """Категория товаров. Поддерживает вложенность через self-FK."""

    name = models.CharField('Название', max_length=100)
    slug = models.SlugField('Slug', unique=True)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
        verbose_name='Родительская категория',
    )
    icon = models.CharField('Иконка', max_length=50, blank=True)
    sort_order = models.IntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """Товар (цифровой ключ для игры) конкретного магазина."""

    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name='products', verbose_name='Магазин'
    )
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='products',
        verbose_name='Категория',
    )
    name = models.CharField('Название', max_length=255)
    slug = models.SlugField('Slug')
    description = models.TextField('Полное описание', blank=True)
    short_description = models.CharField('Краткое описание', max_length=150, blank=True)
    price_stars = models.PositiveIntegerField('Цена в Stars')
    image = models.ImageField('Изображение', upload_to='products/', blank=True)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        unique_together = ('shop', 'slug')
        ordering = ['-created_at']

    @property
    def stock(self):
        """Количество доступных (непроданных) ключей."""
        return self.keys.filter(is_sold=False).count()

    @property
    def in_stock(self):
        return self.stock > 0

    def __str__(self):
        return f'{self.name} ({self.shop.name})'


class ProductKey(models.Model):
    """Ключ товара."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='keys', verbose_name='Товар'
    )
    key = models.CharField('Ключ', max_length=500)
    is_sold = models.BooleanField('Продан', default=False)
    sold_at = models.DateTimeField('Продан в', null=True, blank=True)
    order_item = models.ForeignKey(
        'OrderItem',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='keys',
        verbose_name='Позиция заказа',
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Ключ'
        verbose_name_plural = 'Ключи'

    def __str__(self):
        return f'{self.product.name} — {"продан" if self.is_sold else "в наличии"}'


class Order(models.Model):
    """Заказ покупателя."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает оплаты'
        PAID = 'paid', 'Оплачен'
        DELIVERED = 'delivered', 'Доставлен'
        REFUNDED = 'refunded', 'Возвращён'

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name='Покупатель',
    )
    status = models.CharField('Статус', max_length=10, choices=Status.choices, default=Status.PENDING)
    total_stars = models.PositiveIntegerField('Сумма в Stars', default=0)
    telegram_payment_charge_id = models.CharField('ID платежа Telegram', max_length=255, blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заказ #{self.pk} — {self.buyer} — {self.get_status_display()}'


class OrderItem(models.Model):
    """Позиция заказа (товар + количество + выданные ключи)."""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='items', verbose_name='Заказ'
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='Товар')
    # Денормализация: магазин дублируется для быстрой статистики по магазину.
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, verbose_name='Магазин')
    quantity = models.PositiveIntegerField('Количество', default=1)
    price_stars = models.PositiveIntegerField('Цена на момент покупки')
    delivered_keys = models.JSONField('Выданные ключи', default=list, blank=True)

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'

    def __str__(self):
        return f'{self.product.name} x{self.quantity}'
