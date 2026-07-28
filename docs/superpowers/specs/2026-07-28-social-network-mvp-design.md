# The Craft — Social Network MVP — Design

**Date:** 2026-07-28
**Status:** Approved in brainstorming session (pending final spec review)
**Client:** The Craft (barbers.navonsimon.com) — closed, vetted community of Israeli hair & beauty professionals

## Goal

Turn the vetted applicant list into a living community: approved professionals log in,
see each other, post, react, talk. Mobile-first, Hebrew RTL, same ClickA. dark
oxblood/coral brand as the landing page.

## Decisions (made with client 2026-07-28)

| Question | Decision |
|---|---|
| MVP features | Feed (posts/likes/comments) + profiles/directory + 1-on-1 DMs + groups — all four in v1, each kept deliberately simple |
| Auth | Phone + SMS OTP; SMS sending **stubbed** behind a pluggable interface (codes visible in server log + admin page) until a provider is chosen |
| Brand/domain | Subdomain **community.navonsimon.com**, same ClickA. aesthetic; landing page gets a "כניסת חברים" link |
| Architecture | Extend the existing barbers Django backend (same repo, compose, Postgres, Valkey); UI = Django templates + htmx; no new container or port |

## Architecture

```
barbers/ (existing repo)
├─ backend/
│  ├─ catalog/    ← existing vetting funnel (untouched)
│  ├─ accounts/   ← NEW: Member, OTP auth, onboarding
│  └─ community/  ← NEW: feed, comments, likes, groups, DMs, reports
│                    + templates/ + static/ (htmx UI)
├─ frontend/      ← landing page (one new login link)
└─ docker-compose.yml (unchanged services)
```

- Community UI served by the existing gunicorn on **port 8015** at `/` (existing
  `/api` and `/admin` URLs keep working). WhiteNoise serves collected static files.
- nginx (host): new server block `community.navonsimon.com → 127.0.0.1:8015`.
- DNS record created via the Cloudflare API token on debian01.
- `/srv/the-way-we-do-things-including-NGINX.md` port table gets the new domain row.

## Data model

### `accounts` app

**Member**
- `user` OneToOne → `auth.User`, created on first successful OTP login (gives
  sessions / `request.user` / admin for free)
- `application` OneToOne → `catalog.Barbershop` (approved rows only; the vetting
  funnel is the member registry — no data sync)
- `display_name` (≤50, prefilled from `owner_name`), `avatar` (image), `bio` (≤300)
- `phone_e164` (unique, normalized), `last_seen`
- Occupation / city / Instagram are read through `application` — never duplicated.

**OtpCode** — `phone_e164`, 6-digit code, `created_at`, `expires_at` (+5 min),
`attempts` (max 5), `used`. SMS goes through `accounts.sms.send_sms(phone, text)`;
the MVP implementation logs the code and lists it in a staff-only admin page.
Swapping in Twilio/019/InforU later = one module + API key.

### `community` app

- **Group** — name, emoji, description, `created_by` staff; client creates groups in
  admin. **GroupMembership** — member × group, `joined_at`, unique pair. Members
  join/leave freely.
- **Post** — author FK, `group` FK nullable (null = main feed), `text` (≤2000),
  optional image, `created_at`, `is_deleted` (soft delete). Home feed shows ALL
  posts with a group chip (small community — one lively feed); group pages filter.
- **Comment** — post FK, author FK, `text` (≤500), `created_at`, `is_deleted`.
- **Like** — post FK × member FK, unique together, `created_at`.
- **Conversation** — `member_low` / `member_high` FK pair, normalized by member id
  so each pair exists once (unique constraint).
- **Message** — conversation FK, sender FK, `text` (≤2000), `created_at`,
  `read_at` nullable (drives unread badges).
- **Report** — reporter FK, generic target (post or comment), `reason` (≤500),
  `created_at`, `handled` flag; staff-only admin queue.

## Auth flow

1. `/login`: phone input → POST. Server normalizes to E.164 (`0xx…` → `+972xx…`)
   and compares against normalized `Barbershop.phone` of **approved** rows only.
