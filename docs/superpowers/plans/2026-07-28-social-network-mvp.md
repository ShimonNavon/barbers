# The Craft — Social Network MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Members-only social network (feed, groups, directory, DMs) for approved Craft applicants, with phone-OTP login, inside the existing barbers Django backend.

**Architecture:** Two new Django apps in `backend/`: `accounts` (Member identity, OTP auth, image pipeline, throttling, media auth) and `community` (posts, comments, likes, groups, DMs, reports). UI is server-rendered Django templates + vendored htmx, served by the existing gunicorn on port 8015; `community.navonsimon.com` is a new nginx server block pointing at the same port. Spec: `docs/superpowers/specs/2026-07-28-social-network-mvp-design.md`.

**Tech Stack:** Django 5.2, DRF (existing, untouched), Pillow (new), htmx 2.0.4 (vendored static file), Postgres 16 / SQLite-fallback for local dev, Valkey via Django cache / locmem fallback.

## Global Constraints

- Hebrew UI, RTL, mobile-first. Fonts: Frank Ruhl Libre (headings) + Heebo (body) — same as landing page.
- Every user input bounded: post 2000 · comment 500 · DM 2000 · bio 300 · display name 50 · report reason 500. Enforce in the form/model, never only client-side.
- Write rate-limits per member: posts 10/hr · comments 30/hr · DMs 60/hr · likes 60/hr. OTP: 3/phone/15min, 10/IP/hour.
- OTP: 6 digits, 5-minute TTL, max 5 verify attempts, single-use. Session: 30 days.
- No membership oracle: login endpoints always answer with the same generic message.
- Images: ≤5 MB upload, jpeg/png/webp only, re-encoded to WEBP via Pillow (strips EXIF), longest side ≤1600 px.
- All media behind auth: `certificates/` staff-only, everything else login-required.
- No new containers, no new ports, no websockets, no CDN assets (htmx is vendored).
- Existing `/api` and `/admin` behavior must not change (except the media URL rule above).
- Local dev per house rule has NO Docker: everything must run with `cd backend && python manage.py test` using the SQLite/locmem fallbacks added in Task 1.
- Run tests from `backend/` with a venv holding `requirements.txt` (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`; use `.venv/bin/python` for all commands).
- Commit after every green test cycle. Commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## File Structure

```
backend/
├─ accounts/
│  ├─ __init__.py, apps.py, admin.py, models.py, views.py, urls.py, forms.py
│  ├─ phones.py      ← IL phone normalization (pure)
│  ├─ sms.py         ← pluggable send_sms(); MVP = log stub
│  ├─ throttle.py    ← cache-based rate limiting (pure-ish)
│  ├─ images.py      ← Pillow validate/re-encode pipeline
│  ├─ media.py       ← auth-gated media serving view
│  ├─ migrations/
│  └─ tests/ (test_phones.py, test_models.py, test_auth_views.py, test_onboarding.py, test_images.py, test_media.py, test_throttle.py)
├─ community/
│  ├─ __init__.py, apps.py, admin.py, models.py, urls.py
│  ├─ views_feed.py, views_groups.py, views_members.py, views_dm.py, views_reports.py
│  ├─ templates/community/ (base.html, login.html, verify.html, onboarding.html,
│  │   feed.html, group_list.html, group_detail.html, members.html, profile.html,
│  │   profile_edit.html, dm_list.html, dm_thread.html,
│  │   partials/{post_card,post_list,comment_list,like_button,messages_page,dm_badge,form_errors,throttled}.html)
│  ├─ static/community/ (community.css, htmx.min.js)
│  ├─ migrations/
│  └─ tests/ (test_feed.py, test_comments_likes.py, test_groups.py, test_members.py, test_dm.py, test_reports.py, test_moderation.py)
└─ config/ (settings.py, urls.py — modified)
frontend/public/index.html — one login link added
```

---

### Task 1: Dev fallbacks, Pillow, `accounts` scaffold, phone normalization

**Files:**
- Modify: `backend/config/settings.py` (SECRET_KEY line 6, DATABASES lines 60-69, INSTALLED_APPS line 27)
- Modify: `backend/requirements.txt`
- Create: `backend/accounts/__init__.py`, `backend/accounts/apps.py`, `backend/accounts/phones.py`, `backend/accounts/tests/__init__.py`, `backend/accounts/tests/test_phones.py`, `backend/accounts/migrations/__init__.py`

**Interfaces:**
- Produces: `accounts.phones.normalize_il_phone(raw: str | None) -> str | None` — returns `+972…` E.164 or `None`. Every later task that touches phones uses this.
- Produces: settings run without any env vars (SQLite + insecure dev key); prod behavior unchanged when env vars are present.

- [ ] **Step 1: venv + Pillow dep**

Append to `backend/requirements.txt`:

```
Pillow==11.3.0
```

Run: `cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
Expected: installs cleanly (if the pinned Pillow is unavailable, use the newest 11.x and record it in the file).

- [ ] **Step 2: settings fallbacks + app registration**

In `backend/config/settings.py` replace line 6 with:

```python
# Prod compose always sets a real key; the fallback exists so local dev and
# CI never need env plumbing. Never deploy without DJANGO_SECRET_KEY.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-only-key")
```

Replace the `DATABASES` block with:

```python
if os.environ.get("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ["POSTGRES_USER"],
            "PASSWORD": os.environ["POSTGRES_PASSWORD"],
            "HOST": os.environ.get("POSTGRES_HOST", "db"),
            "PORT": "5432",
        }
    }
else:
    # Local dev / tests run without Docker (house rule) — SQLite file
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "dev.sqlite3",
        }
    }
```

In `INSTALLED_APPS` add `"accounts",` and `"community",` after `"catalog",` (community app dir arrives in Task 9; create both entries now to avoid touching settings twice — Django tolerates it only if the package exists, so ALSO create the bare `community` package in this task: `community/__init__.py` and `community/apps.py` with `class CommunityConfig(AppConfig): name = "community"`, plus `community/migrations/__init__.py`).

Create `backend/accounts/apps.py`:

```python
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "חברי קהילה"
```

Create empty `backend/accounts/__init__.py`, `backend/accounts/migrations/__init__.py`, `backend/accounts/tests/__init__.py`.

Run: `cd backend && .venv/bin/python manage.py check`
Expected: `System check identified no issues`

- [ ] **Step 3: failing tests for phone normalization**

Create `backend/accounts/tests/test_phones.py`:

```python
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
```

- [ ] **Step 4: run tests, verify failure**

Run: `cd backend && .venv/bin/python manage.py test accounts.tests.test_phones -v 2`
Expected: FAIL — `ModuleNotFoundError: No module named 'accounts.phones'`

- [ ] **Step 5: implement `phones.py`**

Create `backend/accounts/phones.py`:

```python
import re

# +972 then area/mobile prefix 2-9, then 7-8 digits (landline 7, mobile 8)
_VALID = re.compile(r"^\+972[2-9]\d{7,8}$")


def normalize_il_phone(raw):
    """Normalize any Israeli phone spelling to E.164 (+972...). None if invalid."""
    if not raw:
        return None
    s = re.sub(r"[^\d+]", "", raw)
    if s.startswith("00972"):
        s = s[5:]
    elif s.startswith("+972"):
        s = s[4:]
    elif s.startswith("972"):
        s = s[3:]
    elif s.startswith("0"):
        s = s[1:]
    else:
        return None
    s = "+972" + s.lstrip("0")
    return s if _VALID.match(s) else None
```

- [ ] **Step 6: run tests, verify pass**

Run: `cd backend && .venv/bin/python manage.py test accounts.tests.test_phones -v 2`
Expected: all 12 PASS

- [ ] **Step 7: commit**

```bash
git add backend/requirements.txt backend/config/settings.py backend/accounts backend/community
git commit -m "feat(accounts): app scaffold, dev fallbacks (sqlite/secret), IL phone normalization

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `Member` + `OtpCode` models and admin

**Files:**
- Create: `backend/accounts/models.py`, `backend/accounts/admin.py`
- Test: `backend/accounts/tests/test_models.py`

**Interfaces:**
- Consumes: `catalog.models.Barbershop` (existing), `accounts.phones.normalize_il_phone`.
- Produces: `Member(user, application, display_name, phone_e164, avatar, bio, onboarded, last_seen, created_at)` with read-through properties `occupation_display`, `city`, `instagram`; `OtpCode.issue(phone_e164) -> OtpCode` and `OtpCode.check_code(phone_e164, code) -> bool` (class method, counts attempts, single-use); `MAX_ATTEMPTS = 5`, `TTL_MINUTES = 5`.

- [ ] **Step 1: failing tests**

Create `backend/accounts/tests/test_models.py`:

```python
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.models import Member, OtpCode
from catalog.models import Barbershop


def make_application(**kw):
    defaults = dict(
        owner_name="דנה כהן", phone="0521234567", city="חיפה",
        occupation=Barbershop.Occupation.HAIR, approved=True,
    )
    defaults.update(kw)
    return Barbershop.objects.create(**defaults)


class MemberTests(TestCase):
    def test_member_reads_profile_fields_through_application(self):
        app = make_application(instagram="dana.hair")
        user = User.objects.create(username="+972521234567")
        m = Member.objects.create(
            user=user, application=app,
            display_name="דנה", phone_e164="+972521234567",
        )
        self.assertEqual(m.city, "חיפה")
        self.assertEqual(m.instagram, "dana.hair")
        self.assertEqual(m.occupation_display, "מעצב/ת שיער")

    def test_phone_unique(self):
        app1, app2 = make_application(), make_application(phone="0529999999")
        u1 = User.objects.create(username="a")
        u2 = User.objects.create(username="b")
        Member.objects.create(user=u1, application=app1,
                              display_name="א", phone_e164="+972521234567")
        with self.assertRaises(Exception):
            Member.objects.create(user=u2, application=app2,
                                  display_name="ב", phone_e164="+972521234567")


class OtpCodeTests(TestCase):
    def test_issue_creates_six_digit_code_with_ttl(self):
        otp = OtpCode.issue("+972521234567")
        self.assertRegex(otp.code, r"^\d{6}$")
        self.assertFalse(otp.used)
        self.assertTrue(otp.expires_at > timezone.now())

    def test_issue_invalidates_previous_codes(self):
        first = OtpCode.issue("+972521234567")
        OtpCode.issue("+972521234567")
        first.refresh_from_db()
        self.assertTrue(first.used)

    def test_check_code_happy_path_is_single_use(self):
        otp = OtpCode.issue("+972521234567")
        self.assertTrue(OtpCode.check_code("+972521234567", otp.code))
        self.assertFalse(OtpCode.check_code("+972521234567", otp.code))

    def test_wrong_code_counts_attempts_and_caps_at_five(self):
        otp = OtpCode.issue("+972521234567")
        for _ in range(5):
            self.assertFalse(OtpCode.check_code("+972521234567", "000000"))
        # even the right code fails after the cap
        self.assertFalse(OtpCode.check_code("+972521234567", otp.code))

    def test_expired_code_fails(self):
        otp = OtpCode.issue("+972521234567")
        OtpCode.objects.filter(pk=otp.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1))
        self.assertFalse(OtpCode.check_code("+972521234567", otp.code))
```

- [ ] **Step 2: run tests, verify failure**

Run: `cd backend && .venv/bin/python manage.py test accounts.tests.test_models -v 2`
Expected: FAIL — cannot import `Member` / `OtpCode`

- [ ] **Step 3: implement models**

Create `backend/accounts/models.py`:

```python
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Member(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="member")
    application = models.OneToOneField(
        "catalog.Barbershop", on_delete=models.PROTECT, related_name="member",
        verbose_name="מועמדות")
    display_name = models.CharField("שם תצוגה", max_length=50)
    phone_e164 = models.CharField("טלפון", max_length=16, unique=True)
    avatar = models.ImageField("תמונת פרופיל", upload_to="avatars/",
                               blank=True, null=True)
    bio = models.CharField("על עצמי", max_length=300, blank=True, default="")
    onboarded = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "חבר/ה"
        verbose_name_plural = "חברי קהילה"

    def __str__(self):
        return self.display_name

    # profile facts live on the vetted application — never duplicated
    @property
    def occupation_display(self):
        return self.application.get_occupation_display()

    @property
    def city(self):
        return self.application.city

    @property
    def instagram(self):
        return self.application.instagram


