import math
import re
from decimal import Decimal

from django.apps import apps
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Max, Min, Q
from django.http import Http404, HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _
from natsort import natsorted

from .models import (ParametersSet, ParameterValue, Product,
                     ProductToParameter, ProductVariationValue)
from .qshop_settings import (FILTER_BY_VARIATION_TYPE, FILTERS_ENABLED,
                             FILTERS_FIELDS, FILTERS_NEED_COUNT, FILTERS_ORDER,
                             FILTERS_PRECLUDING, PRODUCTS_ON_PAGE,
                             VARIATION_FILTER_NAME)


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

        if self.request.get_full_path() != self.link_for_page(skip_page=False):
            self.return_data = HttpResponseRedirect(self.link_for_page(skip_page=False))
            self.need_return = True

    def filter_products(self, exclude_filter_id=None):
        if self.init_products is not None:
            products = self.init_products
        elif not self.menu.page_type == 'pdis':
            products = Product.in_category_objects.filter(category=self.menu)
        else:
            products = Product.in_category_objects.exclude(discount_price=None)

        for filter_q in self.get_q_filters(exclude_filter_id):
            products = products.filter(filter_q)

        return products


    def process_products(self):
        self.products = self.filter_products()

        if FILTERS_PRECLUDING:
            self.set_available_filters(self.products)

        if self.sort[1] == 'price' or self.sort[1] == '-price':
            sort = self.sort[1].replace('price', 'min_price')
            self.products = self.products.extra(select={'min_price': "IF(`qshop_product`.`discount_price`, `qshop_product`.`discount_price`, `qshop_product`.`price`)"}).order_by(sort)
        else:
            sort = self.sort[1]
            if isinstance(sort, str):
                sort = (sort, 'id')
            self.products = self.products.order_by(*sort)

        self.products = self.products.distinct()

        paginator = Paginator(self.products, PRODUCTS_ON_PAGE)
        try:
            products_page = paginator.page(self.page)
        except (PageNotAnInteger, EmptyPage):
            raise Http404('There is no such page')

        if not self.menu.page_type == 'pdis':
            for product in products_page.object_list:
                product._current_category = self.menu

        self.products_page = products_page

    def _get_filters_data(self):
        filters = {}
        filters_order = []

        if FILTERS_ENABLED:

            parameter_name = 'parameter__name'
            value_value = 'value__value'

            if apps.is_installed('modeltranslation'):
                from django.utils.translation import get_language
                parameter_name = 'parameter__name_%s' % get_language()
                value_value = 'value__value_%s' % get_language()


            for filter_key in FILTERS_ORDER:
                if filter_key == 'p':
                    filters_qs = ProductToParameter.objects.values(
                        'parameter__id',
                        parameter_name,
                        'value__id',
                        value_value
                    ).filter(
                        product__hidden=False,
                        parameter__is_filter=True
                    ).exclude(
                        value=None
                    ).order_by(
                        'parameter__parameters_set',
                        'parameter__order',
                        value_value
                    )

                    filters_qs.query.group_by = ['value__id']

                    for item in filters_qs:
                        filter_id = "p{0}".format(item['parameter__id'])
                        if not filter_id in filters:
                            filters_order.append(filter_id)
                            filters[filter_id] = {
                                'name': item[parameter_name],
                                'has_active': False,
                                'values': [],
                                'filter_type': 'or',
                                'filter_aviability_check': self._check_parameter_filter
                            }

                        filters[filter_id]['values'].append(
                            (
                                item['value__id'], {
                                    'name': item[value_value],
                                    'active': False,
                                    'unaviable': False,
                                    'count': 0,
                                    'filter': Q(producttoparameter__value_id=item['value__id'])
                                }
                            )
                        )
                elif filter_key == 'v':
                    variations = ProductVariationValue.objects.filter(
                        # productvariation__product__category=self.menu,
                        productvariation__product__hidden=False
                    ).distinct().order_by('value')

                    if variations:
                        filters_order.append('v')

                        if hasattr(self.menu, 'get_variation_name'):
                            variation_name = self.menu.get_variation_name()
                        elif hasattr(ParametersSet, 'get_variation_name'):
                            try:
                                variation_name = ParametersSet.objects.filter(
                                    product__category=self.menu
                                )[0].get_variation_name()
                            except:
                                variation_name = _(VARIATION_FILTER_NAME)
                        else:
                            variation_name = _(VARIATION_FILTER_NAME)

                        filters['v'] = {
                            'name': variation_name,
                            'has_active': False,
                            'values': [],
                            'filter_type': FILTER_BY_VARIATION_TYPE,
                            'filter_aviability_check': self._check_variation_filter
                        }

                        for variation in variations:
                            filters['v']['values'].append(
                                (variation.id, {
                                        'name': variation.get_filter_name(),
                                        'active': False,
                                        'unaviable': False,
                                        'count': 0,
                                        'filter': Q(productvariation__variation_id=variation.id)
                                    }
                                )
                            )

                elif filter_key == 'range':
                    for field_name in FILTERS_FIELDS[filter_key]:
                        field = Product._meta.get_field(field_name)
                        filters_order.append(field_name)
                        filters[field_name] = {
                            'name': field.verbose_name,
                            'type': 'range',
                            'field_name': field_name,
                            'has_active': False,
                            'values': [],
                            'filter_type': 'or',
                            'filter_aviability_check': self._check_range_filter
                        }

                        fltrs = []
                        if self.filter_string:
                            fltrs = self.decode_filters(self.filter_string)

                        if field_name in fltrs:
                            filters[field_name]['current_min_price'] = fltrs[field_name][0]
                            filters[field_name]['current_max_price'] = fltrs[field_name][1]

                        q = {}
                        filters[field_name]['values'].append(
                            ('', {
                                    'name': '',
                                    'active': False,
                                    'unaviable': False,
                                    'count': 0,
                                    'filter': Q(**q)
                                }
                            )
                        )

                else:
                    field_name = FILTERS_FIELDS[filter_key]
                    if not hasattr(Product, field_name):
                        raise Exception('[qShop exception] Filter configuration error: there is no {0} in Product class!'.format(field_name))
                    field = Product._meta.get_field(field_name)
                    model = field.related_model

                    items = model.objects.filter(product__hidden=False).distinct()

                    try:
                        items = items.order_by(field.related_model.get_order_by_in_filter())
                    except:
                        pass

                    if items:
                        filters_order.append(filter_key)
                        filters[filter_key] = {
                            'name': field.verbose_name,
                            'has_active': False,
                            'values': [],
                            'filter_type': 'or',
                            'filter_aviability_check': self._check_foreignkey_filter
                        }

                        for item in items:
                            q = { '{0}_id'.format(field_name): item.id }
                            filters[filter_key]['values'].append(
                                (item.id, {
                                        'name': item.__str__(),
                                        'active': False,
                                        'unaviable': False,
                                        'count': 0,
                                        'filter': Q(**q)
                                    }
                                )
                            )

        return filters, filters_order

    def process_filters(self):
        filters, filters_order = self._get_filters_data()

        if FILTERS_ENABLED:
            try:
                self.selected_filters = self.decode_filters(self.filter_string)
            except:
                self.selected_filters = {}

            if 'filteradd' in self.request.GET or 'filterdel' in self.request.GET or 'filterset' in self.request.GET or 'filterclear' in self.request.GET:
                if 'filteradd' in self.request.GET:
                    action_type = 'add'
                    action_value = self.request.GET['filteradd']
                elif 'filterdel' in self.request.GET:
                    action_type = 'del'
                    action_value = self.request.GET['filterdel']
                elif 'filterset' in self.request.GET:
                    action_type = 'set'
                    action_value = self.request.GET['filterset']
                else:
                    action_type = 'clear'
                    action_value = ''

                wrong_data = False

                try:
                    f_data = re.search('f([\d\w]+)-([,.:\d]+)', action_value)
                    if not f_data:
                        f_data = re.search('f([\d\w]+)', action_value)
                        filter_id = str(f_data.group(1))
                        filter_value = ""
                    else:
                        filter_id = str(f_data.group(1))

                        try:
                            filter_value = int(f_data.group(2))
                        except ValueError:
                            filter_value = f_data.group(2)

                except AttributeError:
                    wrong_data = True


                if not wrong_data:
                    if action_type == 'add':
                        try:
                            if not filter_value in self.selected_filters[filter_id]:
                                self.selected_filters[filter_id].append(filter_value)
                        except:
                            self.selected_filters[filter_id] = [filter_value]
                    elif action_type == 'del':
                        try:

                            if filter_value:
                                self.selected_filters[filter_id].remove(filter_value)
                            else:
                                del self.selected_filters[filter_id]

                            if not self.selected_filters[filter_id]:
                                del self.selected_filters[filter_id]
                        except:
                            pass
                    elif action_type == 'set':
                        self.selected_filters[filter_id] = [filter_value]
                elif 'filterclear' in self.request.GET:
                    self.selected_filters = {}

                if not self.selected_filters:
                    self.filter_string = ''
                else:
                    self.filter_string = self.encode_filters(self.selected_filters)

                self.return_data = HttpResponseRedirect(self.link_for_page(skip_page=True))

                self.need_return = True
                return

            for filter_id, filter_data in filters.items():
                if filter_id in self.selected_filters:

                    if filter_id == "price":
                        for value_id, value_data in filter_data['values']:
                            value_data['active'] = True
                            filter_data['has_active'] = True
                            value_data['name']= f"{self.selected_filters[filter_id][0]} - {self.selected_filters[filter_id][1]}"
                    else:
                        for value_id, value_data in filter_data['values']:
                            if value_id in self.selected_filters[filter_id]:
                                value_data['active'] = True
                                filter_data['has_active'] = True

        self.filters = filters
        self.filters_order = filters_order

    def get_q_filters(self, exclude_id=None):
        filters_q = []

        if FILTERS_ENABLED:
            for filter_id, filter_data in self.filters.items():
                if filter_id != exclude_id:
                    if "type" in filter_data and filter_data['type'] == "range":
                        if filter_id in self.selected_filters:
                            filters_q.append(
                                Q(price__gte=self.selected_filters[filter_id][0]) & Q(price__lte=self.selected_filters[filter_id][1]) |
                                Q(discount_price__gte=self.selected_filters[filter_id][0]) & Q(discount_price__lte=self.selected_filters[filter_id][1])
                            )
                    else:
                        filter_arr = Q()

                        for value_id, value_data in filter_data['values']:
                            if value_data['active']:
                                if filter_data['filter_type'] == 'or':
                                    filter_arr |= value_data['filter']
                                else:
                                    filters_q.append(value_data['filter'])
                        if filter_arr:
                            filters_q.append(filter_arr)

        return filters_q

    def set_available_filters(self, products):
        if FILTERS_ENABLED:
            for filter_id, filter_data in self.filters.items():
                if hasattr(filter_data['filter_aviability_check'], '__call__'):
                    filter_data['filter_aviability_check'](filter_id, filter_data)

    def encode_filters(self, filters):
        filter_arr = []

        for k, v in filters.items():
            filter_arr.append("%s-%s" % (k, ':'.join(natsorted([str(x) for x in v]))))
        return '_'.join(filter_arr)

    def decode_filters(self, filters):
        filters_ret = {}
        for filter_item in filters.split('_'):
            filter_id, filter_data = filter_item.split('-', 2)

            try:
                filters_ret[str(filter_id)] = [int(x) for x in filter_data.split(':')]
            except ValueError:
                filters_ret[str(filter_id)] = [Decimal(x) for x in filter_data.split(':')]
        return filters_ret

    def link_for_page(self, sorting=None, skip_page=True):
        string = ''
        if not sorting and not self.default_sorting:
            string += 'sort-%s/' % self.sort[0]
        if sorting and (sorting != Product.SORT_VARIANTS[0][0]):
            string += 'sort-%s/' % sorting
        if self.filter_string:
            string += 'filter-%s/' % self.filter_string
        if not skip_page and int(self.page) != 1:
            string += 'page-%s/' % self.page

        return self.menu.get_absolute_url() + string

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
        for item in self.filters_order:
            yield (item, self.filters[item])

    def _check_parameter_filter(self, filter_id, filter_data):
        products = self.filter_products(filter_id)
        if FILTERS_NEED_COUNT:
            aviable_parameters_data = ParameterValue.objects.filter(producttoparameter__product__in=products).annotate(total_items=Count('id')).values_list('id', 'total_items')
            aviable_parameters = []
            parameters_counts = {}
            for aviable_parameter, parameter_count in aviable_parameters_data:
                aviable_parameters.append(aviable_parameter)
                parameters_counts[aviable_parameter] = parameter_count
        else:
            aviable_parameters = ProductToParameter.objects.filter(product__in=products).distinct().values_list('value_id', flat=True)
            parameters_counts = {}


        for value_id, value_data in filter_data['values']:
            if FILTERS_NEED_COUNT and value_id in parameters_counts:
                value_data['count'] = parameters_counts[value_id]
            if value_id not in aviable_parameters:
                value_data['unaviable'] = True



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

    def _check_foreignkey_filter(self, filter_id, filter_data):
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


    def _check_range_filter(self, filter_id, filter_data):
        products = self.filter_products(filter_id)
        prices = products.aggregate(max_price=Max('price'), min_price=Min('price'))
        filter_data['min_price'] = None
        filter_data['max_price'] = None

        try:
            filter_data['min_price'] = math.ceil(prices['min_price'])
        except TypeError:
            pass

        try:
            filter_data['max_price'] = math.floor(prices['max_price'])
        except TypeError:
            pass

