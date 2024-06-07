from decouple import config
from django.urls import path

from .views import main_page

urlpatterns = [
    path(config('MAIN_PAGE_URL', default='main_page'), main_page, name='main_page'),
]