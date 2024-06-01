
from django.urls import path

from .views import create_invoice_link

urlpatterns = [
    path('create_invoice_link', create_invoice_link, name='create_invoice_link'),
]