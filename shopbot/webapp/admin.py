from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from .models import (
    Category,
    Order,
    OrderItem,
    Product,
    ProductKey,
    Shop,
    ShopMembership,
    TelegramUser,
)


@admin.register(TelegramUser)
class TelegramUserAdmin(UserAdmin):
    list_display = ('username', 'telegram_id', 'telegram_username', 'is_staff', 'is_superuser')
    search_fields = ('username', 'telegram_id', 'telegram_username')
    fieldsets = UserAdmin.fieldsets + (
        ('Telegram', {'fields': ('telegram_id', 'telegram_username', 'avatar_url')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Telegram', {'fields': ('telegram_id', 'telegram_username', 'avatar_url')}),
    )


class ShopMembershipInline(admin.TabularInline):
    model = ShopMembership
    extra = 1


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_verified', 'is_active', 'created_at')
    list_filter = ('is_verified', 'is_active')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ShopMembershipInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent', 'sort_order')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


class ProductKeyInline(admin.TabularInline):
    model = ProductKey
    extra = 0
    readonly_fields = ('is_sold', 'sold_at', 'order_item', 'created_at')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'shop', 'category', 'price_stars', 'stock', 'is_active', 'created_at')
    list_filter = ('is_active', 'shop', 'category')
    search_fields = ('name', 'slug', 'description', 'short_description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('stock', 'image_tag', 'created_at', 'updated_at')
    inlines = [ProductKeyInline]

    def image_tag(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width:200px; max-height:200px"/>', obj.image.url)
        return '—'
    image_tag.short_description = 'Изображение'


@admin.register(ProductKey)
class ProductKeyAdmin(admin.ModelAdmin):
    list_display = ('product', 'key', 'is_sold', 'sold_at', 'created_at')
    list_filter = ('is_sold', 'created_at')
    search_fields = ('product__name', 'key')
    readonly_fields = ('sold_at', 'order_item', 'created_at')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'shop', 'quantity', 'price_stars', 'delivered_keys')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'buyer', 'status', 'total_stars', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('buyer__username', 'buyer__telegram_id', 'telegram_payment_charge_id')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [OrderItemInline]
