# Notify on Android — app install & Play Store AAB

## Path A — Free, no Play Store (recommended first)

1. Open the site in **Chrome on Android**: https://samdaniel05.github.io/notify-app/
2. Menu → **Install app** / **Add to Home screen**
3. Sign in → **Delivery** → **Enable app notifications**
4. Allow notification permission when asked
5. **Send test notification**

This uses **Web Push** (same system Chrome apps use). No ntfy required.

### Server env (Render)

```
VAPID_PUBLIC_KEY=<from generate step>
VAPID_PRIVATE_KEY=<from generate step>
VAPID_SUBJECT=mailto:your@email.com
```

Generate keys once (Python):

```bash
pip install py-vapid
vapid --gen
```

Or use keys documented in FREE_SETUP.md if provided for your deploy.

## Path B — Real APK / AAB for Play Store

Requires:

- One-time **Google Play Console** fee (~$25)
- Android Studio on your PC
- Capacitor wrapping this web app

Rough steps later:

```bash
npm create @capacitor/app
# point web dir at frontend/dist
npx cap add android
npx cap sync
# open Android Studio → Build → Generate Signed Bundle / APK
```

Play Store AAB **cannot** be built and signed fully inside this chat environment without your keystore and Play account.

**Order:** get Path A working (install + web push), then do Path B when you want Store listing.
