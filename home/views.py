from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, Count
from django.contrib.auth.models import User
from .models import Product, Order
from django.shortcuts import render, redirect, get_object_or_404
import random
from django.utils import timezone
import datetime
from django.conf import settings
import requests

# ---------------------------
# Login View
# ---------------------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        # Attempt to get user by email
        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(
                request,
                username=user_obj.username,
                password=password
            )
        except User.DoesNotExist:
            user = None

        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid email or password.')

    return render(request, 'login.html')


def logout_view(request):
    """
    Logs out the user and redirects to login page.
    """
    logout(request)  # Clears the session and logs out
    messages.success(request, "You have been successfully logged out.")
    return redirect('login')  # Replace 'login' with your login URL name



# ---------------------------
# Dashboard View
# ---------------------------
@login_required
def dashboard(request):
    # -----------------------------
    # Summary Metrics
    # -----------------------------
    total_products = Product.objects.count()
    active_products = Product.objects.filter(status='active').count()
    inactive_products = Product.objects.filter(status='inactive').count()

    total_orders = Order.objects.filter(status='completed').count()
    total_units_sold = Order.objects.filter(status='completed').aggregate(total=Sum('quantity'))['total'] or 0
    total_revenue = Order.objects.filter(status='completed').aggregate(total=Sum('total_price'))['total'] or 0

    # Total cost = sum of product costs (one-time cost per product)
    total_cost = Product.objects.aggregate(total=Sum('cost'))['total'] or 0
    total_profit = total_revenue - total_cost

    # Most Selling Product
    most_selling_product = Product.objects.annotate(units_sold=Sum('orders__quantity')) \
                                          .filter(orders__status='completed') \
                                          .order_by('-units_sold').first()

    # Most Profitable Product
    most_profitable_product = Product.objects.annotate(total_profit=(F('price') - F('cost')) * Sum('orders__quantity')) \
                                             .filter(orders__status='completed') \
                                             .order_by('-total_profit').first()

    # Products Generated Today
    today = timezone.now().date()
    products_generated_today = Product.objects.filter(created_at__date=today).count()
    daily_quota = 10  # Example daily quota; replace as needed

    # Recent Products (last 5)
    recent_products = Product.objects.order_by('-created_at')[:5]

    # Recent Orders (last 5)
    recent_orders = Order.objects.select_related('product').order_by('-created_at')[:5]

    # -----------------------------
    # Etsy Integration (Optional)
    # -----------------------------
    etsy_data = None
    profile = getattr(request.user, 'profile', None)
    access_token = getattr(profile, 'etsy_access_token', None)

    if access_token:
        try:
            # Example: Fetch shop listings
            shop_id = "YOUR_SHOP_ID"  # Replace with actual shop ID
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(f"https://openapi.etsy.com/v3/application/shops/{shop_id}/listings", headers=headers)
            if response.status_code == 200:
                etsy_data = response.json()
            else:
                etsy_data = {'error': f"Failed to fetch Etsy data: {response.status_code}"}
        except Exception as e:
            etsy_data = {'error': str(e)}

    # -----------------------------
    # Context for Template
    # -----------------------------
    context = {
        # Summary Cards
        'total_products': total_products,
        'active_products': active_products,
        'inactive_products': inactive_products,
        'total_orders': total_orders,
        'products_sold': total_units_sold,
        'total_revenue': total_revenue,
        'total_cost': total_cost,
        'total_profit': total_profit,
        'most_selling_product': most_selling_product,
        'most_profitable_product': most_profitable_product,
        'products_generated_today': products_generated_today,
        'daily_quota': daily_quota,

        # Recent Activity
        'recent_products': recent_products,
        'recent_orders': recent_orders,

        # Etsy Data
        'etsy_data': etsy_data,
    }

    return render(request, 'dashboard.html', context)


# ---------------------------
# Products List (Read-Only)
# ---------------------------
@login_required
def products_list(request):
    """
    Display all products in read-only mode.
    """
    products = Product.objects.order_by('-created_at')
    return render(request, 'products.html', {'products': products})


