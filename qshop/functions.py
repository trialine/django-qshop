from .models import Product

def get_catalogue_root(menu):
    items = menu.__class__.objects.filter(pk__in=menu.get_parents_ids_list() + [menu.pk])
    for item in items:
        if item.page_type == 'prod':
            return item
    return menu


def get_products_page_data(menu, url_add):
    filter_string = ''
    page_num = 1
    product = None
    sort = Product.SORT_VARIANTS[0][0]

    if len(url_add) == 1:
        try:
            product = Product.objects.get(articul=url_add[0], category=menu, hidden=False)
            return(url_add, page_num, sort, product)
        except Exception:
            pass

    for item in url_add:
        if url_add and item.startswith('sort-'):
            sort = item.replace('sort-', '')

        if url_add and item.startswith('page-'):
            page_num = item.replace('page-', '')
    filter_string = '/'.join(url_add)
    return (filter_string, page_num, sort, product)
