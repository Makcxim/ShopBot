from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie

from . import cart as cart_utils
from .models import Category, Order, Product, Shop, SupportTicket

# Допустимые варианты сортировки каталога: ключ из ?sort= -> поле ORM
SORT_OPTIONS = {
    'new': '-created_at',
    'price_asc': 'price_stars',
    'price_desc': '-price_stars',
}
PAGE_SIZE = 12


def _base_context(request):
    """Общий контекст для всех страниц витрины."""
    return {'cart_count': cart_utils.cart_count(request.session)}


@ensure_csrf_cookie
def catalog_view(request, category_slug=None):
    """Каталог: фильтр по категории, поиск, сортировка, пагинация."""
    products = (
        Product.objects.filter(is_active=True, shop__is_active=True)
        .select_related('shop', 'category')
    )

    current_category = None
    if category_slug:
        current_category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=current_category)

    query = request.GET.get('q', '').strip()
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(short_description__icontains=query)
            | Q(description__icontains=query)
        )

    sort = request.GET.get('sort', 'new')
    products = products.order_by(SORT_OPTIONS.get(sort, '-created_at'))

    paginator = Paginator(products, PAGE_SIZE)
    page = paginator.get_page(request.GET.get('page'))

    # Параметры запроса (q/sort/...) для подгрузки следующих страниц, без page
    extra_params = request.GET.copy()
    extra_params.pop('page', None)
    extra_params.pop('partial', None)

    context = _base_context(request)
    context.update({
        'products': page.object_list,
        'page_obj': page,
        'categories': Category.objects.all(),
        'current_category': current_category,
        'query': query,
        'sort': sort,
        'extra_params': extra_params.urlencode(),
    })

    # AJAX-подгрузка следующей страницы: отдаём только карточки + мета
    if request.GET.get('partial'):
        return render(request, 'includes/_catalog_page.html', context)
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


def privacy_view(request):
    """Политика конфиденциальности (URL для BotFather)."""
    return render(request, 'privacy.html', _base_context(request))


@ensure_csrf_cookie
def support_view(request):
    """Список обращений пользователя + форма нового обращения."""
    tickets = []
    if request.user.is_authenticated:
        tickets = (
            request.user.support_tickets.prefetch_related('messages')
            .order_by('-updated_at')
        )
    context = _base_context(request)
    context.update({'tickets': tickets})
    return render(request, 'support.html', context)


@ensure_csrf_cookie
def support_thread_view(request, pk):
    """Переписка по конкретному обращению + добавление сообщения."""
    if not request.user.is_authenticated:
        return render(request, 'support_thread.html', _base_context(request))
    ticket = get_object_or_404(
        SupportTicket.objects.prefetch_related('messages'),
        pk=pk, user=request.user,
    )
    context = _base_context(request)
    context.update({'ticket': ticket})
    return render(request, 'support_thread.html', context)


@ensure_csrf_cookie
def profile_view(request):
    """Профиль пользователя: вход в панель продавца или регистрация магазина."""
    context = _base_context(request)
    if request.user.is_authenticated:
        shops = request.user.shops.all()
        context.update({
            'shops': shops,
            'has_panel_access': request.user.is_superuser or shops.exists(),
        })
    return render(request, 'profile.html', context)


@ensure_csrf_cookie
def shop_profile_view(request, shop_slug):
    """Страница магазина: описание + его товары."""
    shop = get_object_or_404(Shop, slug=shop_slug, is_active=True)
    products = Product.objects.filter(shop=shop, is_active=True).select_related('category')
    context = _base_context(request)
    context.update({'shop': shop, 'products': products})
    return render(request, 'shop_profile.html', context)
