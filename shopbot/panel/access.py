"""Контроль доступа к панели.

- Супер-админ (is_superuser) видит всё.
- Владелец/сотрудник магазина видит только свои магазины и связанные данные.
"""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render

from webapp.models import Shop


def render_forbidden(request, message='Недостаточно прав для этого действия'):
    """Дружелюбная страница 403 с навигацией (вместо голого Forbidden)."""
    has_access = request.user.is_authenticated and (
        request.user.is_superuser or request.user.shop_memberships.exists()
    )
    return render(request, 'panel/forbidden.html',
                  {'message': message, 'has_access': has_access}, status=403)


def shops_for(user):
    """Магазины, доступные пользователю."""
    if user.is_superuser:
        return Shop.objects.all()
    return Shop.objects.filter(memberships__user=user).distinct()


def has_panel_access(user):
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.shop_memberships.exists()


def is_owner(user, shop):
    """Владелец магазина (или суперадмин)."""
    if user.is_superuser:
        return True
    return shop.memberships.filter(
        user=user, role='owner'
    ).exists()


def can_manage(user, shop):
    """Может управлять магазином (владелец или суперадмин)."""
    return is_owner(user, shop)


def panel_required(view_func):
    """Требует вход + доступ к панели (суперадмин или участник магазина)."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not has_panel_access(request.user):
            return render_forbidden(
                request,
                'У вас пока нет магазина. Создайте его, чтобы пользоваться панелью.',
            )
        return view_func(request, *args, **kwargs)

    return wrapper