2. Response is always "אם המספר שלך רשום בקהילה — נשלח קוד" (no membership oracle).
3. OTP throttles (Valkey): 3 requests / phone / 15 min; 10 requests / IP / hour.
4. `/login/verify`: 6-digit code, ≤5 attempts, 5-minute TTL, single-use →
   `get_or_create` User + Member → Django session, 30-day expiry.
5. First login → onboarding page: confirm `display_name`, optional avatar upload.
6. Every community view requires login; anonymous → redirect to `/login`.

## Features / UX

Mobile-first, RTL, Frank Ruhl Libre + Heebo, dark oxblood/coral. Bottom tab bar:
**פיד · קבוצות · חברים · הודעות · פרופיל**.

- **Feed** — composer on top (text + optional photo + destination: main feed or a
  joined group); infinite scroll via htmx (20 posts/page); tap-to-like with
  optimistic htmx swap; comments expand inline under the post.
- **Groups** — list with member counts + join/leave buttons; group page = filtered
  feed + composer scoped to the group.
- **Directory (חברים)** — searchable list (name), filter chips (occupation, city);
  member card → profile page: avatar, occupation, city, Instagram link,
  member-since, their posts, "שלח הודעה" button.
- **DMs (הודעות)** — conversation list with unread badges; thread view htmx-polls
  every ~5 s while open; nav badge polls every ~30 s. No websockets in MVP.
- **Profile (פרופיל)** — own profile edit: display name, bio, avatar; logout.
- **Moderation** — soft-delete via Django admin; member-facing "דיווח" button on
  posts/comments feeds the Report admin queue.

## Abuse resistance (house rule: every input bounded)

- Text bounds: post 2000 · comment 500 · DM 2000 · bio 300 · display name 50 ·
  report reason 500. Enforced in forms AND model constraints.
- Images (avatar, post photo): ≤5 MB, jpeg/png/webp only, re-encoded with Pillow
  (strips EXIF/GPS), longest side capped at 1600 px.
- Write rate-limits per member (Valkey): 10 posts/hr · 30 comments/hr · 60 DMs/hr ·
  60 likes/hr. OTP throttles above.
- **All media served behind login** — community photos are never public URLs;
  Django view streams from the media volume after auth check (fine at MVP scale).
- CSRF everywhere, sessions HttpOnly + Secure, `X-Forwarded-Proto` honored (already
  configured at the edge).

## Error handling

- Hebrew inline form errors rendered as htmx partials.
- Throttle hits → friendly 429 partial ("לאט לאט 🙂 נסו שוב בעוד כמה דקות").
- SMS sender failure → logged with alert-level severity; user still sees the
  generic "if registered, code sent" message (no membership/infra leak).
- DM polling failures degrade silently (retry next tick); no error toasts for
  transient network noise.

## Testing

Django test suite (`manage.py test`), covering:

- OTP lifecycle: request/verify happy path, expiry, attempt cap, single-use,
  throttle behavior, unapproved-applicant + unknown-phone rejection (same
  response body as success), phone normalization (`05x`, `+9725x`, spaces/dashes).
- Permission walls: anonymous redirect; member C cannot fetch A↔B conversation;
  soft-deleted posts/comments invisible to members but present in admin.
- Bounds: over-limit text rejected at form and model level; oversized/wrong-type
  image rejected; rate limits return 429.
- Behavior: like uniqueness (double-tap = one like), unread count correctness,
  group-scoped posting requires membership, report creates queue row.

## Out of scope (v2+)

Real SMS provider wiring (interface is ready) · websockets/push notifications ·
native app · public profiles/SEO · group DMs · media CDN · email notifications.

## Deployment

Standard flow: develop on Mac (`~/Developer/barbers`) → push to GitHub → pull on
debian01 → `docker compose up -d --build`. Then: `migrate`, `collectstatic`,
create groups in admin, add nginx block + CF DNS record, update the process doc.

**Pre-existing drift note:** the server working tree had ~470 lines of uncommitted
work (waitlist/certificate feature). Recovered into the Mac clone as its own
commit before this design lands; server reconciles with `git checkout -- . && git
pull` at next deploy (content identical).
