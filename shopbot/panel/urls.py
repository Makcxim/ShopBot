from django.urls import path

from . import views

urlpatterns = [
    path('panel/', views.dashboard_view, name='panel_dashboard'),
    path('panel/products/', views.product_list_view, name='panel_products'),
    path('panel/products/create/', views.product_create_view, name='panel_product_create'),
    path('panel/products/<int:pk>/edit/', views.product_edit_view, name='panel_product_edit'),
    path('panel/products/<int:pk>/delete/', views.product_delete_view, name='panel_product_delete'),
    path('panel/products/<int:pk>/keys/', views.product_keys_view, name='panel_product_keys'),
    path('panel/orders/', views.order_list_view, name='panel_orders'),
    path('panel/orders/<int:pk>/', views.order_detail_view, name='panel_order_detail'),
    path('panel/shops/', views.shop_list_view, name='panel_shops'),
    path('panel/shops/<int:pk>/', views.shop_detail_view, name='panel_shop_detail'),
    path('panel/users/', views.user_list_view, name='panel_users'),
]
