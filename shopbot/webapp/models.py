from django.db import models


class ShopProduct(models.Model):
    name = models.CharField(verbose_name='Название', max_length=100)
    price = models.DecimalField(verbose_name='Цена', max_digits=10, decimal_places=2)
    short_description = models.TextField(verbose_name='Краткое описание', max_length=30, blank=True)
    admin_comment = models.TextField(verbose_name='Комментарий админа', max_length=300, blank=True)
    image_original = models.ImageField(verbose_name='Изображение', upload_to='products/original', null=True, blank=True)
    remain = models.IntegerField(verbose_name='Остаток', default=0)
    created_at = models.DateTimeField(verbose_name='Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='Дата обновления', auto_now=True)

    def __str__(self):
        return self.name


class ShopProductKey(models.Model):
    product = models.ForeignKey(ShopProduct, verbose_name='Игра', on_delete=models.CASCADE)
    key = models.CharField(verbose_name='Ключ', max_length=255)
    is_sold = models.BooleanField(verbose_name='Продан', default=False)
    created_at = models.DateTimeField(verbose_name='Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='Дата обновления', auto_now=True)

    def __str__(self):
        return f"{self.product.name} {self.key}"


class ShopOrder(models.Model):
    telegram_id = models.IntegerField(verbose_name='ID Telegram')
    product = models.ForeignKey(ShopProduct, verbose_name='Игра', on_delete=models.CASCADE)
    count = models.IntegerField(verbose_name='Количество', default=1)
    total_price = models.DecimalField(verbose_name='Общая цена', max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(verbose_name='Дата создания', auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} {self.telegram_id}"


