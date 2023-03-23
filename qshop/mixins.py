from django.contrib.auth import get_user_model

from qshop import qshop_settings
from qshop.helpers.net import get_country_by_ip


class OSSMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # hack to avoid import looping
        # TODO: find more elegant solution
        from qshop import cart

        self.cart_module = cart

    def get_country_code_by_request(self, request):
        """
        By default IP country iso2 code return (like LV, UK)
        Here you can implement your logic.
        """
        return get_country_by_ip(request)

    def _get_vat_reduction(self, request):
        """
        Return VAT reduction and new VAT depends on request
        """
        ip_country_code = self.get_country_code_by_request(request)

        if request.user.is_authenticated:
            kwargs = self._get_vat_reduction_kwargs_for_authenticated_user(
                request.user, ip_country_code
            )
        else:
            kwargs = self._get_vat_reduction_kwargs_for_anonymous_user(ip_country_code)

        return self.cart_module.models.DeliveryCountry.get_vat_reduction_oss(**kwargs)

    def _get_vat_reduction_kwargs_for_authenticated_user(self, user, ip_country_code):
        """
        Logic is under #984 task
        """
        if user.person_type == get_user_model().PersonType.PHYSICAL:
            legal_country = None
        else:
            legal_country = self.cart_module.models.DeliveryCountry.objects.get(
                iso2_code=(
                    user.legal_country
                    or ip_country_code
                    or qshop_settings.MERCHANT_SHOP_COUNTRY_CODE
                )
            )

        return {
            "delivery_country": self.cart_module.models.DeliveryCountry.objects.get(
                iso2_code=(
                    user.get_delivery_country_code()
                    or ip_country_code
                    or qshop_settings.MERCHANT_SHOP_COUNTRY_CODE
                )
            ),
            "vat_reg_number": user.vat_reg_number,
            "person_type": user.person_type,
            "legal_country": legal_country,
        }

    def _get_vat_reduction_kwargs_for_anonymous_user(self, ip_country_code):
        return {
            "delivery_country": self.cart_module.models.DeliveryCountry.objects.get(
                iso2_code=ip_country_code or qshop_settings.MERCHANT_SHOP_COUNTRY_CODE
            ),
            "vat_reg_number": None,
            # TODO: improve this, User model has to have PersonType class
            "person_type": get_user_model().PersonType.PHYSICAL,
            "legal_country": None,
        }
