from rest_framework import serializers

from .models import Barbershop


class BarbershopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Barbershop
        fields = [
            "business_name",
            "owner_name",
            "phone",
            "email",
            "city",
            "address",
            "description",
            "instagram",
            "sector",
            "education",
        ]
        extra_kwargs = {
            "email": {"required": True, "allow_blank": False},
            "sector": {"required": True},
            "education": {"required": True, "allow_blank": False},
        }
