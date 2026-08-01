// E1 刺激源 —— 单模块 Android 应用（根工程即应用模块）
//
// 版本与 app/gradle/libs.versions.toml 逐字对齐（AGP 8.5.2 / Kotlin 2.0.21），
// 但**不引用**那份 catalog——引用即产生跨工程耦合，改 catalog 会连带影响本工程。
// 供应链纪律同 app/：精确版本，禁 +/动态版本/区间。
//
// 零依赖：只用 android.* 框架类，不引 AndroidX、不引 Compose。理由=刺激源必须
// 尽可能少地把自己的渲染开销与依赖注入到被测的时序里（它是量尺，不是被测物）。
plugins {
    id("com.android.application") version "8.5.2"
    id("org.jetbrains.kotlin.android") version "2.0.21"
}

android {
    namespace = "com.aneb.e1stimulus"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.aneb.e1stimulus"
        // minSdk 29 与 :probe 一致；ViewTreeObserver.registerFrameCommitCallback
        // 亦为 API 29 起（本工程取 t_commit 的手段）。
        minSdk = 29
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0-e1"
    }

    buildTypes {
        debug {
            // 刺激源只有 debug 变体的用途；不配 release 签名（不入商店、不上真机分发）
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}
