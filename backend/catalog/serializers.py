from rest_framework import serializers

from .models import Barbershop


class BarbershopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Barbershop
        fields = [
            "business_name",
            "owner_name",
            "phone",
            "city",
            "address",
            "description",
            "instagram",
            "sector",
            "education",
        ]
        extra_kwargs = {
            "sector": {"required": True},
            "education": {"required": True, "allow_blank": False},
        }
