from django.contrib.auth import get_user_model

from qshop import qshop_settings
from qshop.helpers.net import get_country_by_ip


class OSSMixin:
    """
    Main purpose of using this Mixin is to use "get_vat_reduction" to get VAT reduction and new VAT from request
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # hack to avoid import looping
        from qshop import cart
        self.cart_module = cart

    def get_country_code_from_request(self, request):
        """
        By default IP country iso2 code return (like LV, UK)
        Here you can implement your logic.
        """
        return get_country_by_ip(request)

    def get_fallback_vat_reduction(self):
        """
        Method to catch calling get_vat_reduction without request
        """
        return 0, 0

    def get_vat_reduction(self, request):
        """
        Return VAT reduction and new VAT depends on request

        Sometimes when calling cart.get_cart_object there are no any option get VAT reduction from request
        """
        if not request:
            return self.get_fallback_vat_reduction()

        ip_country_code = self.get_country_code_from_request(request)

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
