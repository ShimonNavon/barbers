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
            "applicant_type",
            "certificate",
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
            "applicant_type": {"required": False},
            "certificate": {"required": False, "allow_null": True},
        }

    def validate_certificate(self, value):
        if value and value.size > 8 * 1024 * 1024:
            raise serializers.ValidationError("הקובץ גדול מדי (עד 8MB).")
        return value
