from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse_lazy
from django.contrib.auth import logout
from django.db.models import Sum, F
from django.http import HttpResponse
from django.core.mail import send_mail

from .models import MenuItem, Order, Earnings, CartItem, OrderItem

# Earnings Report View
@login_required
def earnings_report(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')

    today_earnings = Earnings.daily_earnings().aggregate(Sum('amount'))['amount__sum'] or 0
    monthly_earnings = Earnings.monthly_earnings().aggregate(Sum('amount'))['amount__sum'] or 0
    yearly_earnings = Earnings.yearly_earnings().aggregate(Sum('amount'))['amount__sum'] or 0

    return render(request, 'canteen/earnings_report.html', {
        'today_earnings': today_earnings,
        'monthly_earnings': monthly_earnings,
        'yearly_earnings': yearly_earnings,
    })

class CustomLoginView(LoginView):
    template_name = 'canteen/login.html'

    def get_success_url(self):
        if self.request.user.is_staff:
            return reverse_lazy('owner_dashboard')
        return reverse_lazy('user_dashboard')

def welcome(request):
    return render(request, 'canteen/welcome.html')

@login_required
def owner_dashboard(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')

    menu_items = MenuItem.objects.filter(quantity__gt=0)
    orders = Order.objects.filter(status__in=['ordered', 'confirmed', 'prepared'])

    if request.method == 'POST':
        if "toggle_availability" in request.POST:
            item_id = request.POST.get("item_id")
            menu_item = get_object_or_404(MenuItem, id=item_id)
            menu_item.available = not menu_item.available
            menu_item.save()
        else:
            order_id = request.POST.get('order_id')
            action = request.POST.get('action')
            try:
                order = Order.objects.get(id=order_id)
                if action == 'confirm':
                    order.status = 'confirmed'
                    order.save()
                elif action == 'accept':
                    order.status = 'prepared'
                    order.prepared_at = timezone.now()
                    order.save()
                    for order_item in order.order_items.all():
                        menu_item = order_item.menu_item
                        menu_item.quantity -= order_item.quantity
                        menu_item.save()
                elif action == 'mark_delivered':
                    order.status = 'delivered'
                    order.delivered_at = timezone.now()
                    order.save()
            except Order.DoesNotExist:
                pass

    return render(request, 'canteen/owner_dashboard.html', {'menu_items': menu_items, 'orders': orders})

@login_required
def add_menu_item(request):
    if not request.user.is_staff:
        return redirect('user_dashboard')

    if request.method == 'POST':
        name = request.POST['name']
        price = request.POST['price']
        quantity = request.POST['quantity']
        available = request.POST.get('available') == 'on'
        MenuItem.objects.create(name=name, price=price, quantity=quantity, available=available)
        messages.success(request, "Menu item added successfully!")
        return redirect('owner_dashboard')

    return render(request, 'canteen/add_menu_items.html')

@login_required
def mark_prepared(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order.status = 'prepared'
    order.save()
    return redirect('owner_dashboard')

@login_required
def mark_delivered(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.status == 'prepared':
        for order_item in order.order_items.all():
            menu_item = order_item.menu_item
            menu_item.quantity -= order_item.quantity
            menu_item.save()
            if menu_item.quantity == 0:
                menu_item.delete()
        order.status = 'delivered'
        order.delivered_at = timezone.now()
        order.save()
        messages.success(request, f"Order {order.id} marked as delivered.")
    else:
        messages.error(request, f"Order {order.id} cannot be marked as delivered because it is not prepared.")
    return redirect('owner_dashboard')

@login_required
def user_dashboard(request):
    menu_items = MenuItem.objects.filter(available=True, quantity__gt=0)
    user_orders = Order.objects.filter(user=request.user)
    cart_items = CartItem.objects.filter(user=request.user)
    total_amount = sum(item.quantity * item.menu_item.price for item in cart_items)
    return render(request, 'canteen/user_dashboard.html', {
        'menu_items': menu_items,
        'user_orders': user_orders,
        'cart_items': cart_items,
        'total_amount': total_amount,
    })

@login_required
def accept_order(request, order_id):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    order = Order.objects.get(id=order_id)
    order.status = 'prepared'
    order.save()
    messages.success(request, f"Order {order.id} marked as prepared.")
    return redirect('owner_dashboard')

@login_required
def delete_order(request, order_id):
    if not request.user.is_staff:
        return redirect('user_dashboard')
    order = Order.objects.get(id=order_id)
    Earnings.objects.create(
        user=request.user,
        order=order,
        amount=order.total_price,
    )
    order.delete()
    messages.success(request, f"Order {order.id} deleted after delivery.")
    return redirect('owner_dashboard')

@login_required
def logout_view(request):
    if request.method == 'POST' and request.POST.get('confirm') == 'yes':
        logout(request)
        return redirect('welcome')
    return render(request, 'canteen/logout_confirm.html')

@login_required
def toggle_availability(request, item_id):
    item = get_object_or_404(MenuItem, id=item_id)
    item.toggle_availability()
    return redirect('owner_dashboard')

@login_required
def add_to_cart(request):
    if request.method == "POST":
        item_id = request.POST['item_id']
        quantity = int(request.POST['quantity'])
        item = MenuItem.objects.get(id=item_id)
        user = request.user
        cart_item, created = CartItem.objects.get_or_create(
            user=user,
            menu_item=item,
            defaults={'quantity': quantity}
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
        return redirect('user_dashboard')

@login_required
def view_cart(request):
    cart_items = CartItem.objects.filter(user=request.user)
    return render(request, 'canteen/cart.html', {'cart_items': cart_items})

@login_required
def update_cart_item(request, cart_item_id):
    try:
        cart_item = CartItem.objects.get(id=cart_item_id, user=request.user)
        if request.method == 'POST':
            new_quantity = request.POST.get('quantity')
            if new_quantity.isdigit() and int(new_quantity) > 0:
                cart_item.quantity = int(new_quantity)
                cart_item.save()
                messages.success(request, "Cart item updated successfully.")
            else:
                messages.error(request, "Invalid quantity.")
    except CartItem.DoesNotExist:
        messages.error(request, "Item not found in cart.")
    return redirect('user_dashboard')

@login_required
def remove_from_cart(request, cart_item_id):
    try:
        cart_item = CartItem.objects.get(id=cart_item_id, user=request.user)
        cart_item.delete()
        messages.success(request, "Item removed from cart.")
    except CartItem.DoesNotExist:
        messages.error(request, "Item not found in cart.")
    return redirect('user_dashboard')

@login_required
def cancel_order(request):
    CartItem.objects.filter(user=request.user).delete()
    messages.success(request, "Your cart has been cleared.")
    return redirect('user_dashboard')

@login_required
def confirm_order(request):
    cart_items = CartItem.objects.filter(user=request.user)
    total_amount = sum(item.menu_item.price * item.quantity for item in cart_items)
    if request.method == 'POST':
        order = Order.objects.create(
            user=request.user,
            total_price=total_amount,
            status='confirmed'
        )
        for item in cart_items:
            order_item_total_price = item.menu_item.price * item.quantity
            OrderItem.objects.create(
                order=order,
                menu_item=item.menu_item,
                quantity=item.quantity,
                total_price=order_item_total_price
            )
            item.delete()
        return redirect('order_confirmed', order_id=order.id)
    return render(request, 'canteen/confirm_order.html', {
        'cart_items': cart_items,
        'total_amount': total_amount
    })

def order_confirmation_page(request, order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return render(request, 'canteen/404.html')
    order_status = order.status
    return render(request, 'canteen/order_confirmed.html', {
        'order': order,
        'order_status': order_status
    })

def order_confirmed(request, order_id=None):
    if order_id is None:
        return render(request, 'canteen/order_confirmed.html', {
            'order_status': "No specific order selected.",
            'order': None,
            'order_items': None,
            'total_price': 0
        })
    else:
        order = get_object_or_404(Order, id=order_id)
        order_items = order.order_items.all()
        total_price = sum(item.quantity * item.total_price for item in order_items)
        return render(request, 'canteen/order_confirmed.html', {
            'order_status': "Order Confirmed!",
            'order': order,
            'order_items': order_items,
            'total_price': total_price
        })

@login_required
def owner_mark_prepared(request, order_id):
    order = Order.objects.get(id=order_id)
    order.status = Order.PREPARED
    order.save()
    return redirect('order_confirmed')

def update_order_status(request, order_id):
    order = Order.objects.get(id=order_id)
    if request.POST.get('mark_prepared'):
        order.status = 'prepared'
        order.save()
    elif request.POST.get('mark_delivered'):
        order.status = 'delivered'
        order.save()
    return redirect('owner_dashboard')
