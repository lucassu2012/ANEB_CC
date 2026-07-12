// ANEB Probe — :probe 模块（阶段 0：跑通一次 S1 并把全部时间戳打到屏幕日志）
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
}

android {
    namespace = "com.aneb.probe"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.aneb.probe"
        minSdk = 29 // CellInfoNr / 5G API 需要（设计文档 §5）
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0-phase0"
    }

    buildTypes {
        release {
            // 阶段 0 不混淆；阶段 1 前配置 signingConfig（自管 keystore，密钥不入库）
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        debug {
            // 明文流量仅经 src/debug/res/xml/network_security_config.xml 允许（仿真服务器联调）
            // release 变体不带该配置，targetSdk>=28 默认禁明文
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.kotlinx.coroutines.android)

    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.graphics)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    debugImplementation(libs.compose.ui.tooling)

    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)

    implementation(libs.room.runtime)
    implementation(libs.room.ktx)
    ksp(libs.room.compiler)

    testImplementation(libs.junit)
}
