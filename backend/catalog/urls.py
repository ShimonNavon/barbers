from django.urls import path

from .views import BarbershopCreateView

urlpatterns = [
    path("barbershops/", BarbershopCreateView.as_view(), name="barbershop-create"),
]