# ---------------------------
# Orders List (Read-Only)
# ---------------------------
@login_required
def orders_list(request):
    """
    Display all orders in read-only mode with extended details and summary metrics.
    """
    # Fetch all orders with related product and user to avoid extra queries
    orders = Order.objects.select_related('product', 'user').order_by('-created_at')

    # Summary metrics
    total_orders = orders.count()
    completed_orders = orders.filter(status='completed').count()
    pending_orders = orders.filter(status='pending').count()
    total_revenue = orders.aggregate(total=Sum('total_price'))['total'] or 0

    # Total profit = recurring profit: total revenue minus sum of one-time product costs (per order)
    total_profit = sum(o.total_price - o.product.cost for o in orders)

    # Product-wise summary for optional table
    products = Product.objects.all()
    product_summary = []
    for p in products:
        units_sold = orders.filter(product=p, status='completed').aggregate(total=Sum('quantity'))['total'] or 0
        total_revenue_product = units_sold * p.price
        total_profit_product = total_revenue_product - p.cost  # recurring profit
        product_summary.append({
            'name': p.name,
            'units_sold': units_sold,
            'total_revenue': total_revenue_product,
            'cost': p.cost,
            'total_profit': total_profit_product,
            'status': p.status,
        })

    context = {
        'orders': orders,
        'total_orders': total_orders,
        'completed_orders': completed_orders,
        'pending_orders': pending_orders,
        'total_revenue': total_revenue,
        'total_profit': total_profit,
        'product_summary': product_summary,
    }

    return render(request, 'orders.html', context)



@login_required
def revenue_dashboard(request):
    """
    Revenue dashboard with detailed metrics:
    - One-time product cost
    - Recurring profit
    - Sales, profitability, popularity, customer metrics
    """
    # -----------------------------
    # Global Metrics
    # -----------------------------
    completed_orders = Order.objects.filter(status='completed')
    total_orders = completed_orders.aggregate(total=Count('id'))['total'] or 0
    total_units = completed_orders.aggregate(total=Sum('quantity'))['total'] or 0
    total_revenue = completed_orders.aggregate(total=Sum('total_price'))['total'] or 0

    # Total cost = sum of all product one-time costs
    total_cost = Product.objects.aggregate(total=Sum('cost'))['total'] or 0

    # Total profit = recurring revenue minus one-time cost
    total_profit = total_revenue - total_cost
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0

    # -----------------------------
    # Product Metrics
    # -----------------------------
    products = Product.objects.all()
    product_data = []
    for p in products:
        units_sold = p.total_quantity_sold
        revenue = p.total_revenue
        cost = p.cost
        profit = revenue - cost
        product_data.append({
            'name': p.name,
            'category': getattr(p, 'category', 'N/A'),
            'style': getattr(p, 'style', 'N/A'),
            'units_sold': units_sold,
            'total_revenue': revenue,
            'total_cost': cost,
            'total_profit': profit,
            'status': p.status,
            'views': getattr(p, 'views', 0),
        })

    # Most profitable / selling products
    most_profitable_product = max(product_data, key=lambda x: x['total_profit'], default=None)
    most_sold_product = max(product_data, key=lambda x: x['units_sold'], default=None)
    top_5_products = sorted(product_data, key=lambda x: x['units_sold'], reverse=True)[:5]

    # Trending products (e.g., sold in last 7 days)
    last_week = timezone.now() - datetime.timedelta(days=7)
    trending_products = []
    for p in products:
        recent_sales = Order.objects.filter(product=p, status='completed', created_at__gte=last_week).aggregate(total=Sum('quantity'))['total'] or 0
        trending_products.append({'name': p.name, 'units_sold': recent_sales})
    trending_products = sorted(trending_products, key=lambda x: x['units_sold'], reverse=True)[:5]

    # -----------------------------
    # Customer Metrics
    # -----------------------------
    users_with_orders = User.objects.filter(order__status='completed').distinct()
    active_customers = users_with_orders.count()
    repeat_customers = sum(1 for u in users_with_orders if u.order_set.filter(status='completed').count() > 1)
    avg_orders_per_customer = (total_orders / active_customers) if active_customers > 0 else 0

    pending_orders = Order.objects.filter(status='pending').count()
    completed_orders_count = total_orders
    canceled_orders = Order.objects.filter(status='canceled').count()

    # -----------------------------
    # Operational Metrics
    # -----------------------------
    revenue_per_generated_product = (total_revenue / products.count()) if products.exists() else 0
    cost_efficiency = ((total_profit / total_cost) * 100) if total_cost > 0 else 0
    avg_production_time = getattr(request, 'avg_production_time', 0)  # placeholder
    forecasted_revenue = getattr(request, 'forecasted_revenue', 0)  # placeholder

    # -----------------------------
    # Context
    # -----------------------------
    context = {
        'total_orders': total_orders,
        'total_units': total_units,
        'total_revenue': total_revenue,
        'total_cost': total_cost,
        'total_profit': total_profit,
        'avg_order_value': round(avg_order_value, 2),
        'profit_margin': round(profit_margin, 2),
        'products': product_data,
        'most_profitable_product': most_profitable_product,
        'most_sold_product': most_sold_product,
        'top_5_products': top_5_products,
        'trending_products': trending_products,
        'active_customers': active_customers,
        'repeat_customers': repeat_customers,
        'avg_orders_per_customer': round(avg_orders_per_customer, 2),
        'pending_orders': pending_orders,
        'completed_orders': completed_orders_count,
        'canceled_orders': canceled_orders,
        'revenue_per_generated_product': round(revenue_per_generated_product, 2),
        'cost_efficiency': round(cost_efficiency, 2),
        'avg_production_time': avg_production_time,
        'forecasted_revenue': forecasted_revenue,
    }

    return render(request, 'revenue.html', context)


