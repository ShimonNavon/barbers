from rest_framework.generics import CreateAPIView
from rest_framework.throttling import AnonRateThrottle

from .models import Barbershop
from .serializers import BarbershopSerializer


class BarbershopThrottle(AnonRateThrottle):
    scope = "barbershops"


class BarbershopCreateView(CreateAPIView):
    queryset = Barbershop.objects.all()
    serializer_class = BarbershopSerializer
    throttle_classes = [BarbershopThrottle]
