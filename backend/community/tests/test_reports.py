from django.core.cache import cache
from django.test import TestCase

from community.models import Post, Report
from community.tests.test_models import make_member


class ReportTests(TestCase):
    def setUp(self):
        cache.clear()
        self.member = make_member()
        self.client.force_login(self.member.user)
        self.post = Post.objects.create(author=self.member, text="פוסט")

    def test_report_form_renders(self):
        r = self.client.get(f"/report?post={self.post.pk}")
        self.assertContains(r, "דיווח")

    def test_report_created(self):
        r = self.client.post(f"/report?post={self.post.pk}",
                             {"reason": "תוכן פוגעני"})
        self.assertRedirects(r, "/")
        rep = Report.objects.get()
        self.assertEqual(rep.post, self.post)
        self.assertEqual(rep.reporter, self.member)
        self.assertFalse(rep.handled)

    def test_reason_bounded_500(self):
        self.client.post(f"/report?post={self.post.pk}",
                         {"reason": "א" * 501})
        self.assertEqual(Report.objects.count(), 0)

    def test_unknown_target_404(self):
        self.assertEqual(
            self.client.get("/report?post=999999").status_code, 404)
        self.assertEqual(self.client.get("/report").status_code, 404)
