plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

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
            storeFile = file(rootProject.projectDir.resolve("release-key.jks"))
            storePassword = "REDACTED"
            keyAlias = "orspend"
            keyPassword = "REDACTED"
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