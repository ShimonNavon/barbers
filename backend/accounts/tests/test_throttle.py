from django.core.cache import cache
from django.test import SimpleTestCase

from accounts.throttle import allow


class ThrottleTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_allows_up_to_limit(self):
        results = [allow("k", 3, 60) for _ in range(3)]
        self.assertEqual(results, [True, True, True])

    def test_blocks_over_limit(self):
        for _ in range(3):
            allow("k", 3, 60)
        self.assertFalse(allow("k", 3, 60))

    def test_keys_are_independent(self):
        for _ in range(3):
            allow("a", 3, 60)
        self.assertTrue(allow("b", 3, 60))
