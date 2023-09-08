from math import ceil, floor
from decimal import Decimal
from collections import defaultdict
from django.apps import apps
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import DecimalField, F, Q, Min, Max, Case, When
from django.http import Http404
from django.utils.translation import gettext_lazy as _

from .models import (
    ParametersSet,
    ParameterValue,
    Product,
    ProductToParameter,
    ProductVariationValue,
)
from .qshop_settings import (
    FILTER_BY_VARIATION_TYPE,
    FILTERS_ENABLED,
    FILTERS_FIELDS,
    FILTERS_NEED_COUNT,
    FILTERS_ORDER,
    FILTERS_PRECLUDING,
    PRODUCTS_ON_PAGE,
    REDIRECT_CLASS,
    VARIATION_FILTER_NAME,
)


class CategoryData:
    need_return = False
    return_data = None
    filters = {}
    filters_order = []
    products_page = None

    request = None
    filter_string = ''
    menu = None
    sort = None
    page = 1
    default_sorting = True
    use_filter = False
    parameters_mapping = defaultdict(list)

    def __init__(self, request, filter_string, menu, sort, page=1, products=None):
        self.request = request
        self.filter_string = filter_string
        self.menu = menu
        self.page = page
        self.page_link = menu.get_absolute_url()
        self.init_products = products
        self.filters_set = set(filter_string.split('/'))

        for item in ParameterValue.objects.all():
            self.parameters_mapping[item.slug].append(item.id)

        for i, x in enumerate(Product.SORT_VARIANTS):
            if sort == x[0]:
                self.sort = x
                self.default_sorting = i == 0
                break
        if not self.sort:
            raise Http404('Invalid sorting parameter')

        if not self.menu.page_type == 'pdis':
            self.process_filters()
        self.process_products()

        page_link = self.link_for_page(skip_page=False)

        if not self.request.path == page_link:
            self.return_data = REDIRECT_CLASS(page_link)
            self.need_return = True

    def filter_products(self, exclude_filter_slug=None):
        if self.init_products is not None:
            products = self.init_products
        elif not self.menu.page_type == 'pdis':
            products = Product.in_category_objects.filter(category=self.menu)
        else:
            products = Product.in_category_objects.exclude(discount_price=None)

        products = products.annotate(min_price=Case(
            When(discount_price__isnull=False, then=F('discount_price')),
            default=F('price'),
            output_field=DecimalField(decimal_places=2, max_digits=10)
        ))

        for filter_q in self.get_q_filters(exclude_filter_slug):
            products = products.filter(filter_q)

        return products

    def process_products(self):
        products = self.filter_products()

        if self.sort[1] == 'price' or self.sort[1] == '-price':
            sort = self.sort[1].replace('price', 'min_price')
            products = products.order_by(sort)
        else:
            sort = self.sort[1]
            if isinstance(sort, str):
                sort = (sort, 'id')
            products = products.order_by(*sort)

        products = products.distinct()
        paginator = Paginator(products, PRODUCTS_ON_PAGE)
        try:
            products_page = paginator.page(self.page)
        except (PageNotAnInteger, EmptyPage):
            raise Http404('There is no such page')

        if not self.menu.page_type == 'pdis':
            for product in products_page.object_list:
                product._current_category = self.menu

        self.products_page = products_page

    def set_parameter_filters(self):
        self.filters = {}

        filter_name = 'parameter__name'
        value_value = 'value__value'

        if apps.is_installed('modeltranslation'):
            from django.utils.translation import get_language
            filter_name = 'parameter__name_%s' % get_language().replace('-', '_')
            value_value = 'value__value_%s' % get_language().replace('-', '_')

        self.filters_qs = ProductToParameter.objects.filter(
            product__category=self.menu,
            product__hidden=False,
            parameter__is_filter=True,
            value__isnull=False,
            value__slug__isnull=False
        ).order_by(
            'parameter__parameters_set',
            'parameter__order',
            'parameter__id',
            'value__slug',
        )

        self.filters_qs.query.group_by = ['value__slug']
        self.filters_qs = self.filters_qs.values('value__slug', 'parameter__slug', value_value, filter_name, 'parameter__order')
        for item in self.filters_qs:
            value_slug = item['value__slug']
            parameter_slug = item['parameter__slug']

            filter_is_active = value_slug in self.filters_set

            filter = self.filters.get(parameter_slug, {
                'active': filter_is_active,
                'type': 'coice',
                'name': item[filter_name],
                'choices': [],
            })

            filter['choices'].append({
                 **item,
                'name': item.get(value_value),
                'slug': value_slug,
                'active': filter_is_active,
                'link': self.link_for_page(value_slug, filter_is_active)
            })

            self.filters[parameter_slug] = filter

            for slug in self.filters.keys():
                self._check_parameter_filter(slug)

    def set_price_filters(self):
        field_name = 'price'
        field = Product._meta.get_field(field_name)
        price_filter = next(filter(lambda i: i.startswith('price-range-'), self.filters_set), None)


        self.filters['price_range'] = {
            'active': bool(price_filter),
            'type': 'price_range',
            'name': field.verbose_name,
            'link': self.link_for_page('price_range', bool(price_filter))
        }

        if price_filter:
            self.filters['price_range']['min'], self.filters['price_range']['max'] = self.decode_price_filter(price_filter)

        self._check_price_filter('price_range')

    def decode_price_filter(self, filter_string):
        filter_data = filter_string.split('-')
        try:
            return [(int(x)) for x in filter_data[2].split(':')]
        except ValueError:
            return [Decimal(x) for x in filter_data[2].split(':').split(':')]

    def link_for_page(self, filter_slug="", exclude=False, sorting=None, skip_page=True):
        filters = set([filter_slug]).union(self.filters_set)
        filter_string = ""

        for item in self.filters_qs:
            if item['value__slug'] in filters and not (exclude and item['value__slug'] == filter_slug):
                filter_string += f'{item["value__slug"]}/'
                self.use_filter = False

        price_filter = next(filter(lambda i: i.startswith('price-range-'), self.filters_set), None)

        if filter_slug == 'price_range':
            filter_string += f'price-range-#min:#max/'
        if price_filter and not (exclude and filter_slug == 'price_range'):
            filter_string += f'{price_filter}/'
        if not sorting and not self.default_sorting:
            filter_string += f'sort-{self.sort[0]}/'
        if sorting and sorting != Product.SORT_VARIANTS[0][0]:
            filter_string += f'sort-{sorting}/'
        if not skip_page and not int(self.page) == 1:
            filter_string += f'page-{self.page}/'

        return self.menu.get_absolute_url() + filter_string

    def process_filters(self):
        if FILTERS_ENABLED:
            self.set_parameter_filters()
            self.set_price_filters()

    def get_q_filters(self, exclude_filter_slug=None, filter_preposition=""):
        filters_q = defaultdict(Q)

        for slug, filter in self.filters.items():
            if filter['active'] and not slug == exclude_filter_slug:
                if filter['type'] == 'price_range':
                    filters_q['price'] = (
                        Q(min_price__gte=self._round_min_price(filter['min'])) &
                        Q(min_price__lte=self._round_max_price(filter['max']))
                    )
                else:
                    for item in filter['choices']:
                        if item['active']:
                            filters_q[slug] |= (Q(**{
                                f'{filter_preposition}producttoparameter__value_id__in': self.parameters_mapping[item['slug']]
                            }))
        return filters_q.values()

    def get_sorting_variants(self):
        for variant in Product.SORT_VARIANTS:
            try:
                add = variant[3]
            except IndexError:
                add = None
            yield {
                'link': self.link_for_page(sorting=variant[0]),
                'name': variant[2],
                'selected': variant[0] == self.sort[0],
                'add': add
            }

    def get_sorting_variants_as_list(self):
        return list(self.get_sorting_variants())

    def get_filters(self):
        return self.filters

    def _round_min_price(self, price):
        price = ceil(price)
        if price % 10 == 0:
            return price - 4
        remainder = (price % 5) - 1
        if remainder <= 0:
            return price
        return price - remainder

    def _round_max_price(self, price):
        price = ceil(price)
        remainder = (price % 5)
        if remainder == 0:
            return price
        return price - remainder

    def _check_parameter_filter(self, slug):
        aviable_parameters = ProductToParameter.objects.filter(
            product__hidden=False,
            product__category=self.menu,
        )

        for filter in self.get_q_filters(slug, 'product__'):
            aviable_parameters = aviable_parameters.filter(filter)

        aviable_parameters = aviable_parameters.distinct().values_list('value_id', flat=True)

        for filter in self.filters[slug]['choices']:
            filter['aviable'] = set(self.parameters_mapping[filter['slug']]).intersection(aviable_parameters)

    def _check_price_filter(self, filter_name):
        products = self.filter_products(filter_name)
        prices = products.aggregate(min_price=Min('price'), max_price=Max('price'))
        self.filters[filter_name]['min_price'] = None
        self.filters[filter_name]['max_price'] = None

        try:
            self.filters[filter_name]['min_price'] = ceil(prices['min_price'])
        except TypeError:
            pass

        try:
            self.filters[filter_name]['max_price'] = floor(prices['max_price'])
        except TypeError:
            pass