@login_required
def generate_products(request):
    """
    Generate multiple digital products at once with randomized prices and costs.
    """
    generated_products = []

    if request.method == 'POST':
        count = int(request.POST.get('count', 0))
        base_name = request.POST.get('base_name', 'Product')
        status = request.POST.get('status', 'active')

        if count < 1:
            messages.error(request, 'Please enter a valid number of products.')
            return redirect('generate_products')

        for i in range(1, count + 1):
            name = f"{base_name} #{i}"
            price = round(random.uniform(5, 50), 2)  # Price between $5 and $50
            cost = round(random.uniform(1, price - 1), 2)  # Cost less than price
            product = Product(name=name, price=price, cost=cost, status=status)
            product.save()
            generated_products.append(product)

        messages.success(request, f'{count} products generated successfully!')

    return render(request, 'generate_products.html', {'generated_products': generated_products})


# Step 1: Redirect user to Etsy OAuth
@login_required
def etsy_login(request):
    client_id = settings.ETSY_CLIENT_ID
    redirect_uri = settings.ETSY_REDIRECT_URI
    scope = "listings_r transactions_r"  # Required permissions

    auth_url = (
        "https://www.etsy.com/oauth/connect?"
        f"response_type=code&client_id={client_id}"
        f"&redirect_uri={redirect_uri}&scope={scope}"
    )
    return redirect(auth_url)

# Step 2: Public callback endpoint to receive Etsy code
def etsy_callback(request):
    code = request.GET.get('code')
    if not code:
        return redirect('/dashboard/?error=no_code')

    # Exchange code for access token
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.ETSY_CLIENT_ID,
        "client_secret": settings.ETSY_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.ETSY_REDIRECT_URI
    }
    response = requests.post("https://api.etsy.com/v3/public/oauth/token", data=data)
    token_data = response.json()

    # Save access token to database for the logged-in user
    if request.user.is_authenticated:
        request.user.profile.etsy_access_token = token_data.get("access_token")
        request.user.profile.save()

    # Redirect to private dashboard
    return redirect('/dashboard/?etsy_connected=1')





# Step 1: Redirect user to Canva OAuth
@login_required
def canva_login(request):
    client_id = settings.CANVA_CLIENT_ID
    redirect_uri = settings.CANVA_REDIRECT_URI
    scope = "design:read design:write"  # Example scopes
    auth_url = (
        f"https://www.canva.com/oauth2/authorize?"
        f"response_type=code&client_id={client_id}"
        f"&redirect_uri={redirect_uri}&scope={scope}"
    )
    return redirect(auth_url)

# Step 2: Canva callback handler (public endpoint)
def canva_callback(request):
    code = request.GET.get('code')
    if not code:
        return render(request, 'canva_callback.html', {
            'success': False,
            'message': 'Authorization code not provided by Canva.'
        })

    # Exchange code for access token
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.CANVA_CLIENT_ID,
        "client_secret": settings.CANVA_CLIENT_SECRET,
        "redirect_uri": settings.CANVA_REDIRECT_URI,
        "code": code
    }

    try:
        response = requests.post("https://api.canva.com/v1/oauth/token", data=data)
        token_data = response.json()
    except Exception as e:
        return render(request, 'canva_callback.html', {
            'success': False,
            'message': f"Error contacting Canva API: {e}"
        })

    access_token = token_data.get("access_token")
    if not access_token:
        return render(request, 'canva_callback.html', {
            'success': False,
            'message': token_data.get("error_description", "Unknown error occurred.")
        })

    # Save token to user profile
    profile = getattr(request.user, 'profile', None)
    if profile:
        profile.canva_access_token = access_token
        profile.save()

    return render(request, 'canva_callback.html', {'success': True})