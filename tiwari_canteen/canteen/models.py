from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Model for Canteen (Tracks canteen details and earnings)
class Canteen(models.Model):
    name = models.CharField(max_length=100)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return self.name

# Model for Menu Item
class MenuItem(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=6, decimal_places=2)  # Price in INR
    quantity = models.PositiveIntegerField()  # Available stock of the item
    available = models.BooleanField(default=True)  # Availability status

    def __str__(self):
        return self.name

    def toggle_availability(self):
        """Toggle the availability status of the menu item."""
        self.available = not self.available
        self.save()

# Model for CartItem (Represents items in the user's cart)
class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # User to whom the cart belongs
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, null=True, blank=True)  # Item in the cart
    quantity = models.PositiveIntegerField()  # Quantity of the item
    added_at = models.DateTimeField(auto_now_add=True)  # Time when the item was added to the cart

    def __str__(self):
        return f"Cart item for {self.user.username} - {self.menu_item.name} ({self.quantity})"

    def update_quantity(self, quantity):
        """Update the quantity of the item in the cart."""
        self.quantity = quantity
        self.save()

    def remove_item(self):
        """Remove this item from the cart."""
        self.delete()

# Model for Order (Represents a confirmed order)
class Order(models.Model):
    STATUS_CHOICES = (
        ('ordered', 'Ordered'),
        ('prepared', 'Prepared'),

        ('delivered', 'Delivered'),
        ('confirmed', 'Confirmed'),
    )
    CONFIRMED = 'confirmed'
    PREPARED = 'prepared'
    DELIVERED= 'delivered'
    ORDERED='ordered'

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ordered')
    ordered_at = models.DateTimeField(auto_now_add=True)
    prepared_at = models.DateTimeField(null=True)
    delivered_at = models.DateTimeField(null=True)

    def __str__(self):
        return f"Order #{self.id} by {self.user.username}"

    def update_quantity(self, item, quantity):
        """Update the quantity of an item in the order."""
        order_item = self.order_items.get(menu_item=item)
        order_item.quantity = quantity
        order_item.save()

    def mark_prepared(self):
        """Mark the order as prepared and update timestamps."""
        if self.status == 'ordered':
            self.status = 'prepared'
            self.prepared_at = timezone.now()  # Corrected timezone usage
            self.save()

    def mark_delivered(self):
        """Mark the order as delivered and update timestamps."""
        if self.status == 'prepared':
            self.status = 'delivered'
            self.delivered_at = timezone.now()
            self.save()

            # Update the earnings for the canteen
            canteen = Canteen.objects.first()  # Assuming there's only one canteen instance
            if canteen:
                canteen.total_earnings += self.total_price  # Add order's total_price to total earnings
                canteen.save()

            # Create an entry in Earnings for the canteen's earnings
            Earnings.objects.create(
                user=self.user,
                order=self,
                amount=self.total_price,
            )

# Intermediate model for many-to-many relationship between Order and MenuItem
class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='order_items', on_delete=models.CASCADE)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()  # Quantity of the item in the order
    total_price = models.DecimalField(max_digits=6, decimal_places=2)  # Total price for this item in the order

    def __str__(self):
        return f"Order Item {self.menu_item.name} for Order #{self.order.id}"

    def update_total_price(self):
        """Update the total price of the item in the order."""
        self.total_price = self.menu_item.price * self.quantity
        self.save()

# Model for Earnings (Tracks earnings from orders)
class Earnings(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Earnings for {self.user.username} on {self.created_at}"

    @classmethod
    def daily_earnings(cls):
        today = timezone.now().date()
        return cls.objects.filter(created_at__date=today)

    @classmethod
    def monthly_earnings(cls):
        today = timezone.now()
        return cls.objects.filter(created_at__year=today.year, created_at__month=today.month)

    @classmethod
    def yearly_earnings(cls):
        today = timezone.now()
        return cls.objects.filter(created_at__year=today.year)