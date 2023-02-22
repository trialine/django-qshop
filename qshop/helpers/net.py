from django.conf import settings
from django.contrib.gis.geoip2 import GeoIP2
from ipware.ip import get_client_ip


def get_country_by_ip(request):
    """
    Newest GeoLite2-Country.mmdb db here https://github.com/P3TERX/GeoLite.mmdb
    """
    if settings.DEBUG:
        return "LV"

    try:
        ip, _ = get_client_ip(request)
        g = GeoIP2()
        return g.country_code(ip)
    except Exception:
        return ""
