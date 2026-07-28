from django.template.loader import render_to_string
from django.test import SimpleTestCase


class ShellTests(SimpleTestCase):
    def test_base_template_renders_rtl_shell(self):
        html = render_to_string("community/base.html", {"user": None})
        self.assertIn('dir="rtl"', html)
        self.assertIn("htmx.min.js", html)

    def test_throttled_partial_is_friendly(self):
        html = render_to_string("community/partials/throttled.html")
        self.assertIn("לאט לאט", html)
