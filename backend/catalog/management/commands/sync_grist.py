"""Backfill / repair the Grist CRM from the Barbershop table.

    manage.py sync_grist          # add missing rows, refresh existing ones
    manage.py sync_grist --dry-run

Safe to re-run: rows are matched by django_id; the owner's status/notes
columns are never overwritten (only brand-new rows get status "חדש").
"""
from django.core.management.base import BaseCommand, CommandError

from catalog import grist
from catalog.models import Barbershop


class Command(BaseCommand):
    help = "Upsert every Barbershop signup into the Grist CRM"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        if not grist.enabled():
            raise CommandError("GRIST_URL / GRIST_API_KEY / GRIST_DOC_ID not configured")
        present = grist.existing_ids()
        shops = list(Barbershop.objects.order_by("created_at"))
        new = [s for s in shops if s.pk not in present]
        old = [s for s in shops if s.pk in present]
        self.stdout.write(f"{len(shops)} signups: {len(new)} to add, {len(old)} to refresh")
        if opts["dry_run"]:
            return
        # Grist upserts in one call; chunk to keep payloads modest.
        for i in range(0, len(new), 200):
            grist.upsert(new[i:i + 200], created=True)
        for i in range(0, len(old), 200):
            grist.upsert(old[i:i + 200], created=False)
        self.stdout.write(self.style.SUCCESS("done"))
