# Notify — free production setup (you do these steps)

Code is ready. Only **accounts + env vars** need your login. No paid plugins required.

## Already done in code

- Chat intent + confirm watches
- Weather (Open-Meteo) + keyword (Google News RSS) + RSS checker
- `GET/POST /api/alerts/run-checks/?secret=...`
- `DATABASE_URL` support (Neon SSL on by default)
- GitHub Pages frontend

## Your checklist (about 20–30 minutes)

### 1. Neon free Postgres (stops data wipe)

1. Open https://neon.tech → sign up (GitHub login is fine).
2. Create a project (e.g. `notify`).
3. Copy the **connection string** (starts with `postgresql://...`).
   - Prefer the one that includes `sslmode=require` if shown.

### 2. Render env vars

On your Notify service → **Environment** → add/update:

| Key | Value |
|-----|--------|
| `DATABASE_URL` | Paste Neon connection string |
| `DB_SSL` | `1` |
| `CRON_SECRET` | Long random string (example: `notify-cron-` + random letters) |
| Keep existing | Email / Brevo / Gmail vars you already use |

Optional:

| Key | Value |
|-----|--------|
| `TELEGRAM_BOT_TOKEN` | From @BotFather if you use Telegram |

**Save** → wait for **redeploy** to finish.

### 3. Migrate DB on Render

After deploy with `DATABASE_URL`:

- Render → your service → **Shell** (if available), run:

```bash
cd backend && python manage.py migrate
```

If Shell is not available, set a one-off **Release Command** / start command that runs migrate first (many Render Django blueprints use):

```bash
python manage.py migrate && gunicorn config.wsgi:application
```

(Adjust path if your root is already `backend`.)

### 4. cron-job.org (keep awake + run alerts)

1. Open https://cron-job.org → free account.
2. **Job A — keep awake** (every 10 minutes):
   - URL: `https://notify-app-letm.onrender.com/api/health/`
   - Method: GET
3. **Job B — check watches** (every 15 or 20 minutes):
   - URL: `https://notify-app-letm.onrender.com/api/alerts/run-checks/?secret=YOUR_CRON_SECRET`
   - Method: GET
   - Replace `YOUR_CRON_SECRET` with the same value as on Render.

### 5. ntfy on your phone

1. Install **ntfy** from https://ntfy.sh/
2. Subscribe to a private topic (e.g. `notify-sam-chennai`).
3. In the app site → **Delivery** → save that topic → **Send test notification**.

### 6. Smoke test

1. https://samdaniel05.github.io/notify-app/
2. Create account → OTP from email → Chat → confirm a watch.
3. **Watches** shows it.
4. Wait for cron or hit run-checks URL yourself once.

## What you do NOT need

- No paid Render plan required for this path
- No domain required
- No extra Grok / GitHub plugins beyond what is already connected

## If something fails

- Deploy logs on Render after adding `DATABASE_URL`
- Open run-checks URL in browser: should return JSON `{"detail":"ok",...}` not 401
- Neon dashboard → check connection / storage

When steps 1–4 are done, reply with:

- Neon connected? (yes/no)
- CRON_SECRET set? (yes/no)
- Both cron jobs created? (yes/no)

and we continue testing the full alert loop.
