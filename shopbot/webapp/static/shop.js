(function ($) {
    $.fn.redraw = function () {
        return this.map(function () {
            this.offsetTop;
            return this;
        });
    };
})(jQuery);


var Cafe = {
    canPay: false,
    modeOrder: false,
    totalPrice: 0,
    
    init: function (options) {
        Telegram.WebApp.ready();

        $("body").show();
        $(".js-item-incr-btn").on("click", Cafe.eIncrClicked);
        $(".js-item-decr-btn").on("click", Cafe.eDecrClicked);
        $(".js-order-edit").on("click", Cafe.eEditClicked);
        $(".js-status").on("click", Cafe.eStatusClicked);

        $("#about_us").on("click", Cafe.show_about_us_page);
        $("#make_order").on("click", Cafe.show_make_order_page);
        $("#back_to_main_menu").on("click", Cafe.back_to_main_menu);

        Telegram.WebApp.MainButton.setParams({
            text_color: "#fff",
        }).onClick(Cafe.mainBtnClicked);

        Telegram.WebApp.onEvent('invoiceClosed', function(object) {
            Cafe.toggleLoading(false);
        });

    },
    eIncrClicked: function (e) {
        e.preventDefault();
        var itemEl = $(this).parents(".js-item");
        Cafe.incrClicked(itemEl, 1);
    },
    eDecrClicked: function (e) {
        e.preventDefault();
        var itemEl = $(this).parents(".js-item");
        Cafe.incrClicked(itemEl, -1);
    },
    eEditClicked: function (e) {
        e.preventDefault();
        Cafe.toggleMode(false);
    },
    getOrderItem: function (itemEl) {
        var id = itemEl.data("item-id");
        return $(".js-order-item").filter(function () {
            return $(this).data("item-id") == id;
        });
    },
    updateItem: function (itemEl, delta) {
        var price = +itemEl.data("item-price");
        var count = +itemEl.data("item-count") || 0;
        var counterEl = $(".js-item-counter", itemEl);
        counterEl.text(count ? count : 1);

        var isSelected = itemEl.hasClass("selected");
        var anim_name = isSelected
            ? delta > 0
                ? "badge-incr"
                : count > 0
                    ? "badge-decr"
                    : "badge-hide"
            : "badge-show";
        var cur_anim_name = counterEl.css("animation-name");
        if (
            (anim_name == "badge-incr" || anim_name == "badge-decr") &&
            anim_name == cur_anim_name
        ) {
            anim_name += "2";
        }
        counterEl.css("animation-name", anim_name);
        itemEl.toggleClass("selected", count > 0);

        var orderItemEl = Cafe.getOrderItem(itemEl);
        var orderCounterEl = $(".js-order-item-counter", orderItemEl);
        orderCounterEl.text(count ? count : 1);
        orderItemEl.toggleClass("selected", count > 0);
        var orderPriceEl = $(".js-order-item-price", orderItemEl);
        var item_price = count * price;
        orderPriceEl.text(Cafe.formatPrice(item_price));

        Cafe.updateTotalPrice();
    },
    incrClicked: function (itemEl, delta) {
        var count = +itemEl.data("item-count") || 0;
        count += delta;
        if (count < 0) {
            count = 0;
        }
        itemEl.data("item-count", count);
        Cafe.updateItem(itemEl, delta);
    },
    formatPrice: function (price) {
        return Cafe.formatNumber(price, 0, ".", ",") + " RUB";
    },
    formatNumber: function (number, decimals, decPoint, thousandsSep) {
        number = (number + "").replace(/[^0-9+\-Ee.]/g, "");
        var n = !isFinite(+number) ? 0 : +number;
        var prec = !isFinite(+decimals) ? 0 : Math.abs(decimals);
        var sep = typeof thousandsSep === "undefined" ? "," : thousandsSep;
        var dec = typeof decPoint === "undefined" ? "." : decPoint;
        var s = "";
        var toFixedFix = function (n, prec) {
            if (("" + n).indexOf("e") === -1) {
                return +(Math.round(n + "e+" + prec) + "e-" + prec);
            } else {
                var arr = ("" + n).split("e");
                var sig = "";
                if (+arr[1] + prec > 0) {
                    sig = "+";
                }
                return (+(
                    Math.round(+arr[0] + "e" + sig + (+arr[1] + prec)) +
                    "e-" +
                    prec
                )).toFixed(prec);
            }
        };
        s = (prec ? toFixedFix(n, prec).toString() : "" + Math.round(n)).split(".");
        if (s[0].length > 3) {
            s[0] = s[0].replace(/\B(?=(?:\d{3})+(?!\d))/g, sep);
        }
        if ((s[1] || "").length < prec) {
            s[1] = s[1] || "";
            s[1] += new Array(prec - s[1].length + 1).join("0");
        }
        return s.join(dec);
    },
    updateMainButton: function () {
        var mainButton = Telegram.WebApp.MainButton;
        if (Cafe.modeOrder) {
            if (Cafe.isLoading) {
                mainButton
                    .setParams({
                        is_visible: true,
                        color: "#65c36d",
                    })
                    .showProgress();
            } else {
                mainButton
                    .setParams({
                        is_visible: !!Cafe.canPay,
                        text: "В КОРЗИНЕ НА " + Cafe.formatPrice(Cafe.totalPrice),
                        color: "#31b545",
                    })
                    .hideProgress();
            }
        } else {
            mainButton
                .setParams({
                    is_visible: !!Cafe.canPay,
                    text: "ПОСМОТРЕТЬ ЗАКАЗ",
                    color: "#31b545",
                })
                .hideProgress();
        }
    },
    updateTotalPrice: function () {
        var total_price = 0;
        $(".js-item").each(function () {
            var itemEl = $(this);
            var price = +itemEl.data("item-price");
            var count = +itemEl.data("item-count") || 0;
            total_price += price * count;
        });
        Cafe.canPay = total_price > 0;
        Cafe.totalPrice = total_price;
        Cafe.updateMainButton();
    },
    getOrderData: function () {
        var order_data = [];
        $(".js-item").each(function () {
            var itemEl = $(this);
            var id = itemEl.data("item-id");
            var count = +itemEl.data("item-count") || 0;
            if (count > 0) {
                order_data.push({ label: id, amount: count * 100 });
            }
        });
        return order_data;
    },
    toggleMode: function (mode_order) {
        Cafe.modeOrder = mode_order;
        if (mode_order) {
            $(".cafe-order-overview").show();
            $(".shop_items").hide();

            $("body").addClass("order-mode");

            Telegram.WebApp.expand();
        } else {
            $("body").removeClass("order-mode");

            $(".shop_items").show();
            $(".cafe-order-overview").hide();
        }
        Cafe.updateMainButton();
    },
    toggleLoading: function (loading) {
        Cafe.isLoading = loading;
        Cafe.updateMainButton();
        $("body").toggleClass("loading", !!Cafe.isLoading);
        Cafe.updateTotalPrice();
    },
    mainBtnClicked: function () {
        
        if (!Cafe.canPay || Cafe.isLoading) {
            return false;
        }
        if (Cafe.modeOrder) {
            Cafe.toggleLoading(true);
            
            fetch(`/create_invoice_link`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    prices: Cafe.getOrderData(),
                })
            })
            .then(response => response.json())
            .then(data => {
                let answer = data['result'];
                window.Telegram.WebApp.openInvoice(answer);
            })
            .catch(error => console.error('Error:', error));

            Cafe.toggleLoading(false);

        } else {
            Cafe.toggleMode(true);
        }
    },
    show_about_us_page: function () {
        $("#shop_menu_page").hide();
        $("#shop_about_us_page").show();
    },
    show_make_order_page: function () {
        $("#shop_menu_page").hide();
        $("#shop_items_page").css("display", "flex");
    },
    back_to_main_menu: function () {
        $("#shop_menu_page").show();
        $("#shop_items_page").hide();
        $("#shop_about_us_page").hide();
    },
};


(function() {
    Cafe.init({});
})();


