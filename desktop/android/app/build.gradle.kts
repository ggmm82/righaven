plugins {
    id("com.android.application")
    kotlin("android")
}

// The app's version follows RigHaven's VERSION (MAJOR.MINOR.PATCH).
val release = rootDir.resolve("../../VERSION").readText().trim()
val (major, minor, patch) = release.split("-")[0].split(".").map { it.toInt() }

android {
    namespace = "org.righaven.agent.android"
    compileSdk = 35
    defaultConfig {
        applicationId = "org.righaven.agent"
        minSdk = 26
        targetSdk = 35
        versionCode = major * 10000 + minor * 100 + patch
        versionName = System.getenv("RIGHAVEN_VERSION") ?: release
    }
    signingConfigs {
        // A stable key from CI secrets lets updates install over the previous version.
        create("release") {
            val keystore = System.getenv("ANDROID_KEYSTORE_FILE")
            if (keystore != null) {
                storeFile = file(keystore)
                storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("ANDROID_KEY_ALIAS")
                keyPassword = System.getenv("ANDROID_KEY_PASSWORD")
            }
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = if (System.getenv("ANDROID_KEYSTORE_FILE") != null) signingConfigs.getByName("release") else signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    lint {
        // Permissions are checked at run time by Actions before each Bluetooth or Wi-Fi call.
        disable += "MissingPermission"
        abortOnError = false
    }
}

dependencies {
    implementation(project(":core"))
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
}