class OtpCode(models.Model):
    MAX_ATTEMPTS = 5
    TTL_MINUTES = 5

    phone_e164 = models.CharField(max_length=16, db_index=True)
    code = models.CharField(max_length=6)
    attempts = models.PositiveSmallIntegerField(default=0)
    used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "קוד כניסה"
        verbose_name_plural = "קודי כניסה"

    @classmethod
    def issue(cls, phone_e164):
        cls.objects.filter(phone_e164=phone_e164, used=False).update(used=True)
        return cls.objects.create(
            phone_e164=phone_e164,
            code=f"{secrets.randbelow(10**6):06d}",
            expires_at=timezone.now() + timedelta(minutes=cls.TTL_MINUTES),
        )

    @classmethod
    def check_code(cls, phone_e164, code):
        otp = (cls.objects
               .filter(phone_e164=phone_e164, used=False,
                       expires_at__gt=timezone.now())
               .order_by("-created_at").first())
        if otp is None:
            return False
        otp.attempts += 1
        correct = otp.code == code
        exhausted = otp.attempts >= cls.MAX_ATTEMPTS
        # correct → consumed (single-use); exhausted → burned (attempt cap)
        otp.used = correct or exhausted
        otp.save(update_fields=["attempts", "used"])
        return correct and otp.attempts <= cls.MAX_ATTEMPTS
```

Create `backend/accounts/admin.py`:

```python
from django.contrib import admin

from .models import Member, OtpCode


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("display_name", "phone_e164", "onboarded",
                    "last_seen", "created_at")
    search_fields = ("display_name", "phone_e164")
    readonly_fields = ("created_at", "last_seen")


@admin.register(OtpCode)
class OtpCodeAdmin(admin.ModelAdmin):
    """MVP: the client reads codes here while SMS sending is stubbed."""
    list_display = ("phone_e164", "code", "created_at", "expires_at",
                    "attempts", "used")
    readonly_fields = ("phone_e164", "code", "created_at", "expires_at",
                       "attempts", "used")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False
```

- [ ] **Step 4: migrations + run tests**

Run: `cd backend && .venv/bin/python manage.py makemigrations accounts && .venv/bin/python manage.py test accounts -v 2`
Expected: migration `0001_initial` created; all tests PASS

- [ ] **Step 5: commit**

```bash
git add backend/accounts
git commit -m "feat(accounts): Member + OtpCode models with issue/verify lifecycle, admin

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: SMS stub + throttle helper

**Files:**
- Create: `backend/accounts/sms.py`, `backend/accounts/throttle.py`
- Test: `backend/accounts/tests/test_throttle.py`

**Interfaces:**
- Produces: `accounts.sms.send_sms(phone_e164: str, text: str) -> None` (logs; provider drop-in later).
- Produces: `accounts.throttle.allow(key: str, limit: int, window_seconds: int) -> bool` — cache-backed sliding window; ALL rate limits in the project go through this.

- [ ] **Step 1: failing tests**

Create `backend/accounts/tests/test_throttle.py`:

```python
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
```

- [ ] **Step 2: run tests, verify failure**

Run: `cd backend && .venv/bin/python manage.py test accounts.tests.test_throttle -v 2`
Expected: FAIL — no module `accounts.throttle`

- [ ] **Step 3: implement**

Create `backend/accounts/throttle.py`:

```python
from django.core.cache import cache


def allow(key, limit, window_seconds):
    """True if this hit is within `limit` per `window_seconds` for `key`."""
    full = f"rl:{key}"
    if cache.add(full, 1, timeout=window_seconds):
        return limit >= 1
    try:
        count = cache.incr(full)
    except ValueError:  # expired between add and incr
        cache.add(full, 1, timeout=window_seconds)
        return limit >= 1
    return count <= limit
```

Create `backend/accounts/sms.py`:

```python
import logging

logger = logging.getLogger("accounts.sms")


def send_sms(phone_e164, text):
    """MVP stub — logs the message. Codes are also visible in the OtpCode
    admin. Real provider (Twilio / 019 / InforU) drops in here later; keep
    this exact signature."""
    logger.warning("SMS→%s: %s", phone_e164, text)
```

- [ ] **Step 4: run tests, verify pass**

Run: `cd backend && .venv/bin/python manage.py test accounts.tests.test_throttle -v 2`
Expected: PASS

- [ ] **Step 5: commit**

```bash
git add backend/accounts/sms.py backend/accounts/throttle.py backend/accounts/tests/test_throttle.py
git commit -m "feat(accounts): SMS stub + cache-backed rate-limit helper

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: UI shell — base template, CSS tokens, vendored htmx

**Files:**
- Create: `backend/community/templates/community/base.html`, `backend/community/templates/community/partials/form_errors.html`, `backend/community/templates/community/partials/throttled.html`, `backend/community/static/community/community.css`, `backend/community/static/community/htmx.min.js`
- Test: `backend/community/tests/__init__.py`, `backend/community/tests/test_shell.py`

**Interfaces:**
- Produces: `community/base.html` with blocks `{% block title %}`, `{% block content %}`; bottom tab bar uses literal hrefs `/`, `/groups`, `/members`, `/dm`, `/me` (no `{% url %}` so the shell renders before later tasks exist). All pages extend it.
- Produces: CSS custom properties `--bg --card --ink --muted --coral --oxblood` and utility classes `.card .btn .btn-coral .field .tabbar .chip .badge`.

- [ ] **Step 1: vendor htmx**

Run: `curl -sSL -o backend/community/static/community/htmx.min.js https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js && head -c 60 backend/community/static/community/htmx.min.js`
Expected: file starts with minified JS (`var htmx=...` or similar), size ~50KB.

- [ ] **Step 2: failing smoke test**

Create `backend/community/tests/__init__.py` (empty) and `backend/community/tests/test_shell.py`:

```python
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
```

Run: `cd backend && .venv/bin/python manage.py test community.tests.test_shell -v 2`
Expected: FAIL — `TemplateDoesNotExist`

- [ ] **Step 3: create templates + CSS**

Create `backend/community/templates/community/base.html`:

```html
{% load static %}
<!doctype html>
<html lang="he" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex">
  <title>{% block title %}הקהילה{% endblock %} · The Craft</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Frank+Ruhl+Libre:wght@700;900&family=Heebo:wght@400;500;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{% static 'community/community.css' %}">
  <script src="{% static 'community/htmx.min.js' %}" defer></script>
</head>
<body>
  <main class="page">
    {% if messages %}{% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}{% endif %}
    {% block content %}{% endblock %}
  </main>
  {% if user.is_authenticated %}
  <nav class="tabbar">
    <a href="/">פיד</a>
    <a href="/groups">קבוצות</a>
    <a href="/members">חברים</a>
    <a href="/dm">הודעות <span id="dm-badge" hx-get="/dm/badge" hx-trigger="load, every 30s"></span></a>
    <a href="/me">פרופיל</a>
  </nav>
  {% endif %}
</body>
</html>
```

Create `backend/community/templates/community/partials/form_errors.html`:

```html
{% if form.errors %}
<div class="form-errors">
  {% for field in form %}{% for e in field.errors %}<p>{{ e }}</p>{% endfor %}{% endfor %}
  {% for e in form.non_field_errors %}<p>{{ e }}</p>{% endfor %}
</div>
{% endif %}
```

Create `backend/community/templates/community/partials/throttled.html`:

```html
<div class="flash flash-warn">לאט לאט 🙂 נסו שוב בעוד כמה דקות.</div>
```

Create `backend/community/static/community/community.css` — full file:

```css
/* ClickA. dark tokens. Before deploy, diff these hex values against
   frontend/public/index.html :root and align exactly. */
