# ShopBot -> Marketplace: Детальный план реализации

## Ключевые архитектурные решения

- **Приложения:** всего три.
  - `webapp` — модели (включая кастомного юзера), клиентская витрина, API (DRF), Telegram auth.
  - `panel` — собственная админ-панель (Bootstrap, не CoreUI-копия): дашборд + статистика + CRUD.
  - `bot` — Telegram-бот (aiogram), уже существует, переписываем под Stars.
- **Shop вместо Seller:** пользователь может владеть несколькими магазинами и быть сотрудником нескольких. Связь через `ShopMembership` с ролью owner/staff. Товары привязаны к магазину.
- **Вьюхи:** DRF `APIView` + обычные `serializers.Serializer` (НЕ `ModelSerializer`, НЕ `ViewSet`, НЕ миксины). Все данные проходят через сериализаторы. HTML-страницы рендерятся обычными Django-вьюхами, а данные/действия (auth, корзина, оплата) — через DRF APIView.
- **Оплата:** только Telegram Stars (`currency=XTR`, `provider_token=""`, amount — целое число звёзд).
- **БД сбрасываем** (только тестовые данные), миграции пересоздаём.

```
TelegramUser --M2M через ShopMembership(owner/staff)--> Shop
Shop --> Product --> ProductKey
TelegramUser(buyer) --> Order --> OrderItem --> Product
```

---

## Фаза 0: Фундамент

### 0.1 Кастомный User в `webapp` (без отдельного app)

`telegram_id` делаем **обязательным** (`NOT NULL, unique`). Чтобы `createsuperuser`
не падал из-за отсутствия telegram_id, добавляем его в `REQUIRED_FIELDS` — Django
спросит его в консоли. Главного админа создаём со **своим реальным Telegram ID**
(тем же аккаунтом, под которым он заходит в бота).

`webapp/models.py`:
```python
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class TelegramUserManager(UserManager):
    """Гарантирует наличие telegram_id при создании юзера/суперюзера."""

    def create_user(self, username, telegram_id=None, password=None, **extra):
        if telegram_id is None:
            raise ValueError('telegram_id обязателен')
        return super().create_user(username, password=password, telegram_id=telegram_id, **extra)

    def create_superuser(self, username, telegram_id=None, password=None, **extra):
        if telegram_id is None:
            raise ValueError('telegram_id обязателен')
        return super().create_superuser(username, password=password, telegram_id=telegram_id, **extra)


class TelegramUser(AbstractUser):
    telegram_id = models.BigIntegerField('Telegram ID', unique=True)
    telegram_username = models.CharField('Telegram username', max_length=255, blank=True)
    avatar_url = models.URLField('Аватар', blank=True)

    # login для админки остаётся username; createsuperuser дополнительно спросит telegram_id
    REQUIRED_FIELDS = ['telegram_id']

    objects = TelegramUserManager()

    def __str__(self):
        return self.telegram_username or self.username
```

`AUTH_USER_MODEL = 'webapp.TelegramUser'` в settings.py.

Создание главного админа:
```bash
docker compose exec web python manage.py createsuperuser
# спросит: username, telegram_id, password
```

Обычные пользователи создаются из WebApp-авторизации:
`TelegramUser.objects.get_or_create(telegram_id=..., defaults={'username': ..., ...})`.

> `is_seller` НЕ кладём в юзера — роль определяется через `ShopMembership`
> (owner/staff). Доступ к панели = есть хотя бы одно членство в магазине **или** `is_staff/is_superuser`.

### 0.2 Создать приложение `panel`
```
shopbot/panel/
├── __init__.py
├── apps.py
├── views.py           # дашборд, CRUD, списки (обычные Django views для HTML)
├── urls.py
├── templates/panel/
└── static/panel/      # свой css/js поверх Bootstrap
```
`python manage.py startapp panel` (внутри shopbot/).

### 0.3 Обновить settings.py
```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    'rest_framework',   # для DRF APIView + Serializer
    'webapp',
    'bot',
    'panel',
]

AUTH_USER_MODEL = 'webapp.TelegramUser'
```
- MIDDLEWARE НЕ трогаем (whitenoise не нужен — статику раздаёт nginx).
- `rest_framework` нужен, чтобы работали `APIView`/`Serializer`.

