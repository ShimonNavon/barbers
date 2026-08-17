from django.db.models.signals import post_save
from django.dispatch import receiver

from . import grist, whatsapp
from .models import Barbershop


@receiver(post_save, sender=Barbershop, dispatch_uid="catalog.grist_push")
def push_barbershop_to_grist(sender, instance, created, **kwargs):
    if kwargs.get("raw"):  # loaddata fixtures
        return
    grist.push_async(instance, created)
    if created:
        whatsapp.notify_async(instance)
