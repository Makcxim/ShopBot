import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, ExpressionWrapper, F, IntegerField, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from webapp.models import (
    Order, OrderItem, Product, ProductKey, Shop, ShopMembership, TelegramUser,
)

from .access import can_manage, is_owner, panel_required, render_forbidden, shops_for
from .forms import (
    KeysUploadForm, MemberAddForm, ProductForm, ShopForm, unique_shop_slug,
)

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

    # Выручка и число заказов за последние 14 дней
    start = timezone.now().date() - timedelta(days=13)
    daily = (
        paid_items.filter(order__created_at__date__gte=start)
        .annotate(day=TruncDate('order__created_at'))
        .values('day')
        .annotate(rev=Sum(REVENUE_EXPR), orders=Count('order', distinct=True))
    )
    rev_by_day = {row['day']: row['rev'] for row in daily}
    ord_by_day = {row['day']: row['orders'] for row in daily}
    labels, data, orders_data = [], [], []
    for i in range(14):
        d = start + timedelta(days=i)
        labels.append(d.strftime('%d.%m'))
        data.append(rev_by_day.get(d, 0))
        orders_data.append(ord_by_day.get(d, 0))

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

    # Выручка по категориям (doughnut)
    by_category = (
        paid_items.values('product__category__name')
        .annotate(rev=Sum(REVENUE_EXPR))
        .order_by('-rev')[:8]
    )
    cat_labels = [r['product__category__name'] or 'Без категории' for r in by_category]
    cat_data = [r['rev'] for r in by_category]

    # Статусы заказов (doughnut)
    status_rows = (
        Order.objects.filter(items__shop__in=shops)
        .values('status')
        .annotate(c=Count('id', distinct=True))
    )
    status_map = dict(Order.Status.choices)
    status_labels = [status_map.get(r['status'], r['status']) for r in status_rows]
    status_data = [r['c'] for r in status_rows]

    # Выручка по магазинам (для супер-админа — распределение по всем магазинам)
    shop_labels, shop_data = [], []
    if user.is_superuser:
        by_shop = (
            paid_items.values('shop__name')
            .annotate(rev=Sum(REVENUE_EXPR))
            .order_by('-rev')[:8]
        )
        shop_labels = [r['shop__name'] for r in by_shop]
        shop_data = [r['rev'] for r in by_shop]

    context = {
        'active': 'dashboard',
        'revenue': _revenue(paid_items),
        'orders_count': Order.objects.filter(items__shop__in=shops, status__in=PAID).distinct().count(),
        'products_count': Product.objects.filter(shop__in=shops).count(),
        'shops_count': shops.count(),
        'keys_available': ProductKey.objects.filter(product__shop__in=shops, is_sold=False).count(),
        'keys_sold': ProductKey.objects.filter(product__shop__in=shops, is_sold=True).count(),
        'users_count': TelegramUser.objects.count() if user.is_superuser else None,
        'top_products': top_products,
        'recent_orders': recent_orders,
        'chart_labels': json.dumps(labels),
        'chart_data': json.dumps(data),
        'orders_chart_data': json.dumps(orders_data),
        'cat_labels': json.dumps(cat_labels),
        'cat_data': json.dumps(cat_data),
        'status_labels': json.dumps(status_labels),
        'status_data': json.dumps(status_data),
        'shop_labels': json.dumps(shop_labels),
        'shop_data': json.dumps(shop_data),
        'is_super': user.is_superuser,
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
        return render_forbidden(request, 'Доступно только супер-админу')
    users = TelegramUser.objects.order_by('-date_joined')
    return render(request, 'panel/users/list.html', {'active': 'users', 'users': users})


@login_required
def shop_create_view(request):
    """Создание магазина — доступно любому авторизованному пользователю."""
    form = ShopForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        shop = form.save(commit=False)
        shop.slug = unique_shop_slug(shop.name)
        shop.is_verified = False
        shop.save()
        ShopMembership.objects.create(
            user=request.user, shop=shop, role=ShopMembership.Role.OWNER
        )
        return redirect('panel_shop_detail', pk=shop.pk)
    return render(request, 'panel/shops/form.html', {'active': 'shops', 'form': form})


@panel_required
def shop_verify_view(request, pk):
    """Верификация магазина — только супер-админ."""
    if not request.user.is_superuser:
        return render_forbidden(request, 'Доступно только супер-админу')
    shop = get_object_or_404(Shop, pk=pk)
    if request.method == 'POST':
        shop.is_verified = not shop.is_verified
        shop.save(update_fields=['is_verified'])
    return redirect('panel_shop_detail', pk=shop.pk)


@panel_required
def shop_members_view(request, pk):
    """Управление сотрудниками — владелец или супер-админ."""
    shop = get_object_or_404(shops_for(request.user), pk=pk)
    if not can_manage(request.user, shop):
        return render_forbidden(request, 'Только владелец магазина может управлять сотрудниками')

    form = MemberAddForm(request.POST or None)
    error = None
    if request.method == 'POST' and form.is_valid():
        identifier = form.cleaned_data['identifier'].strip().lstrip('@')
        if identifier.isdigit():
            user = TelegramUser.objects.filter(telegram_id=int(identifier)).first()
        else:
            user = TelegramUser.objects.filter(telegram_username__iexact=identifier).first()
        if not user:
            error = 'Пользователь не найден'
        else:
            ShopMembership.objects.update_or_create(
                user=user, shop=shop,
                defaults={'role': form.cleaned_data['role']},
            )
            return redirect('panel_shop_members', pk=shop.pk)

    return render(request, 'panel/shops/members.html', {
        'active': 'shops', 'shop': shop, 'form': form, 'error': error,
        'members': shop.memberships.select_related('user'),
    })


@panel_required
def member_remove_view(request, pk, membership_id):
    """Удаление сотрудника из магазина."""
    shop = get_object_or_404(shops_for(request.user), pk=pk)
    if not can_manage(request.user, shop):
        return render_forbidden(request, 'Только владелец магазина может управлять сотрудниками')
    if request.method == 'POST':
        ShopMembership.objects.filter(
            id=membership_id, shop=shop, role=ShopMembership.Role.STAFF
        ).delete()
    return redirect('panel_shop_members', pk=shop.pk)
