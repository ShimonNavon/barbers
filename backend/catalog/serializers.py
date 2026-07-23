from rest_framework import serializers

from .models import Barbershop


class BarbershopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Barbershop
        fields = [
            "owner_name",
            "occupation",
            "phone",
            "email",
            "city",
            "description",
            "sector",
            "education",
        ]
        extra_kwargs = {
            "email": {"required": True, "allow_blank": False},
            "occupation": {"required": True},
            "sector": {"required": True},
            "education": {"required": True, "allow_blank": False},
        }
