(function () {
    'use strict';

    const tg = window.Telegram ? window.Telegram.WebApp : null;

    // ===== Инициализация Telegram WebApp =====
    function initTelegram() {
        if (!tg) return;
        tg.ready();
        tg.expand();
        applyTheme();
        tg.onEvent('themeChanged', applyTheme);
        authenticate();
    }

    function applyTheme() {
        if (!tg) return;
        const scheme = tg.colorScheme || 'light';
        document.documentElement.style.colorScheme = scheme;
        // Telegram сам прокидывает CSS-переменные --tg-theme-*, дублируем на случай старых клиентов
        const params = tg.themeParams || {};
        const map = {
            'bg_color': '--tg-theme-bg-color',
            'text_color': '--tg-theme-text-color',
            'hint_color': '--tg-theme-hint-color',
            'link_color': '--tg-theme-link-color',
            'button_color': '--tg-theme-button-color',
            'button_text_color': '--tg-theme-button-text-color',
            'secondary_bg_color': '--tg-theme-secondary-bg-color'
        };
        for (const key in map) {
            if (params[key]) document.documentElement.style.setProperty(map[key], params[key]);
        }
    }

    function authenticate() {
        if (!tg || !tg.initData) return;
        post('/api/auth/telegram/', { init_data: tg.initData }).catch(function () {});
    }

    // ===== Утилиты =====
    function csrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    function post(url, body) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
            body: JSON.stringify(body || {})
        }).then(function (r) {
            return r.json().then(function (data) {
                if (!r.ok) throw data;
                return data;
            });
        });
    }

    function updateCartBadge(count) {
        const badge = document.getElementById('cart-badge');
        if (!badge) return;
        badge.textContent = count;
        badge.classList.toggle('d-none', !count);
    }

    function toast(message) {
        if (tg && tg.showPopup) {
            tg.showPopup({ message: message });
        } else if (tg && tg.showAlert) {
            tg.showAlert(message);
        } else {
            alert(message);
        }
    }

    // ===== Количество на странице товара =====
    function initQtyControl() {
        const control = document.querySelector('.qty-control');
        if (!control) return;
        const valueEl = document.getElementById('qty-value');
        const max = parseInt(control.dataset.max || '99', 10);
        control.addEventListener('click', function (e) {
            const btn = e.target.closest('.qty-control__btn');
            if (!btn) return;
            let value = parseInt(valueEl.textContent, 10);
            value += btn.dataset.action === 'inc' ? 1 : -1;
            value = Math.max(1, Math.min(max, value));
            valueEl.textContent = value;
        });
    }

    // ===== Добавление в корзину =====
    function initAddToCart() {
        const btn = document.getElementById('add-to-cart-btn');
        if (!btn) return;
        btn.addEventListener('click', function () {
            const productId = parseInt(btn.dataset.productId, 10);
            const valueEl = document.getElementById('qty-value');
            const quantity = valueEl ? parseInt(valueEl.textContent, 10) : 1;
            post('/api/cart/add/', { product_id: productId, quantity: quantity })
                .then(function (data) {
                    updateCartBadge(data.cart_count);
                    toast('Добавлено в корзину');
                })
                .catch(function () { toast('Не удалось добавить'); });
        });
    }

    // ===== Удаление из корзины =====
    function initCartRemove() {
        document.querySelectorAll('.cart-item__remove').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const productId = parseInt(btn.dataset.productId, 10);
                post('/api/cart/remove/', { product_id: productId })
                    .then(function (data) {
                        updateCartBadge(data.cart_count);
                        const item = btn.closest('.cart-item');
                        if (item) item.remove();
                        if (!document.querySelector('.cart-item')) location.reload();
                    })
                    .catch(function () { toast('Ошибка'); });
            });
        });
    }

    // ===== Оплата (Telegram Stars) =====
    function initCheckout() {
        const btn = document.getElementById('checkout-btn');
        if (!btn) return;
        btn.addEventListener('click', function () {
            btn.disabled = true;
            post('/api/create-invoice/', {})
                .then(function (data) {
                    if (!data.invoice_link) throw data;
                    if (tg && tg.openInvoice) {
                        tg.openInvoice(data.invoice_link, function (status) {
                            if (status === 'paid') {
                                post('/api/cart/clear/', {}).finally(function () {
                                    window.location.href = '/orders/';
                                });
                            } else {
                                btn.disabled = false;
                            }
                        });
                    } else {
                        // Браузер без Telegram — просто открываем ссылку
                        window.open(data.invoice_link, '_blank');
                        btn.disabled = false;
                    }
                })
                .catch(function (err) {
                    toast((err && err.detail) ? err.detail : 'Не удалось оформить заказ');
                    btn.disabled = false;
                });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initTelegram();
        initQtyControl();
        initAddToCart();
        initCartRemove();
        initCheckout();
    });
})();
