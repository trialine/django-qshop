from django.conf import settings
from django.contrib import admin

from qshop.qshop_settings import CART_ORDER_CUSTOM_ADMIN, ENABLE_QSHOP_DELIVERY

if not CART_ORDER_CUSTOM_ADMIN and not ENABLE_QSHOP_DELIVERY:
    from django.contrib import admin
    from .models import Order

    @admin.register(Order)
    class OrderAdmin(admin.ModelAdmin):
        # form = OrderAdminForm
        list_display = ('pk', '__str__', 'status', 'date_added')
        list_display_links = ('pk', '__str__')
        list_filter = ('status',)
        ordering = ['-date_added']
        readonly_fields = ('name', 'phone', 'email', 'get_cart_text', 'get_comments')
        exclude = ('comments',)

        # def changelist_view(self, request, extra_context=None):

        #     test = request.META['HTTP_REFERER'].split(request.META['PATH_INFO'])
        #     if test[-1] and not test[-1].startswith('?'):
        #         if not 'paid__exact' in request.GET:
        #             q = request.GET.copy()
        #             q['paid__exact'] = '1'
        #             request.GET = q
        #             request.META['QUERY_STRING'] = request.GET.urlencode()
        #     return super(OrderAdmin, self).changelist_view(request, extra_context=extra_context)


if 'modeltranslation' in settings.INSTALLED_APPS:
    from modeltranslation.admin import TranslationAdmin, TranslationTabularInline, TranslationStackedInline

    USE_TRANSLATION = True
    parent_classes_translation = {
        'ModelAdmin': TranslationAdmin,
        'TabularInline': TranslationTabularInline,
        'StackedInline': TranslationStackedInline,
    }
else:
    USE_TRANSLATION = False


if ENABLE_QSHOP_DELIVERY:
    from .models import DeliveryCountry, DeliveryType, DeliveryCalculation
    from qshop.admin import getParentClass

    @admin.register(DeliveryCountry)
    class DeliveryCountryAdmin(getParentClass('ModelAdmin', DeliveryCountry)):
        list_display = ['title', 'iso2_code',  'vat_behavior', 'can_draw_up_an_invoice', 'sort_order']
        list_editable = ['sort_order']
        list_filter = ['vat_behavior', 'can_draw_up_an_invoice']


    class DeliveryCalculationInline(admin.TabularInline):
        model = DeliveryCalculation

    @admin.register(DeliveryType)
    class DeliveryTypeAdmin(getParentClass('ModelAdmin', DeliveryType)):
        list_display = ['title', 'countries_html', 'delivery_calculation',  'calculation_html']
        filter_horizontal = ['delivery_country']
        list_filter = ['delivery_country', 'delivery_calculation', 'delivery_country__vat_behavior']
        inlines = [DeliveryCalculationInline]


    if not CART_ORDER_CUSTOM_ADMIN:
        from .models import Order

        @admin.register(Order)
        class OrderAdmin(admin.ModelAdmin):
            # form = OrderAdminForm
            list_display = ('pk', '__str__', 'status', 'cart_price', 'date_added')
            list_display_links = ('pk', '__str__')
            list_filter = ('status',)
            ordering = ['-date_added']
            readonly_fields = ('get_cart_text',)
