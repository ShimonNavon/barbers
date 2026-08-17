"""Push landing-page signups (Barbershop rows) into the client's Grist CRM.

Grist is the lightweight CRM the shop owner works in
(crm.barbers.navonsimon.com). Django stays the source of truth for the
signup itself; Grist owns the follow-up columns (status, notes). Every
Barbershop save is upserted by ``django_id`` — Django-sourced columns are
(re)written, the owner's own columns are never touched.

Configured with GRIST_URL / GRIST_API_KEY / GRIST_DOC_ID; if any is missing
the integration is a silent no-op so local dev and tests never need Grist.
"""
import json
import logging
import threading
import urllib.error
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)

TABLE = "Clients"
NEW_STATUS = "חדש"
TIMEOUT = 8  # seconds — the push runs off the request thread anyway


def enabled():
    return bool(settings.GRIST_URL and settings.GRIST_API_KEY
                and settings.GRIST_DOC_ID)


def build_fields(shop):
    """Django-owned Grist columns for a Barbershop row."""
    certificate = ""
    if shop.certificate:
        certificate = settings.PUBLIC_BASE_URL.rstrip("/") + shop.certificate.url
    return {
        "django_id": shop.pk,
        "created_at": int(shop.created_at.timestamp()) if shop.created_at else None,
        "applicant_type": shop.get_applicant_type_display(),
        "owner_name": shop.owner_name,
        "phone": shop.phone,
        "email": shop.email,
        "city": shop.city,
        "business_name": shop.business_name,
        "occupation": shop.get_occupation_display(),
        "sector": shop.get_sector_display(),
        "instagram": shop.instagram,
        "description": shop.description,
        "education": shop.education,
        "certificate": certificate,
        "approved": shop.approved,
    }


def _request(method, path, payload=None, params=""):
    url = f"{settings.GRIST_URL.rstrip('/')}/api/docs/{settings.GRIST_DOC_ID}{path}{params}"
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {settings.GRIST_API_KEY}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read() or b"null")


def upsert(shops, *, created=False):
    """Upsert Barbershop rows by django_id.

    created=True adds rows that don't exist yet (with the initial status);
    created=False only updates existing rows, so a later edit in Django admin
    (e.g. approving a designer) never resurrects a row the owner deleted.
    """
    if not enabled():
        return 0
    records = []
    for shop in shops:
        fields = build_fields(shop)
        if created:
            fields["status"] = NEW_STATUS
        records.append({"require": {"django_id": shop.pk}, "fields": fields})
    if not records:
        return 0
    params = "" if created else "?noadd=true"
    _request("PUT", f"/tables/{TABLE}/records", {"records": records}, params)
    return len(records)


def existing_ids():
    """django_ids already present in Grist (for the backfill command)."""
    data = _request("GET", f"/tables/{TABLE}/records")
    return {r["fields"].get("django_id") for r in data.get("records", [])}


def push_async(shop, created):
    """Fire-and-forget upsert so a Grist hiccup never slows/fails a signup."""
    if not enabled():
        return

    def _run():
        try:
            upsert([shop], created=created)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            log.warning("grist push failed for barbershop %s: %s", shop.pk, exc)

    threading.Thread(target=_run, name=f"grist-push-{shop.pk}", daemon=True).start()
