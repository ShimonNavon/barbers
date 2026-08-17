from unittest import mock

from django.test import TestCase, override_settings

from catalog import whatsapp
from catalog.models import Barbershop

CFG = dict(WHATSAPP_BRIDGE_URL="http://bridge:8080", LEAD_ALERT_WHATSAPP_TO="972500000001, +972500000002",
           CRM_URL="https://crm.example")


class WhatsAppAlertTests(TestCase):
    def _shop(self, **kw):
        base = dict(owner_name="דנה", phone="0501234567", city="חיפה",
                    applicant_type=Barbershop.ApplicantType.CLIENT)
        base.update(kw)
        with mock.patch("catalog.grist.push_async"):
            return Barbershop.objects.create(**base)

    def test_disabled_without_config(self):
        with mock.patch("catalog.whatsapp.send") as send:
            self._shop()
        send.assert_not_called()

    @override_settings(**CFG)
    def test_message_and_recipients(self):
        shop = self._shop()
        msg = whatsapp.build_message(shop)
        self.assertIn("לקוח/ה חדש/ה", msg)
        self.assertIn("דנה", msg)
        self.assertIn("0501234567", msg)
        self.assertIn("חיפה", msg)
        self.assertIn("https://crm.example", msg)
        self.assertEqual(whatsapp.recipients(), ["972500000001", "972500000002"])

    @override_settings(**CFG)
    def test_designer_message_includes_occupation(self):
        shop = self._shop(applicant_type=Barbershop.ApplicantType.PROFESSIONAL,
                          occupation=Barbershop.Occupation.BARBER, business_name="הסלון")
        msg = whatsapp.build_message(shop)
        self.assertIn("מועמדות מעצב/ת שיער", msg)
        self.assertIn("ברבר", msg)
        self.assertIn("הסלון", msg)

    @override_settings(**CFG)
    def test_only_new_signups_alert_and_errors_are_swallowed(self):
        with mock.patch("catalog.whatsapp.notify_async") as notify:
            shop = self._shop()
            notify.assert_called_once_with(shop)
            shop.approved = True
            with mock.patch("catalog.grist.push_async"):
                shop.save()
            notify.assert_called_once()
        with mock.patch("catalog.whatsapp.send", side_effect=OSError("down")), \
             mock.patch("catalog.whatsapp.threading.Thread") as thread:
            whatsapp.notify_async(shop)
            thread.call_args[1]["target"]()  # must not raise
