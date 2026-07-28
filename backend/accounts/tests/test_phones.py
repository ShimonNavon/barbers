from django.test import SimpleTestCase

from accounts.phones import normalize_il_phone


class NormalizeIlPhoneTests(SimpleTestCase):
    def test_local_mobile(self):
        self.assertEqual(normalize_il_phone("0521234567"), "+972521234567")

    def test_dashes_and_spaces(self):
        self.assertEqual(normalize_il_phone("052-123 4567"), "+972521234567")

    def test_already_e164(self):
        self.assertEqual(normalize_il_phone("+972521234567"), "+972521234567")

    def test_e164_with_spaces(self):
        self.assertEqual(normalize_il_phone("+972 52 123 4567"), "+972521234567")

    def test_972_no_plus(self):
        self.assertEqual(normalize_il_phone("972521234567"), "+972521234567")

    def test_00972_prefix(self):
        self.assertEqual(normalize_il_phone("00972521234567"), "+972521234567")

    def test_972_with_leading_zero_area(self):
        self.assertEqual(normalize_il_phone("+9720521234567"), "+972521234567")

    def test_landline(self):
        self.assertEqual(normalize_il_phone("03-6001234"), "+97236001234")

    def test_foreign_number_rejected(self):
        self.assertIsNone(normalize_il_phone("+15551234567"))

    def test_garbage_rejected(self):
        self.assertIsNone(normalize_il_phone("banana"))

    def test_empty_and_none_rejected(self):
        self.assertIsNone(normalize_il_phone(""))
        self.assertIsNone(normalize_il_phone(None))

    def test_too_short_rejected(self):
        self.assertIsNone(normalize_il_phone("052123"))
