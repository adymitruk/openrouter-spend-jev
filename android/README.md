# OpenRouter Spend Tracker — Android App

**`com.orspend.app`** — Shows current-month OpenRouter spend in a pinned (non-dismissible) notification. Set your management key (sk-or-...) in the app. No keys or dynamic info hardcoded or committed.

## Project Structure

```
android/
├── Persistent Expense Tracker Notification App.kt   (reference — prior work)
├── README.md                                          ← this file
├── .gitignore
└── OpenRouterSpend/
    ├── app/
    │   ├── build.gradle.kts
    │   └── src/main/
    │       ├── AndroidManifest.xml
    │       └── java/com/orspend/app/MainActivity.kt
    ├── build.gradle.kts
    ├── settings.gradle.kts
    └── release-key.jks                                   (generate, not committed)
```

## Prerequisites

- Java 17+ (`openjdk-17-jdk-headless`)
- Android SDK command-line tools (`sdkmanager`)
- Gradle 8.9 (any flavor — wrapper auto-downloaded)
- For APK signing: `keytool` (ships with Java)

## Build from Scratch (headless, no Android Studio)

### 1. One-time Setup

```bash
cd android/OpenRouterSpend

# Generate the gradle wrapper (committed as gradle-wrapper.properties only)
gradle wrapper --gradle-version 8.9

# Launch the APK (if you previously built with a debug keystore, this is optional)
# Create a release key store (⚠️ for development only — KMS or CI secrets in production)
keytool -genkeypair -v \
    -keystore release-key.jks \
    -alias orspend \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass REDACTED -keypass REDACTED \
    -dname "CN=ORSpend, OU=Dev, O=ORSpend, L=City, S=State, C=US"
```

### 2. Build

```bash
cd android/OpenRouterSpend
./gradlew assembleRelease
```

APK output: `app/build/outputs/apk/release/app-release.apk`

### 3. Verify (every artefact)

```bash
# 3a. Check 4-byte alignment (resources.arsc must be uncompressed)
zipalign -c -v 4 app/build/outputs/apk/release/app-release.apk

# 3b. Check signatures
apksigner verify --verbose app/build/outputs/apk/release/app-release.apk

# 3c. Dump package metadata
aapt2 dump badging app/build/outputs/apk/release/app-release.apk
```

### 4. Re-sign with V1+V2+V3 (optional — V3 is sufficient for Android 14+)

```bash
apksigner sign \
    --ks release-key.jks \
    --ks-pass pass:REDACTED \
    --key-pass pass:REDACTED \
    --v1-signing-enabled \
    --v2-signing-enabled \
    --v3-signing-enabled \
    --out app-release-signed.apk \
    app/build/outputs/apk/release/app-release.apk
```

## Known Fixes Applied (Installation Failures)

This app was tested on a Samsung Galaxy Fold (Android 14/15/16). The following fixes were required to pass Package Manager verification:

| Fix | File | What |
|-----|------|------|
| `FOREGROUND_SERVICE_DATA_SYNC` permission | `AndroidManifest.xml` | Added missing permission for Android 14+ |
| `android:foregroundServiceType="dataSync"` | `AndroidManifest.xml` | Explicit service type declaration on `<service>` |
| `android:extractNativeLibs="false"` | `AndroidManifest.xml` | Prevents resource extraction issues |
| 3-arg `startForeground(id, notification, type)` | `MainActivity.kt:SpendService` | Prevents `MissingForegroundServiceTypeException` on SDK >= 34 |
| V1/V2/V3 signing enabled | `app/build.gradle.kts` | `signingConfigs.releaseSign` with all schemes |
| Release keystore (`release-key.jks`) | app root | Replaced ad-hoc `androiddebugkey` with proper `orspend` alias |
| `targetSdk = 34` | `app/build.gradle.kts` | Matches target device Android version |

## Critical Signing Pitfalls

### Gradle AGP silently drops V1/V2 when targetSdk ≥ 24

AGP 8.x **ignores** `enableV1Signing`/`enableV2Signing` in `signingConfigs` when `minSdk >= 24`. The build will only emit V3. You **must** re-sign after the Gradle build to get the full V1+V2+V3 suite required by Samsung One UI 6+/7/8.

**The magic incantation:**

