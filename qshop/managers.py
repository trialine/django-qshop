from django.db.models import DecimalField, Value
from qshop.mixins import OSSMixin


class OSSManagerMixin(OSSMixin):
    """
    Manager mixin to implement #984 task with automatically apply oss by IP address or logged in logic
    """
    def with_oss(self, request):
        vat_reduction, new_vat = self.get_vat_reduction(request)

        return self.annotate(
            vat_reduction=Value(vat_reduction, output_field=DecimalField()),
            new_vat=Value(new_vat, output_field=DecimalField()),
        )
