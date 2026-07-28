from django.test import TestCase

from community.tests.test_models import make_member


class DirectoryTests(TestCase):
    def setUp(self):
        self.member = make_member()
        self.client.force_login(self.member.user)

    def test_directory_lists_members(self):
        make_member(phone="+972529999999", name="יוסי")
        r = self.client.get("/members")
        self.assertContains(r, "יוסי")

    def test_search_by_name(self):
        make_member(phone="+972529999999", name="יוסי")
        r = self.client.get("/members?q=יוסי")
        self.assertContains(r, "יוסי")
        r = self.client.get("/members?q=שרה")
        self.assertNotContains(r, "יוסי")

    def test_filter_by_occupation(self):
        other = make_member(phone="+972529999999", name="יוסי")
        other.application.occupation = "barber"
        other.application.save()
        r = self.client.get("/members?occupation=barber")
        self.assertContains(r, "יוסי")
        self.assertNotContains(r, "דנה")

    def test_profile_page_shows_posts_and_dm_button(self):
        from community.models import Post
        other = make_member(phone="+972529999999", name="יוסי")
        Post.objects.create(author=other, text="העבודה שלי")
        r = self.client.get(f"/members/{other.pk}")
        self.assertContains(r, "העבודה שלי")
        self.assertContains(r, f"/dm/with/{other.pk}")

    def test_profile_edit_updates_bio(self):
        r = self.client.post("/me", {"display_name": "דנה", "bio": "ביו חדש"})
        self.assertRedirects(r, "/me")
        self.member.refresh_from_db()
        self.assertEqual(self.member.bio, "ביו חדש")

    def test_bio_bounded_at_300(self):
        r = self.client.post("/me", {"display_name": "דנה", "bio": "א" * 301})
        self.assertEqual(r.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.bio, "")
