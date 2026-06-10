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

    function haptic(type) {
        if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred(type || 'light');
    }

    function isRootPage() {
        const p = window.location.pathname;
        return p === '/' || p === '/main_page' || p.indexOf('/category/') === 0;
    }

    // ===== Кнопка «Назад» (нативная в Telegram, fallback в браузере) =====
    function initBack() {
        const root = isRootPage();
        const goBack = function () {
            if (window.history.length > 1) window.history.back();
            else window.location.href = '/';
        };
        if (tg && tg.BackButton) {
            if (root) {
                tg.BackButton.hide();
            } else {
                tg.BackButton.show();
                tg.BackButton.onClick(goBack);
            }
        } else {
            // Браузер без Telegram
            const link = document.getElementById('back-link');
            if (link && !root) {
                link.classList.remove('d-none');
                link.addEventListener('click', function (e) { e.preventDefault(); goBack(); });
            }
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
        const original = btn.textContent;
        let resetTimer = null;
        btn.addEventListener('click', function () {
            const productId = parseInt(btn.dataset.productId, 10);
            const valueEl = document.getElementById('qty-value');
            const quantity = valueEl ? parseInt(valueEl.textContent, 10) : 1;
            post('/api/cart/add/', { product_id: productId, quantity: quantity })
                .then(function (data) {
                    updateCartBadge(data.cart_count);
                    haptic('medium');
                    // Ненавязчивый отклик прямо на кнопке вместо попапа
                    btn.textContent = '✓ В корзине';
                    btn.classList.add('btn-buy--ok');
                    clearTimeout(resetTimer);
                    resetTimer = setTimeout(function () {
                        btn.textContent = original;
                        btn.classList.remove('btn-buy--ok');
                    }, 1400);
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

    // ===== Изменение количества в корзине =====
    function updateMainButtonText(total) {
        const btn = document.getElementById('checkout-btn');
        if (btn) btn.textContent = 'Оплатить ' + total + ' ⭐';
        if (tg && tg.MainButton) tg.MainButton.setText('Оплатить ' + total + ' ⭐');
    }

    function initCartQty() {
        document.querySelectorAll('.cart-qty').forEach(function (ctrl) {
            const productId = parseInt(ctrl.dataset.productId, 10);
            const max = parseInt(ctrl.dataset.max || '99', 10);
            const valueEl = ctrl.querySelector('.cart-qty__value');
            ctrl.addEventListener('click', function (e) {
                const b = e.target.closest('.cart-qty__btn');
                if (!b) return;
                let q = parseInt(valueEl.textContent, 10) + (b.dataset.action === 'inc' ? 1 : -1);
                q = Math.min(Math.max(q, 0), max);
                post('/api/cart/set/', { product_id: productId, quantity: q })
                    .then(function (data) {
                        updateCartBadge(data.cart_count);
                        if (data.quantity < 1) {
                            location.reload();
                            return;
                        }
                        valueEl.textContent = data.quantity;
                        const row = ctrl.closest('.cart-item');
                        const sub = row && row.querySelector('.cart-item__subtotal');
                        if (sub) sub.textContent = data.subtotal + ' ⭐';
                        const totalEl = document.getElementById('cart-total');
                        if (totalEl) totalEl.textContent = data.total;
                        updateMainButtonText(data.total);
                    })
                    .catch(function () { toast('Ошибка'); });
            });
        });
    }

    // ===== Возврат звёзд по заказу =====
    function initRefund() {
        document.querySelectorAll('.order-refund-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const orderId = parseInt(btn.dataset.orderId, 10);
                const confirmRefund = function (ok) {
                    if (!ok) return;
                    btn.disabled = true;
                    btn.textContent = 'Возврат…';
                    post('/api/orders/' + orderId + '/refund/', {})
                        .then(function () {
                            haptic('medium');
                            toast('Звёзды возвращены');
                            setTimeout(function () { location.reload(); }, 600);
                        })
                        .catch(function (err) {
                            toast((err && err.detail) ? err.detail : 'Не удалось вернуть');
                            btn.disabled = false;
                            btn.textContent = 'Вернуть звёзды';
                        });
                };
                if (tg && tg.showConfirm) {
                    tg.showConfirm('Вернуть звёзды за этот заказ?', confirmRefund);
                } else {
                    confirmRefund(confirm('Вернуть звёзды за этот заказ?'));
                }
            });
        });
    }

    // ===== Оплата (Telegram Stars) =====
    function doCheckout(onDone) {
        post('/api/create-invoice/', {})
            .then(function (data) {
                if (!data.invoice_link) throw data;
                if (tg && tg.openInvoice) {
                    tg.openInvoice(data.invoice_link, function (status) {
                        if (status === 'paid') {
                            post('/api/cart/clear/', {}).finally(function () {
                                window.location.href = '/orders/';
                            });
                        } else if (onDone) {
                            onDone();
                        }
                    });
                } else {
                    window.open(data.invoice_link, '_blank');
                    if (onDone) onDone();
                }
            })
            .catch(function (err) {
                toast((err && err.detail) ? err.detail : 'Не удалось оформить заказ');
                if (onDone) onDone();
            });
    }

    function initCheckout() {
        const btn = document.getElementById('checkout-btn');
        if (!btn) return;

        // In-page кнопка (видна в браузере и как fallback)
        btn.addEventListener('click', function () {
            btn.disabled = true;
            doCheckout(function () { btn.disabled = false; });
        });

        // Нативная MainButton в Telegram
        if (tg && tg.MainButton) {
            tg.MainButton.setText(btn.textContent.trim());
            tg.MainButton.show();
            tg.MainButton.onClick(function () {
                tg.MainButton.showProgress();
                doCheckout(function () { tg.MainButton.hideProgress(); });
            });
            btn.classList.add('d-none');  // прячем дублирующую кнопку в Telegram
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        initTelegram();
        initBack();
        initQtyControl();
        initAddToCart();
        initCartRemove();
        initCartQty();
        initRefund();
        initCheckout();
    });
})();
