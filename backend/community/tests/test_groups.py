from django.test import TestCase

from community.models import Group, GroupMembership, Post
from community.tests.test_models import make_member


class GroupPagesTests(TestCase):
    def setUp(self):
        self.member = make_member()
        self.client.force_login(self.member.user)
        self.group = Group.objects.create(name="ברברים", slug="barbers",
                                          emoji="💈")

    def test_group_list_shows_join_state(self):
        r = self.client.get("/groups")
        self.assertContains(r, "ברברים")
        self.assertContains(r, "הצטרפות")
        GroupMembership.objects.create(group=self.group, member=self.member)
        r = self.client.get("/groups")
        self.assertContains(r, "עזיבה")

    def test_join_toggle(self):
        self.client.post("/groups/barbers/join")
        self.assertTrue(GroupMembership.objects.filter(
            group=self.group, member=self.member).exists())
        self.client.post("/groups/barbers/join")
        self.assertFalse(GroupMembership.objects.filter(
            group=self.group, member=self.member).exists())

    def test_group_feed_filters_to_group(self):
        other = make_member(phone="+972529999999", name="יוסי")
        Post.objects.create(author=other, text="ראשי בלבד")
        Post.objects.create(author=other, group=self.group, text="קבוצתי")
        r = self.client.get("/groups/barbers")
        self.assertContains(r, "קבוצתי")
        self.assertNotContains(r, "ראשי בלבד")

    def test_unknown_group_404(self):
        self.assertEqual(self.client.get("/groups/nope").status_code, 404)
