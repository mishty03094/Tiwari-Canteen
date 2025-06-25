#canteen/forms.py
from django import forms
from .models import MenuItem, Order

class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ['name', 'price', 'quantity', 'available']

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['menu_item', 'quantity']
