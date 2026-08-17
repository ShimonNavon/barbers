"""WhatsApp alert for every new landing-page signup.

Two transports, chosen by settings:
  * Meta WhatsApp Cloud API (official business sender, approved template
    ``new_lead_alert``) — WHATSAPP_CLOUD_TOKEN + WHATSAPP_CLOUD_PHONE_ID.
  * Self-hosted whatsmeow bridge (Simon's own number) — WHATSAPP_BRIDGE_URL.
Cloud API wins when configured. Recipients: LEAD_ALERT_WHATSAPP_TO, a
comma-separated list of E.164 numbers without "+". Runs off the request
thread; a delivery failure never affects the signup.
"""
import json
import logging
import threading
import urllib.error
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)
TIMEOUT = 10
GRAPH = "https://graph.facebook.com/v21.0"


def cloud_enabled():
    return bool(settings.WHATSAPP_CLOUD_TOKEN and settings.WHATSAPP_CLOUD_PHONE_ID)


def enabled():
    return bool(settings.LEAD_ALERT_WHATSAPP_TO) and (cloud_enabled() or bool(settings.WHATSAPP_BRIDGE_URL))


def recipients():
    return [r.strip().lstrip("+") for r in settings.LEAD_ALERT_WHATSAPP_TO.split(",") if r.strip()]


def lead_type(shop):
    return "לקוח/ה חדש/ה" if shop.applicant_type == shop.ApplicantType.CLIENT else "מועמדות מעצב/ת שיער"


def build_message(shop):
    """Free-text version (bridge transport)."""
    lines = [f"✂️ ליד חדש — {lead_type(shop)}", f"שם: {shop.owner_name}", f"טלפון: {shop.phone}"]
    if shop.city:
        lines.append(f"עיר: {shop.city}")
    if shop.applicant_type != shop.ApplicantType.CLIENT:
        lines.append(f"תחום: {shop.get_occupation_display()}")
        if shop.business_name:
            lines.append(f"עסק: {shop.business_name}")
    if settings.CRM_URL:
        lines.append(f"CRM: {settings.CRM_URL}")
    return "\n".join(lines)


def _param(name, value):
    # template params may not contain newlines/tabs or >4 consecutive spaces
    return {"type": "text", "parameter_name": name, "text": " ".join(str(value or "—").split()) or "—"}


def build_template_payload(shop, recipient):
    """Cloud API payload for the approved ``new_lead_alert`` (he) template."""
    kind = lead_type(shop)
    if shop.applicant_type != shop.ApplicantType.CLIENT:
        kind = f"{kind} · {shop.get_occupation_display()}"
    return {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "template",
        "template": {
            "name": settings.WHATSAPP_CLOUD_TEMPLATE,
            "language": {"code": "he"},
            "components": [{"type": "body", "parameters": [
                _param("lead_type", kind),
                _param("name", shop.owner_name),
                _param("phone", shop.phone),
                _param("city", shop.city),
            ]}],
        },
    }


def _post(url, payload, headers=None):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read() or b"{}")


def send_cloud(shop, recipient):
    return _post(f"{GRAPH}/{settings.WHATSAPP_CLOUD_PHONE_ID}/messages",
                 build_template_payload(shop, recipient),
                 {"Authorization": f"Bearer {settings.WHATSAPP_CLOUD_TOKEN}"})


def send_bridge(recipient, message):
    return _post(settings.WHATSAPP_BRIDGE_URL.rstrip("/") + "/api/send",
                 {"recipient": recipient, "message": message})


def deliver(shop, recipient):
    if cloud_enabled():
        res = send_cloud(shop, recipient)
        ok = bool(res.get("messages"))
    else:
        res = send_bridge(recipient, build_message(shop))
        ok = bool(res.get("success"))
    if not ok:
        log.warning("whatsapp alert to %s failed: %s", recipient, res)
    return ok


def notify_async(shop):
    if not enabled():
        return

    def _run():
        for r in recipients():
            try:
                deliver(shop, r)
            except urllib.error.HTTPError as exc:
                log.warning("whatsapp alert to %s failed: %s %s", r, exc.code, exc.read()[:300])
            except (urllib.error.URLError, OSError, ValueError) as exc:
                log.warning("whatsapp alert to %s failed: %s", r, exc)

    threading.Thread(target=_run, name=f"wa-alert-{shop.pk}", daemon=True).start()