:root {
  --bg: #140a0d;        /* deep oxblood-black */
  --card: #221116;
  --ink: #f5ede9;
  --muted: #a08a8c;
  --coral: #ff6b57;
  --oxblood: #6d1a2a;
  --radius: 14px;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: radial-gradient(1200px 600px at 80% -10%, #2a1218 0%, var(--bg) 60%);
  color: var(--ink); font-family: "Heebo", sans-serif; min-height: 100dvh;
}
h1, h2, h3 { font-family: "Frank Ruhl Libre", serif; margin: 0 0 .5em; }
.page { max-width: 640px; margin: 0 auto; padding: 16px 16px 84px; }
.card { background: var(--card); border-radius: var(--radius); padding: 14px; margin-bottom: 12px; }
.btn { display: inline-block; border: 0; border-radius: 999px; padding: 10px 22px;
  font: inherit; cursor: pointer; background: #3a222a; color: var(--ink); }
.btn-coral { background: var(--coral); color: #1c0a0e; font-weight: 700; }
.field { width: 100%; font-size: 16px; padding: 12px; border-radius: 10px;
  border: 1px solid #3a2a2e; background: #1b0f13; color: var(--ink); }
.tabbar { position: fixed; bottom: 0; inset-inline: 0; display: flex;
  justify-content: space-around; background: #1b0f13ee; backdrop-filter: blur(8px);
  padding: 10px 4px calc(10px + env(safe-area-inset-bottom)); border-top: 1px solid #33222699; }
.tabbar a { color: var(--muted); text-decoration: none; font-size: 14px; }
.tabbar a:hover, .tabbar a:focus { color: var(--coral); }
.chip { display: inline-block; background: var(--oxblood); color: var(--ink);
  border-radius: 999px; padding: 2px 10px; font-size: 12px; }
.badge { background: var(--coral); color: #1c0a0e; border-radius: 999px;
  padding: 0 6px; font-size: 12px; font-weight: 700; }
.flash { background: var(--oxblood); border-radius: 10px; padding: 10px 14px; margin-bottom: 10px; }
.flash-warn { background: #4a3413; }
.form-errors { color: var(--coral); font-size: 14px; margin: 6px 0; }
.muted { color: var(--muted); font-size: 13px; }
.avatar { width: 44px; height: 44px; border-radius: 50%; object-fit: cover; background: var(--oxblood); }
.row { display: flex; gap: 10px; align-items: center; }
.grow { flex: 1; }
textarea.field { resize: vertical; min-height: 72px; }
```

Note: the Google Fonts `<link>` matches how the landing page already loads fonts — check `frontend/public/index.html`; if the landing self-hosts font files instead, copy the same approach (this site has no CSP restriction, but consistency wins).

- [ ] **Step 4: run tests, verify pass**

Run: `cd backend && .venv/bin/python manage.py test community.tests.test_shell -v 2`
Expected: PASS

- [ ] **Step 5: commit**

```bash
git add backend/community
git commit -m "feat(community): UI shell — RTL base template, ClickA tokens, vendored htmx

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: OTP request (login page)

**Files:**
- Create: `backend/accounts/forms.py`, `backend/accounts/views.py`, `backend/accounts/urls.py`, `backend/community/templates/community/login.html`
- Modify: `backend/config/settings.py` (append session/login settings), `backend/config/urls.py`
- Test: `backend/accounts/tests/test_auth_views.py`

**Interfaces:**
- Consumes: `normalize_il_phone`, `OtpCode.issue`, `send_sms`, `throttle.allow`.
- Produces: URL names `accounts:login`, `accounts:verify`, `accounts:onboarding`, `accounts:logout`; helper `accounts.views.find_approved_application(phone_e164) -> Barbershop | None`; helper `accounts.views.client_ip(request) -> str`; session key `"otp_phone"`.
- Produces settings: `LOGIN_URL = "/login"`, `SESSION_COOKIE_AGE = 60*60*24*30`, `SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not DEBUG`.

- [ ] **Step 1: failing tests**

Create `backend/accounts/tests/test_auth_views.py` (verify-view tests arrive in Task 6 — this file grows):

```python
from django.core.cache import cache
from django.test import TestCase

from accounts.models import OtpCode
from catalog.models import Barbershop

GENERIC = "אם המספר רשום בקהילה"


def make_application(**kw):
    defaults = dict(owner_name="דנה כהן", phone="0521234567", approved=True)
    defaults.update(kw)
    return Barbershop.objects.create(**defaults)


class OtpRequestTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_login_page_renders(self):
        r = self.client.get("/login")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "טלפון")

    def test_approved_phone_gets_code_and_generic_message(self):
        make_application()
        r = self.client.post("/login", {"phone": "052-123-4567"}, follow=True)
        self.assertContains(r, GENERIC)
        self.assertEqual(OtpCode.objects.count(), 1)
        self.assertEqual(OtpCode.objects.get().phone_e164, "+972521234567")

    def test_unknown_phone_same_message_no_code(self):
        r = self.client.post("/login", {"phone": "0529999999"}, follow=True)
        self.assertContains(r, GENERIC)
        self.assertEqual(OtpCode.objects.count(), 0)

    def test_unapproved_application_no_code(self):
        make_application(approved=False)
        r = self.client.post("/login", {"phone": "0521234567"}, follow=True)
        self.assertContains(r, GENERIC)
        self.assertEqual(OtpCode.objects.count(), 0)

    def test_invalid_format_shows_field_error(self):
        r = self.client.post("/login", {"phone": "abc"})
        self.assertContains(r, "מספר טלפון לא תקין")
        self.assertEqual(OtpCode.objects.count(), 0)

    def test_phone_throttle_three_per_window(self):
        make_application()
        for _ in range(4):
            self.client.post("/login", {"phone": "0521234567"}, follow=True)
        self.assertEqual(OtpCode.objects.count(), 3)

    def test_ip_throttle_ten_per_hour(self):
        # 10 distinct unknown phones exhaust the IP budget; approved #11 gets nothing
        make_application(phone="0521111111")
        for i in range(10):
            self.client.post("/login", {"phone": f"05299{i:05d}"}, follow=True)
        self.client.post("/login", {"phone": "0521111111"}, follow=True)
        self.assertEqual(OtpCode.objects.count(), 0)
```

- [ ] **Step 2: run tests, verify failure**

Run: `cd backend && .venv/bin/python manage.py test accounts.tests.test_auth_views -v 2`
Expected: FAIL — 404 on `/login` (no URL yet)

- [ ] **Step 3: implement**

Append to `backend/config/settings.py`:

```python
LOGIN_URL = "/login"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # 30 days
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
```

Create `backend/accounts/forms.py`:

```python
from django import forms

from .phones import normalize_il_phone


class PhoneForm(forms.Form):
    phone = forms.CharField(label="טלפון", max_length=20)

    def clean_phone(self):
        normalized = normalize_il_phone(self.cleaned_data["phone"])
        if normalized is None:
            raise forms.ValidationError("מספר טלפון לא תקין")
        return normalized


class CodeForm(forms.Form):
    code = forms.RegexField(label="קוד", regex=r"^\d{6}$",
                            error_messages={"invalid": "קוד בן 6 ספרות"})
```

Create `backend/accounts/views.py`:

```python
from django.shortcuts import redirect, render

from catalog.models import Barbershop

from .forms import CodeForm, PhoneForm
from .models import OtpCode
from .sms import send_sms
from .throttle import allow


def client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (fwd.split(",")[0].strip() or
            request.META.get("REMOTE_ADDR", "unknown"))


def find_approved_application(phone_e164):
    """Match a normalized phone against approved applications. Their `phone`
    is free text, so normalize each candidate at comparison time. Community
    scale is hundreds of rows — a scan is fine."""
    from .phones import normalize_il_phone
    for app in Barbershop.objects.filter(approved=True):
        if normalize_il_phone(app.phone) == phone_e164:
            return app
    return None


def login_view(request):
    form = PhoneForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        phone = form.cleaned_data["phone"]
        # throttle first — throttled requests look identical (no oracle)
        if (allow(f"otp-ip:{client_ip(request)}", 10, 3600)
                and allow(f"otp-phone:{phone}", 3, 900)):
            app = find_approved_application(phone)
            if app is not None:
                otp = OtpCode.issue(phone)
                send_sms(phone, f"קוד הכניסה שלך לקהילה: {otp.code}")
        request.session["otp_phone"] = phone
        return redirect("accounts:verify")
    return render(request, "community/login.html", {"form": form})
```

Create `backend/accounts/urls.py` (verify/onboarding/logout views land in Task 6 — reference them now, this file is final):

```python
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login", views.login_view, name="login"),
    path("login/verify", views.verify_view, name="verify"),
    path("welcome", views.onboarding_view, name="onboarding"),
    path("logout", views.logout_view, name="logout"),
]
```

Until Task 6 exists this import breaks — add temporary stubs at the bottom of `views.py` NOW and replace them in Task 6:

```python
def verify_view(request):  # replaced in Task 6
    return render(request, "community/verify.html",
                  {"form": CodeForm(), "generic": True})


def onboarding_view(request):  # replaced in Task 6
    return redirect("/")


def logout_view(request):  # replaced in Task 6
    return redirect("accounts:login")
```

In `backend/config/urls.py`, add before the `admin/` line:

```python
path("", include("accounts.urls")),
```

Create `backend/community/templates/community/login.html`:

```html
{% extends "community/base.html" %}
{% block title %}כניסה{% endblock %}
{% block content %}
<div class="card" style="margin-top:18vh">
  <h1>כניסת חברים</h1>
  <p class="muted">הזינו את מספר הטלפון שאיתו נרשמתם לקהילה.</p>
  <form method="post">{% csrf_token %}
    {% include "community/partials/form_errors.html" %}
    <input class="field" type="tel" name="phone" required
           placeholder="050-000-0000" autocomplete="tel">
    <button class="btn btn-coral" style="margin-top:10px" type="submit">שלחו לי קוד</button>
  </form>
</div>
{% endblock %}
```

Create `backend/community/templates/community/verify.html` (used by the Task-6 view; the generic line must appear here so request→verify redirect shows it):

```html
{% extends "community/base.html" %}
{% block title %}אימות{% endblock %}
{% block content %}
<div class="card" style="margin-top:18vh">
  <h1>כמעט שם</h1>
  <p class="muted">אם המספר רשום בקהילה — נשלח אליו קוד בן 6 ספרות.</p>
  <form method="post">{% csrf_token %}
    {% include "community/partials/form_errors.html" %}
    <input class="field" type="text" inputmode="numeric" name="code"
           maxlength="6" required placeholder="••••••" autocomplete="one-time-code">
    <button class="btn btn-coral" style="margin-top:10px" type="submit">כניסה</button>
  </form>
  <p class="muted"><a href="/login" style="color:var(--coral)">שליחה חוזרת</a></p>
</div>
{% endblock %}
```

- [ ] **Step 4: run tests, verify pass**

Run: `cd backend && .venv/bin/python manage.py test accounts.tests.test_auth_views -v 2`
Expected: all PASS

- [ ] **Step 5: commit**

```bash
git add backend/accounts backend/community backend/config
git commit -m "feat(accounts): OTP request flow — no-oracle responses, phone+IP throttles

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: OTP verify, session login, logout

**Files:**
- Modify: `backend/accounts/views.py` (replace the three stubs)
- Test: append to `backend/accounts/tests/test_auth_views.py`

**Interfaces:**
- Consumes: `OtpCode.check_code`, session key `"otp_phone"`, `find_approved_application`.
- Produces: verified login creates `User(username=phone_e164)` + `Member` (display_name from `owner_name[:50]`), Django session; redirects → `/welcome` when `member.onboarded` is False, else `/`. `logout_view` POST-only.

- [ ] **Step 1: failing tests** — append to `test_auth_views.py`:

```python
from django.contrib.auth.models import User

from accounts.models import Member


class OtpVerifyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.app = make_application()
        self.client.post("/login", {"phone": "0521234567"})
        self.code = OtpCode.objects.get().code

    def test_correct_code_logs_in_creates_member_redirects_onboarding(self):
        r = self.client.post("/login/verify", {"code": self.code})
        self.assertRedirects(r, "/welcome")
        m = Member.objects.get()
        self.assertEqual(m.phone_e164, "+972521234567")
        self.assertEqual(m.display_name, "דנה כהן")
        self.assertEqual(m.application, self.app)
        self.assertEqual(int(self.client.session["_auth_user_id"]), m.user.pk)

    def test_onboarded_member_redirects_to_feed(self):
        self.client.post("/login/verify", {"code": self.code})
        Member.objects.update(onboarded=True)
        self.client.post("/logout")
        self.client.post("/login", {"phone": "0521234567"})
        code2 = OtpCode.objects.filter(used=False).get().code
        r = self.client.post("/login/verify", {"code": code2})
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        self.assertEqual(Member.objects.count(), 1)  # no duplicate

    def test_wrong_code_stays_anonymous(self):
        r = self.client.post("/login/verify", {"code": "000000"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "קוד שגוי")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_verify_without_session_phone_redirects_login(self):
        c = self.client_class()
        r = c.post("/login/verify", {"code": "123456"})
        self.assertRedirects(r, "/login")

    def test_logout(self):
        self.client.post("/login/verify", {"code": self.code})
        self.client.post("/logout")
        self.assertNotIn("_auth_user_id", self.client.session)
```

Run: `cd backend && .venv/bin/python manage.py test accounts.tests.test_auth_views -v 2`
Expected: new tests FAIL (stub verify view)

- [ ] **Step 2: replace stubs in `accounts/views.py`**

Delete the three stub functions and add:

```python
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.models import User
from django.views.decorators.http import require_POST

from .models import Member


def verify_view(request):
    phone = request.session.get("otp_phone")
    if not phone:
        return redirect("accounts:login")
    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if OtpCode.check_code(phone, form.cleaned_data["code"]):
            app = find_approved_application(phone)
            if app is None:  # approval revoked between request and verify
                return redirect("accounts:login")
            user, _ = User.objects.get_or_create(username=phone)
            member, _ = Member.objects.get_or_create(
                user=user,
                defaults={"application": app, "phone_e164": phone,
                          "display_name": app.owner_name[:50]},
            )
            auth_login(request, user)
            del request.session["otp_phone"]
            return redirect("/" if member.onboarded else "/welcome")
        form.add_error("code", "קוד שגוי או שפג תוקפו")
    return render(request, "community/verify.html", {"form": form})


@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect("accounts:login")
```

(`onboarding_view` keeps its stub until Task 8 — leave it.)

- [ ] **Step 3: run tests, verify pass**

Run: `cd backend && .venv/bin/python manage.py test accounts -v 2`
Expected: all accounts tests PASS

- [ ] **Step 4: commit**

```bash
git add backend/accounts
git commit -m "feat(accounts): OTP verify — member creation, 30-day session, logout

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Image pipeline (Pillow)

**Files:**
- Create: `backend/accounts/images.py`
- Test: `backend/accounts/tests/test_images.py`

**Interfaces:**
- Produces: `accounts.images.process_upload(uploaded_file) -> django.core.files.base.ContentFile` — validates ≤5 MB and JPEG/PNG/WEBP, applies EXIF rotation, resizes longest side to ≤1600, re-encodes WEBP q85 (EXIF/GPS gone). Raises `django.core.exceptions.ValidationError` with a Hebrew message otherwise. Callers name the file: `field.save(f"{uuid4().hex}.webp", content, save=...)`.
- Produces: constants `MAX_BYTES = 5 * 1024 * 1024`, `MAX_SIDE = 1600`.

- [ ] **Step 1: failing tests**

Create `backend/accounts/tests/test_images.py`:

```python
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from accounts.images import MAX_BYTES, process_upload


def png_upload(width=10, height=10, name="t.png"):
    buf = BytesIO()
    Image.new("RGB", (width, height), "red").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), "image/png")


class ProcessUploadTests(SimpleTestCase):
    def test_valid_png_reencoded_to_webp(self):
        content = process_upload(png_upload())
        self.assertEqual(Image.open(BytesIO(content.read())).format, "WEBP")

    def test_oversize_bytes_rejected(self):
        f = SimpleUploadedFile("big.png", b"x" * (MAX_BYTES + 1), "image/png")
        with self.assertRaises(ValidationError):
            process_upload(f)

    def test_non_image_rejected(self):
        f = SimpleUploadedFile("evil.png", b"MZ not an image", "image/png")
        with self.assertRaises(ValidationError):
            process_upload(f)

    def test_unsupported_format_rejected(self):
        buf = BytesIO()
        Image.new("RGB", (5, 5)).save(buf, "BMP")
        f = SimpleUploadedFile("t.bmp", buf.getvalue(), "image/bmp")
        with self.assertRaises(ValidationError):
            process_upload(f)

    def test_large_dimensions_resized(self):
        content = process_upload(png_upload(width=4000, height=1000))
        img = Image.open(BytesIO(content.read()))
        self.assertLessEqual(max(img.size), 1600)
```

Run: `cd backend && .venv/bin/python manage.py test accounts.tests.test_images -v 2`
Expected: FAIL — no module `accounts.images`

- [ ] **Step 2: implement**

Create `backend/accounts/images.py`:

```python
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024
MAX_SIDE = 1600
_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def process_upload(uploaded_file):
    """Validate and normalize a member-uploaded image. Re-encoding to WEBP
    drops EXIF (incl. GPS) and bounds dimensions/weight."""
    if uploaded_file.size > MAX_BYTES:
        raise ValidationError("התמונה גדולה מדי (עד 5MB)")
    try:
        img = Image.open(uploaded_file)
        img_format = img.format
        img.load()
    except (UnidentifiedImageError, OSError):
        raise ValidationError("קובץ התמונה לא תקין")
    if img_format not in _ALLOWED_FORMATS:
        raise ValidationError("פורמט לא נתמך — JPEG, PNG או WEBP")
    img = ImageOps.exif_transpose(img)
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, "WEBP", quality=85)
    return ContentFile(buf.getvalue())
```

- [ ] **Step 3: run tests, verify pass**

Run: `cd backend && .venv/bin/python manage.py test accounts.tests.test_images -v 2`
Expected: PASS

- [ ] **Step 4: commit**

```bash
git add backend/accounts/images.py backend/accounts/tests/test_images.py
git commit -m "feat(accounts): bounded image pipeline — 5MB/format check, EXIF strip, 1600px cap, WEBP

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Onboarding page

**Files:**
- Modify: `backend/accounts/views.py` (replace `onboarding_view` stub), `backend/accounts/forms.py`
- Create: `backend/community/templates/community/onboarding.html`
- Test: `backend/accounts/tests/test_onboarding.py`

**Interfaces:**
- Consumes: `process_upload`, `Member`.
- Produces: `/welcome` GET/POST; on POST saves `display_name` (≤50), optional avatar, sets `member.onboarded = True`, redirects `/`. Login required.

- [ ] **Step 1: failing tests**

Create `backend/accounts/tests/test_onboarding.py`:

```python
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from accounts.models import Member
from catalog.models import Barbershop
import tempfile

MEDIA_TMP = tempfile.mkdtemp()


def login_member(client, phone="+972521234567", onboarded=False):
    app = Barbershop.objects.create(owner_name="דנה כהן", phone="0521234567",
                                    approved=True)
    user = User.objects.create(username=phone)
    member = Member.objects.create(user=user, application=app,
                                   display_name="דנה כהן", phone_e164=phone,
                                   onboarded=onboarded)
    client.force_login(user)
    return member


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class OnboardingTests(TestCase):
    def test_requires_login(self):
        r = self.client.get("/welcome")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r["Location"])

    def test_get_prefills_display_name(self):
        login_member(self.client)
        r = self.client.get("/welcome")
        self.assertContains(r, "דנה כהן")

    def test_post_saves_and_marks_onboarded(self):
        m = login_member(self.client)
        r = self.client.post("/welcome", {"display_name": "דנה ✂️"})
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        m.refresh_from_db()
        self.assertTrue(m.onboarded)
        self.assertEqual(m.display_name, "דנה ✂️")

    def test_avatar_upload_saved_as_webp(self):
        m = login_member(self.client)
        buf = BytesIO()
        Image.new("RGB", (20, 20), "blue").save(buf, "JPEG")
        avatar = SimpleUploadedFile("me.jpg", buf.getvalue(), "image/jpeg")
        self.client.post("/welcome", {"display_name": "דנה", "avatar": avatar})
        m.refresh_from_db()
        self.assertTrue(m.avatar.name.endswith(".webp"))

    def test_display_name_bounded_at_50(self):
        login_member(self.client)
        r = self.client.post("/welcome", {"display_name": "א" * 51})
        self.assertEqual(r.status_code, 200)  # re-rendered with error
```

Run: `cd backend && .venv/bin/python manage.py test accounts.tests.test_onboarding -v 2`
Expected: FAIL (stub redirects without auth or saving)

- [ ] **Step 2: implement**

Append to `backend/accounts/forms.py`:

```python
class OnboardingForm(forms.Form):
    display_name = forms.CharField(label="שם תצוגה", max_length=50)
    avatar = forms.FileField(label="תמונת פרופיל", required=False)
```

Replace the `onboarding_view` stub in `accounts/views.py`:

```python
from uuid import uuid4

from django.contrib.auth.decorators import login_required

from .forms import OnboardingForm
from .images import process_upload


@login_required
def onboarding_view(request):
    member = request.user.member
    form = OnboardingForm(request.POST or None, request.FILES or None,
                          initial={"display_name": member.display_name})
    if request.method == "POST" and form.is_valid():
        from django.core.exceptions import ValidationError
        member.display_name = form.cleaned_data["display_name"]
        avatar = form.cleaned_data.get("avatar")
        if avatar:
            try:
                content = process_upload(avatar)
            except ValidationError as e:
                form.add_error("avatar", e.messages[0])
                return render(request, "community/onboarding.html",
                              {"form": form, "member": member})
            member.avatar.save(f"{uuid4().hex}.webp", content, save=False)
        member.onboarded = True
        member.save()
        return redirect("/")
    return render(request, "community/onboarding.html",
                  {"form": form, "member": member})
```

Create `backend/community/templates/community/onboarding.html`:

```html
{% extends "community/base.html" %}
{% block title %}ברוכים הבאים{% endblock %}
{% block content %}
<div class="card" style="margin-top:12vh">
  <h1>ברוכים הבאים לקהילה 🎉</h1>
  <p class="muted">איך שנציג אתכם? אפשר לשנות בכל רגע בפרופיל.</p>
  <form method="post" enctype="multipart/form-data">{% csrf_token %}
    {% include "community/partials/form_errors.html" %}
    <label class="muted">שם תצוגה</label>
    <input class="field" name="display_name" maxlength="50" required
           value="{{ form.initial.display_name|default:form.data.display_name }}">
    <label class="muted" style="display:block;margin-top:10px">תמונת פרופיל (לא חובה)</label>
    <input class="field" type="file" name="avatar" accept="image/jpeg,image/png,image/webp">
    <button class="btn btn-coral" style="margin-top:14px" type="submit">אל הפיד ←</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 3: run tests, verify pass**

Run: `cd backend && .venv/bin/python manage.py test accounts -v 2`
Expected: all PASS

- [ ] **Step 4: commit**

```bash
git add backend/accounts backend/community
git commit -m "feat(accounts): onboarding — display name + avatar via image pipeline

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Auth-gated media serving

**Files:**
- Create: `backend/accounts/media.py`
- Modify: `backend/config/urls.py` (replace the staff-only media route)
- Test: `backend/accounts/tests/test_media.py`

**Interfaces:**
- Produces: `accounts.media.media_serve(request, path)` — `certificates/*` requires staff (unchanged behavior); every other media path requires login. Mounted at `^media/(?P<path>.*)$`.

- [ ] **Step 1: failing tests**

Create `backend/accounts/tests/test_media.py`:

```python
import os
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

MEDIA_TMP = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class MediaAuthTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        os.makedirs(os.path.join(MEDIA_TMP, "certificates"), exist_ok=True)
        os.makedirs(os.path.join(MEDIA_TMP, "avatars"), exist_ok=True)
        for p in ("certificates/c.pdf", "avatars/a.webp"):
            with open(os.path.join(MEDIA_TMP, p), "wb") as f:
                f.write(b"data")

    def test_anonymous_gets_redirect(self):
        r = self.client.get("/media/avatars/a.webp")
        self.assertEqual(r.status_code, 302)

    def test_member_can_fetch_community_media(self):
        self.client.force_login(User.objects.create(username="u"))
        r = self.client.get("/media/avatars/a.webp")
        self.assertEqual(r.status_code, 200)

    def test_member_cannot_fetch_certificates(self):
        self.client.force_login(User.objects.create(username="u"))
        r = self.client.get("/media/certificates/c.pdf")
        self.assertEqual(r.status_code, 302)  # bounced to admin login

    def test_staff_can_fetch_certificates(self):
        self.client.force_login(
            User.objects.create(username="s", is_staff=True))
        r = self.client.get("/media/certificates/c.pdf")
        self.assertEqual(r.status_code, 200)
```

Run: `cd backend && .venv/bin/python manage.py test accounts.tests.test_media -v 2`
Expected: FAIL — members bounced from avatars (current route is staff-only)

- [ ] **Step 2: implement**

Create `backend/accounts/media.py`:

```python
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.views.static import serve


@staff_member_required
def _staff_serve(request, path):
    return serve(request, path, document_root=settings.MEDIA_ROOT)


@login_required
def _member_serve(request, path):
    return serve(request, path, document_root=settings.MEDIA_ROOT)


def media_serve(request, path):
    """Closed community: no public media. Certificates carry personal
    documents — staff only. Everything else needs a logged-in member."""
    if path.startswith("certificates/"):
        return _staff_serve(request, path)
    return _member_serve(request, path)
```

In `backend/config/urls.py` replace the existing `re_path(r"^media/...")` entry (and its comment) with:

```python
re_path(r"^media/(?P<path>.*)$", media_serve),
```

adding the import `from accounts.media import media_serve` at the top; drop the now-unused `staff_member_required` / `serve` imports.

- [ ] **Step 3: run tests, verify pass**

Run: `cd backend && .venv/bin/python manage.py test accounts -v 2`
Expected: all PASS

- [ ] **Step 4: commit**

```bash
git add backend/accounts backend/config/urls.py
git commit -m "feat(accounts): auth-gated media — certificates staff-only, rest members-only

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: Community models — Group, GroupMembership, Post, Comment, Like

**Files:**
- Create: `backend/community/models.py`, `backend/community/admin.py`
- Test: `backend/community/tests/test_models.py`

**Interfaces:**
- Consumes: `accounts.models.Member`.
- Produces: `Group(name, slug, emoji, description)`; `GroupMembership(group, member)` unique-together; `Post(author, group?, text≤2000, image?, created_at, is_deleted)`; `Comment(post, author, text≤500, created_at, is_deleted)`; `Like(post, member)` unique-together. Related names: `post.comments`, `post.likes`, `group.memberships`, `member.posts`.

- [ ] **Step 1: failing tests**

Create `backend/community/tests/test_models.py`:

```python
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
```

Run: `cd backend && .venv/bin/python manage.py test community.tests.test_models -v 2`
Expected: FAIL — models missing

- [ ] **Step 2: implement models + admin**

Create `backend/community/models.py`:

```python
from django.db import models


class Group(models.Model):
    name = models.CharField("שם", max_length=60, unique=True)
    slug = models.SlugField(unique=True, allow_unicode=True)
    emoji = models.CharField("אימוג'י", max_length=8, blank=True, default="")
    description = models.CharField("תיאור", max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "קבוצה"
        verbose_name_plural = "קבוצות"

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE,
                              related_name="memberships")
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE,
                               related_name="group_memberships")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["group", "member"], name="uniq_group_member")]


class Post(models.Model):
    author = models.ForeignKey("accounts.Member", on_delete=models.CASCADE,
                               related_name="posts")
    group = models.ForeignKey(Group, on_delete=models.SET_NULL,
                              null=True, blank=True, related_name="posts")
    text = models.CharField("טקסט", max_length=2000)
    image = models.ImageField(upload_to="posts/", blank=True, null=True)
    is_deleted = models.BooleanField("הוסר", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "פוסט"
        verbose_name_plural = "פוסטים"

    def __str__(self):
        return f"{self.author}: {self.text[:40]}"


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE,
                             related_name="comments")
    author = models.ForeignKey("accounts.Member", on_delete=models.CASCADE,
                               related_name="comments")
    text = models.CharField("תגובה", max_length=500)
    is_deleted = models.BooleanField("הוסר", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "תגובה"
        verbose_name_plural = "תגובות"


class Like(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE,
                             related_name="likes")
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE,
                               related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["post", "member"], name="uniq_like_post_member")]
```

Create `backend/community/admin.py`:

```python
from django.contrib import admin

from .models import Comment, Group, Post


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "emoji", "slug", "created_at")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("author", "text", "group", "created_at", "is_deleted")
    list_filter = ("is_deleted", "group", "created_at")
    list_editable = ("is_deleted",)
    search_fields = ("text", "author__display_name")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("author", "text", "post", "created_at", "is_deleted")
    list_filter = ("is_deleted", "created_at")
    list_editable = ("is_deleted",)
    search_fields = ("text", "author__display_name")
```

- [ ] **Step 3: migrate + run tests**

Run: `cd backend && .venv/bin/python manage.py makemigrations community && .venv/bin/python manage.py test community -v 2`
Expected: migration created; tests PASS

- [ ] **Step 4: commit**

```bash
git add backend/community
git commit -m "feat(community): Group/Post/Comment/Like models with uniqueness + moderation admin

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: Feed — list, composer, pagination, `member_required`

**Files:**
- Create: `backend/accounts/decorators.py`, `backend/community/views_feed.py`, `backend/community/urls.py`, `backend/community/forms.py`, `backend/community/templates/community/feed.html`, `backend/community/templates/community/partials/post_list.html`, `backend/community/templates/community/partials/post_card.html`, `backend/community/templates/community/partials/like_button.html`
- Modify: `backend/config/urls.py`
- Test: `backend/community/tests/test_feed.py`

**Interfaces:**
- Produces: `accounts.decorators.member_required` — redirects anonymous → `/login`, logged-in-but-not-onboarded → `/welcome`; sets `request.member`. EVERY community view uses it.
- Produces: URL names `community:feed` (`/`), `community:create_post` (`POST /posts`); feed accepts `?page=N` and `?group=<slug>`; htmx requests (`HX-Request` header) get `partials/post_list.html` only.
- Produces: `community.forms.PostForm(member, data, files)` — validates text ≤2000, optional image, optional `group` slug the member has joined (`ValidationError` otherwise).
- Feed queryset rule (used by every later feed): `Post.objects.filter(is_deleted=False)` + `select_related("author", "group")` + annotations `like_count`, `comment_count` (excluding deleted comments), `liked` (Exists for current member). Page size 20.

- [ ] **Step 1: failing tests**

Create `backend/community/tests/test_feed.py`:

```python
from django.core.cache import cache
from django.test import TestCase

from community.models import Group, GroupMembership, Post
from community.tests.test_models import make_member


class FeedTests(TestCase):
    def setUp(self):
        cache.clear()
        self.member = make_member()
        self.client.force_login(self.member.user)

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r["Location"])

    def test_not_onboarded_redirected_to_welcome(self):
        self.member.onboarded = False
        self.member.save()
        r = self.client.get("/")
        self.assertRedirects(r, "/welcome")

    def test_feed_shows_all_posts_with_group_chip(self):
        g = Group.objects.create(name="ברברים", slug="barbers")
        other = make_member(phone="+972529999999", name="יוסי")
        Post.objects.create(author=other, text="פוסט ראשי")
        Post.objects.create(author=other, group=g, text="פוסט קבוצתי")
        r = self.client.get("/")
        self.assertContains(r, "פוסט ראשי")
        self.assertContains(r, "פוסט קבוצתי")
        self.assertContains(r, "ברברים")  # the chip

    def test_deleted_posts_hidden(self):
        Post.objects.create(author=self.member, text="נמחק", is_deleted=True)
        r = self.client.get("/")
        self.assertNotContains(r, "נמחק")

    def test_create_post_main_feed(self):
        r = self.client.post("/posts", {"text": "שלום לכולם"})
        self.assertRedirects(r, "/")
        self.assertEqual(Post.objects.count(), 1)

    def test_create_post_text_bound(self):
        r = self.client.post("/posts", {"text": "א" * 2001})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Post.objects.count(), 0)

    def test_post_to_group_requires_membership(self):
        g = Group.objects.create(name="ברברים", slug="barbers")
        r = self.client.post("/posts", {"text": "היי", "group": "barbers"})
        self.assertEqual(Post.objects.count(), 0)
        GroupMembership.objects.create(group=g, member=self.member)
        self.client.post("/posts", {"text": "היי", "group": "barbers"})
        self.assertEqual(Post.objects.get().group, g)

    def test_post_rate_limited_at_ten_per_hour(self):
        for i in range(11):
            self.client.post("/posts", {"text": f"פוסט {i}"})
        self.assertEqual(Post.objects.count(), 10)

    def test_pagination_htmx_partial(self):
        for i in range(25):
            Post.objects.create(author=self.member, text=f"פוסט {i}")
        r = self.client.get("/?page=2", HTTP_HX_REQUEST="true")
        self.assertContains(r, "פוסט 4")          # oldest land on page 2
        self.assertNotContains(r, "<nav")          # partial, not full page
```

Run: `cd backend && .venv/bin/python manage.py test community.tests.test_feed -v 2`
Expected: FAIL — `/` returns 404

- [ ] **Step 2: implement**

Create `backend/accounts/decorators.py`:

```python
from functools import wraps

from django.core.cache import cache
from django.shortcuts import redirect
from django.utils import timezone

from .models import Member


def member_required(view):
    """Community pages need a logged-in, onboarded member.
    Attaches `request.member` and refreshes `last_seen` (≤ once / 5 min)."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        member = getattr(request.user, "member", None)
        if member is None:
            return redirect("accounts:login")
        if not member.onboarded:
            return redirect("accounts:onboarding")
        if cache.add(f"seen:{member.pk}", 1, 300):
            Member.objects.filter(pk=member.pk).update(
                last_seen=timezone.now())
        request.member = member
        return view(request, *args, **kwargs)
    return wrapped
```

Create `backend/community/forms.py`:

```python
from django import forms

from .models import Group, GroupMembership


class PostForm(forms.Form):
    text = forms.CharField(max_length=2000)
    image = forms.FileField(required=False)
    group = forms.CharField(required=False)  # slug

    def __init__(self, member, *args, **kwargs):
        self.member = member
        super().__init__(*args, **kwargs)

    def clean_group(self):
        slug = self.cleaned_data.get("group", "").strip()
        if not slug:
            return None
        try:
            group = Group.objects.get(slug=slug)
        except Group.DoesNotExist:
            raise forms.ValidationError("קבוצה לא קיימת")
        if not GroupMembership.objects.filter(
                group=group, member=self.member).exists():
            raise forms.ValidationError("אפשר לפרסם רק בקבוצות שהצטרפת אליהן")
        return group


class CommentForm(forms.Form):
    text = forms.CharField(max_length=500)
```

Create `backend/community/views_feed.py`:

```python
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import member_required
from accounts.images import process_upload
from accounts.throttle import allow

from .forms import PostForm
from .models import Like, Post

PAGE_SIZE = 20


def feed_queryset(member, group=None):
    qs = (Post.objects.filter(is_deleted=False)
          .select_related("author", "group")
          .annotate(
              like_count=Count("likes", distinct=True),
              comment_count=Count("comments", distinct=True,
                                  filter=Q(comments__is_deleted=False)),
              liked=Exists(Like.objects.filter(
                  post=OuterRef("pk"), member=member))))
    if group is not None:
        qs = qs.filter(group=group)
    return qs


@member_required
def feed(request):
    page = Paginator(feed_queryset(request.member),
                     PAGE_SIZE).get_page(request.GET.get("page"))
    template = ("community/partials/post_list.html"
                if request.headers.get("HX-Request")
                else "community/feed.html")
    joined_groups = [gm.group for gm in
                     request.member.group_memberships.select_related("group")]
    return render(request, template,
                  {"page": page, "joined_groups": joined_groups,
                   "feed_url": "/"})


@member_required
def create_post(request):
    if request.method != "POST":
        return redirect("community:feed")
    form = PostForm(request.member, request.POST, request.FILES)
    if not form.is_valid():
        page = Paginator(feed_queryset(request.member),
                         PAGE_SIZE).get_page(1)
        joined_groups = [gm.group for gm in
                         request.member.group_memberships.select_related("group")]
        return render(request, "community/feed.html",
                      {"page": page, "form": form,
                       "joined_groups": joined_groups, "feed_url": "/"})
    if not allow(f"post:{request.member.pk}", 10, 3600):
        return render(request, "community/partials/throttled.html", status=429)
    post = Post(author=request.member, text=form.cleaned_data["text"],
                group=form.cleaned_data.get("group"))
    upload = form.cleaned_data.get("image")
    if upload:
        try:
            content = process_upload(upload)
        except ValidationError as e:
            form.add_error("image", e.messages[0])
            page = Paginator(feed_queryset(request.member),
                             PAGE_SIZE).get_page(1)
            return render(request, "community/feed.html",
                          {"page": page, "form": form,
                           "joined_groups": [], "feed_url": "/"})
        post.image.save(f"{uuid4().hex}.webp", content, save=False)
    post.save()
    dest = form.cleaned_data.get("group")
    return redirect(f"/groups/{dest.slug}" if dest else "community:feed")
```

Create `backend/community/urls.py` (routes for later tasks are included once their views exist — start with exactly these and extend per task):

```python
from django.urls import path

from . import views_feed

app_name = "community"

urlpatterns = [
    path("", views_feed.feed, name="feed"),
    path("posts", views_feed.create_post, name="create_post"),
]
```

In `backend/config/urls.py` add AFTER the accounts include:

```python
path("", include("community.urls")),
```

Create `backend/community/templates/community/feed.html`:

```html
{% extends "community/base.html" %}
{% block title %}פיד{% endblock %}
{% block content %}
<h1>הקהילה</h1>
<form class="card" method="post" action="/posts" enctype="multipart/form-data">
  {% csrf_token %}
  {% include "community/partials/form_errors.html" %}
  <textarea class="field" name="text" maxlength="2000" required
            placeholder="מה קורה אצלך?"></textarea>
  <div class="row" style="margin-top:8px">
    <select class="field grow" name="group">
      <option value="">📣 הפיד הראשי</option>
      {% for g in joined_groups %}
      <option value="{{ g.slug }}">{{ g.emoji }} {{ g.name }}</option>
      {% endfor %}
    </select>
    <input type="file" name="image" accept="image/jpeg,image/png,image/webp">
    <button class="btn btn-coral" type="submit">פרסום</button>
  </div>
</form>
<div id="post-list">
  {% include "community/partials/post_list.html" %}
</div>
{% endblock %}
```

Create `backend/community/templates/community/partials/post_list.html`:

```html
{% for post in page %}
  {% include "community/partials/post_card.html" %}
{% empty %}
  <div class="card muted">עדיין שקט כאן… תהיו הראשונים לפרסם 🎉</div>
{% endfor %}
{% if page.has_next %}
<button class="btn" style="width:100%"
        hx-get="{{ feed_url }}?page={{ page.next_page_number }}"
        hx-target="this" hx-swap="outerHTML">עוד</button>
{% endif %}
```

Create `backend/community/templates/community/partials/post_card.html`:

```html
<article class="card" id="post-{{ post.pk }}">
  <div class="row">
    {% if post.author.avatar %}<img class="avatar" src="/media/{{ post.author.avatar.name }}" alt="">
    {% else %}<div class="avatar"></div>{% endif %}
    <div class="grow">
      <a href="/members/{{ post.author.pk }}" style="color:var(--ink);text-decoration:none">
        <strong>{{ post.author.display_name }}</strong></a>
      <div class="muted">{{ post.author.occupation_display }}
        · {{ post.created_at|date:"j בF, H:i" }}</div>
    </div>
    {% if post.group %}<span class="chip">{{ post.group.emoji }} {{ post.group.name }}</span>{% endif %}
  </div>
  <p style="white-space:pre-line">{{ post.text }}</p>
  {% if post.image %}<img src="/media/{{ post.image.name }}" alt=""
       style="max-width:100%;border-radius:10px">{% endif %}
  <div class="row" style="margin-top:8px">
    {% include "community/partials/like_button.html" %}
    <button class="btn" hx-get="/posts/{{ post.pk }}/comments"
            hx-target="#comments-{{ post.pk }}" hx-swap="innerHTML">
      💬 {{ post.comment_count }}</button>
    <a class="muted grow" style="text-align:left" href="/report?post={{ post.pk }}">דיווח</a>
  </div>
  <div id="comments-{{ post.pk }}"></div>
</article>
```

Create `backend/community/templates/community/partials/like_button.html`:

```html
<button class="btn{% if post.liked %} btn-coral{% endif %}"
        hx-post="/posts/{{ post.pk }}/like" hx-swap="outerHTML"
        hx-headers='{"X-CSRFToken":"{{ csrf_token }}"}'>
  ♥ {{ post.like_count }}</button>
```

- [ ] **Step 3: run tests, verify pass**

Run: `cd backend && .venv/bin/python manage.py test community -v 2`
Expected: PASS (like/comment endpoints 404 for now — those tests come in Task 12)

- [ ] **Step 4: commit**

```bash
git add backend/accounts/decorators.py backend/community backend/config/urls.py
git commit -m "feat(community): feed — composer, group-gated posting, pagination, rate limit

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 12: Likes + comments

**Files:**
- Create: `backend/community/views_engage.py`, `backend/community/templates/community/partials/comment_list.html`
- Modify: `backend/community/urls.py`
- Test: `backend/community/tests/test_comments_likes.py`

**Interfaces:**
- Consumes: `feed_queryset` (for re-rendering the like button with fresh counts), `CommentForm`, `throttle.allow`.
- Produces: `POST /posts/<id>/like` toggles and returns `like_button.html`; `GET /posts/<id>/comments` returns `comment_list.html` (visible comments + inline form); `POST /posts/<id>/comments` creates then returns the same partial. Limits: likes 60/hr, comments 30/hr → `throttled.html` with status 429.

- [ ] **Step 1: failing tests**

Create `backend/community/tests/test_comments_likes.py`:

```python
from django.core.cache import cache
from django.test import TestCase

from community.models import Comment, Like, Post
from community.tests.test_models import make_member


class LikeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.member = make_member()
        self.client.force_login(self.member.user)
        self.post = Post.objects.create(author=self.member, text="פוסט")

    def test_like_then_unlike(self):
        r = self.client.post(f"/posts/{self.post.pk}/like")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Like.objects.count(), 1)
        self.assertContains(r, "♥ 1")
        r = self.client.post(f"/posts/{self.post.pk}/like")
        self.assertEqual(Like.objects.count(), 0)
        self.assertContains(r, "♥ 0")

    def test_like_deleted_post_404(self):
        self.post.is_deleted = True
        self.post.save()
        r = self.client.post(f"/posts/{self.post.pk}/like")
        self.assertEqual(r.status_code, 404)


class CommentTests(TestCase):
    def setUp(self):
        cache.clear()
        self.member = make_member()
        self.client.force_login(self.member.user)
        self.post = Post.objects.create(author=self.member, text="פוסט")

    def test_comment_create_and_list(self):
        r = self.client.post(f"/posts/{self.post.pk}/comments",
                             {"text": "מהמם!"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "מהמם!")
        self.assertEqual(Comment.objects.count(), 1)

    def test_comment_bound_500(self):
        r = self.client.post(f"/posts/{self.post.pk}/comments",
                             {"text": "א" * 501})
        self.assertEqual(Comment.objects.count(), 0)

    def test_deleted_comments_hidden(self):
        Comment.objects.create(post=self.post, author=self.member,
                               text="הוסר", is_deleted=True)
        r = self.client.get(f"/posts/{self.post.pk}/comments")
        self.assertNotContains(r, "הוסר")

    def test_comment_rate_limit_thirty_per_hour(self):
        for i in range(31):
            self.client.post(f"/posts/{self.post.pk}/comments",
                             {"text": f"תגובה {i}"})
        self.assertEqual(Comment.objects.count(), 30)
```

Run: `cd backend && .venv/bin/python manage.py test community.tests.test_comments_likes -v 2`
Expected: FAIL — 404s

- [ ] **Step 2: implement**

Create `backend/community/views_engage.py`:

```python
from django.shortcuts import get_object_or_404, render

from accounts.decorators import member_required
from accounts.throttle import allow

from .forms import CommentForm
from .models import Like, Post
from .views_feed import feed_queryset


def _post_for(member, post_id):
    return get_object_or_404(feed_queryset(member), pk=post_id)


@member_required
def toggle_like(request, post_id):
    if request.method != "POST":
        return render(request, "community/partials/throttled.html", status=405)
    if not allow(f"like:{request.member.pk}", 60, 3600):
        return render(request, "community/partials/throttled.html", status=429)
    post = get_object_or_404(Post, pk=post_id, is_deleted=False)
    existing = Like.objects.filter(post=post, member=request.member)
    if existing.exists():
        existing.delete()
    else:
        Like.objects.get_or_create(post=post, member=request.member)
    return render(request, "community/partials/like_button.html",
                  {"post": _post_for(request.member, post_id)})


@member_required
def comments(request, post_id):
    post = get_object_or_404(Post, pk=post_id, is_deleted=False)
    form = CommentForm()
    status = 200
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            if allow(f"comment:{request.member.pk}", 30, 3600):
                post.comments.create(author=request.member,
                                     text=form.cleaned_data["text"])
                form = CommentForm()
            else:
                status = 429
    visible = post.comments.filter(is_deleted=False).select_related("author")
    return render(request, "community/partials/comment_list.html",
                  {"post": post, "comments": visible, "form": form,
                   "throttled": status == 429},
                  status=status)
```

Append to `backend/community/urls.py` urlpatterns:

```python
    path("posts/<int:post_id>/like", views_engage.toggle_like, name="like"),
    path("posts/<int:post_id>/comments", views_engage.comments, name="comments"),
```

with `from . import views_engage` at the top.

Create `backend/community/templates/community/partials/comment_list.html`:

```html
{% for c in comments %}
<div class="row" style="margin:8px 0">
  <strong>{{ c.author.display_name }}</strong>
  <span class="grow">{{ c.text }}</span>
  <a class="muted" href="/report?comment={{ c.pk }}">דיווח</a>
</div>
{% empty %}<p class="muted">אין תגובות עדיין.</p>{% endfor %}
{% if throttled %}{% include "community/partials/throttled.html" %}{% endif %}
<form hx-post="/posts/{{ post.pk }}/comments"
      hx-target="#comments-{{ post.pk }}" hx-swap="innerHTML">
  {% csrf_token %}
  <div class="row">
    <input class="field grow" name="text" maxlength="500" required
           placeholder="תגובה…">
    <button class="btn btn-coral" type="submit">שליחה</button>
  </div>
</form>
```

- [ ] **Step 3: run tests, verify pass**

Run: `cd backend && .venv/bin/python manage.py test community -v 2`
Expected: PASS

- [ ] **Step 4: commit**

```bash
git add backend/community
git commit -m "feat(community): likes toggle + inline comments, both rate-limited

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 13: Group pages

**Files:**
- Create: `backend/community/views_groups.py`, `backend/community/templates/community/group_list.html`, `backend/community/templates/community/group_detail.html`
- Modify: `backend/community/urls.py`
- Test: `backend/community/tests/test_groups.py`

**Interfaces:**
- Consumes: `feed_queryset(member, group=...)`, `GroupMembership`.
- Produces: `GET /groups` (all groups, joined state, member counts), `POST /groups/<slug>/join` (toggle, redirect back), `GET /groups/<slug>` (group feed page reusing `post_list.html`; composer preselects the group when joined).

- [ ] **Step 1: failing tests**

Create `backend/community/tests/test_groups.py`:

```python
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
```

Run: `cd backend && .venv/bin/python manage.py test community.tests.test_groups -v 2`
Expected: FAIL — 404s

- [ ] **Step 2: implement**

Create `backend/community/views_groups.py`:

```python
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import member_required

from .models import Group, GroupMembership
from .views_feed import PAGE_SIZE, feed_queryset


@member_required
def group_list(request):
    groups = (Group.objects
              .annotate(member_count=Count("memberships"),
                        joined=Exists(GroupMembership.objects.filter(
                            group=OuterRef("pk"), member=request.member))))
    return render(request, "community/group_list.html", {"groups": groups})


@member_required
def join_toggle(request, slug):
    if request.method == "POST":
        group = get_object_or_404(Group, slug=slug)
        existing = GroupMembership.objects.filter(group=group,
                                                  member=request.member)
        if existing.exists():
            existing.delete()
        else:
            GroupMembership.objects.get_or_create(group=group,
                                                  member=request.member)
    return redirect("community:group_detail", slug=slug)


@member_required
def group_detail(request, slug):
    group = get_object_or_404(Group, slug=slug)
    joined = GroupMembership.objects.filter(
        group=group, member=request.member).exists()
    page = Paginator(feed_queryset(request.member, group=group),
                     PAGE_SIZE).get_page(request.GET.get("page"))
    if request.headers.get("HX-Request"):
        return render(request, "community/partials/post_list.html",
                      {"page": page, "feed_url": f"/groups/{slug}"})
    return render(request, "community/group_detail.html",
                  {"group": group, "joined": joined, "page": page,
                   "feed_url": f"/groups/{slug}"})
```

Append to `backend/community/urls.py` (import `views_groups`):

```python
    path("groups", views_groups.group_list, name="groups"),
    path("groups/<slug:slug>", views_groups.group_detail, name="group_detail"),
    path("groups/<slug:slug>/join", views_groups.join_toggle, name="group_join"),
```

Create `backend/community/templates/community/group_list.html`:

```html
{% extends "community/base.html" %}
{% block title %}קבוצות{% endblock %}
{% block content %}
<h1>קבוצות</h1>
{% for g in groups %}
<div class="card row">
  <a class="grow" href="/groups/{{ g.slug }}"
     style="color:var(--ink);text-decoration:none">
    <strong>{{ g.emoji }} {{ g.name }}</strong>
    <div class="muted">{{ g.description }} · {{ g.member_count }} חברים</div>
  </a>
  <form method="post" action="/groups/{{ g.slug }}/join">{% csrf_token %}
    <button class="btn{% if not g.joined %} btn-coral{% endif %}">
      {% if g.joined %}עזיבה{% else %}הצטרפות{% endif %}</button>
  </form>
</div>
{% empty %}<div class="card muted">אין קבוצות עדיין.</div>{% endfor %}
{% endblock %}
```

Create `backend/community/templates/community/group_detail.html`:

```html
{% extends "community/base.html" %}
{% block title %}{{ group.name }}{% endblock %}
{% block content %}
<h1>{{ group.emoji }} {{ group.name }}</h1>
<p class="muted">{{ group.description }}</p>
<form method="post" action="/groups/{{ group.slug }}/join">{% csrf_token %}
  <button class="btn{% if not joined %} btn-coral{% endif %}">
    {% if joined %}עזיבת הקבוצה{% else %}הצטרפות לקבוצה{% endif %}</button>
</form>
{% if joined %}
<form class="card" method="post" action="/posts" enctype="multipart/form-data"
      style="margin-top:12px">
  {% csrf_token %}
  <textarea class="field" name="text" maxlength="2000" required
            placeholder="שיתוף עם {{ group.name }}…"></textarea>
  <input type="hidden" name="group" value="{{ group.slug }}">
  <div class="row" style="margin-top:8px">
    <input class="grow" type="file" name="image"
           accept="image/jpeg,image/png,image/webp">
    <button class="btn btn-coral" type="submit">פרסום</button>
  </div>
</form>
{% endif %}
<div id="post-list" style="margin-top:12px">
  {% include "community/partials/post_list.html" %}
</div>
{% endblock %}
```

- [ ] **Step 3: run tests, verify pass**

Run: `cd backend && .venv/bin/python manage.py test community -v 2`
Expected: PASS

- [ ] **Step 4: commit**

```bash
git add backend/community
git commit -m "feat(community): group list/join/detail with scoped composer

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 14: Directory, profiles, profile edit

**Files:**
- Create: `backend/community/views_members.py`, `backend/community/templates/community/members.html`, `backend/community/templates/community/profile.html`, `backend/community/templates/community/profile_edit.html`
- Modify: `backend/community/urls.py`
- Test: `backend/community/tests/test_members.py`

**Interfaces:**
- Consumes: `Member`, `Barbershop.Occupation.choices`, `process_upload`, `feed_queryset`.
- Produces: `GET /members` (search `?q=` on display_name, filter `?occupation=<value>` and `?city=<text>`), `GET /members/<id>` (profile + posts), `GET|POST /me` (edit display_name/bio/avatar + logout button). Only `onboarded=True` members are listed/visible.

- [ ] **Step 1: failing tests**

Create `backend/community/tests/test_members.py`:

```python
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
        self.member.refresh_from_db()
        self.assertEqual(self.member.bio, "")
```

Run: `cd backend && .venv/bin/python manage.py test community.tests.test_members -v 2`
Expected: FAIL — 404s

- [ ] **Step 2: implement**

Create `backend/community/views_members.py`:

```python
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django import forms
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import member_required
from accounts.images import process_upload
from accounts.models import Member
from catalog.models import Barbershop

from .views_feed import PAGE_SIZE, feed_queryset


class ProfileForm(forms.Form):
    display_name = forms.CharField(max_length=50)
    bio = forms.CharField(max_length=300, required=False)
    avatar = forms.FileField(required=False)


@member_required
def directory(request):
    members = (Member.objects.filter(onboarded=True)
               .select_related("application").order_by("display_name"))
    q = request.GET.get("q", "").strip()[:50]
    occupation = request.GET.get("occupation", "").strip()[:20]
    city = request.GET.get("city", "").strip()[:100]
    if q:
        members = members.filter(display_name__icontains=q)
    if occupation:
        members = members.filter(application__occupation=occupation)
    if city:
        members = members.filter(application__city__icontains=city)
    return render(request, "community/members.html", {
        "members": members[:200],
        "occupations": Barbershop.Occupation.choices,
        "q": q, "occupation": occupation, "city": city,
    })


@member_required
def profile(request, member_id):
    person = get_object_or_404(
        Member.objects.select_related("application"),
        pk=member_id, onboarded=True)
    page = (Paginator(feed_queryset(request.member).filter(author=person),
                      PAGE_SIZE).get_page(request.GET.get("page")))
    return render(request, "community/profile.html",
                  {"person": person, "page": page,
                   "feed_url": f"/members/{member_id}"})


@member_required
def me(request):
    member = request.member
    form = ProfileForm(request.POST or None, request.FILES or None,
                       initial={"display_name": member.display_name,
                                "bio": member.bio})
    if request.method == "POST" and form.is_valid():
        member.display_name = form.cleaned_data["display_name"]
        member.bio = form.cleaned_data.get("bio", "")
        avatar = form.cleaned_data.get("avatar")
        if avatar:
            try:
                content = process_upload(avatar)
                member.avatar.save(f"{uuid4().hex}.webp", content, save=False)
            except ValidationError as e:
                form.add_error("avatar", e.messages[0])
                return render(request, "community/profile_edit.html",
                              {"form": form, "member": member})
        member.save()
        return redirect("community:me")
    return render(request, "community/profile_edit.html",
                  {"form": form, "member": member})
```

Append to `backend/community/urls.py` (import `views_members`):

```python
    path("members", views_members.directory, name="members"),
    path("members/<int:member_id>", views_members.profile, name="profile"),
    path("me", views_members.me, name="me"),
```

Create `backend/community/templates/community/members.html`:

```html
{% extends "community/base.html" %}
{% block title %}חברים{% endblock %}
{% block content %}
<h1>חברי הקהילה</h1>
<form class="card" method="get">
  <input class="field" name="q" value="{{ q }}" placeholder="חיפוש לפי שם…">
  <div class="row" style="margin-top:8px;flex-wrap:wrap">
    <select class="field grow" name="occupation">
      <option value="">כל התחומים</option>
      {% for value, label in occupations %}
      <option value="{{ value }}" {% if value == occupation %}selected{% endif %}>
        {{ label }}</option>
      {% endfor %}
    </select>
    <input class="field grow" name="city" value="{{ city }}" placeholder="עיר">
    <button class="btn btn-coral" type="submit">סינון</button>
  </div>
</form>
{% for m in members %}
<a class="card row" href="/members/{{ m.pk }}"
   style="color:var(--ink);text-decoration:none">
  {% if m.avatar %}<img class="avatar" src="/media/{{ m.avatar.name }}" alt="">
  {% else %}<div class="avatar"></div>{% endif %}
  <div class="grow">
    <strong>{{ m.display_name }}</strong>
    <div class="muted">{{ m.occupation_display }}{% if m.city %} · {{ m.city }}{% endif %}</div>
  </div>
</a>
{% empty %}<div class="card muted">לא נמצאו חברים.</div>{% endfor %}
{% endblock %}
```

Create `backend/community/templates/community/profile.html`:

```html
{% extends "community/base.html" %}
{% block title %}{{ person.display_name }}{% endblock %}
{% block content %}
<div class="card row">
  {% if person.avatar %}<img class="avatar" src="/media/{{ person.avatar.name }}"
       alt="" style="width:72px;height:72px">
  {% else %}<div class="avatar" style="width:72px;height:72px"></div>{% endif %}
  <div class="grow">
    <h1 style="margin:0">{{ person.display_name }}</h1>
    <div class="muted">{{ person.occupation_display }}{% if person.city %} · {{ person.city }}{% endif %}
      · בקהילה מאז {{ person.created_at|date:"F Y" }}</div>
    {% if person.bio %}<p>{{ person.bio }}</p>{% endif %}
    {% if person.instagram %}
    <a style="color:var(--coral)" rel="noopener" target="_blank"
       href="https://instagram.com/{{ person.instagram|cut:"@" }}">אינסטגרם</a>
    {% endif %}
  </div>
</div>
{% if person.pk != request.member.pk %}
<a class="btn btn-coral" href="/dm/with/{{ person.pk }}">שלח/י הודעה 💬</a>
{% endif %}
<div id="post-list" style="margin-top:12px">
  {% include "community/partials/post_list.html" %}
</div>
{% endblock %}
```

Create `backend/community/templates/community/profile_edit.html`:

```html
{% extends "community/base.html" %}
{% block title %}הפרופיל שלי{% endblock %}
{% block content %}
<h1>הפרופיל שלי</h1>
<form class="card" method="post" enctype="multipart/form-data">{% csrf_token %}
  {% include "community/partials/form_errors.html" %}
  <label class="muted">שם תצוגה</label>
  <input class="field" name="display_name" maxlength="50" required
         value="{{ form.initial.display_name }}">
  <label class="muted" style="display:block;margin-top:10px">על עצמי</label>
  <textarea class="field" name="bio" maxlength="300">{{ form.initial.bio }}</textarea>
  <label class="muted" style="display:block;margin-top:10px">תמונת פרופיל</label>
  <input class="field" type="file" name="avatar"
         accept="image/jpeg,image/png,image/webp">
  <button class="btn btn-coral" style="margin-top:12px" type="submit">שמירה</button>
</form>
<form method="post" action="/logout">{% csrf_token %}
  <button class="btn" type="submit">התנתקות</button>
</form>
{% endblock %}
```

- [ ] **Step 3: run tests, verify pass**

Run: `cd backend && .venv/bin/python manage.py test community -v 2`
Expected: PASS

- [ ] **Step 4: commit**

```bash
git add backend/community
git commit -m "feat(community): member directory with filters, profiles, profile edit

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 15: DM models + thread view + send

**Files:**
- Modify: `backend/community/models.py` (append), `backend/community/urls.py`
- Create: `backend/community/views_dm.py`, `backend/community/templates/community/dm_thread.html`, `backend/community/templates/community/partials/messages_page.html`
- Test: `backend/community/tests/test_dm.py`

**Interfaces:**
- Produces: `Conversation.for_pair(a, b) -> Conversation` (pk-ordered pair, unique row per pair); `conversation.other(member)`; `conversation.involves(member) -> bool`; `Message(conversation, sender, text≤2000, created_at, read_at)` with related name `conversation.messages`.
- Produces: `GET /dm/with/<member_id>` → redirect to `/dm/t/<conversation_id>`; `GET /dm/t/<id>` thread page (marks incoming unread as read); `POST /dm/t/<id>/send` (bound 2000, 60/hr, redirect back); `GET /dm/t/<id>/messages?after=<msg_id>` polling partial (also marks read). Non-participants get 404.

- [ ] **Step 1: failing tests**

Create `backend/community/tests/test_dm.py`:

```python
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
        m2 = Message.objects.create(conversation=conv, sender=self.yossi,
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
```

Run: `cd backend && .venv/bin/python manage.py test community.tests.test_dm -v 2`
Expected: FAIL — models/URLs missing

- [ ] **Step 2: implement**

Append to `backend/community/models.py`:

```python
class Conversation(models.Model):
    # pk-ordered pair → exactly one row per pair of members
    member_low = models.ForeignKey("accounts.Member", on_delete=models.CASCADE,
                                   related_name="+")
    member_high = models.ForeignKey("accounts.Member", on_delete=models.CASCADE,
                                    related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["member_low", "member_high"], name="uniq_conversation_pair")]

    @classmethod
    def for_pair(cls, a, b):
        lo, hi = sorted((a, b), key=lambda m: m.pk)
        conv, _ = cls.objects.get_or_create(member_low=lo, member_high=hi)
        return conv

    def involves(self, member):
        return member.pk in (self.member_low_id, self.member_high_id)

    def other(self, member):
        return self.member_high if member.pk == self.member_low_id \
            else self.member_low


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE,
                                     related_name="messages")
    sender = models.ForeignKey("accounts.Member", on_delete=models.CASCADE,
                               related_name="sent_messages")
    text = models.CharField(max_length=2000)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
```

Create `backend/community/views_dm.py`:

```python
from django import forms
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import member_required
from accounts.models import Member
from accounts.throttle import allow

from .models import Conversation, Message


class MessageForm(forms.Form):
    text = forms.CharField(max_length=2000)


def _own_conversation(request, conversation_id):
    conv = get_object_or_404(Conversation, pk=conversation_id)
    if not conv.involves(request.member):
        raise Http404
    return conv


def _mark_read(conv, member):
    (conv.messages.filter(read_at__isnull=True)
     .exclude(sender=member).update(read_at=timezone.now()))


@member_required
def open_with(request, member_id):
    if member_id == request.member.pk:
        raise Http404
    other = get_object_or_404(Member, pk=member_id, onboarded=True)
    conv = Conversation.for_pair(request.member, other)
    return redirect("community:dm_thread", conversation_id=conv.pk)


@member_required
def thread(request, conversation_id):
    conv = _own_conversation(request, conversation_id)
    _mark_read(conv, request.member)
    msgs = conv.messages.select_related("sender")
    return render(request, "community/dm_thread.html",
                  {"conv": conv, "msgs": msgs,
                   "other": conv.other(request.member),
                   "last_id": msgs.last().pk if msgs.exists() else 0})


@member_required
def send(request, conversation_id):
    conv = _own_conversation(request, conversation_id)
    if request.method != "POST":
        return redirect("community:dm_thread", conversation_id=conv.pk)
    form = MessageForm(request.POST)
    if form.is_valid() and allow(f"dm:{request.member.pk}", 60, 3600):
        Message.objects.create(conversation=conv, sender=request.member,
                               text=form.cleaned_data["text"])
    return redirect("community:dm_thread", conversation_id=conv.pk)


@member_required
def poll(request, conversation_id):
    conv = _own_conversation(request, conversation_id)
    try:
        after = int(request.GET.get("after", 0))
    except ValueError:
        after = 0
    newer = conv.messages.filter(pk__gt=after).select_related("sender")
    _mark_read(conv, request.member)
    return render(request, "community/partials/messages_page.html",
                  {"msgs": newer, "me": request.member})
```

Append to `backend/community/urls.py` (import `views_dm`):

```python
    path("dm/with/<int:member_id>", views_dm.open_with, name="dm_with"),
    path("dm/t/<int:conversation_id>", views_dm.thread, name="dm_thread"),
    path("dm/t/<int:conversation_id>/send", views_dm.send, name="dm_send"),
    path("dm/t/<int:conversation_id>/messages", views_dm.poll, name="dm_poll"),
```

Create `backend/community/templates/community/partials/messages_page.html`:

```html
{% for m in msgs %}
<div class="card" data-msg-id="{{ m.pk }}"
     style="max-width:85%;{% if m.sender.pk == me.pk %}margin-inline-start:auto;background:var(--oxblood){% endif %}">
  <div>{{ m.text }}</div>
  <div class="muted">{{ m.created_at|date:"H:i" }}</div>
</div>
{% endfor %}
```

Create `backend/community/templates/community/dm_thread.html`:

```html
{% extends "community/base.html" %}
{% block title %}{{ other.display_name }}{% endblock %}
{% block content %}
<div class="row" style="margin-bottom:10px">
  <a class="btn" href="/dm">→</a>
  <h1 style="margin:0" class="grow">{{ other.display_name }}</h1>
</div>
<div id="messages"
     hx-get="/dm/t/{{ conv.pk }}/messages"
     hx-trigger="every 5s"
     hx-vals='js:{"after": lastMsgId()}'
     hx-swap="beforeend"
     hx-on::after-swap="afterAppend()">
  {% include "community/partials/messages_page.html" with me=request.member %}
</div>
<form method="post" action="/dm/t/{{ conv.pk }}/send">{% csrf_token %}
  <div class="row" style="margin-top:10px">
    <input class="field grow" name="text" maxlength="2000" required
           placeholder="הודעה…" autocomplete="off">
    <button class="btn btn-coral" type="submit">שליחה</button>
  </div>
</form>
<script>
  function lastMsgId() {
    const items = document.querySelectorAll('#messages [data-msg-id]');
    return items.length ? items[items.length - 1].dataset.msgId : 0;
  }
  function afterAppend() { window.scrollTo(0, document.body.scrollHeight); }
  afterAppend();
</script>
{% endblock %}
```

- [ ] **Step 3: migrate + run tests**

Run: `cd backend && .venv/bin/python manage.py makemigrations community && .venv/bin/python manage.py test community -v 2`
Expected: migration created; PASS

- [ ] **Step 4: commit**

```bash
git add backend/community
git commit -m "feat(community): 1:1 DMs — singleton pair conversations, thread, 5s polling

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 16: DM inbox + unread badge

**Files:**
- Modify: `backend/community/views_dm.py`, `backend/community/urls.py`
- Create: `backend/community/templates/community/dm_list.html`, `backend/community/templates/community/partials/dm_badge.html`
- Test: append to `backend/community/tests/test_dm.py`

**Interfaces:**
- Produces: `GET /dm` — conversations of the current member, newest-activity first, each with `other`, last message snippet, unread count; `GET /dm/badge` — total unread count, rendered as `<span class="badge">N</span>` or empty when 0 (polled by the tab bar every 30s).

- [ ] **Step 1: failing tests** — append to `test_dm.py`:

```python
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
```

Run: `cd backend && .venv/bin/python manage.py test community.tests.test_dm -v 2`
Expected: new tests FAIL — 404

- [ ] **Step 2: implement** — append to `views_dm.py`:

```python
from django.db.models import Count, Max, Q


@member_required
def inbox(request):
    me = request.member
    convs = (Conversation.objects
             .filter(Q(member_low=me) | Q(member_high=me))
             .select_related("member_low", "member_high")
             .annotate(last_at=Max("messages__created_at"),
                       unread=Count("messages", filter=Q(
                           messages__read_at__isnull=True)
                           & ~Q(messages__sender=me)))
             .exclude(last_at=None)
             .order_by("-last_at"))
    items = [{"conv": c, "other": c.other(me),
              "last": c.messages.last(), "unread": c.unread}
             for c in convs]
    return render(request, "community/dm_list.html", {"items": items})


@member_required
def badge(request):
    me = request.member
    total = (Message.objects
             .filter(Q(conversation__member_low=me)
                     | Q(conversation__member_high=me),
                     read_at__isnull=True)
             .exclude(sender=me).count())
    return render(request, "community/partials/dm_badge.html",
                  {"total": total})
```

Append to `backend/community/urls.py`:

```python
    path("dm", views_dm.inbox, name="dm"),
    path("dm/badge", views_dm.badge, name="dm_badge"),
```

Create `backend/community/templates/community/partials/dm_badge.html`:

```html
{% if total %}<span class="badge">{{ total }}</span>{% endif %}
```

Create `backend/community/templates/community/dm_list.html`:

```html
{% extends "community/base.html" %}
{% block title %}הודעות{% endblock %}
{% block content %}
<h1>הודעות</h1>
{% for item in items %}
<a class="card row" href="/dm/t/{{ item.conv.pk }}"
   style="color:var(--ink);text-decoration:none">
  {% if item.other.avatar %}<img class="avatar" src="/media/{{ item.other.avatar.name }}" alt="">
  {% else %}<div class="avatar"></div>{% endif %}
  <div class="grow">
    <strong>{{ item.other.display_name }}</strong>
    <div class="muted">{{ item.last.text|truncatechars:60 }}</div>
  </div>
  {% if item.unread %}<span class="badge">{{ item.unread }}</span>{% endif %}
</a>
{% empty %}
<div class="card muted">אין שיחות עדיין — מצאו מישהו בדף החברים 💬</div>
{% endfor %}
{% endblock %}
```

- [ ] **Step 3: run tests, verify pass**

Run: `cd backend && .venv/bin/python manage.py test community -v 2`
Expected: PASS

- [ ] **Step 4: commit**

```bash
git add backend/community
git commit -m "feat(community): DM inbox with unread counts + polled nav badge

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 17: Reports

**Files:**
- Modify: `backend/community/models.py`, `backend/community/admin.py`, `backend/community/urls.py`
- Create: `backend/community/views_reports.py`, `backend/community/templates/community/report.html`
- Test: `backend/community/tests/test_reports.py`

**Interfaces:**
- Produces: `Report(reporter, post?, comment?, reason≤500, handled, created_at)` — DB check constraint: exactly one of post/comment set. `GET /report?post=<id>` or `?comment=<id>` shows the form; POST creates and redirects to `/` with a flash message. Limit 10 reports/hr/member.

- [ ] **Step 1: failing tests**

Create `backend/community/tests/test_reports.py`:

```python
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
```

Run: `cd backend && .venv/bin/python manage.py test community.tests.test_reports -v 2`
Expected: FAIL

- [ ] **Step 2: implement**

Append to `backend/community/models.py`:

```python
class Report(models.Model):
    reporter = models.ForeignKey("accounts.Member", on_delete=models.CASCADE,
                                 related_name="reports")
    post = models.ForeignKey(Post, on_delete=models.CASCADE,
                             null=True, blank=True, related_name="reports")
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE,
                                null=True, blank=True, related_name="reports")
    reason = models.CharField("סיבה", max_length=500)
    handled = models.BooleanField("טופל", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["handled", "-created_at"]
        verbose_name = "דיווח"
        verbose_name_plural = "דיווחים"
        constraints = [models.CheckConstraint(
            name="report_exactly_one_target",
            condition=(models.Q(post__isnull=False, comment__isnull=True)
                       | models.Q(post__isnull=True, comment__isnull=False)))]
```

(Django ≥5.1 uses `condition=`; on older versions the kwarg is `check=` — the pinned Django 5.2 wants `condition=`.)

Append to `backend/community/admin.py`:

```python
from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("reporter", "post", "comment", "reason",
                    "created_at", "handled")
    list_filter = ("handled", "created_at")
    list_editable = ("handled",)
```

Create `backend/community/views_reports.py`:

```python
from django import forms
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import member_required
from accounts.throttle import allow

from .models import Comment, Post, Report


class ReportForm(forms.Form):
    reason = forms.CharField(max_length=500)


def _target(request):
    post_id = request.GET.get("post")
    comment_id = request.GET.get("comment")
    if post_id:
        return {"post": get_object_or_404(Post, pk=post_id)}
    if comment_id:
        return {"comment": get_object_or_404(Comment, pk=comment_id)}
    raise Http404


@member_required
def report(request):
    target = _target(request)
    form = ReportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if allow(f"report:{request.member.pk}", 10, 3600):
            Report.objects.create(reporter=request.member,
                                  reason=form.cleaned_data["reason"], **target)
            messages.success(request, "תודה, הדיווח התקבל ויטופל.")
        return redirect("community:feed")
    return render(request, "community/report.html",
                  {"form": form, "qs": request.META.get("QUERY_STRING", "")})
```

Append to `backend/community/urls.py` (import `views_reports`):

```python
    path("report", views_reports.report, name="report"),
```

Create `backend/community/templates/community/report.html`:

```html
{% extends "community/base.html" %}
{% block title %}דיווח{% endblock %}
{% block content %}
<div class="card">
  <h1>דיווח על תוכן</h1>
  <p class="muted">הדיווח מגיע ישירות למנהלת הקהילה.</p>
  <form method="post" action="/report?{{ qs }}">{% csrf_token %}
    {% include "community/partials/form_errors.html" %}
    <textarea class="field" name="reason" maxlength="500" required
              placeholder="מה הבעיה בתוכן הזה?"></textarea>
    <button class="btn btn-coral" style="margin-top:10px" type="submit">שליחת דיווח</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 3: migrate + run FULL suite**

Run: `cd backend && .venv/bin/python manage.py makemigrations community && .venv/bin/python manage.py test -v 1`
Expected: migration created; the ENTIRE suite (accounts + community + catalog) PASSES.

- [ ] **Step 4: commit**

```bash
git add backend/community
git commit -m "feat(community): content reports with admin queue

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 18: Landing link, Docker/collectstatic, deploy runbook

**Files:**
- Modify: `frontend/public/index.html`, `backend/Dockerfile`
- Create: `docs/deploy-community.md`

**Interfaces:**
- Consumes: everything above.
- Produces: deployable image (static collected at build), member-facing entry link, and a copy-paste runbook for the debian01 deploy.

- [ ] **Step 1: landing page link**

In `frontend/public/index.html`, locate the header/nav area (search for `<nav` or `<header`; this file was heavily reworked in the waitlist commit — read it first). Add inside the nav, styled like sibling links:

```html
<a href="https://community.navonsimon.com" class="nav-link">כניסת חברים</a>
```

If the nav has no obvious link list, place the anchor immediately after the hero CTA button instead, using the CTA's secondary style. Verify by opening the file in a browser: link visible on mobile width, RTL alignment correct.

- [ ] **Step 2: Dockerfile collectstatic**

In `backend/Dockerfile`, after the `COPY . /app/` line and before the `USER appuser` block, add:

```dockerfile
RUN python manage.py collectstatic --noinput
```

(Works env-free thanks to the Task-1 fallbacks; whitenoise then serves hashed files.)

- [ ] **Step 3: write the deploy runbook**

Create `docs/deploy-community.md`:

```markdown
# Deploying the community (first time)

Run on debian01 (or via the Mac mount for file edits). The authoritative
conventions live in /srv/the-way-we-do-things-including-NGINX.md — follow its
current pattern for DNS + nginx; the snippets below fit that doc as of 2026-07-28.

1. Reconcile server checkout (its old uncommitted work is now in git, byte-identical):
   cd /srv/barbers && git status   # confirm only known files listed
   git checkout -- . && git clean -n   # clean -n must list nothing unexpected
   git pull
2. Env: add community.navonsimon.com to DJANGO_ALLOWED_HOSTS in /srv/barbers/.env
3. Build + migrate:
   docker compose up -d --build
   docker compose exec backend python manage.py migrate
4. DNS: create community.navonsimon.com the same way panim was created (CF API
   token on the server), pointing identically to barbers.navonsimon.com's target.
5. nginx: new server block in the shared config, one listen 80 per project:

   server {
       listen 80;
       server_name community.navonsimon.com;
       client_max_body_size 6m;   # 5MB uploads + form overhead
       location / {
           proxy_pass http://127.0.0.1:8015;
           proxy_set_header Host $host;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }

   nginx -t && systemctl reload nginx
6. Update the port table in /srv/the-way-we-do-things-including-NGINX.md:
   | community (barbers) | community.navonsimon.com | — | 8015 (shared) |
7. In Django admin: create initial groups (ברברים 💈, מעצבות שיער ✂️, ציפורניים 💅,
   איפור 💄 — confirm names with the client) and approve a test application.
8. Smoke test: login with the test phone (code appears in
   docker compose logs backend and in admin → קודי כניסה), post, comment, like,
   join group, DM, upload avatar, verify /media/... 302s when logged out.
```

- [ ] **Step 4: verify + final full run**

Run: `cd backend && .venv/bin/python manage.py test -v 1`
Expected: full suite green.

Run: `cd backend && DJANGO_DEBUG=1 .venv/bin/python manage.py runserver`
Manual check on http://127.0.0.1:8000 — login page renders, styles load, tab bar hidden when anonymous.

- [ ] **Step 5: commit**

```bash
git add frontend/public/index.html backend/Dockerfile docs/deploy-community.md
git commit -m "feat: landing login link, build-time collectstatic, community deploy runbook

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Post-plan notes for the executor

- Tests import helpers across files (`community.tests.test_models.make_member`) — keep those helper signatures stable.
- If any Hebrew string assertion fails on punctuation, match a distinctive substring instead of the full sentence.
- `python` in commands = `backend/.venv/bin/python`.
- Never run Docker locally; the server does the containerizing (house rule).
