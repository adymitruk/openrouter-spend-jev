plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// ── Signing credentials ──────────────────────────────────────────────────────
// Taken from keystore.properties (gitignored — copy keystore.properties.example)
// or from environment variables of the same name (CI secrets). This repository is
// public: no credential belongs in this file.
val keystoreProps = java.util.Properties().apply {
    val f = rootProject.file("keystore.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

fun cred(name: String): String? = keystoreProps.getProperty(name) ?: System.getenv(name)

android {
    namespace = "com.orspend.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.orspend.app"
        minSdk = 28
        targetSdk = 34
        versionCode = 2
        versionName = "1.1"
    }

    signingConfigs {
        create("releaseSign") {
            storeFile = file(rootProject.projectDir.resolve(cred("storeFile") ?: "release-key.jks"))
            storePassword = cred("storePassword")
            keyAlias = cred("keyAlias") ?: "orspend"
            keyPassword = cred("keyPassword")
            enableV1Signing = true
            enableV2Signing = true
            enableV3Signing = true
        }
    }

    buildTypes {
        debug {
            signingConfig = signingConfigs.getByName("releaseSign")
        }
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("releaseSign")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    kotlinOptions {
        jvmTarget = "11"
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    // No external dependencies — all APIs from the Android SDK
}