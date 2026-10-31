# Notify on Android

## Path A — Free installable app (do this now)

Works like an app icon + system notifications. **No ntfy required.**

### 1. Render environment

Add:

```
VAPID_PUBLIC_KEY=BHxu0qJNxLXq4tMOmaaEJYrik5K8S-GGzZbgsfaXXULZkgkCc2sqFpZSpUMEdQPGOY797GKwELJntulFuS1ACKM
VAPID_PRIVATE_KEY=HOmFVeGupsZTj0HZ7F_hYsI4eBujNA6nC3WFQxehk_Y
VAPID_SUBJECT=mailto:samdaniel2k04@gmail.com
```

(You can generate your own later with `pip install py-vapid && vapid --gen`.)

Redeploy Render after saving.

### 2. On your Android phone (Chrome)

1. Open https://samdaniel05.github.io/notify-app/
2. Chrome menu → **Install app** / **Add to Home screen**
3. Sign in
4. **Delivery** → **Enable app notifications** → Allow
5. **Send test notification**

You should get a normal Android notification from Notify.

## Path B — Play Store AAB / APK

Cannot be fully built and signed inside this chat (needs your keystore + Play Console ~$25).

Later on your PC:

```bash
npm create @capacitor/app
# use webDir = frontend/dist
npx cap add android
npx cap sync
# Android Studio → Generate Signed Bundle
```

See Capacitor docs. Path A is the free production path today.
