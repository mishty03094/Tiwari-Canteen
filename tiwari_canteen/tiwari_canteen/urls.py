from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('canteen.urls')),  # This includes all URLs from your canteen app
]
