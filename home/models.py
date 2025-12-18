from django.db import models
from django.contrib.auth.models import User

# --------------------------
# Digital Product
# --------------------------
class Product(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def profit(self):
        """Profit per single product"""
        return self.price - self.cost

    @property
    def orders_completed(self):
        """Number of completed orders for this product"""
        return self.orders.filter(status='completed').count()

    @property
    def total_revenue(self):
        """Total revenue from completed orders"""
        completed_orders = self.orders.filter(status='completed')
        return sum(order.total_price for order in completed_orders)

    @property
    def total_quantity_sold(self):
        """Total quantity sold across completed orders"""
        completed_orders = self.orders.filter(status='completed')
        return sum(order.quantity for order in completed_orders)

    def __str__(self):
        return self.name


# --------------------------
# Orders / Purchases
# --------------------------
class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='orders')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Automatically calculate total price
        self.total_price = self.product.price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} x {self.quantity} by {self.user.email}"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    etsy_access_token = models.CharField(max_length=255, blank=True, null=True)
    canva_access_token = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.user.username