### 0.4 Обновить requirements.txt
```
Django==5.0.4
aiogram==3.7.0
python-decouple==3.8
requests==2.31.0            # оставляем, используется в bot/views.py
psycopg2-binary==2.9.9
Pillow==10.3.0
gunicorn==22.0.0
django-extensions==3.2.3
djangorestframework==3.15.1 # ДОБАВИТЬ
```

### 0.5 Сброс БД и миграций
- [ ] Удалить файлы в `webapp/migrations/` (кроме `__init__.py`) и старые модели `ShopProduct/ShopProductKey/ShopOrder`
- [ ] `docker compose down -v`
- [ ] `makemigrations webapp` (ПЕРВЫМ — там AUTH_USER_MODEL)
- [ ] `makemigrations bot panel`
- [ ] `migrate`
- [ ] Переписать `seed_test_data` под новые модели

---

## Фаза 1: Модели + Stars оплата + auth

### 1.1 Модели (всё в `webapp/models.py`)

Рядом с `TelegramUser` (из 0.1) добавляем:

```python
from django.conf import settings


class Shop(models.Model):
    name = models.CharField('Название', max_length=255)
    slug = models.SlugField('Slug', unique=True)
    description = models.TextField('Описание', blank=True)
    logo = models.ImageField('Логотип', upload_to='shops/logos/', blank=True)
    is_verified = models.BooleanField('Проверен', default=False)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='ShopMembership', related_name='shops',
    )

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = 'Магазины'

    def __str__(self):
        return self.name


class ShopMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = 'owner', 'Владелец'
        STAFF = 'staff', 'Сотрудник'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shop_memberships')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField('Роль', max_length=10, choices=Role.choices, default=Role.STAFF)
    joined_at = models.DateTimeField('Присоединился', auto_now_add=True)

    class Meta:
        verbose_name = 'Участник магазина'
        verbose_name_plural = 'Участники магазина'
        unique_together = ('user', 'shop')

    def __str__(self):
        return f'{self.user} — {self.shop} ({self.get_role_display()})'


class Category(models.Model):
    name = models.CharField('Название', max_length=100)
    slug = models.SlugField('Slug', unique=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    icon = models.CharField('Иконка', max_length=50, blank=True)  # emoji или css-класс
    sort_order = models.IntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Product(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name='products')
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
        return self.keys.filter(is_sold=False).count()

    @property
    def in_stock(self):
        return self.stock > 0

    def __str__(self):
        return f'{self.name} ({self.shop.name})'


class ProductKey(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='keys')
    key = models.CharField('Ключ', max_length=500)
    is_sold = models.BooleanField('Продан', default=False)
    sold_at = models.DateTimeField('Продан в', null=True, blank=True)
    order_item = models.ForeignKey('OrderItem', null=True, blank=True, on_delete=models.SET_NULL, related_name='keys')
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Ключ'
        verbose_name_plural = 'Ключи'

    def __str__(self):
        return f'{self.product.name} — {"продан" if self.is_sold else "в наличии"}'


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает оплаты'
        PAID = 'paid', 'Оплачен'
        DELIVERED = 'delivered', 'Доставлен'
        REFUNDED = 'refunded', 'Возвращён'

    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
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
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)  # денормализация для статистики магазина
    quantity = models.PositiveIntegerField('Количество', default=1)
    price_stars = models.PositiveIntegerField('Цена на момент покупки')
    delivered_keys = models.JSONField('Выданные ключи', default=list, blank=True)

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'

    def __str__(self):
        return f'{self.product.name} x{self.quantity}'
```

**Действия:**
- [ ] Дописать модели в webapp/models.py
- [ ] makemigrations + migrate
- [ ] Зарегистрировать модели в webapp/admin.py (стандартная Django-админка для отладки)

### 1.2 Telegram Stars оплата

