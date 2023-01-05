import re
from collections import defaultdict

from django.apps import apps
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Q
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

    def __init__(self, request, filter_string, menu, sort, page=1, products=None):
        self.request = request
        self.filter_string = filter_string
        self.menu = menu
        self.page = page
        self.page_link = menu.get_absolute_url()
        self.init_products = products
        self.filters_set = set(filter_string.split('/'))

        for i, x in enumerate(Product.SORT_VARIANTS):
            if sort == x[0]:
                self.sort = x
                if i == 0:
                    self.default_sorting = True
                else:
                    self.default_sorting = False
                break
        if not self.sort:
            raise Http404('Invalid sorting parameter')

        if not self.menu.page_type == 'pdis':
            self.process_filters()
        self.process_products()

        page_link = self.get_filter_link()

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

        for filter_q in self.get_q_filters(exclude_filter_slug):
            products = products.filter(filter_q)

        return products

    def process_products(self):
        products = self.filter_products()

        if self.sort[1] == 'price' or self.sort[1] == '-price':
            sort = self.sort[1].replace('price', 'min_price')
            products = products.extra(select={'min_price': "IF(`qshop_product`.`discount_price`, `qshop_product`.`discount_price`, `qshop_product`.`price`)"}).order_by(sort)
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
            filter_name = 'parameter__name_%s' % get_language()
            value_value = 'value__value_%s' % get_language()

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
                'active': False,
                'name': item[filter_name],
                'choices': []
            })

            filter['choices'].append({
                 **item,
                'name': item.get(value_value),
                'slug': value_slug,
                'active': filter_is_active,
                'link': self.get_filter_link(value_slug, exclude=filter_is_active)
            })

            if filter_is_active:
                filter['active'] = True
            self.filters[parameter_slug] = filter

        for slug in self.filters.keys():
            self._check_parameter_filter(slug)

    def get_filter_link(self, filter_slug="", exclude=False):
        filter_string = ""

        for item in self.filters_qs:
            filters = set([filter_slug]).union(self.filters_set)
            if item['value__slug'] in filters and not (exclude and item['value__slug'] == filter_slug):
                filter_string += f'{item["value__slug"]}/'

        if not filter_slug and not int(self.page) == 1:
            filter_string += f'page-{self.page}/'

        return self.menu.get_absolute_url() + f'{filter_string}'

    def process_filters(self):
        if FILTERS_ENABLED:
            self.set_parameter_filters()

    def get_q_filters(self, exclude_filter_slug=None):
        filters_q = defaultdict(Q)

        for slug, filter in self.filters.items():
            if filter['active'] and not slug == exclude_filter_slug:
                for item in filter['choices']:
                    if item['active']:
                        filters_q[slug] |= (Q(producttoparameter__value__slug=item['slug']))
        return filters_q.values()

    def link_for_page(self, sorting=None, skip_page=True):
        filter_string = ""
        for filter in self.filters.values():
            for item in filter['choices']:
                if item['value__slug'] in self.filters_set:
                    filter_string += f'{item["value__slug"]}/'
        return self.menu.get_absolute_url() + f'{filter_string}'

    def get_sorting_variants(self):
        for variant in Product.SORT_VARIANTS:
            try:
                add = variant[3]
            except IndexError:
                add = None
            yield {
                'link': self.link_for_page(sorting=variant[0], skip_page=True),
                'name': variant[2],
                'selected': True if variant[0] == self.sort[0] else False,
                'add': add
            }

    def get_sorting_variants_as_list(self):
        return list(self.get_sorting_variants())

    def get_filters(self):
        return self.filters

    def _check_parameter_filter(self, slug):
        products = self.filter_products(slug)
        # if FILTERS_NEED_COUNT:
        #     aviable_parameters_data = ParameterValue.objects.filter(producttoparameter__product__in=products).annotate(total_items=Count('id')).values_list('id', 'total_items')
        #     aviable_parameters = []
        #     parameters_counts = {}
        #     for aviable_parameter, parameter_count in aviable_parameters_data:
        #         aviable_parameters.append(aviable_parameter)
        #         parameters_counts[aviable_parameter] = parameter_count
        # else:
        aviable_parameters = ProductToParameter.objects.filter(product__in=products).distinct().values_list('value__slug', flat=True)
        # parameters_counts = {}

        for filter in self.filters[slug]['choices']:
            filter['aviable'] = filter['slug'] in aviable_parameters

    def _check_variation_filter(self, filter_id, filter_data, products):
        products = self.filter_products(filter_id)

        if FILTERS_NEED_COUNT:
            aviable_variations_data = ProductVariationValue.objects.filter(productvariation__product__in=products).annotate(total_items=Count('id')).values_list('id', 'total_items')
            aviable_variations = []
            variations_counts = {}
            for aviable_parameter, parameter_count in aviable_variations_data:
                aviable_variations.append(aviable_parameter)
                variations_counts[aviable_parameter] = parameter_count
        else:
            aviable_variations = ProductVariationValue.objects.filter(productvariation__product__in=products).distinct().values_list('id', flat=True)
            variations_counts = {}

        for value_id, value_data in filter_data['values']:
            if FILTERS_NEED_COUNT and value_id in variations_counts:
                value_data['count'] = variations_counts[value_id]
            if value_id not in aviable_variations:
                value_data['unaviable'] = True

    def _check_foreignkey_filter(self, filter_id, filter_data, products):
        products = self.filter_products(filter_id)

        field_name = FILTERS_FIELDS[filter_id]
        field = Product._meta.get_field(field_name)
        model = field.related_model

        model.objects.filter(product__category=self.menu).distinct()

        if FILTERS_NEED_COUNT:
            aviable_field_data = model.objects.filter(product__in=products).annotate(total_items=Count('id')).values_list('id', 'total_items')
            aviable_field = []
            field_counts = {}
            for item, count in aviable_field_data:
                aviable_field.append(item)
                field_counts[item] = count
        else:
            aviable_field = model.objects.filter(product__in=products).distinct().values_list('id', flat=True)
            field_counts = {}

        for value_id, value_data in filter_data['values']:
            if FILTERS_NEED_COUNT and value_id in field_counts:
                value_data['count'] = field_counts[value_id]
            if value_id not in aviable_field:
                value_data['unaviable'] = True
