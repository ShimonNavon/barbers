from rest_framework.generics import CreateAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.throttling import AnonRateThrottle

from .models import Barbershop
from .serializers import BarbershopSerializer


class BarbershopThrottle(AnonRateThrottle):
    scope = "barbershops"


class BarbershopCreateView(CreateAPIView):
    queryset = Barbershop.objects.all()
    serializer_class = BarbershopSerializer
    throttle_classes = [BarbershopThrottle]
    # JSON for the client waitlist form, multipart for the designer
    # application pop-up (optional certificate upload)
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    # Public, anonymous, rate-limited endpoint. Disable DRF's default
    # SessionAuthentication so its CSRF check never fires for visitors who
    # happen to hold an admin session cookie (they would otherwise get a 403).
    authentication_classes = []
