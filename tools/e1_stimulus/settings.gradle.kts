// E1 刺激源 —— 独立 Gradle 工程（刻意不 include 进 app/settings.gradle.kts）
//
// 为什么独立：v2 的设备批（任务板 T1）要「核对构建对应提交」，其判据钉在
// app/probe 的产物上。把刺激源挂进主构建会让 :probe 的构建面在别人测试期间发生
// 变化。独立工程 = 与 app/ 零共享，`app/gradlew -p tools/e1_stimulus` 即可构建
// （复用 app/gradle/wrapper 的 Gradle 8.7 发行版，不另下载）。
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "e1-stimulus"
