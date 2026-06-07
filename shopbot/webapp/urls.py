from decouple import config
from django.urls import path

from . import views
from .api import (
    CartAddView,
    CartClearView,
    CartRemoveView,
    CreateInvoiceView,
    TelegramAuthView,
)

# Точка входа WebApp (бот открывает APP_BASE_URL/MAIN_PAGE_URL)
MAIN_PAGE_URL = config('MAIN_PAGE_URL', default='main_page')

urlpatterns = [
    path('', views.catalog_view, name='catalog'),
    path(MAIN_PAGE_URL, views.catalog_view, name='main_page'),
    path('category/<slug:category_slug>/', views.catalog_view, name='catalog_by_category'),
    path('cart/', views.cart_view, name='cart'),
    path('orders/', views.orders_view, name='orders'),
    path('shop/<slug:shop_slug>/', views.shop_profile_view, name='shop_profile'),
    path('shop/<slug:shop_slug>/<slug:product_slug>/', views.product_detail_view, name='product_detail'),
    # API (DRF)
    path('api/auth/telegram/', TelegramAuthView.as_view(), name='telegram_auth'),
    path('api/cart/add/', CartAddView.as_view(), name='cart_add'),
    path('api/cart/remove/', CartRemoveView.as_view(), name='cart_remove'),
    path('api/cart/clear/', CartClearView.as_view(), name='cart_clear'),
    path('api/create-invoice/', CreateInvoiceView.as_view(), name='create_invoice'),
]
