"""Корзина на основе сессии: {product_id(str): quantity(int)}."""
from .models import Product

CART_SESSION_KEY = 'cart'


def get_cart(session) -> dict:
    return session.get(CART_SESSION_KEY, {})


def save_cart(session, cart: dict):
    session[CART_SESSION_KEY] = cart
    session.modified = True


def add_to_cart(session, product_id: int, quantity: int = 1):
    cart = get_cart(session)
    pid = str(product_id)
    cart[pid] = cart.get(pid, 0) + quantity
    if cart[pid] < 1:
        cart.pop(pid, None)
    save_cart(session, cart)
    return cart


def set_quantity(session, product_id: int, quantity: int):
    cart = get_cart(session)
    pid = str(product_id)
    if quantity < 1:
        cart.pop(pid, None)
    else:
        cart[pid] = quantity
    save_cart(session, cart)
    return cart


def remove_from_cart(session, product_id: int):
    cart = get_cart(session)
    cart.pop(str(product_id), None)
    save_cart(session, cart)
    return cart


def cart_count(session) -> int:
    """Суммарное количество единиц товара в корзине."""
    return sum(get_cart(session).values())


def cart_items(session):
    """Возвращает список позиций корзины с подгруженными товарами и суммами."""
    cart = get_cart(session)
    if not cart:
        return [], 0
    products = Product.objects.filter(id__in=cart.keys()).select_related('shop')
    items = []
    total = 0
    for product in products:
        quantity = cart.get(str(product.id), 0)
        subtotal = product.price_stars * quantity
        total += subtotal
        items.append({'product': product, 'quantity': quantity, 'subtotal': subtotal})
    return items, total
