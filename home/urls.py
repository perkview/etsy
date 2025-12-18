from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('products/', views.products_list, name='products'),
    path('orders/', views.orders_list, name='orders'),
    path('revenue/', views.revenue_dashboard, name='revenue'),
    path('generate-products/', views.generate_products, name='generate_products'),

    
    path('etsy/login/', views.etsy_login, name='etsy_login'),       # Initiates OAuth
    path('etsy/callback/', views.etsy_callback, name='etsy_callback'), # Public endpoint for Etsy

    
    path('canva/callback/', views.canva_callback, name='canva_callback'),
    path('canva/login/', views.canva_login, name='canva_login'),  # Optional: button to start auth
]
