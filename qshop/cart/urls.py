from django.urls import path

from qshop.qshop_settings import CART_ORDER_VIEW, ENABLE_QSHOP_DELIVERY, ENABLE_PROMO_CODES

from .views import (OrderDetailView, AjaxOrderDetailView, CartDetailView, add_to_cart, cart_order_cancelled,
                    cart_order_error, cart_order_success, remove_from_cart, update_cart)

if CART_ORDER_VIEW:
    from sitemenu import import_item
    qshop_order_view = import_item(CART_ORDER_VIEW)

if ENABLE_PROMO_CODES:
    from .views import ApplyPromoView


urlpatterns = [
    path('', CartDetailView.as_view(), name='cart'),
    path('add/<product_id>/', add_to_cart, name='add_to_cart'),
    path('remove/<item_id>/', remove_from_cart, name='remove_from_cart'),
    path('update/', update_cart, name='update_cart'),

    path('order/success/', cart_order_success, name='cart_order_success'),
    path('order/cancelled/', cart_order_cancelled, name='cart_order_cancelled'),
    path('order/cancelled/<order_id>/', cart_order_cancelled, name='cart_order_cancelled'),
    path('order/error/', cart_order_error, name='cart_order_error'),
]

if ENABLE_QSHOP_DELIVERY:
    urlpatterns += [
        path('order/', OrderDetailView.as_view(), name='order_cart'),
        path('order/ajax-submit-order/', AjaxOrderDetailView.as_view(), name='ajax_order_cart'),
    ]

if CART_ORDER_VIEW:
    urlpatterns += [
        path('order/', qshop_order_view, name='order_cart')
    ]
elif not ENABLE_QSHOP_DELIVERY:
    from . import views
    urlpatterns += [
        path('order/', views.order_cart, name='order_cart'),
    ]

if ENABLE_PROMO_CODES:
    urlpatterns += [
        path('apply-promo/', ApplyPromoView.as_view(), name='apply_promo'),
    ]
