from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie

from . import cart as cart_utils
from .models import Category, Order, Product, Shop


def _base_context(request):
    """Общий контекст для всех страниц витрины."""
    return {'cart_count': cart_utils.cart_count(request.session)}


@ensure_csrf_cookie
def catalog_view(request, category_slug=None):
    """Каталог товаров с опциональным фильтром по категории."""
    products = (
        Product.objects.filter(is_active=True, shop__is_active=True)
        .select_related('shop', 'category')
    )
    current_category = None
    if category_slug:
        current_category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=current_category)

    context = _base_context(request)
    context.update({
        'products': products,
        'categories': Category.objects.all(),
        'current_category': current_category,
    })
    return render(request, 'catalog.html', context)


@ensure_csrf_cookie
def product_detail_view(request, shop_slug, product_slug):
    """Страница товара с полным описанием."""
    product = get_object_or_404(
        Product.objects.select_related('shop', 'category'),
        shop__slug=shop_slug, slug=product_slug, is_active=True,
    )
    other_products = (
        Product.objects.filter(shop=product.shop, is_active=True)
        .exclude(id=product.id)[:6]
    )
    context = _base_context(request)
    context.update({'product': product, 'other_products': other_products})
    return render(request, 'product_detail.html', context)


@ensure_csrf_cookie
def cart_view(request):
    """Корзина перед оплатой."""
    items, total = cart_utils.cart_items(request.session)
    context = _base_context(request)
    context.update({'items': items, 'total': total})
    return render(request, 'cart.html', context)


@ensure_csrf_cookie
def orders_view(request):
    """История заказов текущего пользователя."""
    orders = []
    if request.user.is_authenticated:
        orders = (
            Order.objects.filter(buyer=request.user)
            .prefetch_related('items__product')
        )
    context = _base_context(request)
    context.update({'orders': orders})
    return render(request, 'orders.html', context)


@ensure_csrf_cookie
def shop_profile_view(request, shop_slug):
    """Страница магазина: описание + его товары."""
    shop = get_object_or_404(Shop, slug=shop_slug, is_active=True)
    products = Product.objects.filter(shop=shop, is_active=True).select_related('category')
    context = _base_context(request)
    context.update({'shop': shop, 'products': products})
    return render(request, 'shop_profile.html', context)
