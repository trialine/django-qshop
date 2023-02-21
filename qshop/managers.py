from django.db.models import DecimalField, Value
from django.contrib.auth import get_user_model

from qshop import qshop_settings
from qshop.helpers.net import get_country_by_ip


class OSSManagerMixin:
    """
    Manager mixin to implement #984 task with automatically apply oss by IP address or logged in logic
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # hack to avoid import looping
        # TODO: find more elegant solution
        from qshop import cart

        self.cart_module = cart

    def with_oss(self, request):
        vat_reduction, new_vat = self._get_vat_reduction(request)

        return self.annotate(
            vat_reduction=Value(vat_reduction, output_field=DecimalField()),
            new_vat=Value(new_vat, output_field=DecimalField()),
        )

    def _get_vat_reduction(self, request):
        ip_country_code = get_country_by_ip(request)

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
