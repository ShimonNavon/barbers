from django.core.cache import cache
from django.test import TestCase

from community.models import Conversation, Message
from community.tests.test_models import make_member


class DmTests(TestCase):
    def setUp(self):
        cache.clear()
        self.dana = make_member()
        self.yossi = make_member(phone="+972529999999", name="יוסי")
        self.client.force_login(self.dana.user)

    def test_for_pair_is_symmetric_singleton(self):
        c1 = Conversation.for_pair(self.dana, self.yossi)
        c2 = Conversation.for_pair(self.yossi, self.dana)
        self.assertEqual(c1.pk, c2.pk)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_dm_with_opens_thread(self):
        r = self.client.get(f"/dm/with/{self.yossi.pk}")
        conv = Conversation.objects.get()
        self.assertRedirects(r, f"/dm/t/{conv.pk}")

    def test_send_and_view(self):
        conv = Conversation.for_pair(self.dana, self.yossi)
        self.client.post(f"/dm/t/{conv.pk}/send", {"text": "היי יוסי"})
        r = self.client.get(f"/dm/t/{conv.pk}")
        self.assertContains(r, "היי יוסי")
        self.assertEqual(Message.objects.get().sender, self.dana)

    def test_third_member_cannot_access(self):
        conv = Conversation.for_pair(self.dana, self.yossi)
        intruder = make_member(phone="+972528888888", name="פורץ")
        self.client.force_login(intruder.user)
        self.assertEqual(self.client.get(f"/dm/t/{conv.pk}").status_code, 404)
        r = self.client.post(f"/dm/t/{conv.pk}/send", {"text": "פריצה"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Message.objects.count(), 0)

    def test_viewing_marks_incoming_read(self):
        conv = Conversation.for_pair(self.dana, self.yossi)
        Message.objects.create(conversation=conv, sender=self.yossi,
                               text="ממתין")
        self.client.get(f"/dm/t/{conv.pk}")
        self.assertIsNotNone(Message.objects.get().read_at)

    def test_polling_returns_only_newer(self):
        conv = Conversation.for_pair(self.dana, self.yossi)
        m1 = Message.objects.create(conversation=conv, sender=self.yossi,
                                    text="ראשונה")
        Message.objects.create(conversation=conv, sender=self.yossi,
                               text="שנייה")
        r = self.client.get(f"/dm/t/{conv.pk}/messages?after={m1.pk}")
        self.assertContains(r, "שנייה")
        self.assertNotContains(r, "ראשונה")

    def test_dm_text_bound_2000(self):
        conv = Conversation.for_pair(self.dana, self.yossi)
        self.client.post(f"/dm/t/{conv.pk}/send", {"text": "א" * 2001})
        self.assertEqual(Message.objects.count(), 0)

    def test_dm_rate_limit_sixty_per_hour(self):
        conv = Conversation.for_pair(self.dana, self.yossi)
        for i in range(61):
            self.client.post(f"/dm/t/{conv.pk}/send", {"text": f"הודעה {i}"})
        self.assertEqual(Message.objects.count(), 60)

    def test_cannot_dm_self(self):
        r = self.client.get(f"/dm/with/{self.dana.pk}")
        self.assertEqual(r.status_code, 404)


class DmInboxTests(TestCase):
    def setUp(self):
        cache.clear()
        self.dana = make_member()
        self.yossi = make_member(phone="+972529999999", name="יוסי")
        self.client.force_login(self.dana.user)
        self.conv = Conversation.for_pair(self.dana, self.yossi)
        Message.objects.create(conversation=self.conv, sender=self.yossi,
                               text="שלום דנה")

    def test_inbox_lists_conversation_with_unread(self):
        r = self.client.get("/dm")
        self.assertContains(r, "יוסי")
        self.assertContains(r, "שלום דנה")
        self.assertContains(r, 'class="badge"')

    def test_badge_counts_unread(self):
        r = self.client.get("/dm/badge")
        self.assertContains(r, ">1<")
        self.client.get(f"/dm/t/{self.conv.pk}")  # reading clears it
        r = self.client.get("/dm/badge")
        self.assertNotContains(r, "badge")
