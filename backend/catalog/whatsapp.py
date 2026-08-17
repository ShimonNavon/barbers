"""WhatsApp alert for every new landing-page signup.

Sends through the self-hosted whatsmeow bridge (debian02, /srv/whatsapp-mcp)
— Simon's own WhatsApp number, zero per-message cost. Recipients are a
comma-separated list of E.164 numbers without "+" in LEAD_ALERT_WHATSAPP_TO.
Runs off the request thread; a bridge outage never affects the signup.
"""
import json
import logging
import threading
import urllib.error
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)
TIMEOUT = 10


def enabled():
    return bool(settings.WHATSAPP_BRIDGE_URL and settings.LEAD_ALERT_WHATSAPP_TO)


def recipients():
    return [r.strip().lstrip("+") for r in settings.LEAD_ALERT_WHATSAPP_TO.split(",") if r.strip()]


def build_message(shop):
    kind = "לקוח/ה חדש/ה" if shop.applicant_type == shop.ApplicantType.CLIENT else "מועמדות מעצב/ת שיער"
    lines = [f"✂️ ליד חדש — {kind}", f"שם: {shop.owner_name}", f"טלפון: {shop.phone}"]
    if shop.city:
        lines.append(f"עיר: {shop.city}")
    if shop.applicant_type != shop.ApplicantType.CLIENT:
        lines.append(f"תחום: {shop.get_occupation_display()}")
        if shop.business_name:
            lines.append(f"עסק: {shop.business_name}")
    if settings.CRM_URL:
        lines.append(f"CRM: {settings.CRM_URL}")
    return "\n".join(lines)


def send(recipient, message):
    body = json.dumps({"recipient": recipient, "message": message}).encode()
    req = urllib.request.Request(
        settings.WHATSAPP_BRIDGE_URL.rstrip("/") + "/api/send", data=body,
        method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read() or b"{}")


def notify_async(shop):
    if not enabled():
        return
    message = build_message(shop)

    def _run():
        for r in recipients():
            try:
                res = send(r, message)
                if not res.get("success"):
                    log.warning("whatsapp alert to %s failed: %s", r, res)
            except (urllib.error.URLError, OSError, ValueError) as exc:
                log.warning("whatsapp alert to %s failed: %s", r, exc)

    threading.Thread(target=_run, name=f"wa-alert-{shop.pk}", daemon=True).start()
