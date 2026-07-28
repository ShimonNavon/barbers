from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase

from accounts.models import Member
from catalog.models import Barbershop
from community.models import Group, GroupMembership, Like, Post


def make_member(phone="+972521234567", name="דנה"):
    app = Barbershop.objects.create(owner_name=name, phone=phone, approved=True)
    user = User.objects.create(username=phone)
    return Member.objects.create(user=user, application=app,
                                 display_name=name, phone_e164=phone,
                                 onboarded=True)


class CommunityModelTests(TestCase):
    def test_like_unique_per_member_and_post(self):
        m = make_member()
        p = Post.objects.create(author=m, text="שלום")
        Like.objects.create(post=p, member=m)
        with self.assertRaises(IntegrityError):
            Like.objects.create(post=p, member=m)

    def test_group_membership_unique(self):
        m = make_member()
        g = Group.objects.create(name="ברברים", slug="barbers", emoji="💈")
        GroupMembership.objects.create(group=g, member=m)
        with self.assertRaises(IntegrityError):
            GroupMembership.objects.create(group=g, member=m)

    def test_post_ordering_newest_first(self):
        m = make_member()
        first = Post.objects.create(author=m, text="ראשון")
        second = Post.objects.create(author=m, text="שני")
        self.assertEqual(list(Post.objects.all()), [second, first])
