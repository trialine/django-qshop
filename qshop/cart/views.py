import re

from django.contrib import messages
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, FormView, TemplateView

from qshop import qshop_settings
from qshop.qshop_settings import CART_CLASS, CART_ORDER_VIEW, REDIRECT_CLASS

from ..models import Product
from .cart import ItemTooMany
from .forms import OrderForm
from .models import Order

if CART_CLASS:
    from sitemenu import import_item
    Cart = import_item(CART_CLASS)
else:
    from .cart import Cart


def add_to_cart(request, product_id):
    cart = Cart(request)

    quantity = request.GET.get('quantity', 1)
    variation_id = request.GET.get('variation', None)
    variation_quantities = {}

    if not variation_id:
        variation_quantity_re = re.compile('^variation_quantity_(\d+)$')
        for item in request.GET:
            match = variation_quantity_re.match(item)
            if match:
                try:
                    variation_quantities[int(match.group(1))] = int(request.GET.get(item))
                except ValueError:
                    pass

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        messages.add_message(request, messages.ERROR, _('Wrong product.'))
    else:
        result = False
        if not variation_quantities:
            product.select_variation(variation_id)
            try:
                if cart.add(product, quantity):
                    result = True
            except ItemTooMany as e:
                messages.add_message(
                    request, messages.WARNING, _(u'Can\'t add product "%s" due to lack in stock. Try to decrease quantity.') % e.product
                )
        else:
            for k, v in variation_quantities.items():
                product.select_variation(k)
                try:
                    if cart.add(product, v):
                        result = True
                except ItemTooMany as e:
                    messages.add_message(
                        request, messages.WARNING, _(u'Can\'t add product "%s" due to lack in stock. Try to decrease quantity.') % e.product
                    )

        if result:
            messages.add_message(request, messages.INFO, _(u'Product added to <a href="%s">cart</a>.') % reverse('cart'))

    return_url = request.GET.get('return_url', None)

    request._server_cache = {'set_cookie': True}
    if return_url:
        return REDIRECT_CLASS(return_url)
    return REDIRECT_CLASS(reverse('cart'))


def remove_from_cart(request, item_id):
    cart = Cart(request)
    cart.remove(item_id)

    request._server_cache = {'set_cookie': True}
    return REDIRECT_CLASS(reverse('cart'))


def update_cart(request):
    cart = Cart(request)
    for (key, quantity) in request.POST.items():
        if not key.startswith('quantity.'):
            continue
        try:
            item_id = int(key.replace('quantity.', ''))
        except:
            continue

        try:
            quantity = int(quantity)
            cart.update(item_id, quantity)
        except ItemTooMany as e:
            messages.add_message(
                request, messages.WARNING, _(u'Can\'t add product "%s" due to lack in stock. Try to decrease quantity.') % e.product
            )

    request._server_cache = {'set_cookie': True}
    return REDIRECT_CLASS(reverse('cart'))


class CartDetailView(TemplateView):
    template_name = "qshop/cart/cart.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cart'] = Cart(self.request)
        if qshop_settings.ENABLE_PROMO_CODES:
            context['apply_promo_form'] = ApplyPromoForm()
        return context


class OrderDetailView(CreateView):
    form_class = OrderForm
    template_name = 'qshop/cart/order_extended.html'

    @property
    def cart(self):
        cart = Cart(self.request)
        return cart

    def dispatch(self, request, *args, **kwargs):
        if self.cart.total_products() < 1:
            return REDIRECT_CLASS(reverse('cart'))
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super(OrderDetailView, self).get_form_kwargs()
        kwargs['cart'] = self.cart
        return kwargs

    def form_valid(self, form):
        try:
            order = form.save()
            order.finish_order(self.request)
            self.request.session['order_pk'] = order.pk
            return order.get_redirect_response()
        except ItemTooMany:
            messages.add_message(self.request, messages.WARNING, _('Someone already bought product that you are trying to buy.'))

        return super(OrderDetailView, self).form_valid(form)


class AjaxOrderDetailView(OrderDetailView):
    # need to return cart html always even if form_valid, because we need to show refreshed cart items before checkout
    def form_valid(self, form):
        return self.form_invalid(form)

    def form_invalid(self, form):
        # remove html errors from fields
        fnames_errors = list(form.errors.keys())
        for field_name in fnames_errors:
            form.errors.pop(field_name)

        return super().form_invalid(form)


def cart_order_success(request):
    order_pk = request.session.get('order_pk', None)
    try:
        del request.session['order_pk']
    except Exception:
        pass
    try:
        order = Order.objects.get(pk=order_pk)
    except Exception:
        return REDIRECT_CLASS('/')
    return render(request, 'qshop/cart/order_success.html', {
        'order': order,
    })


@csrf_exempt
def cart_order_cancelled(request, order_id=None):
    if order_id:
        order = get_object_or_404(Order, pk=order_id, paid=False)
        order.status = 4
        order.add_log_message('Order canceled!')
        order.save()
    return render(request, 'qshop/cart/order_cancelled.html', {
    })


def cart_order_error(request):
    return render(request, 'qshop/cart/order_error.html', {
    })


if CART_ORDER_VIEW:
    from sitemenu import import_item
    qshop_order_view = import_item(CART_ORDER_VIEW)


def order_cart(request):
    if CART_ORDER_VIEW:
        return qshop_order_view(request)

    cart = Cart(request)

    order_form = OrderForm()

    if request.method == 'POST':
        order_form = OrderForm(request.POST)

        if order_form.is_valid():
            try:
                order = order_form.save(cart)
                request.session['order_pk'] = order.pk
                cart.checkout()
                order.finish_order(request)
                return order.get_redirect_response()
            except ItemTooMany:
                messages.add_message(request, messages.WARNING, _('Someone already bought product that you are trying to buy.'))

    if cart.total_products() < 1:
        return REDIRECT_CLASS(reverse('cart'))

    return render(request, 'qshop/cart/order.html', {
        'cart': cart,
        'order_form': order_form,
    })


if qshop_settings.ENABLE_PROMO_CODES:
    from .forms import ApplyPromoForm

    class ApplyPromoView(FormView):
        form_class = ApplyPromoForm
        template_name = 'qshop/cart/cart.html'

        def get_success_url(self):
            messages.add_message(self.request, messages.INFO, _(u'Promo code applied successfully.'))
            return reverse('cart')

        def get_context_data(self, **kwargs):
            kwargs = super(ApplyPromoView, self).get_context_data(**kwargs)
            kwargs['cart'] = Cart(self.request)
            kwargs['apply_promo_form'] = kwargs['form']
            return kwargs

        def get_form_kwargs(self):
            kwargs = super(ApplyPromoView, self).get_form_kwargs()
            kwargs['cart'] = Cart(self.request)
            return kwargs

        def form_valid(self, form):
            form.cart.set_promo_code(form.promo_code)
            return super(ApplyPromoView, self).form_valid(form)
