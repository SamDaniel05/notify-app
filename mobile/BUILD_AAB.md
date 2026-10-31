# Build Notify AAB for Google Play

## Package identity (do not change after first upload)

- **applicationId / package name:** `app.notify.personal`
- **App name:** Notify
- **versionCode:** 1 (increase every Play upload)
- **versionName:** 1.0.0

## On your Windows / Mac PC

1. Install **Android Studio**.
2. Open the folder: `mobile/android` from this repo.
3. Wait for Gradle sync.
4. Menu: **Build → Generate Signed Bundle / APK**.
5. Choose **Android App Bundle**.
6. Create a **new keystore** (save file + passwords offline forever):
   - Example alias: `notify`
7. Build **release**.
8. Output file (upload this):

   `mobile/android/app/release/app-release.aab`

## Play Console (when ready)

1. Pay one-time developer fee.
2. Create app → package name **must** be `app.notify.personal`.
3. Upload the `.aab`.
4. Store listing, screenshots, privacy policy, content rating.

## Test APK without Play

Same wizard → choose **APK** instead of Bundle → install on phone.

## Bump version before next upload

In `android/app/build.gradle`:

```
versionCode 2
versionName "1.0.1"
```

## Never commit

- `*.jks` / `*.keystore`
- passwords
- `local.properties`
