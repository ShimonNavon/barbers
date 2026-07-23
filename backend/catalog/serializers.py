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
            # only name + phone are mandatory; everything else falls back to
            # blank / model defaults
            "owner_name": {"required": True, "allow_blank": False},
            "phone": {"required": True, "allow_blank": False},
            "occupation": {"required": False},
            "sector": {"required": False},
            "city": {"required": False, "allow_blank": True},
            "email": {"required": False, "allow_blank": True},
            "education": {"required": False, "allow_blank": True},
            # TextField has no model-level bound — cap it here
            "description": {"required": False, "allow_blank": True, "max_length": 1000},
        }
