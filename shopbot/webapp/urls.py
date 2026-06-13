from decouple import config
from django.urls import path

from . import views
from .api import (
    CartAddView,
    CartClearView,
    CartRemoveView,
    CartSetView,
    CreateInvoiceView,
    RefundOrderView,
    SupportMessageView,
    SupportTicketsView,
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
    path('privacy/', views.privacy_view, name='privacy'),
    path('support/', views.support_view, name='support'),
    path('support/<int:pk>/', views.support_thread_view, name='support_thread'),
    path('profile/', views.profile_view, name='profile'),
    path('shop/<slug:shop_slug>/', views.shop_profile_view, name='shop_profile'),
    path('shop/<slug:shop_slug>/<slug:product_slug>/', views.product_detail_view, name='product_detail'),
    # API (DRF)
    path('api/auth/telegram/', TelegramAuthView.as_view(), name='telegram_auth'),
    path('api/cart/add/', CartAddView.as_view(), name='cart_add'),
    path('api/cart/remove/', CartRemoveView.as_view(), name='cart_remove'),
    path('api/cart/set/', CartSetView.as_view(), name='cart_set'),
    path('api/cart/clear/', CartClearView.as_view(), name='cart_clear'),
    path('api/create-invoice/', CreateInvoiceView.as_view(), name='create_invoice'),
    path('api/orders/<int:pk>/refund/', RefundOrderView.as_view(), name='order_refund'),
    path('api/support/tickets/', SupportTicketsView.as_view(), name='support_tickets'),
    path('api/support/tickets/<int:pk>/messages/', SupportMessageView.as_view(), name='support_messages'),
]