**Как работает (справка):**
- `currency="XTR"`, `provider_token=""`, `prices=[{label, amount}]`, `amount` — целое число звёзд (НЕ копейки, НЕ делить на 100).
- Провайдер/фискализация НЕ нужны (в отличие от RUB).
- Поток: `createInvoiceLink` → юзер платит → `pre_checkout_query` (отвечаем ok=True) → `successful_payment` с `telegram_payment_charge_id`.
- Тестирование бесплатно — в Telegram **Test Environment** (отдельный DC, бесплатные тестовые звёзды). В проде звёзды настоящие.
- Возврат — `refundStarPayment` по сохранённому `telegram_payment_charge_id`.

**bot/views.py** (create_invoice) — изменения:
```python
# было RUB: currency='RUB', provider_token=<...>, amount в копейках, need_name/phone/email
# стало Stars:
'currency': 'XTR',
'provider_token': '',
'prices': [{'label': product.name, 'amount': product.price_stars}],  # целые звёзды
# need_name/need_phone_number/need_email — УБРАТЬ
```

**bot/telegram_bot.py** (successful_payment) — изменения:
- Создавать `Order` (status=PAID, total_stars, telegram_payment_charge_id из `message.successful_payment`)
- Создавать `OrderItem` на каждый товар (price_stars, shop)
- Брать свободные `ProductKey`, помечать is_sold=True, sold_at=now, привязывать к order_item, складывать в `delivered_keys`
- Отправлять ключи покупателю, ставить Order.status=DELIVERED
- `update_remain_keys` больше НЕ нужен (stock = property), команду удалить

**Действия:**
- [ ] Переписать bot/views.py под Stars
- [ ] Переписать bot/telegram_bot.py: payment handlers под новые модели
- [ ] Удалить webapp/management/commands/update_remain_keys.py
- [ ] Обновить generate_product_keys под новые модели (или влить в seed_test_data)

### 1.3 Telegram auth (валидация initData)

Одна функция-валидатор (НЕ отдельный backend, НЕ отдельный app):

`webapp/telegram_auth.py`:
```python
# validate_init_data(init_data: str) -> dict | None
# 1. распарсить query-string initData
# 2. вынуть hash, остальные пары отсортировать -> data_check_string ("k=v\n...")
# 3. secret_key = HMAC_SHA256(key=b"WebAppData", msg=bot_token)
# 4. сверить HMAC_SHA256(key=secret_key, msg=data_check_string).hexdigest() == hash
# 5. проверить auth_date (не старше ~24ч)
# 6. вернуть распарсенного user (id, username, first_name, photo_url) или None
```

**Зачем:** без проверки подписи можно открыть URL вне Telegram и подделать `telegram_id` → выдать себя за другого. HMAC (ключ = bot token) — официальный способ Telegram подтвердить подлинность данных. Для ВКР = раздел «безопасность».

`webapp/api.py` (DRF APIView):
```python
class TelegramAuthView(APIView):
    # POST /api/auth/telegram/  body: {"init_data": "..."}
    # валидирует -> get_or_create(TelegramUser) -> django login() (session)
    # отдаёт TelegramUserSerializer
```

Фронт вызывает этот эндпоинт при загрузке WebApp (`Telegram.WebApp.initData`).

**Действия:**
- [ ] Написать validate_init_data (HMAC-SHA256)
- [ ] TelegramAuthView (APIView) + get_or_create + session login
- [ ] URL /api/auth/telegram/

---

## Фаза 2: Клиентский фронтенд (Django templates + Bootstrap 5 + DRF)

### 2.1 Подход к вьюхам
- **HTML-страницы** (каталог, товар, корзина, заказы, магазин) — обычные Django-вьюхи (`def view(request): return render(...)`).
- **Данные/действия** (auth, добавить/удалить из корзины, создать инвойс) — DRF `APIView` + `serializers.Serializer`.
- Сериализаторы — только ручные `serializers.Serializer` (поля прописываем явно), НЕ `ModelSerializer`.

### 2.2 Сериализаторы (webapp/serializers.py)
```python
from rest_framework import serializers

class TelegramUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    telegram_id = serializers.IntegerField()
    telegram_username = serializers.CharField()
    avatar_url = serializers.CharField()

class ProductSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    short_description = serializers.CharField()
    price_stars = serializers.IntegerField()
    image = serializers.CharField()          # url
    stock = serializers.IntegerField()
    shop_name = serializers.CharField(source='shop.name')

class CartItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)

class OrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    total_stars = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    items = serializers.ListField()          # сериализуем вручную
```

