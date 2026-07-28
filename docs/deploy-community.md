# Deploying the community (first time)

Run on debian01 (or via the Mac mount for file edits). The authoritative
conventions live in `/srv/the-way-we-do-things-including-NGINX.md` — follow its
current pattern for DNS + nginx; the snippets below fit that doc as of 2026-07-28.

1. **Reconcile the server checkout** (its old uncommitted work is now in git,
   byte-identical):

   ```bash
   cd /srv/barbers && git status        # confirm only known files listed
   git checkout -- . && git clean -n    # clean -n must list nothing unexpected
   git pull
   ```

2. **Env:** add `community.navonsimon.com` to `DJANGO_ALLOWED_HOSTS` in
   `/srv/barbers/.env`.

3. **Build + migrate:**

   ```bash
   docker compose up -d --build
   docker compose exec backend python manage.py migrate
   ```

4. **DNS:** create `community.navonsimon.com` the same way panim was created
   (CF API token on the server), pointing identically to
   `barbers.navonsimon.com`'s target.

5. **nginx:** new server block in the shared config, one `listen 80` per
   project:

   ```nginx
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
   ```

   Then `nginx -t && systemctl reload nginx`.

6. **Process doc:** add to the port table in
   `/srv/the-way-we-do-things-including-NGINX.md`:

   `| community (barbers) | community.navonsimon.com | — | 8015 (shared) |`

7. **Seed content:** in Django admin create initial groups (ברברים 💈,
   מעצבות שיער ✂️, ציפורניים 💅, איפור 💄 — confirm names with the client) and
   approve a test application.

8. **Smoke test:** log in with the test phone (the OTP code appears in
   `docker compose logs backend` and in admin → קודי כניסה), post, comment,
   like, join a group, DM, upload an avatar, and verify `/media/...` URLs
   redirect (302) when logged out.

## SMS provider (post-MVP)

OTP delivery is stubbed (`accounts/sms.py` logs the code; admin shows it).
To go live with real SMS: implement the same `send_sms(phone_e164, text)`
signature against Twilio / 019 / InforU and add the provider's credentials to
`.env`. Nothing else changes.
