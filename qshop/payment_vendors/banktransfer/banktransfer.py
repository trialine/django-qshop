from django.urls import reverse

from qshop.payment_vendors.payment import BasePayment
from qshop.qshop_settings import REDIRECT_CLASS


class BanktransferPayment(BasePayment):
    def get_redirect_response(self, cart):
        return REDIRECT_CLASS(reverse('cart_order_success'))

    def parse_response(self, request):
        raise NotImplementedError()