### 2.3 Шаблоны (webapp/templates/)
```
webapp/templates/
├── base.html              # head, TG SDK, Bootstrap 5, нижняя навигация, тема
├── catalog.html           # сетка product_card + фильтр по категориям
├── product_detail.html    # ПОЛНАЯ страница товара (см. 2.6)
├── cart.html              # корзина перед оплатой
├── orders.html            # история покупок
├── shop_profile.html      # страница магазина (инфо + его товары)
└── includes/
    ├── product_card.html  # карточка для каталога
    ├── navbar.html        # нижняя навигация
    └── empty_state.html   # "Ничего не найдено"
```

### 2.4 base.html — ключевое
- `<script src="https://telegram.org/js/telegram-web-app.js">`
- Bootstrap 5 (CDN или static)
- Тема из `Telegram.WebApp.colorScheme` → классы `theme-light/theme-dark`, CSS-переменные `--tg-theme-*`
- Нижняя навигация: Каталог | Корзина (с badge) | Заказы | Профиль
- Работает и в TG WebApp, и в браузере (fallback-стили)

### 2.5 HTML-вьюхи (webapp/views.py) и API (webapp/api.py)
HTML (render):
- `catalog_view(request, category_slug=None)`
- `product_detail_view(request, shop_slug, product_slug)`
- `cart_view(request)`
- `orders_view(request)`
- `shop_profile_view(request, shop_slug)`

API (DRF APIView):
- `TelegramAuthView` — POST /api/auth/telegram/
- `CartAddView` — POST /api/cart/add/ (CartItemSerializer)
- `CartRemoveView` — POST /api/cart/remove/
- `CreateInvoiceView` — POST /api/create-invoice/ (валидирует stock, дёргает Telegram createInvoiceLink)

### 2.6 Карточка и страница товара (вопрос 8 — детали отображения)

`includes/product_card.html` (в каталоге):
- картинка (с placeholder при отсутствии), название, краткое описание (обрезка),
  цена в Stars (со значком ⭐), название магазина, бейдж наличия, кнопка «Подробнее».

`product_detail.html` (полноценная страница, чего сейчас нет):
- большое изображение,
- название + название магазина (ссылка на профиль магазина),
- категория,
- **полное описание** (`description`),
- цена в Stars крупно,
- индикатор наличия (`stock`),
- селектор количества,
- кнопка «В корзину» / «Купить»,
- блок «другие товары магазина».

### 2.7 URLs (webapp/urls.py)
```python
urlpatterns = [
    path('', catalog_view, name='catalog'),
    path('category/<slug:category_slug>/', catalog_view, name='catalog_by_category'),
    path('shop/<slug:shop_slug>/', shop_profile_view, name='shop_profile'),
    path('shop/<slug:shop_slug>/<slug:product_slug>/', product_detail_view, name='product_detail'),
    path('cart/', cart_view, name='cart'),
    path('orders/', orders_view, name='orders'),
    # API (DRF)
    path('api/auth/telegram/', TelegramAuthView.as_view()),
    path('api/cart/add/', CartAddView.as_view()),
    path('api/cart/remove/', CartRemoveView.as_view()),
    path('api/create-invoice/', CreateInvoiceView.as_view()),
]
```

### 2.8 Корзина (session-based)
- `request.session['cart']` = `{product_id: quantity}`
- Badge с количеством в навигации
- На оплате — проверка `stock` каждого товара через сериализатор

### 2.9 Static
```
webapp/static/
├── css/webapp.css     # стили поверх Bootstrap, TG-тема, карточки
└── js/webapp.js       # init TG WebApp, тема, AJAX корзина, оплата
```

**Действия:**
- [ ] Удалить main_page.html, shop.js, shop.css
- [ ] serializers.py (ручные Serializer)
- [ ] base.html + Bootstrap + TG SDK
- [ ] catalog.html + product_card.html
- [ ] product_detail.html (полные детали)
- [ ] cart.html, orders.html, shop_profile.html
- [ ] includes/ (navbar, empty_state)
- [ ] HTML-вьюхи + DRF APIView
- [ ] webapp.css + webapp.js
- [ ] urls.py

