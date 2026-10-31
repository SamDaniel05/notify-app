# Notify on Android

## Landing + APK download (one click)

**Site:** https://samdaniel05.github.io/notify-app/get/

- Shows app details
- **Download APK** pulls the latest file from GitHub Release `apk-latest`

## How the APK is produced

GitHub Action: `.github/workflows/build-apk.yml`

- Runs on push to `mobile/android/**` or **Actions → Build APK → Run workflow**
- Uploads a **debug APK** to release tag `apk-latest`

### First time

1. GitHub → **Actions** → **Build APK** → **Run workflow**
2. Wait until green
3. Open https://samdaniel05.github.io/notify-app/get/ → **Download APK**

## Install on phone

1. Download APK
2. Allow install from browser/files
3. Open Notify → sign up → Delivery → Enable app notifications

## Web Push (optional server env)

```
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
VAPID_SUBJECT=mailto:you@email.com
```

## Play Store AAB (later)

See `mobile/BUILD_AAB.md` — signed bundle on your PC when you pay the Play fee.
