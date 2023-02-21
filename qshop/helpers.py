from decimal import Decimal, ROUND_UP, ROUND_HALF_UP

from django.conf import settings
from django.contrib.gis.geoip2 import GeoIP2
from ipware.ip import get_client_ip


def get_country_by_ip(request):
    if settings.DEBUG:
        return "LV"

    try:
        ip, _ = get_client_ip(request)
        g = GeoIP2()
        return g.country_code(ip)
    except Exception:
        return ""


def round_decimal(value):
    return Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def round_to_whole_number(value):
    return value.quantize(Decimal('1.'), rounding=ROUND_UP)


def round_up_to_5_or_10(value):
    """
    Round up to nearest 5 or 10 and return Decimal
    """
    value_last_digit = value % 10

    if not value_last_digit == 5:
        value = round(value, -1)
    if value_last_digit < 5 and not value_last_digit == 0:
        value += 5

    return Decimal(str(value))