---

## Фаза 3: Собственная админ-панель (`panel`, Bootstrap)

Своя панель на той же Bootstrap-базе (НЕ копия CoreUI). Цель — базовый функционал магазина и статистика по тому, что есть в БД.

### 3.1 Шаблоны (panel/templates/panel/)
```
panel/templates/panel/
├── base.html          # боковое меню + шапка (Bootstrap)
├── dashboard.html     # KPI + графики
├── products/{list,form}.html
├── orders/{list,detail}.html
├── shops/{list,detail}.html
├── keys/list.html
└── users/list.html
```

### 3.2 Дашборд — статистика (по имеющимся данным)
- Выручка в Stars: сегодня / неделя / месяц / всего (`Order.objects.filter(status...).aggregate(Sum('total_stars'))`)
- Кол-во заказов, товаров, магазинов, пользователей
- Топ-товары по продажам (по `OrderItem`)
- Последние заказы
- График выручки по дням (простой, можно Chart.js с CDN)

### 3.3 Вьюхи (panel/views.py)
- Обычные Django-вьюхи (рендер HTML), защита `@login_required` + проверка доступа.
- CRUD: Product, ProductKey (загрузка ключей textarea — 1 на строку).
- Списки: Orders, Shops, Users (с простыми фильтрами через GET-параметры, без django-filter).

### 3.4 Роли и доступ (без миксинов — простая проверка)
| Роль | Доступ |
|------|--------|
| Superadmin (`is_superuser`) | всё: все магазины, заказы, юзеры, глобальная статистика |
| Owner (ShopMembership role=owner) | только свои магазины: товары/ключи/заказы/статистика |
| Staff (ShopMembership role=staff) | товары/ключи магазинов, где состоит; без удаления магазина |

Фильтрация queryset по магазинам пользователя обычной функцией:
```python
def shops_for(user):
    if user.is_superuser:
        return Shop.objects.all()
    return user.shops.all()
```

### 3.5 URLs (panel/urls.py)
```python
urlpatterns = [
    path('panel/', dashboard_view, name='panel_dashboard'),
    path('panel/products/', product_list_view, name='panel_products'),
    path('panel/products/create/', product_form_view, name='panel_product_create'),
    path('panel/products/<int:pk>/edit/', product_form_view, name='panel_product_edit'),
    path('panel/orders/', order_list_view, name='panel_orders'),
    path('panel/orders/<int:pk>/', order_detail_view, name='panel_order_detail'),
    path('panel/shops/', shop_list_view, name='panel_shops'),
    path('panel/shops/<int:pk>/', shop_detail_view, name='panel_shop_detail'),
    path('panel/keys/', key_list_view, name='panel_keys'),
    path('panel/users/', user_list_view, name='panel_users'),
]
```

**Действия:**
- [ ] panel/base.html (Bootstrap layout: sidebar + header)
- [ ] dashboard.html + агрегации + Chart.js (CDN)
- [ ] CRUD products/keys
- [ ] списки orders/shops/users + простые фильтры
- [ ] проверка доступа (superuser / owner / staff)

---

## Фаза 4: Магазин — регистрация и панель владельца

### 4.1 Создание магазина
- Страница `/create-shop/` — форма (name, description, logo)
- При отправке: `Shop(is_verified=False)` + `ShopMembership(role=owner)`
- Суперадмин верифицирует через панель → товары попадают в каталог

### 4.2 Панель владельца
- Переключатель между своими магазинами
- Товары своего магазина: добавить/редактировать/удалить
- Ключи: textarea (1 на строку)
- Заказы своего магазина
- Статистика: выручка в Stars, кол-во продаж, топ-товары

### 4.3 Сотрудники
- Владелец приглашает по `telegram_username`/id (создаёт ShopMembership role=staff)
- Меняет роли, удаляет сотрудников
- `/panel/shops/<id>/members/`

### 4.4 Баланс магазина
- Для ВКР — отображение суммарной выручки в Stars
- Вывод средств — концепция (Fragment/TON или ручной процесс админа)

