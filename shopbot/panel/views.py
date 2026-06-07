import json
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db.models import Count, ExpressionWrapper, F, IntegerField, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from webapp.models import Order, OrderItem, Product, ProductKey, Shop, TelegramUser

from .access import is_owner, panel_required, shops_for
from .forms import KeysUploadForm, ProductForm

PAID = [Order.Status.PAID, Order.Status.DELIVERED]
REVENUE_EXPR = ExpressionWrapper(
    F('price_stars') * F('quantity'), output_field=IntegerField()
)


def _revenue(items_qs):
    return items_qs.aggregate(total=Sum(REVENUE_EXPR))['total'] or 0


@panel_required
def dashboard_view(request):
    user = request.user
    shops = shops_for(user)
    paid_items = OrderItem.objects.filter(shop__in=shops, order__status__in=PAID)

    # График выручки за последние 14 дней
    start = timezone.now().date() - timedelta(days=13)
    daily = (
        paid_items.filter(order__created_at__date__gte=start)
        .annotate(day=TruncDate('order__created_at'))
        .values('day')
        .annotate(rev=Sum(REVENUE_EXPR))
    )
    by_day = {row['day']: row['rev'] for row in daily}
    labels, data = [], []
    for i in range(14):
        d = start + timedelta(days=i)
        labels.append(d.strftime('%d.%m'))
        data.append(by_day.get(d, 0))

    top_products = (
        paid_items.values('product__name')
        .annotate(qty=Sum('quantity'), revenue=Sum(REVENUE_EXPR))
        .order_by('-qty')[:5]
    )
    recent_orders = (
        Order.objects.filter(items__shop__in=shops)
        .distinct()
        .order_by('-created_at')[:10]
    )

    context = {
        'active': 'dashboard',
        'revenue': _revenue(paid_items),
        'orders_count': Order.objects.filter(items__shop__in=shops, status__in=PAID).distinct().count(),
        'products_count': Product.objects.filter(shop__in=shops).count(),
        'shops_count': shops.count(),
        'keys_available': ProductKey.objects.filter(product__shop__in=shops, is_sold=False).count(),
        'users_count': TelegramUser.objects.count() if user.is_superuser else None,
        'top_products': top_products,
        'recent_orders': recent_orders,
        'chart_labels': json.dumps(labels),
        'chart_data': json.dumps(data),
    }
    return render(request, 'panel/dashboard.html', context)


@panel_required
def product_list_view(request):
    shops = shops_for(request.user)
    products = (
        Product.objects.filter(shop__in=shops)
        .select_related('shop', 'category')
        .order_by('-created_at')
    )
    shop_id = request.GET.get('shop')
    if shop_id:
        products = products.filter(shop_id=shop_id)
    return render(request, 'panel/products/list.html', {
        'active': 'products', 'products': products, 'shops': shops,
        'current_shop': shop_id,
    })


@panel_required
def product_create_view(request):
    shops = shops_for(request.user)
    form = ProductForm(request.POST or None, request.FILES or None, shops=shops)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('panel_products')
    return render(request, 'panel/products/form.html', {
        'active': 'products', 'form': form, 'is_create': True,
    })


@panel_required
def product_edit_view(request, pk):
    shops = shops_for(request.user)
    product = get_object_or_404(Product, pk=pk, shop__in=shops)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product, shops=shops)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('panel_products')
    return render(request, 'panel/products/form.html', {
        'active': 'products', 'form': form, 'product': product, 'is_create': False,
    })


@panel_required
def product_delete_view(request, pk):
    shops = shops_for(request.user)
    product = get_object_or_404(Product, pk=pk, shop__in=shops)
    if request.method == 'POST':
        product.delete()
    return redirect('panel_products')


@panel_required
def product_keys_view(request, pk):
    shops = shops_for(request.user)
    product = get_object_or_404(Product, pk=pk, shop__in=shops)
    form = KeysUploadForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        created = [ProductKey(product=product, key=k) for k in form.cleaned_keys()]
        ProductKey.objects.bulk_create(created)
        return redirect('panel_product_keys', pk=product.pk)
    keys = product.keys.order_by('is_sold', '-created_at')
    return render(request, 'panel/keys/list.html', {
        'active': 'products', 'product': product, 'keys': keys, 'form': form,
    })


@panel_required
def order_list_view(request):
    shops = shops_for(request.user)
    orders = (
        Order.objects.filter(items__shop__in=shops)
        .distinct()
        .select_related('buyer')
        .order_by('-created_at')
    )
    status = request.GET.get('status')
    if status:
        orders = orders.filter(status=status)
    return render(request, 'panel/orders/list.html', {
        'active': 'orders', 'orders': orders,
        'statuses': Order.Status.choices, 'current_status': status,
    })


@panel_required
def order_detail_view(request, pk):
    shops = shops_for(request.user)
    order = get_object_or_404(
        Order.objects.filter(items__shop__in=shops).distinct(), pk=pk
    )
    # Сотрудник/владелец видит только позиции своих магазинов; суперадмин — все
    items = order.items.select_related('product', 'shop')
    if not request.user.is_superuser:
        items = items.filter(shop__in=shops)
    return render(request, 'panel/orders/detail.html', {
        'active': 'orders', 'order': order, 'items': items,
    })


@panel_required
def shop_list_view(request):
    shops = shops_for(request.user).annotate(products_count=Count('products'))
    return render(request, 'panel/shops/list.html', {'active': 'shops', 'shops': shops})


@panel_required
def shop_detail_view(request, pk):
    shops = shops_for(request.user)
    shop = get_object_or_404(shops, pk=pk)
    paid_items = OrderItem.objects.filter(shop=shop, order__status__in=PAID)
    context = {
        'active': 'shops',
        'shop': shop,
        'is_owner': is_owner(request.user, shop),
        'revenue': _revenue(paid_items),
        'products_count': shop.products.count(),
        'orders_count': Order.objects.filter(items__shop=shop, status__in=PAID).distinct().count(),
        'keys_available': ProductKey.objects.filter(product__shop=shop, is_sold=False).count(),
        'members': shop.memberships.select_related('user'),
    }
    return render(request, 'panel/shops/detail.html', context)


@panel_required
def user_list_view(request):
    if not request.user.is_superuser:
        raise PermissionDenied('Только для супер-админа')
    users = TelegramUser.objects.order_by('-date_joined')
    return render(request, 'panel/users/list.html', {'active': 'users', 'users': users})
