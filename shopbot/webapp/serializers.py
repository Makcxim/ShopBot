from rest_framework import serializers


class TelegramUserSerializer(serializers.Serializer):
    """Сериализатор пользователя (обычный Serializer, не ModelSerializer)."""

    id = serializers.IntegerField(read_only=True)
    telegram_id = serializers.IntegerField()
    telegram_username = serializers.CharField(allow_blank=True)
    avatar_url = serializers.CharField(allow_blank=True)


class ProductSerializer(serializers.Serializer):
    """Товар для каталога/корзины."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    short_description = serializers.CharField(allow_blank=True)
    description = serializers.CharField(allow_blank=True)
    price_stars = serializers.IntegerField()
    image = serializers.SerializerMethodField()
    stock = serializers.IntegerField()
    shop_id = serializers.IntegerField(source='shop.id')
    shop_name = serializers.CharField(source='shop.name')

    def get_image(self, obj):
        return obj.image.url if obj.image else ''


class CartItemSerializer(serializers.Serializer):
    """Позиция, добавляемая/удаляемая из корзины."""

    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
