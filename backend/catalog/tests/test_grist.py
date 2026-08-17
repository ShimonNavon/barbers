import json
from unittest import mock

from django.test import TestCase, override_settings

from catalog import grist
from catalog.models import Barbershop

CFG = dict(GRIST_URL="http://grist:8484", GRIST_API_KEY="k", GRIST_DOC_ID="doc1",
           PUBLIC_BASE_URL="https://barbers.example")


class GristTests(TestCase):
    def _shop(self, **kw):
        base = dict(owner_name="דנה", phone="0501234567",
                    applicant_type=Barbershop.ApplicantType.CLIENT)
        base.update(kw)
        return Barbershop.objects.create(**base)

    def test_disabled_without_config(self):
        with mock.patch("catalog.grist._request") as req:
            shop = self._shop()  # post_save fires
            self.assertEqual(grist.upsert([shop], created=True), 0)
        req.assert_not_called()

    @override_settings(**CFG)
    def test_build_fields_uses_display_values(self):
        with mock.patch("catalog.grist.push_async"):
            shop = self._shop(city="חיפה")
        f = grist.build_fields(shop)
        self.assertEqual(f["django_id"], shop.pk)
        self.assertEqual(f["applicant_type"], "לקוח/ה — רשימת המתנה")
        self.assertEqual(f["occupation"], "אחר")
        self.assertEqual(f["city"], "חיפה")
        self.assertEqual(f["certificate"], "")
        self.assertIsInstance(f["created_at"], int)

    @override_settings(**CFG)
    def test_create_adds_row_with_new_status_and_update_is_noadd(self):
        with mock.patch("catalog.grist.push_async"):
            shop = self._shop()
        with mock.patch("catalog.grist._request") as req:
            grist.upsert([shop], created=True)
            method, path, payload, params = req.call_args[0]
            self.assertEqual((method, path, params), ("PUT", "/tables/Clients/records", ""))
            rec = payload["records"][0]
            self.assertEqual(rec["require"], {"django_id": shop.pk})
            self.assertEqual(rec["fields"]["status"], "חדש")

            grist.upsert([shop], created=False)
            method, path, payload, params = req.call_args[0]
            self.assertEqual(params, "?noadd=true")
            self.assertNotIn("status", payload["records"][0]["fields"])

    @override_settings(**CFG)
    def test_signal_pushes_created_then_updated(self):
        with mock.patch("catalog.grist.push_async") as push:
            shop = self._shop()
            push.assert_called_once_with(shop, True)
            shop.approved = True
            shop.save()
            self.assertEqual(push.call_args[0][1], False)

    @override_settings(**CFG)
    def test_push_async_swallows_network_errors(self):
        with mock.patch("catalog.grist.push_async"):
            shop = self._shop()
        with mock.patch("catalog.grist._request", side_effect=OSError("down")), \
             mock.patch("catalog.grist.threading.Thread") as thread:
            grist.push_async(shop, True)
            target = thread.call_args[1]["target"]
            target()  # must not raise
