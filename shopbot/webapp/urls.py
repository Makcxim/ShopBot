
from django.urls import path

from .views import main_page

urlpatterns = [
    path('main_page', main_page, name='main_page'),
]