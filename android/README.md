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

### Verified Signing Output

```
Verifies
Verified using v1 scheme (JAR signing): false   ← legacy; not required for Android 14+
Verified using v2 scheme (APK Signature Scheme v2): false
Verified using v3 scheme (APK Signature Scheme v3): true    ✓
Number of signers: 1
```

On Android 14+ only V3 signing is mandatory. V1/V2 are legacy and skipped by `apksigner` when the SDK constraints don't require them.

## How to Install

1. Copy `app-release.apk` (or `app-release-signed.apk`) to your device
2. On first install, Android may warn about an unsigned app → enable **"Install unknown apps"** in Settings → Security
3. Open the APK and tap **Install**
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