```bash
zipalign -f -p -v 4 unsigned.apk aligned.apk
apksigner sign \
  --ks release-key.jks --ks-pass pass:REDACTED --key-pass pass:REDACTED \
  --v1-signing-enabled true --v2-signing-enabled true --v3-signing-enabled true \
  --min-sdk-version 21 \                    # ← THIS is critical for V1/V2 emission
  --out final-signed.apk \
  aligned.apk
```

`--min-sdk-version 21` forces `apksigner` to emit V1/V2 signatures which it otherwise skips when the APK's manifest declares `targetSdk >= 24`.

### `apksigner verify` is misleading

`apksigner verify --verbose` reports `v1: false, v2: false` even when both are present, if the APK's `targetSdk >= 24`. To see the **real** signature state:

```bash
# Use min-sdk-version to match the signing range
apksigner verify --verbose --min-sdk-version 21 app-release.apk
# → Verified using v1 scheme (JAR signing): true
# → Verified using v2 scheme (APK Signature Scheme v2): true
# → Verified using v3 scheme (APK Signature Scheme v3): true

# Or use jarsigner for a true V1 check:
jarsigner -verify app-release.apk
# → jar verified.
```

### `pm install -r` on Samsung: Binder IPC error

Trying to install with `pm install -r /path/to/app.apk` on Samsung devices (Galaxy Fold, One UI 8) may fail with:

```
cmd: Failure calling service package: Failed transaction (2147483646)
```

This is a **Binder IPC** communication error (Termux → PackageManagerService channel broken), not an APK issue. Possibly triggered by SELinux enforcing on Samsung. **Workaround:** copy the APK to the device and **tap it directly** in the file manager — Samsung's native installer will handle it.

```bash
# Does NOT work:
pm install -r /storage/emulated/0/Download/app.apk

# Use instead — tap the APK in file manager or use Settings:
Settings → Apps → Install APK (or tap the file in Downloads)
```

## Verified Signing Output (with the fix applied)

```
Verifies
Verified using v1 scheme (JAR signing): true    ✓
Verified using v2 scheme (APK Signature Scheme v2): true  ✓
Verified using v3 scheme (APK Signature Scheme v3): true  ✓
Number of signers: 1
```

All three schemes verified. Samsung One UI 6/7/8 accepts V1+V2+V3-signed APKs through the direct file-tap installation method.

## How to Install

1. Copy `app-release-v123.apk` to your device (via Telegram file download, USB, etc.)
2. **Do NOT use `pm install`** — tap the APK file directly in your file manager
3. Tap **Install** when the Android Package Manager dialog appears
4. Get a management key at https://openrouter.ai/keys (Admin scope)
5. Paste it into the app, tap **Fetch Now**, then toggle the switch to pin the notification

## What Goes into the APK vs What the User Enters

| In the APK (hardcoded / compiled) | Entered by user (not in source) |
|-----------------------------------|---------------------------------|
| OpenRouter API endpoint URL | Management key (sk-or-...) |
| App manifest, permissions | Refresh interval (future) |
| UI layout, notification layout | |
| NumberFormat locale (US) | |

The API key is stored in encrypted `SharedPreferences` scoped to the app.

## Full Build Pipeline (source → installable APK)

```bash
cd android/OpenRouterSpend

# 1. Bootstrap (once)
gradle wrapper --gradle-version 8.9
keytool -genkeypair -v -keystore release-key.jks \
  -alias orspend -keyalg RSA -keysize 2048 -validity 10000 \
  -storepass REDACTED -keypass REDACTED \
  -dname "CN=ORSpend, OU=Dev, O=ORSpend, L=City, S=State, C=US"

# 2. Build (Gradle — emits V3 only)
./gradlew clean assembleRelease

# 3. Align + re-sign with V1+V2+V3
zipalign -f -p -v 4 app/build/outputs/apk/release/app-release.apk release-aligned.apk
apksigner sign \
  --ks release-key.jks --ks-pass pass:REDACTED --key-pass pass:REDACTED \
  --v1-signing-enabled --v2-signing-enabled --v3-signing-enabled \
  --min-sdk-version 21 \
  --out app-release-v123.apk \
  release-aligned.apk

# 4. Verify
apksigner verify --verbose --min-sdk-version 21 app-release-v123.apk
zipalign -c -v 4 app-release-v123.apk
aapt2 dump badging app-release-v123.apk
jarsigner -verify app-release-v123.apk
```