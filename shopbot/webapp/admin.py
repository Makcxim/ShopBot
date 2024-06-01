from django.contrib import admin
from django.utils.html import format_html

from .models import ShopOrder, ShopProduct, ShopProductKey


class ShopProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'short_description', 'remain', 'created_at', 'updated_at',)
    search_fields = ('name', 'short_description', 'admin_comment',)
    readonly_fields = ('remain', 'image_tag', 'created_at', 'updated_at',)
    list_filter = ('created_at',) 
    exclude = ('image_small',)

    def image_tag(self, obj):
        return format_html('<img src="{}" style="max-width:200px; max-height:200px"/>'.format(obj.image_original.url))
    image_tag.short_description = 'Изображение'


class ShopProductKeyAdmin(admin.ModelAdmin):
    list_display = ('product', 'key', 'is_sold', 'created_at', 'updated_at',)
    search_fields = ('product__name', 'key',)
    list_filter = ('created_at', 'updated_at', 'is_sold',) 
    readonly_fields = ('created_at', 'updated_at',)


class ShopOrderAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'product', 'count', 'total_price', 'created_at',)
    search_fields = ('user__username', 'product__name',)
    list_filter = ('created_at', 'total_price',) 
    readonly_fields = ('created_at',)


admin.site.register(ShopProduct, ShopProductAdmin)
admin.site.register(ShopProductKey, ShopProductKeyAdmin)
admin.site.register(ShopOrder, ShopOrderAdmin)
