from django.shortcuts import render

from .models import ShopProduct


def main_page(request):
    products = list(ShopProduct.objects.all())
    return render(request, 'main_page.html', context={'products': products})
