from django.http import Http404
from django.shortcuts import get_object_or_404, render

from .classes import CategoryData
from .functions import get_products_page_data
from .models import Currency, Product
from .qshop_settings import REDIRECT_CLASS


def render_shopspage(request, menu, url_add, products=None):
    filter_string, page_num, sort, product = get_products_page_data(menu, url_add)

    if product:
        # render single product page
        menu._page_title = product.name

        return render(request, 'qshop/productpage.html', {
            'menu': menu,
            'url_add': url_add,
            'product': product,
        })
    else:
        # render products page

        productdata = CategoryData(request, filter_string, menu, sort, page_num, products)
        if productdata.need_return:
            return productdata.return_data

        return render(request, 'qshop/productspage.html', {
                'menu': menu,
                'url_add': url_add,
                'productdata': productdata,
            })


def redirect_to_product(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    return REDIRECT_CLASS(product.get_absolute_url_slow())


def set_currency(request, currency_code=None):
    if not currency_code:
        currency_code = request.POST.get('currency_code', None)
    redirect_url = request.GET.get('redirect_url', request.POST.get('redirect_url', '/'))

    currency = get_object_or_404(Currency, code=currency_code)

    Currency.set_default_currency(currency)

    return REDIRECT_CLASS(redirect_url)
