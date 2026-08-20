// ANEB Probe — :probe 模块（阶段 0：跑通一次 S1 并把全部时间戳打到屏幕日志）
import java.util.Properties

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

    // 签名配置（D-500④ 双轨）：**密钥与口令绝不入库**——从 `local.properties`（已 gitignore）
    // 或同名环境变量读取；四项齐备且 keystore 文件存在才注册 signingConfig，否则 release
    // 回落为 unsigned（不阻断没有密钥的协作方构建）。
    //   local.properties 键：anebStoreFile / anebStorePassword / anebKeyAlias / anebKeyPassword
    //   环境变量同名：ANEB_STORE_FILE / ANEB_STORE_PASSWORD / ANEB_KEY_ALIAS / ANEB_KEY_PASSWORD
    // 当前装机验证用**临时 throwaway keystore**（CN 标注 NOT a release identity），
    // **不作发布身份**；正式发布 keystore 归 PO 持有（D-500④ PO 待办）。
    val localProps = Properties().apply {
        val f = rootProject.file("local.properties")
        if (f.exists()) f.inputStream().use { load(it) }
    }
    fun secret(propKey: String, envKey: String): String? =
        (localProps.getProperty(propKey) ?: System.getenv(envKey))?.takeIf { it.isNotBlank() }

    val ksPath = secret("anebStoreFile", "ANEB_STORE_FILE")
    val ksPass = secret("anebStorePassword", "ANEB_STORE_PASSWORD")
    val ksAlias = secret("anebKeyAlias", "ANEB_KEY_ALIAS")
    val ksKeyPass = secret("anebKeyPassword", "ANEB_KEY_PASSWORD")
    val ksFile = ksPath?.let { file(it) }
    val signingReady = ksFile != null && ksFile.exists() &&
        ksPass != null && ksAlias != null && ksKeyPass != null

    signingConfigs {
        if (signingReady) {
            create("aneb") {
                storeFile = ksFile
                storePassword = ksPass
                keyAlias = ksAlias
                keyPassword = ksKeyPass
            }
        }
    }

    buildTypes {
        release {
            // 阶段 0 不混淆（D-500②：R8 现关零影响，开启前置=keep 规则 + 12 个 MigrationVxTest 全量）
            if (signingReady) signingConfig = signingConfigs.getByName("aneb")
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
        // BuildConfig.DEBUG 门控注入透传（P1 范围 9：--es inject 仅 debug 生效）
        buildConfig = true
    }

    sourceSets {
        getByName("main") {
            // 打包内置 profiles 副本（P1 范围 1：/api/v1/profiles 拉取失败时的兜底）。
            // 直接指向仓库共享目录，单一事实来源，防内置副本与服务端版本静默漂移。
            assets.srcDirs("../../profiles")
        }
    }
}

ksp {
    // T45/D-463 §6.2：exportSchema 打开后 Room 快照写入这里，随仓库一起提交版本管理
    arg("room.schemaLocation", "$projectDir/schemas")
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
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

    // 阶段 2 P2-C05：Cronet 内嵌网络栈（TCP(TLS) vs QUIC(h3) 背靠背 A/B，D-17/D-19）。
    // 仅 AbRunner/CronetStreamClient 使用——OkHttp 主测量路径不变；两栈计时钩子
    // 粒度不同，数据不可互比（A/B 结论只在 Cronet 栈内得出）。
    implementation(libs.cronet.embedded)

    // 阶段 2 API 探针：key 存 EncryptedSharedPreferences（初始化失败退私有明文 prefs，
    // 见 ApiKeyStore KDoc 取舍说明）
    implementation(libs.androidx.security.crypto)

    implementation(libs.room.runtime)
    implementation(libs.room.ktx)
    ksp(libs.room.compiler)

    testImplementation(libs.junit)
}

// ---- 单测输入声明：仓库根 spec/语料文件（T66/D-508，含对本条自身首版的订正）----
//
// 背景：部分单测按既有惯例（`repoFile()`：从 user.dir 向上找仓库根）直接读真实
// spec/profile/语料文件——这是对的（读真文件而不是在测试里复制一份会各自漂移的副本，
// D-315）。但 Gradle 并不知道这层依赖：这些文件不在任何 task 的 inputs 里，于是
// **改了它们，测试任务仍判 UP-TO-DATE 而不重跑**。
//
// 实证：把 profiles/s4_throughput.json 的 window_ms 从 4000 改成 2000，
// `gradlew :probe:testDebugUnitTest` 报 BUILD SUCCESSFUL——测试根本没跑（XML 时间戳未变）；
// 加 --rerun-tasks 才如期 FAILED。即守卫逻辑对，但**在最需要它的那一刻是睡着的**。
//
// 订正记录（D-341：做完修复要把刚写的修复本身当被审对象再问一遍同类）：本声明的**首版
// 只手写了 2 条路径**，而从代码枚举（`grep -rl "user.dir" src/test`）实为 **6 个测试、
// 7 处路径**——AdapterSpecTest / CalibrationFixtureTest / SpecScoringParityTest /
// ClientProfileDataParityTest 四个当时仍睡着。故改为**按目录声明**，新增同类文件天然被覆盖，
// 不再依赖会漏会过期的手写清单（D-275）。
//
// 声明目录而非逐文件是语义正确而非过宽：这些测试的职责本就是"spec 与代码对拍"，
// spec 变了本就该重跑。四个目录规模都很小（spec 42 文件/664K、profiles 4 文件、
// assets 5 文件、calibration 9 文件），不会造成显著的重跑噪声。
tasks.withType<Test>().configureEach {
    val repoRoot = rootProject.projectDir.parentFile // app/ 的上一级 = 仓库根
    listOf(
        "spec",                            // AdapterSpecTest / SpecScoringParityTest
                                           // / ClientProfileDataParityTest / VoiceExecutionPlanParityTest
        "profiles",                        // RttDominanceGuardTest（window_ms 绊线）
        "app/probe/src/main/assets",       // AdapterSpecTest / ClientProfileDataParityTest 的运行时镜像侧
        "evidence/phase1/calibration",     // CalibrationFixtureTest
        "app/probe/schemas",               // MigrationRegistryTest（当前 schema 版本的派生来源，T68）
    ).forEach { rel ->
        val d = File(repoRoot, rel)
        if (d.isDirectory) inputs.dir(d).withPropertyName(rel.replace('/', '_'))
    }
}