**Действия:**
- [ ] форма создания магазина
- [ ] верификация (для суперадмина)
- [ ] panel-вьюхи, фильтрованные по магазину
- [ ] загрузка ключей (textarea)
- [ ] управление сотрудниками

---

## Фаза 5: Прод-деплой

### 5.1 Settings split
```
shopbot/shopbot/settings/
├── __init__.py         # from .base import *; переключение по ENV
├── base.py             # общие настройки
├── development.py      # DEBUG=True
└── production.py       # DEBUG=False, SECURE_*
```

### 5.2 docker-compose.prod.yml
- web: gunicorn, без volume-bind кода, `DJANGO_SETTINGS_MODULE=shopbot.settings.production`
- bot: тот же образ, команда `start_telegram_bot`
- db: postgres с named volume

### 5.3 Старт-команда прод-контейнера web
```yaml
command: >
  sh -c "python manage.py migrate --noinput &&
         python manage.py collectstatic --noinput &&
         gunicorn shopbot.wsgi:application --bind 0.0.0.0:8000 --workers 3"
```

### 5.4 Nginx (хостовой)
- Уже настроен на VPS с Let's Encrypt, `proxy_pass http://127.0.0.1:9000`
- Static и media — отдельные `location` или через Django

**Действия:**
- [ ] settings split base/dev/prod
- [ ] docker-compose.prod.yml
- [ ] прод-команда web (migrate + collectstatic + gunicorn)
- [ ] проверить деплой на VPS

---

## Post-MVP (Фаза 6+)

- [ ] Поиск — PostgreSQL full-text (SearchVector/SearchRank)
- [ ] Пагинация — Django Paginator на каталоге
- [ ] Wishlist — модель Wishlist(user, product)
- [ ] Отзывы — Review(buyer, product, rating, text)
- [ ] Уведомления бота — покупателю при покупке, владельцу при продаже
- [ ] Категории-дерево с иконками в каталоге
- [ ] Рефанды — `refundStarPayment` по telegram_payment_charge_id
- [ ] Промокоды

---

## Чеклист реализации

| # | Фаза | Задача | Статус |
|---|------|--------|--------|
| 1 | 0.1 | TelegramUser в webapp + AUTH_USER_MODEL | [x] |
| 2 | 0.2 | Создать app panel | [x] |
| 3 | 0.3 | settings: INSTALLED_APPS (+rest_framework, panel) | [x] |
| 4 | 0.4 | requirements (+DRF) | [x] |
| 5 | 0.5 | сброс миграций и БД | [x] |
| 6 | 1.1 | модели webapp (Shop, Product, Order...) | [x] |
| 7 | 1.2 | Telegram Stars оплата (bot) | [x] |
| 8 | 1.3 | Telegram auth initData (HMAC) + APIView | [x] |
| 9 | 2.2 | сериализаторы (ручные Serializer) | [x] |
| 10 | 2.3-2.4 | base.html + Bootstrap + TG SDK | [x] |
| 11 | 2.5-2.6 | catalog + product_detail (полные карточки) | [x] |
| 12 | 2.8 | cart (session) + API | [x] |
| 13 | 2.x | orders + shop_profile | [x] |
| 14 | 2.9 | webapp.css + webapp.js | [x] |
| 15 | 3.1-3.2 | panel base + dashboard (статистика) | [x] |
| 16 | 3.3 | panel CRUD products/keys | [x] |
| 17 | 3.4 | panel роли и доступ | [x] |
| 18 | 4.1-4.2 | создание магазина + панель владельца | [ ] |
| 19 | 4.3 | управление сотрудниками | [ ] |
| 20 | 5 | settings split + прод-compose + деплой | [ ] |

---

## Диаграмма моделей

```
webapp.TelegramUser
    ├── ShopMembership (role: owner/staff) ── Shop
    │                                           ├── Product ── ProductKey
    │                                           │       └── Category (FK)
    │                                           └── OrderItem.shop (денормализация)
    └── Order (buyer)
            └── OrderItem
                ├── Product (FK)
                └── ProductKey (order_item FK)
```
