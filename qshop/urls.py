from django.urls import path, include

from .views import redirect_to_product, set_currency
from . import qshop_settings

urlpatterns = [
    path('show-product/<product_id>/', redirect_to_product, name='redirect_to_product'),
    path('shop-set-currency/', set_currency, name='set_currency'),
    path('shop-set-currency/<currency_code>/', set_currency, name='set_currency'),
]

if qshop_settings.ENABLE_PAYMENTS:
    urlpatterns += [
        path('vendors/', include('qshop.payment_vendors.urls')),
    ]
